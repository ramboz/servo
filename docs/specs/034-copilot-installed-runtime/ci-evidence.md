# Validation and integration evidence (2026-10-12)

## Executed gates

Before the final main synchronization, the exact established
`python3 scripts/ci_check.py` passed **2244 tests**, four-manifest validation,
the pinned Ruff floor, all **150 install-surface tests**, and the committed
three-host drift guard. This is current executed evidence, not the September
CI claim. Earlier failed runs and their corrections remain in the review logs.

All three synchronized version0.10.0 release archives were built with the
existing `build_release_zip.py` and their host-specific smoke checks passed.
These archive checks are static, not live model/hook proofs.

Native evaluation's owned/new/legacy suites passed on actual CPython3.9.6
and3.12.12, separately from syntax checks. Final edge fixes were witnessed
red-to-green (relative executable identity and cyclic path resolution on3.9);
no unsafe fallback, skipped criterion or passing injected native score.

## Fresh main synchronization

Main advanced to `972e8d4` (merged heartbeat diagnostic handoff) during this work.
The branch fetched, reviewed `HEAD..origin/main`, mechanically relocated its
provisional Copilot spec033→034 and capabilityADR0039→0043, then merged current
main at `7661527`. No lifecycle cross-ref gate was bypassed.

Merge resolution retained both additive memory entries, regenerated the derived
decision/spec indexes, kept main's canonical scaffold sentinel and regenerated
all hosts from the combined heartbeat source. Targeted converging heartbeat/
accounting/host tests passed **363 tests, 73 subtests**. New heartbeat closed
records are byte-identical to main; September AcceptedADR0038/closedspec032 are
unchanged from the original PR head.

This is required upstream synchronization, not an unrelated duplicate
implementation or silent import of an open adjacent PR.

## Final post-sync gate

The exact `python3 scripts/ci_check.py` completed with exit **0** against the
synchronized source snapshot:

- **2255 tests passed** in 390.96 seconds.
- Four host manifests agree on Servo0.10.0.
- Pinned Ruff: all checks passed.
- Plugin-root verification and all **150 install-surface tests** passed.
- Committed three-host package drift guard passed.

Supported slices can now finish their recorded lifecycle. Fresh remote PR-head
CI is still a separate landing check; no merge is authorized.

## Lifecycle and capability boundaries

Required frame, compliance, craft, architecture and reconciliation passes have
actual independent reviewer evidence, including failed rounds and corrections.
No percentage or broad "all native parity" claim is used:
034-01/02/04/05/06/08 own supported delivery; 034-03 native autonomy/whole-pass
runtime and 034-07 enforcing stop continuation remain **DEFERRED** with precise
reactivation triggers. A safe refusal is not native-loop completion.
