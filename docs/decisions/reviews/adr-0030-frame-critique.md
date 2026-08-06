---
adr: 0030
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-08-06T17:02:20Z
prompt_source: review.py frame-critique adr-0030
---

## Scope

Adversarial frame-critique of ADR-0030 and its two DRAFT specs (024
durable-cross-run-quarantine, 025 lifecycle-aware-coordinator) before
acceptance/implementation, run against the shipped `loop.py` / `heartbeat.py`
seams and the ADR-0010 / ADR-0011 boundary posture.

## Outcome

**PASS after reframe.** The critique surfaced eight framing flaws (two CRITICAL);
ADR-0030's Decision, Context §1, and Verification were rewritten to resolve every
one, and the flaw→resolution table is recorded in the ADR's `## Frame-critique`
section. The reframe preserves the ADR's intent on every count while making the
contracts self-contained and testable against the shipped code without depending
on the unlanded jig peer (ADR-0050 / spec 105).

## Flaws found and resolved

1. **CRIT — wrong writer.** `loop.py` runs against an ephemeral dispatch worktree
   and has no `finding_id`, so it cannot write a `finding_id`-keyed record at the
   real target. → **`heartbeat.py`** writes the record from the loop summary's
   `terminal_reason`; `loop.py` unchanged.
2. **CRIT — non-existent thrash.** "re-dispatched every tick forever" is false:
   ADR-0010's sticky-`tried` lifecycle + `open`-only `_select_candidates` already
   bound a finding to one attempt. → Re-scoped to a durable-legibility +
   evidence-gated re-admission layer.
3. **HIGH — unsourced ladder rungs.** security/data-loss, resume-interrupted, and
   active-work have no signal source in `_classify_ci`/`_classify_issue`. →
   Ladder narrowed to security (new label gate) > failing-CI > new work > idle;
   the two unsourced rungs deferred.
4. **HIGH — undefined release rule.** `run_url` mutates every re-run → over-release.
   → `evidence_pointer` hashes the stable evidence projection (drops
   `run_url`/`*_url`/`*_at`).
5. **HIGH — verified against unlanded jig artifacts.** jig spec 105 / `QUARANTINED`
   board do not exist. → servo owns the schema + fixture, fail-open when jig
   absent; live jig round-trip is a deferred integration slice.
6. **MED — self-defeating fingerprint.** → Key is `finding_id` alone;
   `failure_signature` is a stored field, not part of the key.
7. **MED — unversioned schema change.** Adding `priority` is an ADR-0010 change. →
   Explicit `SCHEMA_VERSION` 2→3 bump + migration in 025-01.
8. **LOW — worktree provisioning leak.** → Add `quarantine` to
   `_NON_PROVISIONED_SERVO_DIRS`; skip reads the real target.

## Provenance

Critique executed by a general-purpose reviewer subagent over the ADR, specs,
ADR-0010/0011, and the `loop.py`/`heartbeat.py` seams; flaws synthesised and
resolved by the orchestrator via the ADR reframe. FLAW 2 (the load-bearing
sticky-`tried` finding) was independently re-verified against
`_merge_findings`/`_merge_one`/`_select_candidates` before acceptance.
