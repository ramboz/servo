"""034-08 safety closure: only explicitly bounded gates enforce the marker."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "unpriced_gate", Path(__file__).with_name("gate.py")
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

NAMES = ["generic-eval", "content-eval", "design-eval"]
MARKER_CASES = [
    *[([name], "unpriced_oracle_components") for name in NAMES],
    (NAMES, "unpriced_oracle_components"),
    *[
        (marker, "unpriced_components_invalid")
        for marker in (None, False, 0, "", NAMES[0], {}, [None], [1], [False],
                       [""], [" \t"], [NAMES[0], NAMES[0]], ["unknown"], [[]], [{}])
    ],
]


@pytest.fixture
def target(tmp_path):
    (tmp_path / ".servo").mkdir()
    (tmp_path / "oracle.sh").write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / "oracle.sh").chmod(0o755)
    return tmp_path


def seed(target, marker, components=NAMES):
    (target / ".servo/install.json").write_text(json.dumps({
        "installed_tier": "tier-0", "components": components,
        "unpriced_components": marker,
    }))


def snapshot(target):
    return {
        str(p.relative_to(target)): (
            p.stat().st_mode, p.read_bytes() if p.is_file() else None
        )
        for p in target.rglob("*")
    }


@pytest.mark.parametrize("marker,reason", MARKER_CASES)
def test_opt_in_gate_refuses_marker_before_oracle(target, capsys, marker, reason):
    seed(target, marker)
    before = snapshot(target)
    with patch.object(gate, "_run_oracle_bounded", side_effect=AssertionError("oracle")) as oracle:
        rc = gate.run_gate(target, json_mode=True, usd_budget_context=True)
    assert rc == 2
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1
    assert result["exit_code"] == 2
    assert result["status"] == "env_error"
    assert result["reason"] == reason
    assert result["composite"] is None
    assert result.get("cost_usd") is None
    oracle.assert_not_called()
    assert snapshot(target) == before


@pytest.mark.parametrize("components", [None, NAMES[0], {}, [None], [""], [" "], [1], []])
def test_opt_in_gate_refuses_incompatible_component_registration(target, capsys, components):
    seed(target, [NAMES[0]], components)
    with patch.object(gate, "_run_oracle_bounded", side_effect=AssertionError("oracle")) as oracle:
        assert gate.run_gate(target, json_mode=True, usd_budget_context=True) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "unpriced_components_invalid"
    oracle.assert_not_called()


@pytest.mark.parametrize("raw", ["{", "null", '["not-a-manifest"]', "\udcff"])
def test_opt_in_bad_manifest_reports_accounting_error_without_oracle(target, capsys, raw):
    (target / ".servo/install.json").write_bytes(raw.encode("utf-8", errors="surrogatepass"))
    with patch.object(gate, "_run_oracle_bounded", side_effect=AssertionError("oracle")) as oracle:
        assert gate.run_gate(target, json_mode=True, usd_budget_context=True) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["reason"] == "unpriced_components_invalid"
    assert "repair" in captured.err
    assert "USD" in captured.err
    oracle.assert_not_called()


def test_opt_in_unreadable_manifest_fails_explicitly(target, capsys):
    seed(target, [])
    with patch.object(gate, "_load_manifest", side_effect=PermissionError("denied")):
        assert gate.run_gate(target, json_mode=True, usd_budget_context=True) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "unpriced_components_invalid"


@pytest.mark.parametrize("oracle_exit", [0, 1, 2])
@pytest.mark.parametrize("context", ["absent-marker", "empty-marker", "standalone-native",
                                   "standalone-invalid-marker"])
def test_priced_and_standalone_gate_preserve_closed_exit_contract(
    target, capsys, oracle_exit, context
):
    seed(target, [] if context == "empty-marker" else NAMES)
    if context == "absent-marker":
        (target / ".servo/install.json").write_text(json.dumps({
            "installed_tier": "tier-0", "components": NAMES,
        }))
    if context == "standalone-invalid-marker":
        seed(target, None)
    bounded = not context.startswith("standalone")
    with patch.object(gate, "_run_oracle_bounded", return_value=(
        "oracle: composite=0.7 threshold=0.5", "", oracle_exit, False
    )) as oracle:
        assert gate.run_gate(
            target, json_mode=True, usd_budget_context=bounded,
        ) == oracle_exit
    assert json.loads(capsys.readouterr().out)["exit_code"] == oracle_exit
    oracle.assert_called_once()


def test_cli_opt_in_honors_refusal_even_with_disabled_timeout(target, capsys):
    seed(target, [NAMES[0]])
    with patch.object(gate, "_run_oracle_bounded", side_effect=AssertionError("oracle")) as oracle:
        assert gate.main([
            str(target), "--json", "--usd-budget-context", "--timeout", "0",
        ]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["reason"] == "unpriced_oracle_components"
    assert "standalone" in captured.err
    oracle.assert_not_called()
