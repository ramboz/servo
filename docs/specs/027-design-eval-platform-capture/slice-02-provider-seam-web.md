---
status: IN_PROGRESS
dependencies: [adr-0032]
last_verified: 2026-08-21
claimed_by: claude/027-01-342c59
---

## Slice 027-02 — capture-provider seam + web default

**Goal:** Introduce a `capture.transport` selector (reviving spec 026-02's
designed-but-unbuilt field) and a provider dispatch inside `capture_app`, with
the existing Playwright path refactored into the default **web** provider —
behavior-preserving for every current web project, and recording the chosen
provider in `ledger.jsonl` (unfrozen, per [ADR-0032](../../decisions/adr-0032-design-eval-capture-providers.md) §6 / ADR-0031).

**Scope note:** minimal interface — one provider (web), no non-web target yet.
Absent config → web default, zero change. The seam is the enabling surface the
later provider slices plug into. This slice deliberately does **not** widen the
provider contract to state-seeding or frame-normalization (ADR-0032 §1/§4/§5);
today's web path already satisfies both for free, and native seeding/cropping is
027-04/05 work. This slice ships only the *selection + dispatch + ledger* seam.

**DoR:**
- ✅ Current behaviour probe-verified (2026-08-21): capture is a single hardwired
  path — `capture_app` (`score.py:175`) spawns `node capture.mjs …`; nothing reads
  a `capture.transport` field (it was designed in ADR-0031/spec 026-02 but never
  built — grep-confirmed only `judge.transport` is read, `score.py:212`).
- ✅ Freeze coupling probe-verified: `definition_hash` is computed over a fixed
  field set — `_CASES_KEY="screens"`, `_CASE_FILE_FIELDS`, `_EXTRA_HASH_FIELDS=("viewport",)`
  (`score.py:40-44`) — so a new top-level `capture` key is naturally excluded from
  the hash and must stay excluded (ADR-0032 §6: transport is environmental, never
  frozen). Guarded today by `test_definition_hash_unchanged_for_pre_existing_frozen_config`.
- ✅ Env-override precedent: `SERVO_DESIGN_EVAL_CLAUDE_BIN` (`score.py:222`) is the
  existing "env overrides config" pattern to mirror for the transport selector.
- ✅ No new dependency; ADR-0032 is Accepted and already governs this seam.

**Acceptance Criteria:**

1. **Absent config → web default, behavior-preserving.** With no `capture` block
   in `config.json` and no env override, a live-capture run drives the **exact**
   existing Playwright path (`node capture.mjs --screen <id> --out <path>`), byte
   contract unchanged. A frozen eval authored before this slice scores without
   going stale and produces the same composite it would have pre-seam.
2. **Explicit `capture.transport: "web"` selects the web provider.** A config that
   names `web` explicitly behaves identically to the absent case — same spawn,
   same result.
3. **Env override beats config.** `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` overrides
   `config.capture.transport` when both are set (mirroring `SERVO_DESIGN_EVAL_CLAUDE_BIN`).
   Resolution precedence is: env var → `config.capture.transport` → `"web"`.
4. **Unknown provider fails closed.** A `capture.transport` (via config or env)
   that names a provider not in the registry raises `EnvError` → rc 2
   `env_error`, surfaced **before** any per-screen capture — never a silent `0.0`,
   never a fall-through to web. The message names the unknown provider and the
   known set.
5. **The ledger records the chosen provider.** Each live-capture run's ledger row
   carries a top-level `capture_provider` field = the resolved provider name
   (e.g. `"web"`). A fake-scores run (no capture ran) records
   `capture_provider: null`, mirroring the `not_captured` / `shot: null`
   honesty pattern. The field is advisory — never part of `definition_hash`.
6. **`capture.transport` is environmental, not frozen (additive).** Adding,
   removing, or changing a `capture` block does **not** change `definition_hash`
   and does **not** make an existing frozen eval stale. The composite value, the
   freeze/`StaleError` validation, the `env_error`-on-failure contract, and the
   0/1/2 oracle contract are untouched; the change is a selector + dispatch + one
   new ledger field.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one fixture
      (absent→web spawn; explicit web; env-beats-config precedence; unknown→rc2
      env_error; ledger `capture_provider` name on live + null on fake; a `capture`
      block leaves `definition_hash` unchanged).
- [ ] Each new test shown to fail when the feature is removed (drop the selector /
      the registry guard / the ledger field → tests go red).
- [ ] Reviewed by `reviewer` subagent (compliance + craft passes).
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred.

**Anti-horizontal-phasing check:** After this slice lands, a design-eval user can
*select* their capture provider through `capture.transport` (env or config), see
which provider scored a run in the ledger, and get an honest `env_error` for an
unknown provider — a real, user-facing selection surface today, even though only
the web provider exists. The later slices register additional providers into the
same seam without touching the scoring path.

**Deferred (candidate for refinement-todo):** none anticipated — the widened
state/frame contract (ADR-0032 §1/§4/§5) is explicitly 027-03/04/05 work, not a
deferral of this slice.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` regenerated by `workflow.py status-board` (only if it
      closes the spec — it does not; 03–05 remain).

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

_TBD during reconciliation._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | _TBD._ |
| `docs/specs/README.md` | `deferred` | _TBD: status-board regen at close-out; spec not closed._ |
| `docs/product-vision.md` | `no-op` | _TBD._ |
| `docs/architecture.md` | `no-op` | _TBD: additive selector + ledger field, no module-boundary change._ |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | _TBD._ |
| `docs/inbox.md` | `no-op` | _TBD._ |
| `docs/refinement-todo.md` | `no-op` | _TBD._ |
| `docs/memory/**` | `no-op` | _TBD._ |
| `docs/decisions/README.md` / ADR index | `no-op` | _TBD: no ADR touched (ADR-0032 already Accepted)._ |
| `skills/design-eval/SKILL.md` | `updated` | _TBD: document the `capture.transport` selector + `capture_provider` ledger field._ |
