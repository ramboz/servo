---
slice: 043-01 — refuse known-USD-priced oracle components under Copilot
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T01:41:01Z
prompt_source: review.py frame-critique spec.md 043-01 (R1 needs-changes -> R2 pass after re-scope)
---

VERDICT: pass (round 2)

Round 1 (needs-changes) raised one `[blocker]` on assumption A1 as realized —
that "known-USD-priced-under-Copilot" is a real, markable, reachable
configuration. Grounded against the codebase, the *reachability* half was false
for any automatic path: `usd_priced_components` had a reader (loop.py) but NO
producer — `register_manifest` (skills/_common/fidelity_eval.py) exposes only an
`unpriced` knob, every native judge self-marks `unpriced` (native judges cannot
supply a USD conversion — ADR-0041 Context), so servo ships no USD-priced
component and no auto-writer, and scaffold-init has no USD-pricing signal
(ADR-0041 Option B rejected scanning `oracle.sh`). As framed, the slice shipped a
refusal nothing servo produces could trigger, and the Goal / Anti-horizontal-
phasing prose over-claimed ("closes the one real safety hole end to end"),
falsifying the Anti-horizontal-phasing check.

Round 2 (pass): the re-scope (reviewer's option (b)) is honest and the frame
survives the strongest attack. The slice now ships the enforcement half (reader +
copilot-gated refusal) and states the marker's writer today is an explicit
registration / hand-edit — a narrow but legitimate writer, the same project-owned
surface ADR-0041 clause 5 relies on — with the auto-writer a named sequenced
follow-up. The enforcement path (install.json → `_usd_priced_oracle_error` →
copilot-gated `_usd_priced_oracle_preflight` → fail-closed rc) is a real,
observable, tested thin vertical (NOT horizontal detect-without-act). The
misdirection cost if no USD-priced component is ever built is small and terminal
(a leaf reader+refusal, no downstream slice depends on it); arming an accepted
safety policy ahead of the hazard matches ADR-0048 part 5's resolved OQ5
("keep refusing") default. At worst slightly early, not misframed.

Non-blocking residual/secondary (addressed in R2 prose): the hand-edit producer
is unevidenced but surfaced and correctly bounded; the ADR-0041 analogy was
softened to "guard/registrar split without a concurrent producer" (ADR-0041
shipped its producer alongside its guard); the headline Goal was brought down to
"enforceable for a marked component". Single-call-site vs unpriced's eight is a
coverage point confirmed sound by the arch pass (run_loop is the sole Copilot
execution chokepoint), not a frame risk.
