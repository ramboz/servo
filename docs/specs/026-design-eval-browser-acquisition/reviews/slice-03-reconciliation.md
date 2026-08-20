---
slice: 026-03 — ledger-browser-identity
pass: reconciliation
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-20T01:42:06Z
prompt_source: review.py reconciliation (spec 026-03, round 3 after two needs-changes)
---

PASS on round 3, after two rounds of needs-changes.

The deviation log is the strongest part of the record: it admits BOTH shipped
bugs with their real mechanism, and names the systemic cause rather than the
symptom — every ledger test ran only the fake-scores arm, so the live path where
both bugs lived had zero coverage. Its checkable claims were verified, not taken
on trust: capture.mjs really imports only attestationLine/safeAttest (no JS
parser), and the AC1b narrowing (stderr report rather than a null-engine line) is
real and accurately described.

Round 1 found DoD boxes ticked over work that did not exist — including one
sitting directly on a production branch (`if not att.get("engine")`) with zero
coverage, the same shape as the two bugs the slice shipped; and an
accessor-throw box claiming "never touches process.exitCode" where that half was
a COMMENT, not an assertion (re-adding the assignment would have passed the whole
suite). Both closed with tests, both mutation-verified.

Round 1 also found the sweep asserting ADR-0031 as a `no-op` when the ADR asks
for the reference-render engine in the ledger and this slice deliberately dropped
it — with 026-02 DEFERRED and 026-04 ABANDONED, nothing will pick it up, so a
future reader would have inherited "fully implemented" as a false belief. Now
disclosed as partial, with spec.md's matching claim corrected.

Round 2 found the labelling fix made the box assert MORE than before while still
being untrue. AC7 is now eight enumerated, individually-labelled tests (seven
CI-runnable, one node-skipped), and the box records in-line that it was ticked
twice before it was true — so the history is inherited rather than hidden behind
a clean tick.

Verified clean at HEAD: fake_run threading, the isinstance guard, per-screen
provenance with no row-level collision, hash-invariance, the cross-language
marker parity test, the emission-before-setup delegation guard, SKILL.md's AC6
and AC2b content, and hosts/ regeneration. Scope confined to 026-03. The
SKILL.md drift-tripwire gap is a named residual in refinement-todo with owner,
trigger and fix — not a placeholder.
