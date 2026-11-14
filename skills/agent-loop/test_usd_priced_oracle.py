"""043-01 (ADR-0048 part 5): refuse known-USD-priced oracle components under Copilot.

Companion to `test_unpriced_oracle.py` (ADR-0041, unknown-cost). The difference
is the *trigger*: ADR-0041 refuses an unknown-cost (`unpriced_components`)
component under any host, because unknown cost can never be accounted. ADR-0048
part 5 refuses a KNOWN-USD-priced (`usd_priced_components`) component only under
`--host copilot`, where there is no USD bound (the credit ceiling bounds the
worker's Copilot session only, never oracle USD spend). Under `--host claude` a
non-null `cost_ceiling` bounds the same component (ADR-0005 clause 6), so the
new refusal is a no-op there (AC4).
"""

import importlib.util
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "usd_priced_loop", Path(__file__).with_name("loop.py")
)
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)

NAMES = ["generic-eval", "content-eval", "design-eval"]

# Marker-protocol cases for the host-agnostic reader `_usd_priced_oracle_error`.
# Mirrors `test_unpriced_oracle.PROTOCOL_CASES` exactly, keyed on
# `usd_priced_components` with the parallel reason strings — the two markers
# share a validator shape (ADR-0041 §6 / ADR-0048 part 5) but are independent
# keys, so the two refusals stay separately identifiable (AC1, AC5).
PROTOCOL_CASES = [
    ({}, None),
    ({"components": []}, None),
    ({"components": NAMES}, None),
    ({"components": [], "usd_priced_components": []}, None),
    ({"components": NAMES, "usd_priced_components": []}, None),
    *[
        ({"components": NAMES, "usd_priced_components": [name]},
         "usd_priced_oracle_components")
        for name in NAMES
    ],
    ({"components": NAMES, "usd_priced_components": NAMES},
     "usd_priced_oracle_components"),
    *[
        ({"components": NAMES, "usd_priced_components": marker},
         "usd_priced_components_invalid")
        for marker in (None, False, 0, "", NAMES[0], {}, [None], [1], [False],
                       [""], [" \t"], [NAMES[0], NAMES[0]], ["unknown"])
    ],
    *[
        ({"components": components, "usd_priced_components": [NAMES[0]]},
         "usd_priced_components_invalid")
        for components in (None, NAMES[0], {}, [None], [""], [" "], [1], [])
    ],
    ({"usd_priced_components": []}, "usd_priced_components_invalid"),
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
    summary = json.loads(captured.out.splitlines()[-1])
    assert summary["final_oracle_status"] == "env_error"
    assert summary["terminal_reason"] == reason
    assert "usd_priced_components" in captured.err
    assert ".servo/install.json" in captured.err
    assert "USD" in captured.err
    assert "ADR-0048" in captured.err
    assert snapshot(target) == before
    for mock in mocks:
        mock.assert_not_called()
    return summary, captured.err


# ---- AC1 / AC5: the host-agnostic marker reader -----------------------------

@pytest.mark.parametrize("manifest,reason", PROTOCOL_CASES)
def test_marker_protocol(target, manifest, reason):
    seed(target, manifest)
    before = snapshot(target)
    error = loop._usd_priced_oracle_error(target)
    if reason is None:
        assert error is None
    else:
        assert error[0] == reason
        assert "usd_priced_components" in error[1]
        assert ".servo/install.json" in error[1]
        assert "USD" in error[1]
        assert "ADR-0048" in error[1]
    assert snapshot(target) == before


def test_unreadable_manifest_fails_closed(target):
    with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
        error = loop._usd_priced_oracle_error(target)
    assert error[0] == "usd_priced_components_invalid"
    assert "repair" in error[1]


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_target_defers_to_other_preflight(tmp_path, kind):
    target = tmp_path / "invalid-target"
    if kind == "file":
        target.write_text("not a directory")
    assert loop._usd_priced_oracle_error(target) is None


def test_reader_is_host_agnostic_and_independent_of_unpriced(target):
    # A usd_priced marker must NOT trip the unpriced reader, and an unpriced
    # marker must NOT trip the usd_priced reader: independent keys (AC5).
    seed(target, {"components": NAMES, "usd_priced_components": [NAMES[0]]})
    assert loop._unpriced_oracle_error(target) is None
    assert loop._usd_priced_oracle_error(target)[0] == "usd_priced_oracle_components"
    seed(target, {"components": NAMES, "unpriced_components": [NAMES[0]]})
    assert loop._usd_priced_oracle_error(target) is None
    assert loop._unpriced_oracle_error(target)[0] == "unpriced_oracle_components"


def test_reasons_are_distinct():
    # AC5: the two refusal reason strings are not the same symbol or value.
    assert (
        loop.REASON_USD_PRICED_ORACLE_COMPONENTS
        != loop.REASON_UNPRICED_ORACLE_COMPONENTS
    )
    assert (
        loop.REASON_USD_PRICED_COMPONENTS_INVALID
        != loop.REASON_UNPRICED_COMPONENTS_INVALID
    )
    assert loop.REASON_USD_PRICED_ORACLE_COMPONENTS == "usd_priced_oracle_components"
    assert loop.REASON_USD_PRICED_COMPONENTS_INVALID == "usd_priced_components_invalid"


# ---- AC4: the preflight is copilot-gated (no USD bound is the hazard) --------

@pytest.mark.parametrize("marker", [
    [NAMES[0]], NAMES, None, ["unknown"],  # refuse-worthy AND malformed markers
])
def test_preflight_is_a_noop_under_claude(target, marker, capsys):
    # Under --host claude a USD cost_ceiling bounds the component, so the new
    # refusal never fires — even for a malformed marker (the hazard this slice
    # closes exists only when there is no USD bound).
    seed(target, {"components": NAMES, "usd_priced_components": marker})
    before = snapshot(target)
    rc = loop._usd_priced_oracle_preflight(
        target, host=loop.HOST_CLAUDE, cost_ceiling=5.0,
        context_fill_threshold=0.5, run_id="r",
    )
    assert rc is None
    assert capsys.readouterr().out == ""
    assert snapshot(target) == before


def test_preflight_default_host_is_claude(target):
    # Default host must be the safe no-op (claude), not copilot.
    seed(target, {"components": NAMES, "usd_priced_components": [NAMES[0]]})
    assert loop._usd_priced_oracle_preflight(target) is None


@pytest.mark.parametrize("marker,reason", [
    ([NAMES[0]], "usd_priced_oracle_components"),
    (NAMES, "usd_priced_oracle_components"),
    (None, "usd_priced_components_invalid"),
    (["unknown"], "usd_priced_components_invalid"),
])
def test_preflight_refuses_under_copilot(target, capsys, marker, reason):
    seed(target, {"components": NAMES, "usd_priced_components": marker})
    before = snapshot(target)
    rc = loop._usd_priced_oracle_preflight(
        target, host=loop.HOST_COPILOT, cost_ceiling=None,
        context_fill_threshold=None, run_id="run-xyz",
    )
    summary, _ = assert_refusal(rc, capsys, target, before, reason, [])
    assert summary["run_id"] == "run-xyz"


def test_preflight_noop_when_no_marker_under_copilot(target):
    # A copilot target with a plain (unmarked) manifest is not refused.
    seed(target, {"components": NAMES})
    assert loop._usd_priced_oracle_preflight(
        target, host=loop.HOST_COPILOT) is None


# ---- AC2 / AC3: refuse at the run_loop launch gate (the copilot chokepoint) --

@pytest.mark.parametrize("credit_ceiling", [30, 100, 1000, 30.5])
def test_run_loop_refuses_under_copilot_any_credit_ceiling(
    target, capsys, credit_ceiling
):
    # AC2 (refuse) + AC3 (independent of the credit ceiling's value): whatever
    # the credit ceiling, a usd_priced component is refused under copilot.
    seed(target, {"components": NAMES, "usd_priced_components": [NAMES[1]]})
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack, [
            "_install_signal_handlers", "_invoke_copilot", "_invoke_claude",
            "_invoke_gate", "_ensure_vendored_gate", "_create_run_dir",
            "_atomic_write_state", "_get_claude_version",
        ])
        rc = loop.run_loop(
            target, prompt="x", max_iterations=1, cost_ceiling=None,
            context_fill_threshold=0, allow_dirty=True,
            host=loop.HOST_COPILOT, credit_ceiling=credit_ceiling,
        )
    _, message = assert_refusal(
        rc, capsys, target, before, "usd_priced_oracle_components", mocks
    )
    assert NAMES[1] in message
    assert "copilot" in message
    assert "part 5" in message


def test_run_loop_refusal_names_all_offending_components(target, capsys):
    seed(target, {"components": NAMES, "usd_priced_components": NAMES})
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack, ["_install_signal_handlers", "_invoke_copilot"])
        rc = loop.run_loop(
            target, prompt="x", max_iterations=1, cost_ceiling=None,
            context_fill_threshold=0, allow_dirty=True,
            host=loop.HOST_COPILOT, credit_ceiling=30,
        )
    _, message = assert_refusal(
        rc, capsys, target, before, "usd_priced_oracle_components", mocks
    )
    for name in NAMES:
        assert name in message


def test_run_loop_fails_closed_on_malformed_marker_under_copilot(target, capsys):
    seed(target, {"components": NAMES, "usd_priced_components": None})
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack, ["_install_signal_handlers", "_invoke_copilot"])
        rc = loop.run_loop(
            target, prompt="x", max_iterations=1, cost_ceiling=None,
            context_fill_threshold=0, allow_dirty=True,
            host=loop.HOST_COPILOT, credit_ceiling=30,
        )
    _, message = assert_refusal(
        rc, capsys, target, before, "usd_priced_components_invalid", mocks
    )
    assert "repair" in message


def test_cli_refuses_under_copilot(target, capsys):
    # The CLI launch surface (main → run_loop) refuses before any Copilot call.
    seed(target, {"components": NAMES, "usd_priced_components": [NAMES[0]]})
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack, [
            "_install_signal_handlers", "_invoke_copilot", "_decide_route",
        ])
        rc = loop.main([
            str(target), "--host", "copilot", "--credit-ceiling", "30",
            "--max-iterations", "1", "--prompt", "x",
        ])
    _, message = assert_refusal(
        rc, capsys, target, before, "usd_priced_oracle_components", mocks
    )
    assert NAMES[0] in message


# ---- AC4: the claude launch path is unaffected by a usd_priced marker --------

@pytest.mark.parametrize("flags", [
    # The new refusal is HOST-keyed (copilot only), so it never fires under
    # claude whatever the ceiling value. `--driver loop` forces the mocked
    # run_loop path (so routing/host-probe does not divert to the goal driver),
    # mirroring test_unpriced_oracle's legacy-manifest test.
    ["--host", "claude", "--cost-ceiling", "5", "--driver", "loop", "--prompt", "x"],
    ["--driver", "loop", "--prompt", "x"],  # default host=claude, default ceiling
    # `--cost-ceiling 0` is the DISABLE sentinel, not a $0 bound; included to show
    # the copilot-only refusal still does not fire under claude. Whether claude's
    # own USD bounding suffices for a (hypothetical) usd_priced oracle when the
    # cumulative ceiling is disabled is a claude-side question out of this slice's
    # scope (a future ADR-0005 revisit) — claude behavior is unchanged here.
    ["--cost-ceiling", "0", "--driver", "loop", "--prompt", "x"],
])
def test_cli_claude_proceeds_despite_usd_priced_marker(target, flags):
    # A usd_priced component under claude stays bounded by the USD ceiling and
    # does NOT trigger the new refusal — the launch proceeds to run_loop.
    seed(target, {"components": NAMES, "usd_priced_components": NAMES})
    before = snapshot(target)
    with patch.object(loop, "run_loop", return_value=17) as run:
        assert loop.main([str(target), *flags]) == 17
    run.assert_called_once()
    assert snapshot(target) == before


def test_run_loop_claude_passes_gate_to_signal_install(target):
    # Direct programmatic claude entry: the usd_priced gate is a no-op, so
    # control reaches `_install_signal_handlers` (our sentinel just past it).
    seed(target, {"components": NAMES, "usd_priced_components": [NAMES[0]]})
    with patch.object(
        loop, "_install_signal_handlers",
        side_effect=RuntimeError("reached signal install"),
    ):
        with pytest.raises(RuntimeError, match="reached signal install"):
            loop.run_loop(
                target, prompt="x", max_iterations=1, cost_ceiling=5.0,
                context_fill_threshold=0, allow_dirty=True,
                host=loop.HOST_CLAUDE,
            )


# ---- AC5: the unpriced path is unchanged and both refusals coexist -----------

def assert_unpriced_refusal(rc, capsys, target, before, mocks):
    # The ADR-0041 unpriced refusal has its OWN (unchanged) message — assert on
    # it directly rather than through the usd_priced-specific assert_refusal.
    captured = capsys.readouterr()
    assert rc == loop.EXIT_ENV_ERROR
    summary = json.loads(captured.out.splitlines()[-1])
    assert summary["final_oracle_status"] == "env_error"
    assert summary["terminal_reason"] == "unpriced_oracle_components"
    assert "unpriced_components" in captured.err
    assert "usd_priced_components" not in captured.err  # the other guard stayed quiet
    assert "ADR-0041" in captured.err
    assert snapshot(target) == before
    for mock in mocks:
        mock.assert_not_called()


def test_both_markers_under_copilot_unpriced_takes_precedence(target, capsys):
    # With BOTH markers, the ADR-0041 unpriced (unknown-cost) refusal fires
    # first — it is the stricter, host-agnostic rule — and the two reasons stay
    # distinct. Proves the usd_priced guard did not displace the unpriced one.
    seed(target, {
        "components": NAMES,
        "unpriced_components": [NAMES[0]],
        "usd_priced_components": [NAMES[1]],
    })
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack, ["_install_signal_handlers", "_invoke_copilot"])
        rc = loop.run_loop(
            target, prompt="x", max_iterations=1, cost_ceiling=None,
            context_fill_threshold=0, allow_dirty=True,
            host=loop.HOST_COPILOT, credit_ceiling=30,
        )
    assert_unpriced_refusal(rc, capsys, target, before, mocks)


def test_unpriced_only_under_copilot_still_refuses_unchanged(target, capsys):
    # AC5: an unknown-cost component still refuses under its existing reason.
    seed(target, {"components": NAMES, "unpriced_components": [NAMES[0]]})
    before = snapshot(target)
    with ExitStack() as stack:
        mocks = forbid(stack, ["_install_signal_handlers", "_invoke_copilot"])
        rc = loop.run_loop(
            target, prompt="x", max_iterations=1, cost_ceiling=None,
            context_fill_threshold=0, allow_dirty=True,
            host=loop.HOST_COPILOT, credit_ceiling=30,
        )
    assert_unpriced_refusal(rc, capsys, target, before, mocks)
