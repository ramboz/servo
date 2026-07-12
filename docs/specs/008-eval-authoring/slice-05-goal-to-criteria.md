---
status: DONE
dependencies: [008-01, 015-04, 006-05, adr-0027, adr-0001]
last_verified: 2026-07-12
---

## Slice 008-05 — goal-to-criteria

**Goal:** Expand a free-form **goal** into a *proposed* acceptance-criteria set,
each AC tagged `deterministic | judged | human-only` with a rationale; have a fresh
**independent-reviewer subagent** check the frame; let the human curate and approve;
then emit a spec-shaped AC artifact that re-enters the pipeline at `edd-suitability`
(015) → `spec-oracle classify` (006) → 008-01 triage. The opt-in front-end that
closes servo's goal-vs-spec impedance, gated so it cannot manufacture a false
criterion ([ADR-0027](../../decisions/adr-0027-goal-to-eval-assisted-authoring.md)).

### Acceptance criteria

- **AC1** `eval_authoring.py from-goal <goal>` expands a free-form goal into a
  proposed AC set; each AC carries a tag `deterministic | judged | human-only` and a
  one-line rationale.
- **AC2** A **fresh independent-reviewer subagent** (no access to the expansion
  conversation) reviews the proposal against the goal for **faithfulness**, **honest
  tagging**, **measurability**, and **gaps** — reliably on the *structural* forms
  (wording-obvious mis-tags, unmeasurable predicates, goal-restatement, surface-literal
  coverage gaps); faithfulness AND *implicit* coverage of intent are best-effort
  advisory reads only, since both are epistemic and the human's job (ADR-0027 Decision #2) — emitting advisory flags, not a
  rubber-stampable verdict. It reuses `jig:independent-review` when jig is co-installed (the ADR-0001
  filesystem-hint coupling), else a built-in eval-frame-review **prompt shipped with the `eval-authoring`
  skill and run in a fresh subagent** (not a new entry in servo's `runner`/`judge`
  agent roster — ADR-0003's loop roster is untouched; this mirrors the
  architect→`jig:architect` delegation posture). servo does not hard-depend on jig.
- **AC3** The proposal + reviewer flags are presented to the human, who edits /
  accepts / rejects / **adds** each AC (adding covers criteria the expansion
  omitted — the human is the backstop for coverage-of-intent). Only the curated set proceeds; **nothing is frozen
  without recorded human approval** (spec 008 goal 6; ADR-0005).
- **AC4** The curated AC set is emitted as a **minimal spec-shaped Markdown
  artifact** (frontmatter + a tagged `## Acceptance criteria` list) that
  `spec-oracle classify` (006) consumes **unchanged** via its existing spec-AC
  parser; `edd-suitability` (015) reads the same artifact for its criteria split
  (AC5), not a full verdict. No new format, no downstream contract change.
- **AC5** Running the criteria-classification half of `edd-suitability` (015) on the
  emitted artifact surfaces the **evaluable-vs-human-residual split** over the ACs,
  so the author learns early whether the goal is mostly evaluable vs mostly taste.
  The **full** `suitable | needs_evidence | unsuitable` verdict is explicitly
  deferred until the target's signals + reference set exist (post-008-03) — an eval-able AC with no reference set resolves to
  `needs_evidence` (ADR-0015), and the reference set is collected only later
  (008-03; cf. ADR-0018 on not expecting a verdict from an inputs-missing synthesis), so goal→eval does not claim the full verdict here.
- **AC6** Goal→eval is **opt-in**: an author with hand-written ACs skips `from-goal`
  and enters at 008-01. The review + curation stay in the authoring layer and never
  invoke `gate.py`/`oracle.sh` (ADR-0021 / ADR-0011 / ADR-0005 boundary).
- **AC7** Tests cover: expansion producing tagged ACs; a **structurally** mis-tagged
  taste-call (one whose own wording marks it policy/taste — e.g. "requires a senior
  editor's sign-off" tagged `deterministic`) **flagged by the reviewer**; a plausible-but-unfaithful criterion NOT
  assumed caught — instead the **human-curation gate** is asserted to block any AC
  from freezing without a recorded per-AC approval, and the human can **add** a
  criterion the expansion omitted; the built-in reviewer path
  exercised with jig absent; the emitted artifact feeding 006 (and 015's criteria
  split) unchanged.

> This is the net-new capability the surveyed prior art deliberately refused — made
> safe by the independent-review + human-curation gate it was missing.

### Deviation log (after reconciliation)

Original ACs preserved above.

- **`from-goal` + expansion/review via `claude -p`.** Both the goal→ACs expansion and
  the fresh independent-reviewer pass are separate one-shot `claude -p
  --output-format json` subprocesses (mirroring `score.py::_judge_cli` /
  `loop.py`), each with exhaustive fail-closed handling (not-found / timeout /
  non-zero / malformed / `is_error` → clean `EnvError` exit 2, **never a fabricated
  AC**). The reviewer is fed **only the goal text + the proposed AC list** (never the
  expansion's reasoning), enforcing ADR-0027 Decision #2's structural independence.
  Tests inject a PATH-shadowed mock `claude` (a per-call sequence via a counter file,
  the `loop.py` idiom) — no real model.
- **Reviewer sourcing (ADR-0001 filesystem hint).** `_jig_independent_review_skill_path()`
  probes `~/.claude/skills/independent-review/SKILL.md` (honoring `$HOME`); present →
  its text frames the reviewer prompt (`reviewer_source: jig`), absent → the shipped
  built-in `eval-frame-review.md` (`reviewer_source: built-in`). servo does not
  hard-depend on jig; both branches tested. The "reuse" is prompt-text reuse, not a
  jig subagent invocation, and adds no entry to servo's runner/judge roster
  (ADR-0003 untouched).
- **Emitted artifact + `extract_acs` round-trip (AC4).** `criteria.md` (frontmatter +
  a `## Proposed classification & reviewer flags` human table + a **plain** numbered
  `## Acceptance criteria` list) and `criteria.json` (machine contract) under
  `<spec-dir>/<goal-slug>/`. **AC4-wording deviation:** the AC says "a *tagged* `##
  Acceptance criteria` list," but the tags/rationale/flags are carried in the
  companion table, NOT inline in the AC list — because inline tags would leak into
  `oracle_plan.extract_acs`'s statement text and break the "consumed unchanged"
  round-trip, which is the load-bearing requirement (proven by
  `test_round_trips_through_extract_acs_unchanged`). The tag information is still in
  the artifact.
- **Human gate, no auto-approve (AC3), strengthened at review.** Every AC starts
  `approval_status: proposed`; nothing auto-progresses. `from-goal` now **refuses to
  overwrite** an existing curated `criteria.md`/`criteria.json` (raises
  `EnvError("criteria_exists")` *before* any model call) unless `--force` — closing a
  craft-review [blocker] where a re-run silently clobbered human curation. The
  explicit human-approval check `require_all_approved` is wired via a new
  **`criteria-check <criteria.md>`** subcommand (exit 0 all-approved / 1 not-yet / 2
  env-error); `criteria.md` instructs the human to run it before proceeding. The
  no-freeze-without-work guarantee remains **procedural** (ADR-0027 Decision #5): the
  human must curate `criteria.md` and hand-author the dataset, and 008-04's
  empty-dataset freeze-refusal blocks a free ride.
- **AC5 criteria-split, not a full verdict.** `criteria-split` subprocesses
  `oracle_plan.py classify` (the same mechanism `suitability.py::_classify` uses)
  and reports `n_evaluable` / `n_human_residual` — it never produces a
  `suitable|needs_evidence|unsuitable` verdict (deferred per ADR-0027 Decision #4 /
  ADR-0018, since the reference set doesn't exist yet). It is deliberately **not**
  gated on approval (the author needs the split to *inform* approval).
- **Boundary (AC6).** `from-goal`/review/curation never import or subprocess
  `gate.py`/`oracle.sh`; a `from-goal` run leaves an already-scaffolded target's
  `oracle.sh`/`.servo/install.json` byte-for-byte untouched (tested). Opt-in: a
  hand-written spec enters directly at 008-01 triage.

**Nits logged (non-blocking, from both review passes):**

- `_iso_now` duplicates `fidelity_eval.iso_now` (reachable in this module) — two
  timestamp helpers; cosmetic.
- `criteria.md` frontmatter renders `goal: {!r}` (Python repr), not guaranteed
  YAML-safe for goals with mixed quotes — harmless (nothing YAML-parses the
  frontmatter; `extract_acs` reads only the AC list).
- `criteria-split`'s `oracle_plan classify` subprocess has no `timeout` (a local
  deterministic classifier, no network) — inconsistent with the bounded `claude -p`
  call but low-risk.
- The two-file curation surface (`approval_status` in `criteria.json`, editable ACs
  in `criteria.md`) is intentional per ADR-0027 Decision #5, but is a coupling a
  future reader should understand.

### Reconciliation sweep

- **`docs/architecture.md`** — `no-op`. New authoring subcommands on the existing
  skill; no module-boundary/contract change (no `arch_review`). The reviewer pass is
  advisory, in the authoring layer, never an oracle gate (ADR-0021/0011/0005 boundary
  preserved — asserted by the never-touches-gate.py/oracle.sh test).
- **Load-bearing decision / ADR trigger** — `no-op` (new ADR). The slice *implements*
  ADR-0027 (already Accepted); no new load-bearing choice with rejected alternatives.
- **`.claude-plugin/install-contract.json`** — `deferred`. No SKILL.md yet; the new
  built-in `eval-frame-review.md` prompt is a skill asset that will be picked up when
  the skill surface + install-contract registration land at close-out.
- **`docs/refinement-todo.md`** — `no-op`. The logged nits are cheap in-skill
  follow-ups captured here, not open-ended debt.
- **Status board** — `deferred`. Regenerated after `DONE`.
