---
slice: 020-01 — extract-shared-harness
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-04T02:52:05Z
prompt_source: review.py frame-critique docs/specs/020-content-fidelity-eval/spec.md 020-01 docs/specs/020-content-fidelity-eval/slice-01-extract-shared-harness.md
---

VERDICT: pass (round 2)

Round 1 (needs-changes): the DoR overstated oracle.sh's "$PWD" argument as
load-bearing for import resolution; score.py::main() actually ignores that
argument and resolves via Path(__file__).resolve().parent. Also flagged: no
re-sync/staleness story for the copied shared module. Fixed by correcting the
DoR's claim and adding an explicit "known, accepted, pre-existing limitation"
paragraph (deferred to ADR-0024 Open Questions / refinement-todo.md).

Round 2 (pass): corrected DoR claim verified byte-for-byte accurate against
score.py; traced design_eval.py::_load_score()'s importlib-based loading to
confirm the two-candidate import probe (Assumption A1) behaves consistently
whether score.py runs as __main__ or is dynamically loaded, and confirmed the
one untested invocation-style combination never occurs in production. Minor
non-blocking precision note applied: AC2's tests now specify direct
subprocess execution (matching the real oracle.sh invocation contract).
