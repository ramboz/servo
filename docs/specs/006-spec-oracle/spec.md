---
status: IN_PROGRESS
dependencies: [001, 002, 003]
last_verified: 2026-06-09
---

# Spec 006 — spec-oracle

> Compile a spec or slice into a **spec-specific evidence oracle**:
> acceptance-criteria mapping, deterministic checks, negative controls,
> an installable oracle component, and an evidence ledger that lets
> `/servo:agent-loop` optimize against the spec without pretending one
> generic LLM judge can understand every product promise.

## Why this spec

Specs 001–003 prove the closed-loop substrate:

- 001 scaffolds a project-owned `oracle.sh`.
- 002 makes that oracle uniformly callable through `gate.py`.
- 003 runs a guarded unattended loop against the oracle.

That is enough for projects whose existing tests already encode the
desired outcome. It is not enough for spec-driven projects where each
feature has its own acceptance criteria. In those projects, the hard
part is not "run the loop"; it is "make the loop's target trustworthy."

The pattern is emerging from jig dogfood candidates:

- Spec 039 needed checks for a removed dead file, a `.gitignore` guard,
  and no live runtime references.
- Spec 046 needs temp-scaffold command/link checks and version
  provenance checks.
- Spec 047 needs plugin/scaffold install-contract validators.

Those checks are spec-specific, but their shape is reusable. Servo
should not ship one generic judge that hand-waves over every spec. It
should ship a **spec-to-evidence compiler** that turns acceptance
criteria into a reviewable, executable overlay on top of the repo's
baseline oracle.

This spec closes the gap between "the repo still passes tests" and "the
current spec's promises are proven enough for unattended iteration."

## Goals

1. **Plan from acceptance criteria.** Given a target repo and a
   spec/slice path, extract acceptance criteria and classify each one
   into a check family: command/test, file/content invariant, generated
   artifact smoke check, schema/manifest contract, doc/link check,
   package/archive inventory, or residual judgment.
2. **Produce a traceable evidence contract.** Write a reviewable plan
   that maps `AC -> check -> evidence -> failure message -> negative
   control`. Uncovered judgment stays visible instead of being hidden
   behind a passing baseline suite.
3. **Compile deterministic checks.** Generate stdlib-only check code
   or shell fragments for the common families above, plus a small JSON
   contract the runtime can consume.
4. **Prevent self-grading with extra steps.** The loop must not silently
   invent its own judge and then satisfy it. Generated oracles are
   frozen before unattended implementation, carry hashes, and can be
   changed only through an explicit re-plan/review step.
5. **Install as a project-owned oracle overlay.** The generated
   spec-oracle becomes a component in `oracle.sh` or a called helper
   that `oracle.sh` scores. It composes with the repo baseline instead
   of replacing it.
6. **Record evidence per run.** Each check emits machine-readable
   evidence so loop summaries, future races, and human review can see
   which ACs passed, failed, or remained judgment-only.
7. **Dogfood on jig-shaped specs.** The first useful examples should be
   validator/docs/install-contract specs like jig 046/047, because they
   are rich enough to exercise the pattern without requiring product
   taste judgment.

## Non-goals

- **No universal semantic judge.** Servo will not claim one prompt can
  decide whether every arbitrary spec is complete.
- **No replacement for human policy/taste decisions.** ADR choices,
  product positioning, copy tone, and "is this good enough?" judgments
  are surfaced as residual judgment, not auto-passed.
- **No automatic mutation of source specs.** The planner reads specs and
  writes `.servo/spec-oracles/...` artifacts. It does not rewrite the
  source spec's ACs or DoD.
- **No CI productization.** Generated checks may be CI-friendly, but
  this spec does not add GitHub Actions or other CI wiring.
- **No deep natural-language proof.** The first version extracts
  Markdown acceptance criteria by structure and asks the model only for
  classification/candidate generation. Deterministic checks remain the
  source of truth.
- **No hidden dependency on jig.** Jig specs are dogfood fixtures, not a
  hard dependency. The check families must work for non-jig projects.

## Core model

Servo layers evidence instead of trusting a single score:

1. **Repo baseline oracle** — existing `oracle.sh` components from
   scaffold-init: tests, lint, CI, language-specific checks.
2. **Spec overlay oracle** — generated for one spec or slice from its
   acceptance criteria.
3. **Residual judge notes** — ACs that cannot be safely made
   deterministic, plus the reason and suggested human review path.
4. **Evidence ledger** — per-check structured output that shows what was
   actually observed.

The composite score remains the same servo shape: deterministic
components return scores in `[0.0, 1.0]`; env errors return 2; `gate.py`
and `loop.py` do not need a new exit-code contract.

## Evidence contract

The generated plan lives under:

```
<target>/.servo/spec-oracles/<spec-id>/
├── plan.md
├── checks.json
├── oracle.sh.fragment
├── checks.py
└── ledger.jsonl          # produced by check runs, append-only
```

`checks.json` is the machine contract:

```json
{
  "schema_version": 1,
  "spec_id": "046-scaffold-artifact-fidelity",
  "source_spec_path": "docs/specs/046-scaffold-artifact-fidelity/spec.md",
  "source_hash": "sha256:...",
  "planner_version": "0.1.0",
  "baseline_commands": ["python3 scripts/run_tests.py"],
  "checks": [
    {
      "id": "AC-046-01-1",
      "statement": "Stocktake command works from the scaffold target.",
      "family": "generated_artifact_command",
      "status": "generated",
      "command": "python3 .claude/skills/jig-scaffold-init/stocktake.py .",
      "working_directory": "<temp_scaffold>",
      "expected": {"exit_code": 0},
      "failure_message": "stocktake command failed from scaffold target",
      "negative_control": "remove .claude/skills/jig-scaffold-init/stocktake.py"
    }
  ],
  "residual_judgment": [
    {
      "id": "AC-XYZ",
      "reason": "copy tone / product positioning",
      "suggested_review": "human or craft-review pass"
    }
  ]
}
```

The exact schema can evolve before implementation, but the principles are
load-bearing:

- every generated check names the AC it covers;
- every check has an actionable failure message;
- uncovered ACs are explicit;
- the source spec hash is recorded;
- a re-plan is required when the source spec hash changes.

## Check families

First-version deterministic primitives:

| Family | Examples |
|---|---|
| `command` | Run an existing test/lint/build command and assert exit code. |
| `file_presence` | Path exists, path absent, executable bit present. |
| `text_invariant` | Text contains / does not contain string or regex. |
| `json_contract` | JSON file parses; required key exists; value equals expected. |
| `archive_inventory` | Zip/tar contains required paths and excludes forbidden paths. |
| `markdown_links` | Local Markdown links resolve from generated docs. |
| `generated_artifact_command` | Build/scaffold into tempdir, then run a command from that generated tree. |
| `runtime_reference_scan` | Scan live roots for forbidden stale references, excluding historical docs. |
| `residual_judgment` | Explicitly not deterministic in v1. |

These primitives are intentionally boring. Most large projects already
have feature-specific acceptance checks in this shape; servo makes them
cheap to generate and attach to a loop.

## Guardrails

- **Frozen before loop.** `/servo:agent-loop` consumes a generated
  spec-oracle only after it is marked `approved` in `checks.json`.
  A runner iteration must not edit approved oracle artifacts as part of
  satisfying the spec.
- **Hash mismatch refuses.** If the source spec hash changes, the
  spec-oracle exits 2 with `reason=spec_oracle_stale` until re-planned.
- **Negative controls required when feasible.** A generated check should
  include a simple "known bad" mutation or fixture proving that the
  check can fail. The first version can mark `negative_control:
  not_applicable` for command checks that already invoke an existing
  suite, but new generated invariants need controls.
- **Residual judgment blocks auto-complete by default.** A spec-oracle
  with unresolved residual-judgment ACs may still help iteration, but
  it should not report a perfect spec-overlay score unless the user
  explicitly allows judgment-only ACs to be excluded from the composite.
- **Project-owned artifacts.** Generated checks live in the target under
  `.servo/spec-oracles/`; users can inspect and edit them through an
  explicit re-plan flow. Servo does not hide the judge in plugin state.

## SPIDR analysis

| Technique | Question | Decision |
|---|---|---|
| **S — Spike** | Can a useful planner classify real spec ACs into reusable check families? | **Yes, but spike-shaped first slice.** 006-01 validates against existing jig specs 039/046/047 without installing anything. |
| **P — Path** | Generate checks first or integrate with loop first? | **Plan → compile → freeze → integrate.** The loop should consume only reviewed/frozen checks. |
| **I — Interface** | What is the stable boundary? | `checks.json` + `oracle.sh.fragment` + ledger JSONL under `.servo/spec-oracles/<spec-id>/`. |
| **D — Data** | What data makes this safe? | AC mapping, source hash, check family, command/expectation, failure message, negative control, residual judgment. |
| **R — Rules** | What prevents self-grading? | Approved/frozen spec-oracle artifacts, hash checks, negative controls, residual-judgment visibility. |

## Slices

- [006-01 — evidence-plan](slice-01-evidence-plan.md)
- [006-02 — check-library](slice-02-check-library.md)
- [006-03 — oracle-overlay](slice-03-oracle-overlay.md)
- [006-04 — freeze-and-controls](slice-04-freeze-and-controls.md)
- [006-05 — skill-and-dogfood](slice-05-skill-and-dogfood.md)


## Open questions

- Should approval be a field in `checks.json`, a separate
  `approval.json`, or a signed/hash-pinned line in `plan.md`?
- Should residual-judgment ACs contribute `0.0`, be excluded from the
  denominator, or force env error until explicitly waived?
- Should generated overlays be one component per spec or one component
  per slice? Lean: per slice for active iteration, with spec-level
  rollup later if needed.
- Should `agent-loop` gain a first-class `--spec-oracle <id>` flag, or
  is installing the overlay into `oracle.sh` sufficient? Lean: install
  into `oracle.sh` first; add a flag only if users need concurrent
  overlays.
- What is the smallest review artifact that counts as explicit approval
  for unattended use?

## References

- [Spec 001 — scaffold-init](../001-scaffold-init/spec.md)
- [Spec 002 — quality-gate](../002-quality-gate/spec.md)
- [Spec 003 — agent-loop](../003-agent-loop/spec.md)
- [ADR-0001 — filesystem-only coupling](../../decisions/adr-0001-reuse-jig-test-detector.md)
- [ADR-0002 — gate caller contract](../../decisions/adr-0002-gate-caller-contract.md)
- [ADR-0003 — fresh subagent roster](../../decisions/adr-0003-fresh-subagent-roster.md)
- [ADR-0004 — session state file format](../../decisions/adr-0004-session-state-file-format.md)
