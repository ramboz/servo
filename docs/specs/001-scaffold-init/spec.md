---
status: DRAFT
dependencies: []
last_verified:
---

# Spec 001 — scaffold-init

> Probe a target project's signals, run a Q&A flow, and drop a tailored set of unattended-agent infrastructure (`oracle.sh` always; agent-loop / hook / race stubs when offered and accepted) into the target — with an install manifest the runtime skills (specs 002–005) can read back.

## Why this spec

Servo's whole value proposition is **per-project artifacts that reflect the project's actual signals**. A generic `oracle.sh` stub the dev has to rewrite is no better than the curriculum's existing examples. The scaffolder is the first piece of servo's surface that *can't* be replaced by docs — it has to read filesystem state and produce tailored output.

It is also the foundation every other servo spec presupposes:

- 002 `quality-gate` invokes the scaffolded `oracle.sh`
- 003 `agent-loop` refuses to run without `oracle.sh`
- 004 `oracle-hook` reads `.servo/install.json` to know what was installed
- 005 `variant-race` reuses signal-detection results to score across worktrees

So 001 is unblocking for the entire servo backlog.

## Out of scope (deferred to later specs)

- Runtime invocation of `oracle.sh` (→ 002)
- Loop driver implementation (→ 003)
- Hook installer implementation (→ 004)
- Race driver implementation (→ 005)
- Refactoring jig's `slice-land prepare` to emit servo pull-hints (→ jig-side spec)

## SPIDR decomposition

Mirrors jig's spec-001 structure (greenfield scaffold → content → signals → deferred → wizard) because the problem shape is identical: probe filesystem, copy templates, manifest the install, expose to the LLM via Q&A.

### Slice index

| Slice | Title | Goal |
|---|---|---|
| 001-01 | greenfield-scaffold | Helper that copies bare `oracle.sh` template + writes `.servo/install.json` into an empty target |
| 001-02 | template-content | Real `oracle.sh.template` content: weighted composite, threshold, `# SEED:` annotation convention |
| 001-03 | signal-detection | Probe target for tests / lint / CI / language; tailor generated `oracle.sh` to detected components |
| 001-04 | deferred-decisions | Emit a `refinement-todo`-style record of what couldn't be inferred (weight tuning, custom signals) |
| 001-05 | qa-wizard | `SKILL.md` Q&A flow that asks user about scope before invoking helper |

Five slices, sized to match jig-001's cadence.

---

## Slice 001-01 — greenfield-scaffold

**Goal:** A `scaffold.py` helper that, invoked against an empty target directory, copies a placeholder `oracle.sh` from `${CLAUDE_PLUGIN_ROOT}/templates/` to `<target>/oracle.sh`, makes it executable, and writes `<target>/.servo/install.json` recording what landed. End-to-end value: an empty repo gains a runnable (if minimal) oracle in one command.

**DoR:**
- ✅ Plugin shell exists (`.claude-plugin/`, `templates/`, `skills/`)
- ✅ Target dir exists and is a git repo (servo's own dogfood case)
- ✅ Architecture decision recorded: scaffolder is a Python helper invoked by SKILL.md (mirrors jig)

**Acceptance Criteria:**

1. **Empty-target install succeeds.** `python3 skills/scaffold-init/scaffold.py <empty-dir>` exits 0; `<empty-dir>/oracle.sh` exists and is executable (`-rwxr-xr-x`); `<empty-dir>/.servo/install.json` exists and parses as JSON with keys `servo_version`, `timestamp`, `installed_tier="tier-0"`, `signals` (empty object at this slice), `components` (empty list).
2. **Refusal on existing oracle.** Re-running against the same dir exits non-zero with a message naming `oracle.sh` already present; nothing on disk changes.
3. **Force overwrites.** `--force` against the same dir overwrites `oracle.sh` and rewrites `.servo/install.json` with a new timestamp.
4. **Refusal on missing target.** Invoking against a nonexistent path exits non-zero with a clear error; nothing on disk changes.
5. **Helper is dependency-free.** `scaffold.py` runs on system Python 3.10+ with no `pip install` step.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Helper test coverage: at least one fixture per AC under `skills/scaffold-init/test_scaffold.py`.
- [ ] Reviewed by `reviewer` subagent (jig's, or servo's own once it ships one). Reviewer prompt built by jig's `review.py` if available, else hand-rolled.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred during implementation.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` status board updated.
- [ ] `README.md` skills table row for `scaffold-init` flipped from DRAFT to IN PROGRESS (or DONE if final slice).

**Anti-horizontal-phasing check:** After this slice, a user can run servo's scaffolder against an empty repo and get a working `oracle.sh` (even if minimal) and a manifest the next spec can read. That is end-to-end value, not intermediate state.

**Spike-shape note:** Servo has no prior Spike 0. Treat 001-01 as **spike-shaped** — its purpose is partly to validate that the weighted-composite-oracle approach holds up in practice. If implementation reveals a structural problem (e.g., bash composition doesn't compose cleanly across heterogeneous signals, or the manifest schema needs to encode more than expected), pause and re-plan slices 001-02 through 001-05 before proceeding. A re-plan here is cheaper than carrying a wrong shape through four more slices.

### Deviation log (after reconciliation)

_TODO: populated during reconciliation._

---

## Slice 001-02 — template-content

**Goal:** Replace the placeholder `oracle.sh` with a real weighted-composite template: configurable component blocks, threshold gate, normalized exit codes (0 pass / 1 below-threshold / 2 env error), and a documented `# SEED:` annotation convention for project-specific signal functions. End-to-end value: the generated `oracle.sh` is actually useful (composes signals into a score), not just a stub.

**DoR:**
- ✅ Slice 001-01 DONE
- ✅ Exit-code convention agreed (0 / 1 / 2)
- ✅ Weight schema agreed (component name → weight float; threshold float)

**Acceptance Criteria:**

1. **Scaffolded `oracle.sh` runs.** Against a target with at least one detected component, the scaffolded script exits 0, 1, or 2 (never another code) and prints a single-line composite-score summary.
2. **Threshold gate works.** With `THRESHOLD=1.0` and one component scoring 0.0, the script exits 1. With `THRESHOLD=0.0` and the same input, it exits 0.
3. **Env error is distinguishable from below-threshold.** If a component's command isn't installed, the script exits 2 (not 1) and prints which component is missing.
4. **`# SEED:` blocks are clearly demarcated.** The template includes at least one `# SEED:start <name>` / `# SEED:end <name>` block with a placeholder shell function, and the README section explains how a project adds their own.
5. **No bashisms-that-bite.** Script passes `shellcheck` with severity ≥ warning silent.

**DoD:** _(same shape as 001-01)_

### Close-out (post-DONE)

- [ ] Architecture doc's "open question" about weighting heuristic resolved (or moved to ADR).

**Anti-horizontal-phasing check:** After this slice, the generated oracle is something a project could actually adopt — not a phase that needs slice 003 to be useful.

### Deviation log (after reconciliation)

_TODO_

---

## Slice 001-03 — signal-detection

**Goal:** Helper sub-routine that probes the target for tests / lint / CI / language signals and *tailors* the generated `oracle.sh` to include only components the project actually has. Output also lands in `.servo/install.json` under `signals` and `components`. End-to-end value: a Python project with pytest but no lint gets an `oracle.sh` that scores pytest only, instead of failing on a missing `eslint` command.

**DoR:**
- ✅ Slice 001-02 DONE
- ✅ Decision: reuse jig's `tdd.py detect` via subprocess when jig is present (per ADR-TBD)
- ✅ Fallback detector spec'd (built-in minimal matcher for pytest/vitest/jest/cargo/go)

**Acceptance Criteria:**

1. **Pytest-only project gets pytest-only oracle.** Against a target with `pyproject.toml` containing `[tool.pytest.ini_options]` and no lint config, the generated `oracle.sh` includes a pytest block and no eslint/ruff blocks.
2. **Mixed project gets multiple components.** Against a target with `package.json` (vitest) + `.eslintrc.json`, the generated script includes both blocks.
3. **No-signal project gets a comment-only oracle.** Against a target with no detectable signals, the generated script is still valid bash, exits 2 with "no signals detected — populate `# SEED:` blocks manually", and `.servo/install.json` has `components: []`.
4. **Jig-fallback path works.** With jig absent (`${CLAUDE_PLUGIN_ROOT}/jig/skills/tdd-loop/tdd.py` missing), the built-in detector still classifies the four primary test frameworks correctly.
5. **Detection results are inspectable.** `scaffold.py detect <target>` (subcommand) prints the JSON audit *without* writing anything to disk.

**DoD:** _(same shape)_

### Close-out (post-DONE)

- [ ] ADR-0001 recorded for "reuse jig's detector when present" (or whatever the final decision was).
- [ ] `docs/architecture.md` "Signal detection" section status updated.

**Anti-horizontal-phasing check:** After this slice, a real project's first run produces a tailored oracle that matches what's actually in the repo — the headline servo promise.

### Deviation log (after reconciliation)

_TODO_

---

## Slice 001-04 — deferred-decisions

**Goal:** When the scaffolder can't infer a tailoring decision (weights when multiple signals are present, threshold tuning, signals it detected but couldn't classify, project-specific custom signals), it records the open question in `<target>/.servo/refinement-todo.md` with a resolution trigger — mirroring jig's deferred-decisions slice. End-to-end value: the dev gets an explicit list of "things you need to tune," not silent defaults that pass review.

**DoR:**
- ✅ Slice 001-03 DONE
- ✅ Decision categories agreed: weights, threshold, ambiguous signals, custom signals
- ✅ Refinement-todo format mirrors jig's (heading per decision, "Deferred:" reason, "Resolution trigger:" line)

**Acceptance Criteria:**

1. **Multi-signal install creates a weight-tuning todo.** When ≥2 components are detected, `<target>/.servo/refinement-todo.md` contains a `Weights` decision with "Deferred: equal weights applied — tune to reflect project priorities" and a resolution trigger.
2. **Threshold default is flagged.** Every install creates a `Threshold` decision with the chosen default and a resolution trigger ("first time oracle gate misfires").
3. **Ambiguous signals are listed.** A project with both vitest and jest configs gets an `Ambiguous test runner` decision with both names listed.
4. **Refinement-todo is idempotent.** Re-running with `--force` doesn't duplicate decisions; it rewrites the file from scratch.
5. **No spurious decisions.** A perfectly-tailorable install (one component, no ambiguity) produces a refinement-todo with only the unavoidable `Threshold` decision.

**DoD:** _(same shape)_

**Anti-horizontal-phasing check:** After this slice, every install lands with an explicit `refinement-todo.md` the dev can scan in 30 seconds. The next supervised session can resolve the items via jig's normal refinement-todo flow.

### Deviation log (after reconciliation)

_TODO_

---

## Slice 001-05 — qa-wizard

**Goal:** `skills/scaffold-init/SKILL.md` exposes the helper to the LLM via a Q&A wizard mirroring jig's scaffold-init flow: each question skippable, "skip every question" is the legitimate pure-inference path, never invent answers. End-to-end value: a user typing "set up servo on this project" gets a coherent question flow that fills in flags before the helper runs.

**DoR:**
- ✅ Slice 001-04 DONE
- ✅ Q&A questions enumerated (see below)
- ✅ Anti-greediness test pattern decided (mirror jig's `pr-review` `DescriptionBoundsTests`)

**Acceptance Criteria:**

1. **SKILL.md trigger phrases.** SKILL.md description fires on "set up servo", "scaffold oracle for this project", "install agent loop infrastructure", and similar; does *not* fire on bare "oracle" or "score this code".
2. **Five Q&A questions documented.**
   1. Project type — service / library / plugin / unsure → flag-mapped to component bias
   2. Tier offered — Tier 0 only / Tier 0 + 1 / all three → maps to which templates ship
   3. Loop guardrails — defaults / custom → if custom, ask iteration cap + cost ceiling
   4. Hook installation — yes (Tier 2 only) / no / skip → installs `oracle-hook` registration
   5. Existing servo install — proceed / abort → if `.servo/install.json` present
3. **Each question independently skippable.** Skipping any question omits the corresponding flag; helper falls back to filesystem inference.
4. **Skipping all = pure inference.** Equivalent to invoking `scaffold.py <target>` with no flags.
5. **Refusal on already-scaffolded target without `--force`.** SKILL.md surfaces the helper's refusal message to the user verbatim; doesn't silently retry.

**DoD:** _(same shape)_

### Close-out (post-DONE)

- [ ] SKILL.md anti-greediness tests pass (`pytest skills/scaffold-init/test_skill_surface.py`).
- [ ] `README.md` skills table row for `scaffold-init` flipped to DONE.
- [ ] `docs/specs/README.md` status board: spec 001 → DONE.

**Anti-horizontal-phasing check:** After this slice, the user-facing surface is real — typing the trigger phrase produces a tailored install in one Q&A pass. This is the slice that closes the spec.

### Deviation log (after reconciliation)

_TODO_

---

## Spec-level Definition of Done

- [ ] All five slices DONE.
- [ ] End-to-end dogfood: scaffold servo's own repo (yes, recursively — `python3 skills/scaffold-init/scaffold.py .`). Verify `oracle.sh` lands, scores servo's pytest tests, exits 0.
- [ ] [README.md](../../../README.md) skills table: `scaffold-init` row reads `DONE`.
- [ ] `docs/architecture.md` "Open questions" section reduced to genuinely-open items only.
- [ ] At least one ADR recorded (likely the jig-detector-reuse decision from 001-03).
- [ ] [docs/specs/README.md](../README.md) status board reflects DONE.

## Critical files (when implementation starts)

In jig (reference patterns):
- `skills/scaffold-init/scaffold.py` — wizard helper shape
- `skills/scaffold-init/SKILL.md` — Q&A surface pattern
- `skills/_common/parsing.py` — shared utilities pattern
- `skills/tdd-loop/tdd.py` — `detect` subcommand pattern (reused via subprocess in 001-03)
- `skills/pr-review/test_skill_surface.py` — anti-greediness test pattern (mirrored in 001-05)
- `templates/CLAUDE.md.template` + `templates/docs/specs/slice-template.md` — template-content slice shape

In this repo:
- `templates/oracle.sh.template` — new in 001-02
- `skills/scaffold-init/scaffold.py` — new in 001-01
- `skills/scaffold-init/SKILL.md` — new in 001-05
- `skills/scaffold-init/test_scaffold.py` — new in 001-01, extended each slice
