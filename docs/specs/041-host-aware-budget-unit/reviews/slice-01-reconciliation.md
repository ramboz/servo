---
slice: 041-01 — Copilot contract probe
pass: reconciliation
verdict: pass
reviewer: build-session reconciliation (cites jig:reviewer compliance+craft pass)
reviewed_at: 2026-11-12T00:05:22Z
prompt_source: ADR-0014 §5 reconciliation sweep
---

VERDICT: pass

Reconciliation of a `kind: spike` slice (deliverable is findings + evidence + an
ADR Assumptions update; no code, so no tests owed).

DEVIATION LOG — attested. The six deviations are faithfully recorded and each is
either beneficial or immaterial: the run plan grew to five runs (a cheap smoke/A5
gate + a dedicated forced-overrun run) because gpt-6.1-sol's cache efficiency let
the coding tasks finish under their 30-credit invocation caps, and total spend
stayed within authorization (85.0 / 150 cr); `aiCreditsStatus` (primary partial
gate) and `--fleet`-omission (subagent control) are refinements already folded
into ADR-0048 A5/A6; A2's different-scopes result is sharper than the ADR's
"either answer is workable" framing; the worked bound's one unexposed input
(gpt-6.1-sol max output) leaves the launch-refusal conclusion intact because the
input term alone (68 cr) swamps the 30-credit minimum; A4 is unobservable on a
credit-billed account.

RECONCILIATION SWEEP — attested. Artifact coverage is complete and consistent:
slice Findings + Outcome `spec 041-02 unblocked` + `last_verified`; ADR-0048
Assumptions A1–A6 updated (Accepted ADR; Assumptions block only); `evidence/`
staged, redacted, PII-clean (0 identifier hits); compliance + craft reviews pass
(independent `jig:reviewer` re-derived every number). git touches only the 041
spec tree and `adr-0048`. The frame-critique evidence-file gap (the slice entered
working state via READY_FOR_IMPLEMENTATION, not READY_FOR_REVIEW) is a
disposition, not a correctness gap — `frame_review: true` holds from authoring and
the compliance pass independently validated all evidence.

No unresolved deviations; DoD met.
