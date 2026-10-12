"""034-08 AC2-4: bounded heartbeat refuses before discovery or dispatch writes."""

import importlib.util
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "unpriced_heartbeat", Path(__file__).with_name("heartbeat.py")
)
heartbeat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(heartbeat)

NAMES = ["generic-eval", "content-eval", "design-eval"]
# Mirrored verbatim in loop's standalone protocol tests (ADR-0041 §6).
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


def forbid(stack):
    mocks = [
        stack.enter_context(patch.object(
            heartbeat, name, side_effect=AssertionError(f"{name} called before refusal")
        ))
        for name in ("run_discover", "_run_gate_json", "_dispatch_one",
                     "_inbox_lock", "_atomic_write", "_provision_oracle")
    ]
    for name in ("run", "Popen"):
        mocks.append(stack.enter_context(patch.object(
            heartbeat.subprocess, name, side_effect=AssertionError("subprocess dispatched")
        )))
    return mocks


def launch(target, entry, ceiling):
    if entry == "run":
        return heartbeat.run_heartbeat(target, cost_ceiling=ceiling)
    if entry == "dispatch":
        return heartbeat.run_dispatch(target, cost_ceiling=ceiling)
    if entry == "whole_dispatch":
        return heartbeat.run_dispatch(target, whole_cost_ceiling=ceiling)
    return heartbeat.main([entry.removeprefix("main_"), str(target),
                           "--cost-ceiling", str(ceiling)])


@pytest.mark.parametrize("entry,ceiling", [
    ("run", 5), ("run", 0), ("dispatch", None), ("dispatch", 0),
    ("whole_dispatch", 5), ("whole_dispatch", 0),
    ("main_run", 5), ("main_dispatch", 0),
])
@pytest.mark.parametrize("inbox", ["absent", "empty", "candidate"])
def test_bounded_entries_refuse_before_discovery_gate_dispatch_or_writes(
    target, capsys, entry, ceiling, inbox
):
    seed(target, {"components": NAMES, "unpriced_components": NAMES})
    if inbox != "absent":
        path = target / ".servo/triage/inbox.jsonl"
        path.parent.mkdir()
        record = {
            "schema_version": heartbeat.SCHEMA_VERSION, "finding_id": "known",
            "status": "open", "actionable": True, "priority": 1,
            "outcome": {"cost_usd": None},
        }
        path.write_text(json.dumps(record) + "\n" if inbox == "candidate" else "")
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack)
        rc = launch(target, entry, ceiling)
    captured = capsys.readouterr()
    assert rc == heartbeat.EXIT_ENV_ERROR
    assert "unpriced_oracle_components" in captured.err
    assert "unpriced_components" in captured.err
    assert ".servo/install.json" in captured.err
    assert "USD" in captured.err
    assert "standalone" in captured.err
    for name in NAMES:
        assert name in captured.err
    for mock in mocks:
        mock.assert_not_called()
    assert snapshot(target) == before


@pytest.mark.parametrize("manifest,reason", PROTOCOL_CASES)
def test_marker_protocol(target, manifest, reason):
    seed(target, manifest)
    before = snapshot(target)
    error = heartbeat._unpriced_oracle_error(target)
    if reason is None:
        assert error is None
    else:
        assert error[0] == reason
        assert "unpriced_components" in error[1]
        assert ".servo/install.json" in error[1]
        assert "USD" in error[1]
    assert snapshot(target) == before


@pytest.mark.parametrize("raw", [
    "{", "null", '["not-a-manifest"]', "\udcff",
    '{"components":[],"unpriced_components":null}',
])
@pytest.mark.parametrize("entry", ["run", "dispatch", "main_run", "main_dispatch"])
def test_bad_metadata_refuses_explicitly_before_launch(target, capsys, raw, entry):
    (target / ".servo/install.json").write_bytes(raw.encode("utf-8", errors="surrogatepass"))
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack)
        rc = launch(target, entry, 5)
    message = capsys.readouterr().err
    assert rc == heartbeat.EXIT_ENV_ERROR
    assert "unpriced_components_invalid" in message
    assert "unpriced_components" in message
    assert "repair" in message
    for mock in mocks:
        mock.assert_not_called()
    assert snapshot(target) == before


def test_unreadable_manifest_fails_closed(target):
    with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
        error = heartbeat._unpriced_oracle_error(target)
    assert error[0] == "unpriced_components_invalid"
    assert "repair" in error[1]


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_target_keeps_old_preflight_authority(tmp_path, kind):
    target = tmp_path / "invalid-target"
    if kind == "file":
        target.write_text("not a directory")
    assert heartbeat._unpriced_oracle_error(target) is None


@pytest.mark.parametrize("manifest", [None, {"components": NAMES},
                                       {"components": NAMES, "unpriced_components": []}])
def test_missing_or_legacy_manifest_keeps_whole_pass_behavior_without_config_scan(
    target, manifest
):
    if manifest is not None:
        seed(target, manifest)
    (target / "native-config.json").write_text('{"provider":"copilot","cost_usd":null}')
    before = snapshot(target)
    with patch.object(heartbeat, "run_discover", return_value=0) as discover:
        with patch.object(heartbeat, "run_dispatch", return_value=17) as dispatch:
            assert heartbeat.run_heartbeat(target, cost_ceiling=5) == 17
    discover.assert_called_once_with(target)
    assert dispatch.call_args.kwargs["whole_cost_ceiling"] == 5
    assert snapshot(target) == before


def test_missing_manifest_still_uses_old_dispatch_preflight(target, capsys):
    path = target / ".servo/triage/inbox.jsonl"
    path.parent.mkdir()
    path.write_text(json.dumps({
        "schema_version": heartbeat.SCHEMA_VERSION,
        "finding_id": "known", "status": "open", "actionable": True,
    }) + "\n")
    before = snapshot(target)
    with patch.object(heartbeat, "_run_gate_json", return_value={
        "exit_code": 2, "reason": "manifest_missing"
    }) as gate:
        assert heartbeat.run_dispatch(target) == heartbeat.EXIT_ENV_ERROR
    gate.assert_called_once_with(target)
    assert "manifest_missing" in capsys.readouterr().err
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
    assert heartbeat._unpriced_oracle_error(target) is None
    seed(target, {"components": NAMES, "unpriced_components": marker})
    before = snapshot(target)
    with patch.object(heartbeat.subprocess, "run", side_effect=AssertionError("gate")) as gate:
        result = heartbeat._run_gate_json(target)
    gate.assert_not_called()
    assert result["exit_code"] == heartbeat.EXIT_ENV_ERROR
    assert result["status"] == "env_error"
    assert result["reason"] == reason
    assert result["composite"] is None
    assert result.get("cost_usd") is None
    assert "USD" in capsys.readouterr().err
    assert snapshot(target) == before


@pytest.mark.parametrize("marker,reason", [
    ([NAMES[0]], "unpriced_oracle_components"),
    (None, "unpriced_components_invalid"),
])
def test_first_candidate_activation_halts_pass_before_next_candidate(
    target, capsys, marker, reason
):
    seed(target, {"components": NAMES})
    inbox = target / ".servo/triage/inbox.jsonl"
    inbox.parent.mkdir()
    records = [
        {"schema_version": heartbeat.SCHEMA_VERSION, "finding_id": fid,
         "status": "open", "actionable": True, "attempts": 0, "outcome": None}
        for fid in ("first", "second")
    ]
    inbox.write_text("".join(json.dumps(r) + "\n" for r in records))
    ledger = target / ".servo/native-ledger.json"
    raw_ledger = '{"cost_usd": null}'

    def activate(*args, **kwargs):
        seed(target, {"components": NAMES, "unpriced_components": marker})
        ledger.write_text(raw_ledger)
        return {
            "run_id": "known-model", "oracle_status": "below_threshold",
            "oracle_composite": 0.2, "cost_usd": 0.25,
            "dispatched_at": heartbeat._now_iso(),
        }, "max_iterations_reached"

    with patch.object(heartbeat, "_run_gate_json", return_value={"exit_code": 1}) as gate:
        with patch.object(heartbeat, "_dispatch_one", side_effect=activate) as dispatch:
            rc = heartbeat.run_dispatch(target, whole_cost_ceiling=5)
    assert rc == heartbeat.EXIT_ENV_ERROR
    assert reason in capsys.readouterr().err
    dispatch.assert_called_once()
    gate.assert_called_once_with(target)
    saved = [json.loads(line) for line in inbox.read_text().splitlines()]
    assert saved[0]["outcome"]["cost_usd"] == 0.25
    assert saved[1] == records[1]  # No synthetic zero-cost outcome or launch.
    assert ledger.read_text() == raw_ledger


@pytest.mark.parametrize("stage", ["provision", "verification"])
def test_candidate_activation_refuses_next_gate_or_model_without_outcome(
    target, capsys, stage
):
    seed(target, {"components": NAMES})
    inbox = target / ".servo/triage/inbox.jsonl"
    inbox.parent.mkdir()
    record = {"schema_version": heartbeat.SCHEMA_VERSION, "finding_id": "first",
              "status": "open", "actionable": True, "attempts": 0, "outcome": None}
    inbox.write_text(json.dumps(record) + "\n")
    raw_inbox = inbox.read_bytes()
    calls = []

    def subprocess_gate(argv, **kwargs):
        calls.append(argv)
        if stage == "verification" and len(calls) == 2:
            worktree = Path(argv[2])
            seed(worktree, {"components": NAMES, "unpriced_components": [NAMES[0]]})
        return type("Result", (), {"stdout": '{"exit_code":1}', "returncode": 1})()

    def provision(source, worktree):
        worktree.mkdir(parents=True)
        (worktree / ".servo").mkdir()
        manifest = {"components": NAMES}
        if stage == "provision":
            manifest["unpriced_components"] = [NAMES[0]]
        seed(worktree, manifest)

    with ExitStack() as stack:
        stack.enter_context(patch.object(heartbeat, "_is_git_work_tree", return_value=True))
        stack.enter_context(patch.object(heartbeat, "_remove_worktree_if_present"))
        stack.enter_context(patch.object(heartbeat, "_create_worktree", return_value=(True, None)))
        stack.enter_context(patch.object(heartbeat, "_provision_oracle", side_effect=provision))
        stack.enter_context(patch.object(heartbeat.subprocess, "run", side_effect=subprocess_gate))
        model = stack.enter_context(patch.object(
            heartbeat, "_run_loop", side_effect=AssertionError("model dispatched")
        ))
        rc = heartbeat.run_dispatch(target, whole_cost_ceiling=5)
    assert rc == heartbeat.EXIT_ENV_ERROR
    assert "unpriced_oracle_components" in capsys.readouterr().err
    assert len(calls) == (1 if stage == "provision" else 2)
    model.assert_not_called()
    assert inbox.read_bytes() == raw_inbox


@pytest.mark.parametrize("marker,reason", [
    ([NAMES[0]], "unpriced_oracle_components"),
    (None, "unpriced_components_invalid"),
])
def test_unpriced_child_terminal_preserves_real_outcome_and_known_spend_before_halt(
    target, capsys, marker, reason
):
    seed(target, {"components": NAMES})
    inbox = target / ".servo/triage/inbox.jsonl"
    inbox.parent.mkdir()
    records = [
        {"schema_version": heartbeat.SCHEMA_VERSION, "finding_id": fid,
         "status": "open", "actionable": True, "attempts": 0, "outcome": None}
        for fid in ("first", "second")
    ]
    inbox.write_text("".join(json.dumps(r) + "\n" for r in records))
    ledger_raw = '{"cost_usd": null}'

    def provision(source, worktree):
        worktree.mkdir(parents=True)
        (worktree / ".servo").mkdir()
        seed(worktree, {"components": NAMES})

    def child(worktree, *args, **kwargs):
        seed(worktree, {"components": NAMES, "unpriced_components": marker})
        (worktree / ".servo/native-ledger.json").write_text(ledger_raw)
        return {
            "run_id": "known-child", "terminal_reason": reason,
            "final_oracle_status": "env_error", "iterations_completed": 1,
            "cumulative_cost_usd": 0.75, "oracle_score_history": [],
        }

    with ExitStack() as stack:
        stack.enter_context(patch.object(heartbeat, "_is_git_work_tree", return_value=True))
        stack.enter_context(patch.object(heartbeat, "_remove_worktree_if_present"))
        stack.enter_context(patch.object(heartbeat, "_create_worktree", return_value=(True, None)))
        stack.enter_context(patch.object(heartbeat, "_provision_oracle", side_effect=provision))
        stack.enter_context(patch.object(
            heartbeat, "_run_gate_json", return_value={"exit_code": 1}
        ))
        run = stack.enter_context(patch.object(heartbeat, "_run_loop", side_effect=child))
        rc = heartbeat.run_dispatch(target, whole_cost_ceiling=5)
    assert rc == heartbeat.EXIT_ENV_ERROR
    saved = [json.loads(line) for line in inbox.read_text().splitlines()]
    assert saved[0]["status"] == "tried"
    assert saved[0]["attempts"] == 1
    assert saved[0]["outcome"]["run_id"] == "known-child"
    assert saved[0]["outcome"]["oracle_status"] == "env_error"
    assert saved[0]["outcome"]["oracle_composite"] is None
    assert saved[0]["outcome"]["cost_usd"] == 0.75
    assert heartbeat._spent_cost_usd(saved) == 0.75
    assert saved[1] == records[1]  # Halt, but do not lose the first child's spend.
    assert reason in capsys.readouterr().err
    run.assert_called_once()
    ledger = target / ".servo/dispatch/first/.servo/native-ledger.json"
    assert ledger.read_text() == ledger_raw
