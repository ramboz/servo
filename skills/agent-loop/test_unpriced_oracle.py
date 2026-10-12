"""033-08 AC2-4: the installed accounting marker guards bounded callers."""

import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "unpriced_loop", Path(__file__).with_name("loop.py")
)
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)

NAMES = ["generic-eval", "content-eval", "design-eval"]
# Mirrored verbatim in heartbeat's standalone protocol tests (ADR-0041 §6).
PROTOCOL_CASES = [
    ({}, None),
    ({"components": []}, None),
    ({"components": NAMES}, None),
    ({"components": [], "unpriced_components": []}, None),
    ({"components": NAMES, "unpriced_components": []}, None),
    *[
        ({"components": NAMES, "unpriced_components": [name]},
         "unpriced_oracle_components")
        for name in NAMES
    ],
    ({"components": NAMES, "unpriced_components": NAMES},
     "unpriced_oracle_components"),
    *[
        ({"components": NAMES, "unpriced_components": marker},
         "unpriced_components_invalid")
        for marker in (None, False, 0, "", NAMES[0], {}, [None], [1], [False],
                       [""], [" \t"], [NAMES[0], NAMES[0]], ["unknown"])
    ],
    *[
        ({"components": components, "unpriced_components": [NAMES[0]]},
         "unpriced_components_invalid")
        for components in (None, NAMES[0], {}, [None], [""], [" "], [1], [])
    ],
    ({"unpriced_components": []}, "unpriced_components_invalid"),
    ([], "unpriced_components_invalid"),
    (None, "unpriced_components_invalid"),
]


@pytest.fixture
def target(tmp_path):
    (tmp_path / ".servo").mkdir()
    (tmp_path / "oracle.sh").write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / "oracle.sh").chmod(0o755)
    return tmp_path


def seed(target, manifest):
    (target / ".servo/install.json").write_text(json.dumps(manifest))


def snapshot(target):
    return {
        str(p.relative_to(target)): (
            p.stat().st_mode, p.read_bytes() if p.is_file() else None
        )
        for p in target.rglob("*")
    }


def forbid(stack, names):
    mocks = [
        stack.enter_context(patch.object(
            loop, name, side_effect=AssertionError(f"{name} called before refusal")
        ))
        for name in names
    ]
    for name in ("run", "Popen"):
        mocks.append(stack.enter_context(patch.object(
            loop.subprocess, name, side_effect=AssertionError("subprocess dispatched")
        )))
    return mocks


def assert_refusal(rc, capsys, target, before, reason, mocks):
    captured = capsys.readouterr()
    assert rc == loop.EXIT_ENV_ERROR
    summary = json.loads(captured.out)
    assert summary["final_oracle_status"] == "env_error"
    assert summary["terminal_reason"] == reason
    assert "unpriced_components" in captured.err
    assert ".servo/install.json" in captured.err
    assert "USD" in captured.err
    assert snapshot(target) == before
    for mock in mocks:
        mock.assert_not_called()
    return summary, captured.err


@pytest.mark.parametrize("flags", [
    ["--prompt", "x"],
    ["--driver", "loop", "--prompt", "x"],
    ["--driver", "goal", "--prompt", "x"],
    ["--background", "--prompt", "x"],
    ["--emit-routine-prompt", "--prompt", "x"],
    ["--resume", "old-run"],
    ["--resume", "old-run", "--resume-anyway", "--cost-ceiling", "0"],
    ["--plan", "nonexistent-plan.json", "--prompt", "x"],
    ["--cost-ceiling", "0", "--context-fill-threshold", "0", "--prompt", "x"],
    ["--_detached-run-id", "old-run", "--prompt", "x"],
])
def test_public_launch_refuses_before_readiness_plan_routing_or_dispatch(
    target, flags, capsys
):
    seed(target, {"components": NAMES, "unpriced_components": NAMES})
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack, [
            "_readiness_check_rc", "_load_plan", "_decide_route",
            "run_loop", "run_goal_loop", "run_goal_loop_background",
            "_emit_routine_prompt",
        ])
        rc = loop.main([str(target), "--host", "claude", *flags])
    _, message = assert_refusal(
        rc, capsys, target, before, "unpriced_oracle_components", mocks
    )
    for name in NAMES:
        assert name in message
    assert "standalone" in message


@pytest.mark.parametrize("entry", ["loop", "resume", "goal", "child", "background", "routine"])
@pytest.mark.parametrize("ceiling", [None, 0])
def test_direct_entries_refuse_before_signals_models_gates_or_writes(
    target, capsys, entry, ceiling
):
    seed(target, {"components": NAMES, "unpriced_components": [NAMES[0]]})
    state_path = target / ".servo/runs/old-run/state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"backend": "claude", "cumulative_cost_usd": null}')
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack, [
            "_install_signal_handlers", "_get_claude_version", "_invoke_claude",
            "_invoke_claude_goal", "_invoke_gate", "_ensure_vendored_gate",
            "_create_run_dir", "_atomic_write_state", "_spawn_detached",
        ])
        kwargs = dict(prompt="x", max_iterations=1, cost_ceiling=ceiling)
        if entry in ("loop", "resume"):
            rc = loop.run_loop(
                target, **kwargs, context_fill_threshold=0, allow_dirty=True,
                resume_run_id="old-run" if entry == "resume" else None,
                resume_anyway=entry == "resume",
            )
        elif entry in ("goal", "child"):
            rc = loop.run_goal_loop(
                target, **kwargs, allow_dirty=True, detached=entry == "child",
                run_id="old-run" if entry == "child" else None,
            )
        elif entry == "background":
            rc = loop.run_goal_loop_background(target, **kwargs, allow_dirty=True)
        else:
            rc = loop._emit_routine_prompt(target, "x")
    summary, _ = assert_refusal(
        rc, capsys, target, before, "unpriced_oracle_components", mocks
    )
    if entry == "resume":
        assert summary["run_id"] == "old-run"


@pytest.mark.parametrize("manifest,reason", PROTOCOL_CASES)
def test_marker_protocol(target, manifest, reason):
    seed(target, manifest)
    before = snapshot(target)
    error = loop._unpriced_oracle_error(target)
    if reason is None:
        assert error is None
    else:
        assert error[0] == reason
        assert "unpriced_components" in error[1]
        assert ".servo/install.json" in error[1]
        assert "USD" in error[1]
    assert snapshot(target) == before


@pytest.mark.parametrize("raw", ["{", "null", '["not-a-manifest"]', "\udcff"])
def test_bad_metadata_refuses_explicitly_before_launch(target, capsys, raw):
    (target / ".servo/install.json").write_bytes(raw.encode("utf-8", errors="surrogatepass"))
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack, ["_decide_route", "run_loop"])
        rc = loop.main([str(target), "--prompt", "x", "--cost-ceiling", "0"])
    _, message = assert_refusal(
        rc, capsys, target, before, "unpriced_components_invalid", mocks
    )
    assert "repair" in message


def test_unreadable_manifest_fails_closed(target):
    with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
        error = loop._unpriced_oracle_error(target)
    assert error[0] == "unpriced_components_invalid"
    assert "repair" in error[1]


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_target_keeps_old_preflight_authority(tmp_path, kind):
    target = tmp_path / "invalid-target"
    if kind == "file":
        target.write_text("not a directory")
    assert loop._unpriced_oracle_error(target) is None


@pytest.mark.parametrize("manifest", [None, {"components": NAMES},
                                       {"components": NAMES, "unpriced_components": []}])
def test_missing_or_legacy_manifest_keeps_launch_behavior_without_config_scan(
    target, manifest
):
    if manifest is not None:
        seed(target, manifest)
    # Arbitrary project configs/ledgers are not another registration protocol.
    (target / "native-config.json").write_text('{"provider":"copilot","cost_usd":null}')
    before = snapshot(target)
    with patch.object(loop, "run_loop", return_value=17) as run:
        assert loop.main([str(target), "--driver", "loop", "--prompt", "x"]) == 17
    run.assert_called_once()
    assert snapshot(target) == before


def test_missing_manifest_still_uses_old_direct_preflight(target, capsys):
    before = snapshot(target)
    with patch.object(loop, "_install_signal_handlers"):
        assert loop.run_loop(
            target, prompt="x", max_iterations=1, cost_ceiling=None,
            context_fill_threshold=None,
        ) == loop.EXIT_ENV_ERROR
    assert json.loads(capsys.readouterr().out)["terminal_reason"] == "manifest_missing"
    assert snapshot(target) == before


@pytest.mark.parametrize("marker,reason", [
    ([NAMES[0]], "unpriced_oracle_components"),
    (None, "unpriced_components_invalid"),
    (["unknown"], "unpriced_components_invalid"),
])
def test_each_gateway_rechecks_current_marker_without_subprocess(
    target, capsys, marker, reason
):
    seed(target, {"components": NAMES})
    assert loop._unpriced_oracle_error(target) is None
    seed(target, {"components": NAMES, "unpriced_components": marker})
    before = snapshot(target)
    with patch.object(
        loop.subprocess, "Popen", side_effect=AssertionError("gate dispatched")
    ) as gate:
        result = loop._invoke_gate(target, gate_path=target / "alternate-gate.py")
    gate.assert_not_called()
    assert result["exit_code"] == loop.EXIT_ENV_ERROR
    assert result["status"] == "env_error"
    assert result["reason"] == reason
    assert result["composite"] is None
    assert result.get("cost_usd") is None
    assert "USD" in capsys.readouterr().err
    assert snapshot(target) == before


@pytest.mark.parametrize("driver,subtype", [
    ("loop", "success"), ("goal", "success"),
    ("goal", "error_max_turns"), ("goal", "error_max_budget_usd"),
])
@pytest.mark.parametrize("marker,reason", [
    ([NAMES[0]], "unpriced_oracle_components"),
    (None, "unpriced_components_invalid"),
])
def test_model_activation_halts_next_gate_and_preserves_only_known_model_spend(
    target, capsys, driver, subtype, marker, reason
):
    seed(target, {"components": NAMES})
    ledger = target / ".servo/native-ledger.json"
    raw_ledger = '{"cost_usd": null}'

    def activate(*args, **kwargs):
        seed(target, {"components": NAMES, "unpriced_components": marker})
        ledger.write_text(raw_ledger)
        payload = {
            "session_id": "test-session", "total_cost_usd": 0.25,
            "subtype": subtype, "num_turns": 1, "terminal_reason": "completed",
            "result": "done", "usage": {},
        }
        return (payload, None) if driver == "loop" else (payload, "", None)

    model_name = "_invoke_claude" if driver == "loop" else "_invoke_claude_goal"
    with ExitStack() as stack:
        stack.enter_context(patch.object(loop, "_install_signal_handlers"))
        stack.enter_context(patch.object(loop, "_was_interrupted", return_value=False))
        stack.enter_context(patch.object(loop, "_get_claude_version", return_value="test"))
        stack.enter_context(patch.object(loop, "_tree_snapshot", return_value=None))
        stack.enter_context(patch.object(
            loop, "_ensure_vendored_gate", return_value=(target / "gate.py", None)
        ))
        model = stack.enter_context(patch.object(loop, model_name, side_effect=activate))
        gate = stack.enter_context(patch.object(
            loop.subprocess, "Popen", side_effect=AssertionError("unpriced gate dispatched")
        ))
        kwargs = dict(prompt="x", max_iterations=3, cost_ceiling=2, allow_dirty=True)
        if driver == "loop":
            rc = loop.run_loop(target, **kwargs, context_fill_threshold=0)
        else:
            rc = loop.run_goal_loop(target, **kwargs)
    assert rc == loop.EXIT_ENV_ERROR
    summary = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert summary["terminal_reason"] == reason
    assert summary["final_oracle_status"] == "env_error"
    assert summary["cumulative_cost_usd"] == 0.25
    if driver == "goal":
        assert summary["oracle_composite"] is None
        assert summary["oracle_threshold"] is None
    else:
        assert not summary.get("oracle_score_history")
    assert ledger.read_text() == raw_ledger
    model.assert_called_once()
    gate.assert_not_called()


@pytest.mark.parametrize("driver", ["loop", "goal"])
def test_activation_during_state_setup_refuses_before_first_model(target, capsys, driver):
    seed(target, {"components": NAMES})

    def activate_version():
        seed(target, {"components": NAMES, "unpriced_components": [NAMES[0]]})
        return "test"

    with ExitStack() as stack:
        stack.enter_context(patch.object(loop, "_install_signal_handlers"))
        stack.enter_context(patch.object(loop, "_get_claude_version", side_effect=activate_version))
        stack.enter_context(patch.object(
            loop, "_ensure_vendored_gate", return_value=(target / "gate.py", None)
        ))
        model_name = "_invoke_claude" if driver == "loop" else "_invoke_claude_goal"
        model = stack.enter_context(patch.object(
            loop, model_name, side_effect=AssertionError("model")
        ))
        kwargs = dict(prompt="x", max_iterations=2, cost_ceiling=2, allow_dirty=True)
        if driver == "loop":
            rc = loop.run_loop(target, **kwargs, context_fill_threshold=0)
        else:
            rc = loop.run_goal_loop(target, **kwargs)
    assert rc == loop.EXIT_ENV_ERROR
    assert json.loads(capsys.readouterr().out)["terminal_reason"] == "unpriced_oracle_components"
    model.assert_not_called()


@pytest.mark.parametrize("surface", ["goal", "routine"])
@pytest.mark.parametrize("marker,reason", [
    ([NAMES[0]], "unpriced_oracle_components"),
    (None, "unpriced_components_invalid"),
    (["unknown"], "unpriced_components_invalid"),
])
def test_actual_clone_portable_per_turn_command_refuses_after_activation(
    target, tmp_path, capsys, surface, marker, reason
):
    seed(target, {"installed_tier": "tier-0", "components": NAMES})
    (target / "oracle.sh").write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "Path('oracle-called').write_text('called')\n"
        "print('oracle: composite=0.9 threshold=0.5')\n"
    )
    if surface == "routine":
        assert loop._emit_routine_prompt(target, "x") == 0
        prompt = capsys.readouterr().out
    else:
        vendored, error = loop._ensure_vendored_gate(target)
        assert error is None
        assert vendored == target / loop.VENDORED_GATE_REL
    clone = tmp_path / "cloud-clone"
    shutil.copytree(target, clone)
    if surface == "goal":
        # Match run_goal_loop's absolute vendored path; Routine uses the
        # portable relative path printed by the actual emitter above.
        prompt = loop._compose_goal_prompt("x", gate_path=clone / loop.VENDORED_GATE_REL)
    line = next(line for line in prompt.splitlines() if line.startswith("1. Run exactly: "))
    command = shlex.split(line.removeprefix("1. Run exactly: "))
    # First turn was priced/compatible. Execute the real vendored command,
    # with no dependency on importing the installation's loop.py.
    first = subprocess.run(command, cwd=clone, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    called = clone / "oracle-called"
    assert called.exists()
    called.unlink()
    seed(clone, {"installed_tier": "tier-0", "components": NAMES,
                 "unpriced_components": marker})
    ledger = clone / ".servo/native-ledger.json"
    ledger.write_text('{"cost_usd": null}')
    before = snapshot(clone)
    second = subprocess.run(command, cwd=clone, capture_output=True, text=True)
    assert second.returncode == 2
    result = json.loads(second.stdout)
    assert result["status"] == "env_error"
    assert result["reason"] == reason
    assert result["composite"] is None
    assert result.get("cost_usd") is None
    assert "USD" in second.stderr
    assert not called.exists()
    assert snapshot(clone) == before
    assert "--usd-budget-context" in command
    # The same helper still supports standalone attended scoring.
    standalone = [arg for arg in command if arg != "--usd-budget-context"]
    attended = subprocess.run(standalone, cwd=clone, capture_output=True, text=True)
    assert attended.returncode == 0
    assert called.exists()
    assert json.loads(ledger.read_text())["cost_usd"] is None
