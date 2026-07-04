---
adr: 0024
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-04T02:52:05Z
prompt_source: review.py frame-critique docs/decisions/adr-0024-extract-frozen-eval-harness.md
---

VERDICT: pass (round 3, after two amendment rounds)

Round 1 (needs-changes): the ADR never named the copy-based deployment-topology
risk (design-eval's runtime is copied into targets, not referenced like
spec-oracle's checks.py) that its extraction depends on. Fixed by adding a
"Named risk" paragraph + Open Questions section.

Round 2 (needs-changes): the fix's fallback claim ("vendored duplicate kept in
sync by a byte-equality test, the same class of fallback ADR-0023 reserved")
was inaccurate — verified by direct read of oracle_overlay.py that
--vendor-engine only hashes at freeze time (drift-from-snapshot detection),
never against live source. Corrected to state the fallback relocates the
staleness risk rather than resolving it.

Round 3 (pass): correction verified accurate and fair to ADR-0023; the ADR's
core value proposition (one edited canonical file instead of N duplicates)
does not depend on which reach-the-target mechanism 020-01 picks. One minor
housekeeping gap noted (Open Questions claimed a refinement-todo.md entry
that didn't exist yet) — fixed by adding the entry.
