---
status: DONE
dependencies: []
last_verified: 2026-05-15
---

> **DONE 2026-05-15.** All five slices (001-01 through 001-05) implemented, reviewed, reconciled. Spec-level DoD passed including the servo-on-servo dogfood (exit 0, composite=1.0000).

# Spec 001 — scaffold-init

> Probe a target project's signals, run a Q&A flow, and drop a tailored set of unattended-agent infrastructure (`oracle.sh` always; agent-loop / hook / race stubs when offered and accepted) into the target — with an install manifest the runtime skills (specs 002–005) can read back.

## Why this spec

Servo's whole value proposition is **per-project artifacts that reflect the project's actual signals**. A generic `oracle.sh` stub the dev has to rewrite is no better than the docs-only examples that exist elsewhere. The scaffolder is the first piece of servo's surface that *can't* be replaced by docs — it has to read filesystem state and produce tailored output.

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

## Slices

- [001-01 — greenfield-scaffold](slice-01-greenfield-scaffold.md)
- [001-02 — template-content](slice-02-template-content.md)
- [001-03 — signal-detection](slice-03-signal-detection.md)
- [001-04 — deferred-decisions](slice-04-deferred-decisions.md)
- [001-05 — qa-wizard](slice-05-qa-wizard.md)


## Spec-level Definition of Done

- [x] All five slices DONE. _001-01 (greenfield-scaffold), 001-02 (template-content), 001-03 (signal-detection), 001-04 (deferred-decisions), 001-05 (qa-wizard) — each reviewed by jig:reviewer subagent (PASS / PASS-WITH-CAVEATS); 53/53 tests across `test_scaffold.py` + `test_skill_surface.py`._
- [x] End-to-end dogfood: scaffold servo's own repo (recursively — `python3 skills/scaffold-init/scaffold.py .`). Verify `oracle.sh` lands, scores servo's pytest tests, exits 0. _Verified 2026-05-15: scaffold detected pytest (servo's own `pyproject.toml` added during dogfood close-out), produced `oracle.sh` with `score_pytest`, manifest with `components: ["pytest"]`, refinement-todo with only `Threshold` (single-component case). With pytest on PATH (via venv), oracle ran composite=1.0000 threshold=0.5 → exit 0._
- [x] [README.md](../../../README.md) skills table: `scaffold-init` row reads `DONE`.
- [x] `docs/architecture.md` "Open questions" section reduced to genuinely-open items only. _Composite weighting heuristic resolved in 001-02; ADR-0001 promoted out of pending in 001-03. Remaining items (`.servo/install.json` checked-in vs ignored, scaffold-init vs jig-scaffolded interaction, agent-loop driver shell vs Python) are all genuinely-open future-spec items._
- [x] At least one ADR recorded. _[ADR-0001](../../decisions/adr-0001-reuse-jig-test-detector.md) Accepted in 001-03 — reuse jig's `tdd.py detect` when co-installed; fall back to built-in detectors otherwise._
- [x] [docs/specs/README.md](../README.md) status board reflects DONE.

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
