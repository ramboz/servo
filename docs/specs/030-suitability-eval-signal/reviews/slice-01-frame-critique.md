---
slice: 030-01 — eval-component-signal
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-18T04:10:36Z
prompt_source: review.py frame-critique (R1,R2 needs-changes + R3 pass)
---

**VERDICT: PASS** (frame-critique, round 3 — fresh `general-purpose` reviewer each round; `frame_review: true`, load-bearing).

The frame survives after two `needs-changes` rounds that materially tightened it. The load-bearing premise — a reviewed, frozen eval widens only `has_signal`, and a design-led target is admitted iff it *also* carries ≥1 AC `oracle_plan`'s token-based classifier recognises as deterministic — is now honest and grounded against the **real** classifier, not the fixture stub.

Round history (fresh reviewer per round):
- **R1 needs-changes → addressed.** Caught that `suitable` needs `n_evaluable >= 1` **AND** `has_signal`, and the slice widens only `has_signal`: a purely-residual design spec (`n_evaluable == 0`) stays refused even with the eval, and the stubbed fixtures (`SERVO_SUITABILITY_ORACLE_PLAN` + hard-coded `n_evaluable >= 1`) hid it. Fixed: an explicit **Scope boundary** (spec overview) + **AC6** fencing the all-residual case via the real classifier.
- **R2 needs-changes → addressed.** Caught that the re-scoped "realistic design target carries ≥1 deterministic AC" claim used examples ("the component mounts" / "no console errors" / "the build produces output") that the token-based classifier itself classifies `residual_judgment` (verified by running `oracle_plan classify`). Fixed: examples replaced with real-classifier-verified phrasings ("the built `dist/index.html` file **is present**" → `file_presence`; "`npm run build` **exits 0**" → `command`; "**contains** 'Sign in'" → `text_invariant`); the value claim narrowed to "targets carrying ≥1 classifier-recognised AC"; **AC7** pins that positive case end-to-end through the real classifier; and vellum-population sufficiency named as an explicit **Open question** (unverifiable from this repo — if those specs are mostly all-residual, the `n_evaluable`-leg decision is load-bearing for the motivating population and must follow soon).
- **R3 pass + one non-blocking note (applied).** Reviewer independently re-ran `oracle_plan classify` on all seven example phrasings (reproducing `n_evaluable` for each) and verified every manifest/provenance fact against live code (`.servo/design-eval/config.json`, `COMPONENT="design_fidelity"`, `register_manifest` → `install.json` `components`, the four freeze fields, `reviewed` enforced via a distinct-reviewer re-enumeration record). **Note applied:** the all-residual case does not "*stay*" `needs_evidence` — with **no** signal it is the terminal `unsuitable` (rule 4 `all_acs_residual_no_signal`), and the eval **upgrades** it to recoverable `needs_evidence` (rule 3 `signal_without_evaluable_acs`), never `suitable` — a bonus (it lifts a false *terminal* refusal). The Scope boundary + AC6 now state that `unsuitable → needs_evidence` delta precisely, and AC6 asserts **both** ends (a testless target class AC3's byte-identity fence does not cover).

Residuals (named, not blocking): the self-mint / fabricated-review residual, the `scaffold-init --force` re-scaffold fail-closed direction, and the alias-map future-preset risk are all carried by ADR-0036 (guardrail 4, Assumptions, kill criterion). The safety-critical claim — an all-judge / zero-deterministic-anchor oracle is **never** `suitable` — holds throughout. Secondary R2 note (the distinct judged-only reason code needs the signal *source* threaded into `decide()`/the rule table) is acknowledged in the slice Assumptions and realised by the `eval_signal` parameter.
