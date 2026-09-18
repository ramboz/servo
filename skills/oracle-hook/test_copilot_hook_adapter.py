"""Tests for `skills/oracle-hook/copilot_hook_adapter.py` — slice 028-04 (hooks).

servo's Copilot plugin package is hook-free; its one hook — the oracle `Stop` —
is installed target-side as a Copilot `agentStop` hook. This adapter is the
INPUT-payload half ported from jig (spec 113-04): it reshapes Copilot's
camelCase `agentStop` stdin into the snake_case servo's `meta-judge.sh` reads,
exports `CLAUDE_PROJECT_DIR` from the payload's `cwd` (Copilot sets no such env
var), execs the target script, and forwards its stdout + exit code verbatim.

Coverage:

  * ``TranslatePayloadTests`` — the field reshaping (`sessionId`→`session_id`,
    `transcriptPath`→`transcript_path`, `stop_hook_active` passthrough,
    `hook_event_name` from argv) and its fail-open behaviour on bad input.
  * ``ProjectDirFromPayloadTests`` — `cwd`/`workingDirectory` extraction used to
    export `CLAUDE_PROJECT_DIR`.
  * ``AdapterMainTests`` — real subprocess invocation in front of a fake target
    script that echoes its env + stdin and exits with a chosen code: proves
    `CLAUDE_PROJECT_DIR` is exported from `cwd`, `stop_hook_active` reaches the
    child, and the child's stdout + exit code are forwarded verbatim (the
    deterministic substitute for a live `copilot -p` firing — jig 113-08).

Run via unittest or pytest:
    python3 skills/oracle-hook/test_copilot_hook_adapter.py
    uvx pytest skills/oracle-hook/test_copilot_hook_adapter.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
ADAPTER_PATH = HOOK_DIR / "copilot_hook_adapter.py"

sys.path.insert(0, str(HOOK_DIR))
import copilot_hook_adapter  # noqa: E402


# --------------------------------------------------------------------------- #
# translate_payload — camelCase Copilot stdin → snake_case meta-judge stdin
# --------------------------------------------------------------------------- #
class TranslatePayloadTests(unittest.TestCase):
    def _translate(self, payload, event="Stop") -> dict:
        raw = json.dumps(payload).encode()
        return json.loads(copilot_hook_adapter.translate_payload(raw, event))

    def test_hook_event_name_injected_from_argv(self):
        """The Claude event name comes from the adapter's argv, not the payload
        (Copilot's agentStop input carries no event-name field)."""
        out = self._translate({}, event="Stop")
        self.assertEqual(out["hook_event_name"], "Stop")

    def test_session_id_mapped(self):
        out = self._translate({"sessionId": "abc123"})
        self.assertEqual(out["session_id"], "abc123")

    def test_stop_hook_active_true_reaches_child(self):
        """The load-bearing field: Copilot's agentStop supplies `stop_hook_active`
        (already snake_case); the meta-judge's runaway guard reads it, so it must
        survive the reshaping."""
        out = self._translate({"stop_hook_active": True})
        self.assertIs(out["stop_hook_active"], True)

    def test_stop_hook_active_false_reaches_child(self):
        out = self._translate({"stop_hook_active": False})
        self.assertIs(out["stop_hook_active"], False)

    def test_transcript_path_mapped(self):
        out = self._translate({"transcriptPath": "/tmp/s/transcript.jsonl"})
        self.assertEqual(out["transcript_path"], "/tmp/s/transcript.jsonl")

    def test_full_agent_stop_payload_translates(self):
        out = self._translate({
            "sessionId": "s1",
            "timestamp": "2026-09-18T00:00:00Z",
            "cwd": "/tmp/proj",
            "transcriptPath": "/tmp/proj/session.jsonl",
            "stopReason": "end_turn",
            "stop_hook_active": False,
        })
        self.assertEqual(out, {
            "hook_event_name": "Stop",
            "session_id": "s1",
            "stop_hook_active": False,
            "transcript_path": "/tmp/proj/session.jsonl",
        })

    # -- fail-open (mutation-verify: without the guard these would raise) -- #
    def test_malformed_json_returns_raw_unchanged(self):
        raw = b"not valid json{{{"
        self.assertEqual(
            copilot_hook_adapter.translate_payload(raw, "Stop"), raw
        )

    def test_non_dict_json_returns_raw_unchanged(self):
        raw = b"[1, 2, 3]"
        self.assertEqual(
            copilot_hook_adapter.translate_payload(raw, "Stop"), raw
        )

    def test_empty_bytes_still_produce_valid_json_with_event_name(self):
        out = json.loads(copilot_hook_adapter.translate_payload(b"", "Stop"))
        self.assertEqual(out, {"hook_event_name": "Stop"})


# --------------------------------------------------------------------------- #
# project_dir_from_payload — the source of CLAUDE_PROJECT_DIR
# --------------------------------------------------------------------------- #
class ProjectDirFromPayloadTests(unittest.TestCase):
    def _dir(self, payload):
        return copilot_hook_adapter.project_dir_from_payload(json.dumps(payload).encode())

    def test_cwd_returned(self):
        """Copilot's agentStop input names the project dir `cwd`."""
        self.assertEqual(self._dir({"cwd": "/tmp/proj"}), "/tmp/proj")

    def test_working_directory_returned_as_fallback(self):
        """The base Copilot hook-input shape spells it `workingDirectory`; accept
        it too so the adapter is faithful to jig's port across event types."""
        self.assertEqual(self._dir({"workingDirectory": "/tmp/proj"}), "/tmp/proj")

    def test_cwd_preferred_over_working_directory(self):
        self.assertEqual(
            self._dir({"cwd": "/from/cwd", "workingDirectory": "/from/wd"}),
            "/from/cwd",
        )

    def test_absent_returns_none(self):
        self.assertIsNone(self._dir({}))

    def test_non_string_returns_none(self):
        self.assertIsNone(self._dir({"cwd": 123}))

    def test_malformed_returns_none(self):
        self.assertIsNone(copilot_hook_adapter.project_dir_from_payload(b"not json"))


# --------------------------------------------------------------------------- #
# main() — real subprocess in front of a fake target script
# --------------------------------------------------------------------------- #
class AdapterMainTests(unittest.TestCase):
    """Deterministic substitute for a live `copilot -p` agentStop firing (jig
    113-08): drive a synthetic Copilot agentStop payload through the adapter as
    a real subprocess in front of a fake target script that echoes its own
    `CLAUDE_PROJECT_DIR` + stdin and exits with a chosen code."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="servo-copilot-adapter-"))
        self.fake = self.tmp / "fake_target.sh"
        self.fake.write_text(
            "#!/bin/sh\n"
            'printf "CLAUDE_PROJECT_DIR=%s\\n" "$CLAUDE_PROJECT_DIR"\n'
            'printf "STDIN="\n'
            "cat\n"
            'printf "\\n"\n'
            'exit "${FAKE_EXIT:-0}"\n'
        )
        self.fake.chmod(0o755)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, payload, *, event="Stop", script=None, env_extra=None):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(ADAPTER_PATH), event, str(script or self.fake)],
            input=json.dumps(payload).encode(),
            capture_output=True,
            timeout=15,
            env=env,
        )

    def test_claude_project_dir_exported_from_cwd(self):
        """AC1: the adapter exports CLAUDE_PROJECT_DIR from the payload's `cwd`
        (Copilot sets no such env var; the meta-judge needs it to locate the
        oracle). Mutation-verify: drop the export and the child echoes empty."""
        proc = self._run({"cwd": "/some/project", "stop_hook_active": False})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("CLAUDE_PROJECT_DIR=/some/project", proc.stdout.decode())

    def test_stop_hook_active_reaches_child_stdin(self):
        """AC1: the reshaped snake_case payload the child reads carries
        `stop_hook_active` (the meta-judge's runaway guard)."""
        proc = self._run({"cwd": "/p", "stop_hook_active": True})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stdin_line = next(
            ln for ln in proc.stdout.decode().splitlines() if ln.startswith("STDIN=")
        )
        forwarded = json.loads(stdin_line[len("STDIN="):])
        self.assertIs(forwarded["stop_hook_active"], True)
        self.assertEqual(forwarded["hook_event_name"], "Stop")

    def test_stdout_forwarded_verbatim(self):
        """AC1: the child's stdout reaches Copilot unchanged — including a
        block-decision body the meta-judge would emit."""
        block = self.tmp / "block.sh"
        block.write_text(
            "#!/bin/sh\n"
            "cat >/dev/null\n"
            'printf \'{"decision":"block","reason":"keep working"}\'\n'
        )
        block.chmod(0o755)
        proc = self._run({"cwd": "/p", "stop_hook_active": False}, script=block)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout.decode()),
            {"decision": "block", "reason": "keep working"},
        )

    def test_exit_code_forwarded_verbatim(self):
        """AC1: a non-zero child exit is forwarded, not masked. Mutation-verify:
        a hardcoded `return 0` would fail this."""
        proc = self._run(
            {"cwd": "/p", "stop_hook_active": False}, env_extra={"FAKE_EXIT": "7"}
        )
        self.assertEqual(proc.returncode, 7)

    def test_does_not_override_an_existing_claude_project_dir(self):
        """The guard: an already-set CLAUDE_PROJECT_DIR is not clobbered by the
        payload's cwd (faithful to jig's don't-clobber posture)."""
        proc = self._run(
            {"cwd": "/from/payload", "stop_hook_active": False},
            env_extra={"CLAUDE_PROJECT_DIR": "/already/set"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout.decode()
        self.assertIn("CLAUDE_PROJECT_DIR=/already/set", out)
        self.assertNotIn("/from/payload", out)

    def test_too_few_args_fails_open_zero(self):
        """A malformed invocation must never raise to Copilot's hook runner."""
        self.assertEqual(copilot_hook_adapter.main(["adapter.py"]), 0)
        self.assertEqual(copilot_hook_adapter.main(["adapter.py", "Stop"]), 0)

    def test_spawn_failure_fails_open_zero(self):
        """A Stop hook must never trap the session on a packaging error: an
        unresolvable target script fails open (exit 0), never blocks."""
        proc = self._run(
            {"cwd": "/p", "stop_hook_active": False},
            script=self.tmp / "does-not-exist.sh",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


class InterpreterSelectionTests(unittest.TestCase):
    """`_interpreter_for` picks python3 for a `.py` target, bash otherwise —
    servo's only target today is the `.sh` meta-judge, but the split keeps the
    port faithful to jig and ready for a future `.py` hook."""

    def test_python_for_py_target(self):
        self.assertEqual(copilot_hook_adapter._interpreter_for("x/foo.py"), "python3")

    def test_bash_for_sh_target(self):
        self.assertEqual(
            copilot_hook_adapter._interpreter_for(".servo/hooks/meta-judge.sh"), "bash"
        )


if __name__ == "__main__":
    unittest.main()
