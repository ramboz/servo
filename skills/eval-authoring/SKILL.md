---
name: eval-authoring
description: >-
  Author a frozen, kind-agnostic **text-judged** eval component for a
  non-deterministic acceptance criterion — starting either from a spec-006
  `residual_judgment` AC or from a free-form goal with no spec at all. Guides
  an engineer through the hard part of EDD setup: triage (which residual ACs
  are actually eval-able), rubric-shaping, reference-set collection, and
  frozen n/δ/threshold/judge params, then freezes + installs a `score_<name>`
  component onto the shared ADR-0024 harness — the same mechanism
  design-eval/content-fidelity already use. A light advisory judge-audit
  reports whether the judge itself can be trusted. Use when the user wants
  to "author an eval for this AC," "turn a goal into acceptance criteria,"
  "shape a rubric / build a reference set for this criterion," "freeze and
  install this eval," or "can I trust this judge?" Do NOT use to run an
  eval (`quality-gate`/`agent-loop`), to classify a spec's ACs into
  deterministic check families (`spec-oracle`), to decide whether a spec is
  EDD-suitable (`edd-suitability`), or to author a design/content fidelity
  eval (the `design-eval` / `content-fidelity` presets already cover those
  modalities) — this skill is the generic surface for everything else that
  is text-judged.
---

# /servo:eval-authoring — generic text-judged eval authoring

Between "this AC is `residual_judgment`" (spec-oracle's classification) and "here
is a frozen component `gate.py` can score," a human does the genuinely hard part
of EDD with no help today unless the AC happens to be design or content fidelity.
This skill is that missing middle: it turns a fuzzy judgment call — or a
free-form goal with no acceptance criteria at all — into a rubric, a reference
set, frozen parameters, and an installed `score_<name>` oracle component, human-
approved at every stage
([ADR-0026](../../docs/decisions/adr-0026-generic-eval-authoring-surface.md),
[ADR-0027](../../docs/decisions/adr-0027-goal-to-eval-assisted-authoring.md)).

**Ownership.** servo owns the mechanism (the guided authoring flow, the shared
[ADR-0024](../../docs/decisions/adr-0024-extract-frozen-eval-harness.md) harness,
the freeze/install machinery); the human/project owns the policy (which ACs are
eval-able, the rubric wording, every case in the dataset, the frozen judge/n/δ/
threshold). This is **one guided servo skill**
([ADR-0019](../../docs/decisions/adr-0019-eval-authoring-servo-owned.md)) — jig
stays attest-only; it never authors rubric or scoring content. It is
kind-agnostic across **text-judged** ACs only (ADR-0026) — a non-text (visual/
audio) modality stays preset-only; `design-eval` and `content-fidelity` remain
the bespoke siblings this skill sits beside, not a replacement for either.

**This skill authors, freezes, and installs; it never runs.** `emit` freezes the
definition (the ADR-0005 clause-2 human-approval gate) and, with `--target`,
installs the resulting component into `oracle.sh` exactly as the two presets
self-install — `/servo:spec-oracle` has no "eval-family compile step" that does
this for you (an earlier spec draft implied one; it doesn't exist). Running the
installed component is `gate.py`'s job, via `/servo:quality-gate` or
`/servo:agent-loop`.

## Prerequisites

- A spec-006 evidence plan for the deterministic-vs-eval-able split: run
  `/servo:spec-oracle`'s plan step first so a `checks.json` exists at
  `<spec_dir>/oracle/<spec_id>/checks.json` — `triage` (and everything chained
  after it) reads that file.
- **Or**, with no spec yet, start from `from-goal` (below) to produce a
  spec-shaped `criteria.md`/`criteria.json` you then run `/servo:spec-oracle`'s
  plan step over, same as a hand-written spec.
- Python 3.9+ stdlib only (servo's ADR-0020 floor) — no third-party deps.
- A judge transport, needed only when a subcommand actually calls a model
  (`from-goal`'s expansion + review, or a live `score()` run once installed —
  `triage`/`rubric`/`dataset`/`params`/`emit`/`criteria-check`/`criteria-split`
  never call a model):
  - **`"api"`** (default) — the Anthropic Messages API; needs
    `ANTHROPIC_API_KEY` in the environment.
  - **`"cli"`** — a headless `claude -p` (subscription auth, no API key); needs
    the `claude` CLI on `PATH`, or point `SERVO_EVAL_AUTHORING_CLAUDE_BIN` at it
    (one env var covers both `from-goal`'s two prompt calls and the installed
    component's own judge calls).

## Core model

```
GOAL (free text, opt-in)                                   human-only ACs
  → from-goal          propose (tagged) ────────────────────→ (hand off,
        → independent review (structural sanity)               out of scope)
        → human curate + approve (criteria-check)
  → curated AC set (spec-shaped criteria.md, project-owned)
  → [/servo:spec-oracle plan]  → checks.json (deterministic families │ residual_judgment)
                                                              │
  → triage         eval-able ──────────────────────────────────┤   human-residual
  → rubric                                                    │   (stays waived)
  → dataset (reference set)                                   │
  → params + emit (freeze)                                    │
  → eval definition (human-approved, config.json)              │
  → emit --target  (install: splice score_<name> into oracle.sh)
  → [/servo:quality-gate | /servo:agent-loop runs it]
  → audit  (advisory judge-trust: auto vs confirmed-only)
```

Two overlapping "plan" inputs run through this pipeline: the spec-006
`checks.json` **evidence plan** (from `/servo:spec-oracle`), consumed by
`triage`/`rubric`/`dataset`/`params`/`emit`/`uninstall`; and the goal-to-criteria
`criteria.md`/`criteria.json` **pair** (from `from-goal`), consumed by
`criteria-check`/`criteria-split`. `from-goal`'s output is spec-shaped precisely
so it can also be handed to `/servo:spec-oracle`'s plan step and re-enter the
first pipeline at `triage`, unchanged.

## Flow

```bash
# 0. (Opt-in) No spec yet — expand a free-form goal into proposed, tagged ACs.
#    Runs two fresh one-shot `claude -p` calls (expansion, then an independent
#    reviewer with NO access to the expansion's own reasoning) and writes the
#    result under <spec-dir>/<goal-slug>/.
python3 "${CLAUDE_PLUGIN_ROOT}/skills/eval-authoring/eval_authoring.py" \
    from-goal "make the onboarding summary faithful to the source doc" \
    --spec-dir docs/specs/ [--force]
#    → <spec-dir>/<goal-slug>/{criteria.json,criteria.md}. Every AC starts
#    approval_status: "proposed" — never auto-approved. Refuses (exit 2) to
#    re-run over an already-curated goal directory unless --force is given
#    (a fresh non-deterministic expansion must never silently clobber curation
#    already recorded in criteria.md/criteria.json).

# Curate criteria.md by hand: edit / accept / reject / ADD any AC (there is no
# row to reject for something the expansion never proposed — adding is how you
# backstop coverage), then flip each AC's approval_status to "approved" in
# criteria.json.

# The human-curation gate: reports each AC's approval status; exit 0 only once
# every AC reads "approved" (exit 1 if not yet, exit 2 on an env/read error).
python3 ".../eval_authoring.py" criteria-check docs/specs/<goal-slug>/criteria.md

# Optional early signal: evaluable-vs-human-residual split ONLY (015's
# classify half) — NOT a full suitable|needs_evidence|unsuitable verdict (no
# reference set exists yet at this point, so a full verdict would be
# needs_evidence across the board — ADR-0018).
python3 ".../eval_authoring.py" criteria-split docs/specs/<goal-slug>/criteria.md

# 1. Once curated (or starting from a hand-written spec): plan it with
#    /servo:spec-oracle, then triage the residual_judgment bucket into
#    eval-able vs human-residual (never auto-promotes a taste/policy/ADR call).
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-oracle/oracle_plan.py" <target> <spec-or-criteria.md>
python3 ".../eval_authoring.py" triage <spec-dir>/oracle/<spec-id>/checks.json
#    → <spec-dir>/eval/<spec-id>/{triage.json,triage.md}

# 2. Shape a rubric for one eval-able AC (an editable starting archetype).
python3 ".../eval_authoring.py" rubric <plan> --ac <AC-id> \
    [--archetype single_dimension|multi_criteria|comparative]   # default: single_dimension
#    → <spec-dir>/eval/<spec-id>/<eval-name>/{config.json,rubric.md}

# 3. Scaffold/grow the reference set. First run seeds cases verbatim from the
#    spec's own "## Examples"/"## Edge cases" sections (or a labeled EDIT ME
#    placeholder per happy_path/edge_case/skip_case if neither exists); every
#    later run only re-validates — a human-grown dataset is never overwritten.
python3 ".../eval_authoring.py" dataset <plan> --ac <AC-id>
#    → prints a non-fatal advisory below the provisional 12-case floor; never
#    autofills toward it (no fabricated ground truth).

# 4. Set/confirm the frozen n/δ/threshold/judge — every flag left unset keeps
#    what `rubric` already seeded, so accepting every default is a bare call.
python3 ".../eval_authoring.py" params <plan> --ac <AC-id> \
    [--n N] [--delta D] [--threshold T] [--model M] \
    [--temperature X] [--max-tokens N] [--transport api|cli]
#    → prints a one-line plain-language trade-off note per knob.

# 5. Freeze (the human-approval gate) — and, with --target, install the
#    resulting score_<name> component. Never runs it (that's gate.py's job).
python3 ".../eval_authoring.py" emit <plan> --ac <AC-id> [--target <dir>] [--weight W]
#    → freezes <eval-name>/config.json (approval_status: "approved", pinned
#    hashes). With --target: splices score_<component> into <dir>/oracle.sh
#    and copies score.py + fidelity_eval.py + config.json into
#    <dir>/.servo/<component>/. Idempotent re-emit refreshes in place.

# Remove an installed component (frozen artifacts under .servo/<component>/
# are left untouched):
python3 ".../eval_authoring.py" uninstall <plan> --ac <AC-id> --target <dir>

# 6. Run it — not this skill's job:
python3 "${CLAUDE_PLUGIN_ROOT}/skills/quality-gate/gate.py" <target> --json
#    or `/servo:agent-loop`.

# 7. (Advisory, any time after at least one scoring run) Light judge-trust
#    audit: samples a mixed pass/fail set for human spot-checking, computes
#    fail-precision/pass-miss-rate/(above a 20-labeled-case floor) drift, and
#    recommends auto vs confirmed-only. Never touches the composite,
#    config.json, or oracle.sh.
python3 ".../eval_authoring.py" audit <spec-dir>/eval/<spec-id>/<eval-name> \
    [--labels <file>] [--scores <file>] [--sample-size N]
#    → appends a "kind": "judge_audit" record to that eval's ledger.jsonl.
```

## Files

| Path | Role |
|---|---|
| `<spec_dir>/<goal-slug>/{criteria.json,criteria.md}` | goal→eval proposal (008-05, opt-in) — the human-curation surface + the spec-shaped AC list `/servo:spec-oracle` reads unchanged |
| `<spec_dir>/eval/<spec_id>/{triage.json,triage.md}` | the eval-able vs human-residual classification of the plan's `residual_judgment` bucket |
| `<spec_dir>/eval/<spec_id>/<eval-name>/config.json` | the `fidelity_eval.py`-shaped eval definition: judge/samples/threshold/rubric/cases, plus (post-`emit`) `hashes`/`approved_content_hash`/`approval_status` |
| `<spec_dir>/eval/<spec_id>/<eval-name>/{rubric.md,dataset.md}` | human-reviewable renderings of the rubric and the case table |
| `<spec_dir>/eval/<spec_id>/<eval-name>/ledger.jsonl` | append-only scoring + judge-audit records (once installed and run/audited) |
| `<target>/.servo/<component>/{score.py,fidelity_eval.py,config.json}` | the installed, frozen runtime (post-`emit --target`); `<component>` = `component_name(spec_id, ac_id)`, namespaced so two specs' identically-slugged AC ids never collide |

All durable artifacts are project-owned and colocated with the spec
([ADR-0023](../../docs/decisions/adr-0023-colocate-durable-spec-oracle-artifacts.md)),
resolved from the plan/criteria file's own on-disk location — never CWD or
plugin/target state.

## Do NOT fire on

- "run this eval" / "score this code" / "what's the oracle composite?" —
  that's `/servo:quality-gate` (or `/servo:agent-loop`). This skill authors,
  freezes, and installs `score_<name>`; it never runs it.
- "classify this spec's ACs" / "map ACs to check families" / "generate a spec
  oracle" — that's `/servo:spec-oracle` (006), the deterministic classifier
  this skill's `triage` *consumes* (its `residual_judgment` bucket) but never
  re-implements.
- "is this spec suitable for EDD?" — that's `/servo:edd-suitability` (015),
  which issues the full `suitable | needs_evidence | unsuitable` verdict.
  `criteria-split` here only forwards 015's evaluable-vs-human-residual
  *classification* half over a freshly-expanded goal, deliberately not a full
  verdict (no reference set exists yet at that point — ADR-0018).
- "author a design-fidelity eval" / "author a content-fidelity eval" — those
  are the two bespoke presets (`design-eval` / `content-fidelity`); each
  already ships its own modality-specific capture + tuned judge. This skill
  is the generic surface for text-judged ACs outside those two shapes.
- "scaffold the oracle" / "install servo" — that's `/servo:scaffold-init`,
  which produces the baseline `oracle.sh` an emitted component splices into.

## Human is the sole gate

Nothing here freezes or runs on its own:

- `from-goal` never auto-approves an AC (every entry starts
  `approval_status: "proposed"`) and refuses to overwrite an already-curated
  `criteria.md`/`criteria.json` without `--force` — a fresh, non-deterministic
  expansion must never silently clobber recorded human curation.
- The independent-reviewer pass (jig's `independent-review` skill when
  co-installed, else the shipped `eval-frame-review.md`) is **advisory and
  structural only** — reliable on mis-tagging-by-wording, unmeasurable
  predicates, goal-restatement, and surface-literal coverage gaps; it does
  *not* reliably catch a plausible-but-unfaithful criterion or an *implicit*
  coverage gap. That residue is the human's job. servo never hard-depends on
  jig (ADR-0001/ADR-0027).
- `emit` is the one freeze point (ADR-0005 clause 2): it refuses an empty
  dataset, and any later edit to the rubric/dataset/model/n/δ/threshold
  invalidates the freeze — the installed component then refuses to score
  (`StaleError`) rather than silently scoring against a changed definition.
- The judge-audit (`audit`) is **advisory only** — it reports and recommends
  (`auto` vs `confirmed-only`); it never alters the composite,
  `config.json`, or `oracle.sh`. Auto-demoting an untrusted judge is
  explicitly deferred (see `docs/refinement-todo.md`).
- A malformed/unreachable judge, an unparseable reply, or a stale/unapproved
  definition all raise a clean `env_error`/`StaleError` (exit 2) — **never a
  silent `0.0`** (ADR-0005).

## Known limitation: candidate-gather is not yet built

**This is a named limitation, not a soft tip.** design-eval/content-fidelity
both ship a real "gather the candidate under test" step; this skill's
installed `score.py` does **not** yet. Its `_gather_candidate` seam is a
documented, deliberately-unbuilt placeholder — running the system under test
on a case's `input` to produce the text the judge scores is out of scope for
every slice shipped so far (spec 008's non-goal: "this skill authors; it does
not run"). Concretely: a **live** (no-fake-scores) `score()` call on an
installed component always raises `env_error` today, never a placeholder
score. Offline testing/dry-runs use the `SERVO_EVAL_AUTHORING_FAKE_SCORES`
(`{case_id: [sample, ...]}`) and `SERVO_EVAL_AUTHORING_FAKE_ACTUALS`
(`{case_id: {field: value}}`, for constraint-DSL cases) environment hooks to
exercise the composite without a real candidate. A real candidate-gather is
tracked as future work, not silently assumed.

## Authoring tips

- The shipped rubric defaults sample at `temperature: 0.0` (lower than
  content-fidelity's `0.6`) — the n-sample lower bound already absorbs the
  judge's residual stochasticity, so a low-temperature judge here trades a
  little sample spread for more consistent repeated judgments.
- The reference-set floor (12 cases) and the judge-audit thresholds
  (fail-precision ≥ 0.70, pass-miss-rate ≤ 0.20, a ≥20-labeled-case drift
  floor) are **provisional** — starting numbers borrowed from surveyed prior
  art, expected to be re-tuned once the first real eval runs end-to-end. They
  are advisories, never a reason to fabricate cases or labels to clear them.
- The string-constraint DSL (`<field> <op> <value>`, `op` in `==`/`>=`/`<=`)
  gates a case's judged lower bound to `0.0` the moment any hard constraint
  fails — a case that fails a stated requirement can never "mostly" pass on
  the strength of a good judged score alone.
- `category: "skip_case"` is excluded from scoring entirely (never judged,
  never weighted) — use it to record a scenario the eval deliberately does
  not score, not as a way to soften a failing case.
- Keep `n` × `|cases|` bounded — like the presets, it counts against the
  loop's cost ceiling once installed.
