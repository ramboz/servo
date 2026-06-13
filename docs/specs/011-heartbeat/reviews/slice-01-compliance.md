---
slice: 011-01 — discover-and-inbox
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-06-12T23:52:24Z
prompt_source: review.py implementation docs/specs/011-heartbeat/spec.md 011-01 skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py
---

All nine acceptance criteria for slice 011-01 are met by `heartbeat.py` and
exercised by meaningful tests (52/52 green at review time; 53/53 after the
post-review robustness fix below). AC2's read-only guarantee is proven by a
real before/after byte-snapshot of the target tree (excluding `.servo/triage/`);
AC3's "schema_version first" by an order-preserving re-parse; AC8 by exact
per-source hash assertions; AC4's closed {0,2} contract across every degradation
path. No correctness bugs found. Security posture is sound — list-form argv with
no `shell=True`, gh/git subprocessed not imported, bounded timeouts, output
treated as untrusted data — matching guardrail #4 (inert in this discovery-only
slice).

The single real deviation (CI fingerprint on `workflowName+headBranch`, not
AC8's illustrative `workflow+job`) is forced by the live `gh run list` surface
having no `job` field, is documented in the deviation log, and is correctly
deferred to the 011-02 fingerprint-scheme ADR.

Non-defect note: the jig review prompt's generic "seven design principles"
labels don't match servo's six product-vision bullets — a prompt/repo template
mismatch, not a slice fault. Against the principles servo actually documents,
the slice complies.

VERDICT: pass (no blocking issues).
