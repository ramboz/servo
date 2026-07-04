---
slice: 020-02 — content-fidelity-skill
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-04T02:52:05Z
prompt_source: review.py frame-critique docs/specs/020-content-fidelity-eval/spec.md 020-02 docs/specs/020-content-fidelity-eval/slice-02-content-fidelity-skill.md
---

VERDICT: pass (round 4, after three amendment rounds)

Round 1 (needs-changes): the "command" artifact-gathering mechanism had no
determinism/invocation-cadence requirement, risking generator noise conflated
with judge noise in the n-sample lower bound (ADR-0005 clause 3). Fixed: AC3
rewritten to require the artifact be gathered exactly once per scoring run and
reused across all n judge samples, mirroring capture_app's single-capture
pattern.

Round 2 (needs-changes): AC7's claim to "mirror design-eval's own tip" was
inaccurate (design-eval's real analog is the structural setups/<id>.mjs
requirement, not its temperature tip), and cross-run generator drift can
produce a composite delta ADR-0005 clause 4's plateau noise floor was never
sized to absorb, with zero servo-side mitigation. Fixed: AC7 and Assumption A1
rewritten to name this explicitly, steer authors toward file-backed cases for
anything gating a loop, and defer a structural fix to refinement-todo.md.

Round 3 (needs-changes, wording only): AC7 said the generator drift "can
defeat clause 4's anti-flap guarantee," overstating the failure — the
noise-floor mechanism itself works correctly; the actual gap is that delta is
calibrated to judge stderr and not sized for generator drift. Also: the
refinement-todo item should name the concrete cheap mitigation candidate
(content-hash-keyed caching of the gathered artifact across the plateau
window). Both reworded.

Round 4 (pass): both wording fixes verified accurate and consistent across
the slice file and docs/refinement-todo.md. No new load-bearing issues.
