---
slice: 026-03 — ledger-browser-identity
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-20T01:31:46Z
prompt_source: review.py implementation (spec 026-03, round 2 after needs-changes)
---

Round 2, after a round-1 needs-changes. All ACs met.

Round 1 found TWO shipped bugs, both real and both reachable:

1. AC5 — `_provenance(att, fake_run=att is None)` passed a value DERIVED FROM the
   same predicate the function branches on, so `not_attested` was unreachable on
   the live path: a real capture whose marker line was missing or malformed was
   recorded as `not_captured` ("no browser ran at all"), the exact merge AC5
   exists to prevent. Now threaded from score() as `fake is not None`.
2. AC4 — a non-object JSON payload after the marker (`##servo-capture:123`)
   reached `att.get(...)` and raised AttributeError, which is NOT in main()'s
   catch tuple: a successful capture-and-judge run died on a provenance detail.
   AC1a explicitly anticipates an adopter echoing the marker, so this was
   reachable. Guarded with `isinstance(payload, dict)`.

Both mutation-verified: reintroducing either fails its test.

Root cause of both: every ledger test ran only the fake-scores arm, so the live
path had zero coverage. Four LIVE-arm tests added — attested provenance, the
missing-line regression, hostile payloads still scoring, and two screens with
differing attestations recorded separately. The helper calls score.score()
directly, because _capture_main loads a fresh copy of score.py from the eval dir
and module-level monkeypatches never reach it.

Also fixed: stable row shape (all provenance keys always present); SKILL.md's
AC2b evidential-weight statement (engine+version are the attestation,
capture_transport is the instructed value echoed as a canary); three vacuous
assertions, one of which was unfailable by construction (a needle containing
spaces its haystack had stripped).

capture_lib.mjs's `parseAttestation` was deleted — no production consumer, a
test-only shadow of the authoritative Python parser that would silently diverge.
Replaced with a cross-language ATTEST_MARKER parity test, the one place the
contract can actually break.
