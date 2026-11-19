---
slice: 044-01 — required-policy-evaluable
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-19T20:17:02Z
prompt_source: review.py frame-critique docs/specs/044-required-policy-evaluability/spec.md 044-01 (3 fresh rounds)
---

Frame-critique ran THREE rounds against fresh, independent `general-purpose`
reviewers, each verifying grounding against the real code. The decision frame —
ADR-0050's Option C: credit a deterministic, spec-attributed required-policy
check toward `n_evaluable`, never the stochastic judge — **held through all three
rounds**; each round caught a distinct, real implementation-frame defect,
corrected before the next.

- **R1 (needs-changes):** the `fidelity_contract` frontmatter binding is a
  **target-independent constant** (`static_contract.py::prepare` hardcodes
  `spec/oracle/static`), so it delivers **author opt-in, not content attribution**
  — the gate proves the declared path is a *real sealed check*, never that the
  check's redline corresponds to *this* spec's ACs. The spec **overclaimed** a
  mechanical guarantee ("a mis-pointed or fabricated binding fails closed and
  cannot manufacture a pass"), false for the one mis-pointing that can occur:
  pointing at a valid contract authored for a different spec's redline.
  → Reframed to the **honest-author threat model** servo already runs on
  (ADR-0036 g4 self-reported `reviewed`; ADR-0049 honest-worker), scoped to
  ADR-0050's own **single-redline-per-target by-construction closure**, with the
  residual made first-class and **fenced by a test (AC3b)**: a second feature spec
  that *deliberately* declares the binding on a shared target IS credited (caught
  by spec review, not the gate) — degrading to a real deterministic floor
  attributed to the wrong spec (Option-A-grade), never Option B's vacuous
  judge-only oracle. Corrected the overclaim everywhere.

- **R2 (needs-changes):** the gate's seal predicate (`required_policy` +
  `approval_status == "approved"` + `family: command` + `required`) is a strict
  **subset** of the real seal — `prepare` writes `checks.json` *without*
  `approval_status`; the install step stamps `approved_required_binding` + the
  live `oracle.sh` hash-pin + writes `.servo/required-policy.json`. Trusting the
  committed label would credit honest-drift states the score-time oracle refuses:
  the airtight case is `oracle.sh` **regenerated after sealing** (`driver_seal`'s
  pin no longer matches → env-error), and worse, a committed-sealed contract that
  is **not the installed required gate** lets the oracle green on the
  `design_fidelity` *judge* alone — re-laundering Option B's false pass through the
  evaluability leg. → Replaced with a **two-layer liveness check**: **L1** (committed
  `checks.json` sealed + its `approved_required_binding` pins the *current*
  `oracle.sh`, mirroring `driver_seal`) and **L2** (the static check is a registered
  component in the runtime `.servo/required-policy.json` whose entry *equals* the
  committed binding — the `plan.approved_required_binding == entry` identity
  score-time enforces). Widened AC4 (a–i) to fence each layer; documented that the
  full cryptographic seal stays score-time authority.

- **R3 (PASS):** verified the L1/L2 predicate against the real code and confirmed
  the catastrophic axis is **structurally closed** — L2 forces the static check
  into `required-policy.json`'s `components`, and `required_runtime.outcome`
  (~707) then degrades *any* residual seal failure to a score-time **env-error,
  never a green**, so no `suitable` verdict can admit a loop that greens on the
  judge alone. Every code citation checks out (`driver_seal` 911–927,
  `installed_policy` 504–521, `oracle` oracle.sh-pin 742–745 + binding identity
  779–785, `prepare` refuse-a-second-contract 1113–1117; `analyze` already holds
  the spec path and threads `eval_signal` as a kwarg, so `policy_evaluable` mirrors
  a proven 030-01 pattern). AC3b is a settled residual, not a fresh flaw.

Applied before recording this pass (R3's two non-blocking notes):
1. The "mirror-drift is safe" justification was **literally backwards** — the gate
   mirrors a *subset* of the seal, so benign false-`suitable`-that-env-error states
   DO exist (`runtime_hash` drift, config/fragment drift). Rewrote the guarantee as
   the correct **structural** one: **"no false *green*"** (no silent Option-B
   judge-only pass), not "no false `suitable`", and named the benign env-error
   residual explicitly.
2. L2 phrasing — a `components` **entry** *is* an `approved_required_binding` (not a
   nested `.approved_required_binding` field); corrected in both the spec and AC4.

Verdict: **pass.** The decision and its two hardened constraints (honest-author
attribution scoped to the single-redline closure; two-layer score-time-liveness
seal check) are sound; the integration is the implementing slice's work, under
test (AC1/AC3/AC3b/AC4 fence every boundary).
