---
status: DONE
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
- [x] All ACs pass; full test suite green (no regressions). — `CaptureProviderSeamTests`
      7/7 green; 102/102 in `test_design_eval` bar the one pre-existing red
      (`CaptureLibNodeTests.test_capture_lib_node_suite_passes`, a Node
      output-format mismatch, red on a clean tree, unrelated to this slice);
      `test_skill_surface` 25/25 green after the SKILL.md edits.
- [x] Implementer test coverage exercises each AC with at least one fixture
      (absent→web spawn; explicit web; env-beats-config precedence; unknown→rc2
      env_error; ledger `capture_provider` name on live + null on fake; a `capture`
      block leaves `definition_hash` unchanged).
- [x] Each new test shown to fail when the feature is removed (drop the selector /
      the registry guard / the ledger field → tests go red). — demonstrated red
      before implementation (5 of 7 red). Honest caveat: the two AC6 tests are
      regression-guards on the freeze (a `capture` key is *already* excluded from
      the hash), so they stay green even without the selector; the five
      feature-bearing tests go red without it (see deviation log).
- [x] Reviewed by `reviewer` subagent (compliance + craft passes). — `jig:reviewer`,
      independent, 2026-08-21.
- [x] Implementation review passed. — VERDICT: pass, no blocking issues.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Compliance + craft review verdicts recorded under `reviews/` (`slice-02-compliance.md`, `slice-02-craft.md`). *(Backfilled 2026-08-21 after PR #31 flagged missing review traces; the compliance + craft passes ran per-slice during implementation.)*
- [x] Reconciliation review passed. — `jig:reviewer` reconciliation pass,
      VERDICT: pass, 2026-08-21; deviation-log claims verified line-for-line
      against `score.py`, SKILL.md additions confirmed accurate, sweep dispositions
      confirmed, git working tree confirmed clean (only this slice + SKILL.md).
- [x] `docs/refinement-todo.md` updated if any decisions were deferred. — none
      deferred by this slice (the widened state/frame contract is 027-03/04/05
      scope, not a deferral); no entry needed.

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

- **Registry-based dispatch.** The seam is a module-level `_CAPTURE_PROVIDERS`
  dict (`{"web": _capture_web}`) plus `_resolve_capture_transport(config)` for
  precedence and a lookup in `capture_app`. The old `capture_app` body moved
  verbatim into `_capture_web` (behavior-preserving); `capture_app` became a thin
  dispatcher taking a defaulted `provider="web"` param, so the existing 2-/3-arg
  callers (`CaptureAppHonestyTests`, the `CaptureLibNodeTests` routing test, and
  027-01's `ShotRetentionTests`) keep working unchanged.
- **Fail-closed validated twice, on purpose.** `score()` resolves and validates
  the provider *before* the preflight/capture (so an unknown provider is an
  `env_error` at run start, not mid-loop), and `capture_app` independently guards
  its own lookup (so any direct caller also fails closed). The reviewer noted the
  AC4 test is therefore double-guarded — it proves fail-closed but does not
  *isolate* the "before preflight" ordering; kept as-is (feature-bearing, and the
  ordering is asserted by reading `score()`), classified honestly rather than
  padded with a brittle ordering-only probe.
- **Preflight gated to web.** The node/Playwright `preflight_capture` is the web
  provider's precheck, so it runs only when `provider == "web"`. A future non-web
  provider brings its own environment and is unaffected.
- **Fake-scores arm leaves `provider = None`** and skips transport validation —
  consistent with AC4 (no capture runs) and AC5 (records `capture_provider: null`).
  An unknown transport combined with `SERVO_DESIGN_EVAL_FAKE_SCORES` is not
  flagged, by design: fake-scores is the offline/test hook, not a capture path.
- **`_ledger` gained a required keyword-only `provider`** (mirroring the existing
  required `fake_run`), so no caller can silently omit it and mis-record the
  provider. New top-level ledger field `capture_provider`; `capture.transport`
  deliberately kept out of `_EXTRA_HASH_FIELDS`, so `definition_hash` is unchanged
  (AC6).
- **AC6 tests are regression-guards, not feature-driven.** A `capture` key was
  *already* excluded from the hash (the hash covers a fixed field set), so those
  two tests stay green even without the selector. They pin the environmental-not-
  frozen property against a future regression; the DoD "red when removed" note
  scopes the claim to the five feature-bearing tests.
- **Beyond the letter of the ACs:** documented the `capture.transport` selector,
  the `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` override, and the `capture_provider`
  ledger field in `SKILL.md` (config-authoring step + "Provenance in the ledger"),
  disambiguating the three transport-ish names.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Root orientation; no surface it describes changed. |
| `docs/specs/README.md` | `deferred` | Status-board regen is post-DONE close-out; not run (spec not closed — 03–05 remain; and `workflow.py status-board` mis-rolls umbrella-spec frontmatter, a known `refinement-todo` bug). |
| `docs/product-vision.md` | `no-op` | No vision-level claim affected. |
| `docs/architecture.md` | `no-op` | Additive selector + one ledger field; no module boundary, contract, or artifact-path change. |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | None reference capture transport or the ledger shape. |
| `docs/inbox.md` | `no-op` | Nothing to hand off. |
| `docs/refinement-todo.md` | `no-op` | No decision deferred by this slice. |
| `docs/memory/**` | `no-op` | No durable cross-session fact beyond spec + code. |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR touched — ADR-0032 already Accepted and governs this seam. |
| `reviews/slice-02-{compliance,craft,reconciliation}.md` | `added` | Committed review traces — verdicts + findings (backfilled per PR #31). |
| `skills/design-eval/SKILL.md` | `updated` | Documented the `capture.transport` selector, the `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` override, and the `capture_provider` ledger field. |
