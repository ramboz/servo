---
status: READY_FOR_IMPLEMENTATION
dependencies: [020-01, adr-0005, adr-0024]
arch_review: true
frame_review: true
last_verified: 2026-07-03
---

## Slice 020-02 — content-fidelity-skill

**Goal:** Ship `/servo:content-fidelity` — a sibling skill to `design-eval`
that turns "does this generated text match the intended rubric/spec?" into a
frozen `score_content_fidelity` oracle component, judged by a pinned **text**
model instead of a vision model, built on the shared harness from 020-01.

**DoR:**
- ✅ **020-01 DONE** — `skills/_common/fidelity_eval.py` exports the
  freeze/hash/aggregate/ledger/splice primitives this slice consumes.
- ✅ **ADR-0005** — the frozen-eval contract (clauses 1-7) this component
  must satisfy, identical obligations to design-eval's, restated for text.
- ✅ **Mirrors design-eval's own shape** (`skills/design-eval/SKILL.md`,
  `design_eval.py`) for the authoring CLI verbs (`init` /
  `capture-refs`-equivalent / `freeze` / `install` / `uninstall`) and the
  `config.json` skeleton pattern (`templates/config.example.json`).

**Acceptance Criteria:**

1. **Drops into the existing oracle contract.** `score_content_fidelity` is
   an ordinary `score_<name>` component echoing `[0,1]` / rc 2, spliced into
   `oracle.sh` via the shared install helper from 020-01 (parameterized
   component name — no copy-pasted splice regex); `gate.py` and the 0/1/2
   contract are unchanged (ADR-0005 clause 1).
2. **Frozen + hashed definition.** Rubric, the case set (each case: an id,
   weight, a **reference** — the rubric/spec text or a path to one — and an
   **artifact source** describing how to obtain the generated text under
   test), judge model + decoding, `n`, `k`, `δ`, and threshold are pinned and
   sha256-hashed via the shared `validate_freeze`; a change refuses as
   **stale** (rc 2) until re-frozen (ADR-0005 clause 2). *Test:*
   `FreezeStaleOnEachFieldTests`, mirroring design-eval's own freeze-stale
   coverage but against content-fidelity's config shape.
3. **Confidence lower-bound scoring — judge noise only, never generator
   noise.** Per case, the artifact under test is gathered **exactly once**
   per scoring run (mirroring `capture_app`'s single-screenshot pattern:
   `score.py::score()` captures once, then calls `judge()` `n` times against
   that one fixed artifact); the same gathered text is then judged `n`× and
   the shared `aggregate_lower_bound` contributes `mean − k·stderr` from
   those `n` judge calls. The gathering step — file read or command
   execution — is **never re-invoked per sample**. This is required, not
   incidental: if a case's `command` generator is itself non-deterministic
   (e.g. LLM-backed) and were re-invoked per sample, the `n` scores would
   conflate judge stochasticity with generator stochasticity, and the lower
   bound would silently stop measuring "is the judge confident" — the entire
   point of ADR-0005 clause 3 — and start measuring "did the generator
   happen to produce similar output twice." Composite is the weighted
   average across cases. *Test:* `SingleGatherPerRunTests` — asserts the
   configured command/file-read is invoked exactly once per case per `score()`
   call regardless of `n`.
4. **Fail-closed honesty.** Missing judge credentials, unreachable judge,
   artifact-gathering failure (the configured generator command errors, or
   the configured output file is missing), or an unparseable judge reply →
   `env_error` (rc 2), never a silent `0.0`. Each run appends sampled +
   aggregated scores + hashes to `ledger.jsonl` via the shared ledger writer
   (ADR-0005 clauses 5, 7).
5. **Text-judge runtime.** The judge call sends a **text-only** prompt (the
   rubric + the reference text + the generated text under test) to a pinned
   **text-capable** model — no image content blocks, no vision-model
   requirement — via the same two transports design-eval offers
   (`"api"`: Anthropic Messages API; `"cli"`: headless `claude -p`), reusing
   the shared `_post_with_retry`/`_extract_json` helpers from 020-01.
6. **Artifact-under-test gathering is project-configured, with one shipped
   default.** Each case's config names either a **file** (read the target's
   already-generated text output at a given path) or a **command** (run a
   project-supplied generator script and capture its stdout) — see
   Assumption A1. Missing file / non-zero command exit is `env_error`, not a
   `0.0` (consistent with AC4).
7. **Guided skill surface.** `skills/content-fidelity/SKILL.md` documents the
   flow: `init` (scaffold `.servo/content-fidelity/` with the runtime +
   `config.json` skeleton) → author `config.json` (cases, rubric, judge,
   samples, threshold) → `freeze` → `install` → run via
   `/servo:quality-gate` / `/servo:agent-loop`. Prerequisites name a
   text-capable judge model and (for the `"api"` transport) `ANTHROPIC_API_KEY`
   — no Playwright, no browser, no vision-model requirement. **Correction
   (caught by frame-critique, 2026-07-03): this is NOT the same shape as
   design-eval's precedent, and the SKILL.md must say so plainly rather than
   imply parity.** Design-eval enforces cross-run determinism *structurally*
   — every case requires a `setups/<id>.mjs` that seeds deterministic app
   state before capture (`skills/design-eval/SKILL.md`); a `command`-backed
   content-fidelity case has no equivalent structural requirement, only a
   documentation warning. That gap is real, not cosmetic: ADR-0005 clause 4's
   plateau noise floor `δ` is calibrated to *judge* stderr (clause 3), not to
   *generator* output drift. The noise-floor mechanism itself keeps working
   correctly on whatever composite delta it's given — it is not "broken" —
   but a non-deterministic `command` case can produce a delta `δ` was never
   sized to absorb, so `loop.py` may read generator drift as false progress
   or a false plateau, with **zero servo-side mitigation for that specific
   input class**, only prose. The SKILL.md states this as an
   explicit, named limitation (not a soft tip) and recommends `file`-backed
   cases (a target-written, inherently stable artifact) over `command` for
   any case that gates a loop's plateau detection until a structural fix
   exists.

8. **`content_fidelity.py` mirrors `design_eval.py`'s authoring CLI.**
   `init` / `freeze` / `install` / `uninstall` subcommands with the same
   idempotency guarantees (re-`install` replaces the SEED block and updates
   the weight; `uninstall` keeps frozen artifacts), built on the shared
   splice helpers from 020-01 rather than re-implementing them.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions to design-eval or
      the shared module).
- [ ] Implementer test coverage exercises each AC with at least one fixture,
      using the fake-scores-style offline hook (mirroring design-eval's
      `SERVO_DESIGN_EVAL_FAKE_SCORES` pattern) so the suite runs with no live
      API/CLI dependency.
- [ ] Compliance review pass (`jig:independent-review` implementation).
- [ ] Craft review pass (`pr-review` rubric).
- [ ] Arch review pass (`arch_review: true` — new skill, new oracle
      component kind).
- [ ] Frame-critique pass recorded (`frame_review: true` — see Assumptions
      A1-A2).
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review pass.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred.

## Assumptions

- **A1 — artifact-under-test gathering defaults to file-or-command, not a
  framework integration (unverified: no real content-fidelity consumer
  exists yet to validate this against).** Design-eval's analogous step
  (`capture_app`) is a fixed mechanism (Playwright screenshot) because every
  UI-vs-mockup case looks the same. Text generation does not have one
  universal shape — a chatbot reply, a doc generator's output file, and a
  templated email body are gathered differently. AC6's file-or-command
  config knob is the smallest mechanism that covers the shape servo's own
  eval-authoring precedent (ADR-0005's dataset-is-a-hashed-artifact framing)
  requires, but it is **not validated against a real project** the way
  design-eval was de-risked by the 012 spike before it shipped. Flagged
  explicitly rather than asserted as sufficient; the frame-critique pass
  should weigh whether this needs its own throwaway spike before 020-02
  ships, or whether shipping it provisionally (like 012-05's "PENDING,
  project work" first-consumer note) is the right posture given there is no
  committed first consumer yet either.
  **Partially resolved by frame-critique, round 1 (2026-07-03):** the
  sharper risk under A1 was not "is file-or-command the right config shape"
  but whether a non-deterministic `command` (the likely shape for an
  LLM-backed generator) would silently defeat ADR-0005 clause 3's n-sample
  contract by conflating generator noise with judge noise. AC3 now pins
  gather-once-per-run as a hard requirement, which closes that specific gap
  regardless of whether the generator itself is deterministic. The narrower,
  still-open question — is file-or-command a *sufficient* shape for real
  projects — remains unresolved and is not blocking; ship provisionally per
  012-05's precedent.
  **A real, still-unmitigated risk surfaced by frame-critique, round 2
  (2026-07-03), NOT resolved by AC3:** gather-once-per-run only protects a
  *single* `score()` call. It does nothing for **across-run** stability, and
  unlike design-eval (which structurally requires a `setups/<id>.mjs` to seed
  deterministic state for every case), a `command`-backed content-fidelity
  case has no equivalent structural requirement. ADR-0005 clause 4's plateau
  noise floor `δ` is calibrated to *judge* stderr (clause 3), not to
  *generator* output drift across iterations — so a non-deterministic
  `command` case can produce a composite delta `δ` was never sized to
  absorb, so `loop.py` may read generator drift as false progress or a false
  plateau, with zero servo-side mitigation for that input class. AC7 now
  names this explicitly and steers authors toward `file`-backed cases for
  anything gating a loop; this slice does **not** build a structural fix —
  the cheapest candidate identified (not required, logged for a future
  implementer): cache the gathered artifact keyed by its content hash across
  a loop's plateau window, so a `command` case naturally behaves like a
  `file` case once generated once, without requiring the generator itself to
  be deterministic. Deliberately deferred, logged to
  `docs/refinement-todo.md` with that candidate named, not silently dropped.
  Ship provisionally, same posture as the config-shape question
  above; revisit if a real consumer hits it.
- **A2 — no vision-capable-model requirement carries over.** The judge model
  for content-fidelity is any text-capable pinned model id; nothing in this
  slice requires multimodal capability. Low-risk (the API/CLI transport
  plumbing is identical minus the image content blocks, already proven by
  design-eval), listed for completeness rather than because it's contested.

**Anti-horizontal-phasing check:** a project author can run
`/servo:content-fidelity` end-to-end — author a rubric + case set, freeze,
install — and get a working `score_content_fidelity` component that gates
`quality-gate`/`agent-loop` on text fidelity, the same observable capability
design-eval gives UI projects today.

### Deviation log (after reconciliation)

_Filled during reconciliation._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | _TODO during reconciliation._ |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board`; new skill row. |
| `docs/product-vision.md` | `no-op` | _TODO during reconciliation._ |
| `docs/architecture.md` | `updated` | New skill + shared-module consumer worth recording. |
| Primer surfaces | `no-op` | _TODO during reconciliation._ |
| `docs/inbox.md` | `no-op` | _TODO during reconciliation._ |
| `docs/refinement-todo.md` | `updated` | A1's two open items: (1) is file-or-command a sufficient config shape for real projects, if not resolved during implementation; (2) `command`-backed cases have no structural cross-run determinism requirement, so ADR-0005 clause 4's plateau noise floor `δ` is not sized to absorb generator drift — deliberately deferred, with the cheapest candidate mitigation (content-hash-keyed artifact caching across the plateau window) named for a future implementer. |
| `docs/memory/**` | `no-op` | _TODO during reconciliation._ |
| `docs/decisions/README.md` / ADR index | `no-op` | ADR-0024 already indexed. |
