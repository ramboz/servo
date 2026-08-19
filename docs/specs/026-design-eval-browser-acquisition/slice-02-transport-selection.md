---
status: DRAFT
dependencies: [026-01, adr-0031]
last_verified:
arch_review: true
frame_review: true
---

## Slice 026-02 — transport-selection

**Goal:** Let an adopter reuse an installed Chrome instead of downloading a
pinned Chromium — the footprint concern that motivated ADR-0031 — via an
**unfrozen** `capture.transport` config field plus an env override, with
`capture.mjs` launching accordingly.

**DoR:**
- ✅ **The freeze boundary is settled and grounded:** `capture.transport` is
  environmental and is **excluded from `definition_hash`**, exactly as `app_url`
  is. Verified — `app_url` is in `templates/config.example.json:4` and is named
  in `definition_hash`'s docstring as the excluded-environmental example;
  `validate_freeze` compares config-to-its-own-hash plus on-disk artifact hashes
  and never probes the environment.
- ✅ **Override precedent exists:** `SERVO_DESIGN_EVAL_CLAUDE_BIN`
  (`score.py:128-129`) is an established unfrozen environmental escape hatch;
  `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` mirrors it.
- ⚠️ **A1 is the load-bearing unknown and is probed inside this slice:** does
  `channel: 'chrome'` (or `playwright-core` + `executablePath`) reliably drive an
  installed system Chrome across target OS/versions? **Probe this first.** If it
  does not, ADR-0031 kill criterion 1 fires: report it, keep bundled-only, and
  re-read the ADR rather than forcing the transport through.

**Acceptance criteria:**
1. `config.json` gains a `capture` block with a `transport` field; absent block
   ⇒ **assume bundled, warn, never refuse** (back-compat for existing frozen
   configs — a silent behavior change for current adopters is unacceptable).
2. `capture.transport` is **excluded from `definition_hash`**; changing it does
   **not** re-freeze and can never raise `StaleError`. A test asserts the
   definition hash is byte-identical before and after a transport change.
3. `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` overrides the config value, so a CI box
   lacking the configured browser selects another without editing the eval.
4. `capture.mjs` launches per resolved transport (bundled Chromium vs system
   Chrome).
5. 026-01's preflight is transport-aware: it probes the browser the *resolved*
   transport needs and names the remedy for that transport.
6. Invalid/unknown transport values fail closed with a clear `env_error`.
7. `SKILL.md` documents both transports and the footprint/comparability trade
   plainly — including that BYO engine drift is real and unpoliced.

**DoD:**
- [ ] A1 probed and the result recorded in the deviation log (viable / not).
- [ ] `capture` block read at runtime; excluded-from-hash test green.
- [ ] Env override honored, with precedence tested.
- [ ] Back-compat: a pre-existing frozen config still scores, with a warning and
      no `StaleError`.
- [ ] Preflight extended to be transport-aware.
- [ ] `SKILL.md` + `templates/config.example.json` updated.
- [ ] Compliance + craft + **arch** review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Why `arch_review: true`:** this slice changes the `config.json` schema and
touches the freeze boundary — a public contract for every existing adopter.

**Vertical?** Yes — an adopter can skip the ~150 MB download and score with the
Chrome they already have.
