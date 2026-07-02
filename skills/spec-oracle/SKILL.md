---
name: servo:spec-oracle
description: |
  Compile a spec or slice into a reviewable, project-owned **evidence
  overlay**: map each acceptance criterion to a deterministic check family,
  write a `plan.md` + `checks.json` under `.servo/spec-oracles/<id>/`, compile
  the checks into an installable `oracle.sh` component, and freeze it behind an
  explicit approval so an unattended loop can optimize against the spec's
  promises instead of a hand-waved single judge.

  Fire this skill when the user wants to:

    - "generate an oracle for this spec" / "spec oracle for <spec>"
    - "turn this spec/slice into checks" / "compile acceptance criteria into checks"
    - "evaluate / specify an oracle for a spec" / "what would servo judge for this spec?"
    - "plan the evidence for <spec>" / "install the spec overlay" / "approve the spec oracle"

  Do NOT fire on:

    - "run the oracle" / "score this code" / "what's the oracle score?" —
      that's `/servo:quality-gate`. This skill *builds and installs* the
      overlay; quality-gate *runs* it.
    - "iterate on this" / "run an agent loop" / "let claude fix it" — that's
      `/servo:agent-loop`. This skill produces the target the loop optimizes
      against; it does not iterate.
    - "set up servo" / "scaffold the oracle" / "install servo" — that's
      `/servo:scaffold-init`, which produces the baseline `oracle.sh` this
      overlay composes onto.

  When in doubt, ask which servo skill the user means rather than invent a
  trigger match.
---

# /servo:spec-oracle

Compile a spec/slice into a **spec-specific evidence oracle**: acceptance-criteria
mapping, deterministic checks, negative controls, an installable oracle component,
and an evidence ledger — so `/servo:agent-loop` can optimize against the spec
without pretending one generic LLM judge understands every product promise.

The helpers live at `${CLAUDE_PLUGIN_ROOT}/skills/spec-oracle/`:

| Helper | Role | Spec |
|---|---|---|
| `oracle_plan.py` | Read a spec/slice → `plan.md` + `checks.json` (AC → check-family map) | 006-01 |
| `checks.py` | Stdlib check engine: run a `checks.json` → JSONL evidence + composite score | 006-02 |
| `oracle_overlay.py` | Compile a checked plan into an installable `oracle.sh` component | 006-03 |
| `oracle_overlay.py approve` | Freeze the overlay (negative controls + hashes) before unattended use | 006-04 |

## When to use this skill

Use when the user wants to **turn a spec into a trustworthy scoring target**.
Scaffolding the baseline oracle is `/servo:scaffold-init`; *running* any oracle is
`/servo:quality-gate`; *iterating* against it is `/servo:agent-loop`. This skill
is the compiler in between: spec → reviewable plan → installed, frozen overlay.

## Q&A before planning

Before generating anything, confirm:

1. **Target path** — the repo the overlay installs into (where `oracle.sh` lives).
2. **Spec / slice path** — the Markdown spec or slice file whose Acceptance
   Criteria become checks.
3. **Baseline commands** — the existing test/lint/build commands the overlay
   should reuse for `command`-family checks (so it composes with, not replaces,
   the baseline oracle).
4. **Stop point** — whether to **stop after plan generation** (the user reviews
   `plan.md` and elaborates checks by hand) or **proceed to install an approved
   overlay**. Installation and approval are separate, explicit steps — see below.

## Workflow

```bash
# 1. Plan — read the spec, classify ACs, write a reviewable plan. Read-only over
#    the target except the spec-oracle dir.
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-oracle/oracle_plan.py" <target> <spec-path>
#    → <target>/.servo/spec-oracles/<spec-id>/{plan.md,checks.json}

# 2. Review plan.md with the user. Deterministic checks are listed; residual
#    judgment (taste / positioning / "good enough") is surfaced explicitly with
#    a reason and a suggested human-review path. Elaborate executable fields
#    (command, path, expected, ...) into checks.json as needed.

# 3. Install the overlay as an ordinary oracle.sh component (does not approve).
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-oracle/oracle_overlay.py" install <target> <spec-id>

# 4. Approve — ONLY on explicit user instruction. Runs each check's negative
#    control where one is defined (proving it can fail), records source +
#    artifact hashes, and flips approval_status to approved.
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-oracle/oracle_overlay.py" approve <target> <spec-id>

# 5. Run it — the overlay is now a normal component; score it with the gate or
#    let the loop optimize against it.
python3 "${CLAUDE_PLUGIN_ROOT}/skills/quality-gate/gate.py" <target> --json

# Remove the component without deleting the plan/check artifacts:
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-oracle/oracle_overlay.py" uninstall <target> <spec-id>
```

## No silent approval

**This skill never marks an overlay `approved` on its own.** Approval is a
deliberate, separate step (`oracle_overlay.py approve`) that requires an explicit
user instruction or a reviewed approval artifact. Until approved, the installed
component runs with `--enforce-freeze` and **refuses to score** (`rc=2`,
`spec_oracle_unapproved`), so `/servo:agent-loop` cannot consume a draft overlay.
Approval is also where falsifiability is proven: a check whose negative control
does not fail blocks approval. Generating or installing a plan is safe and
reversible; approving it is the trust boundary — treat it like one.

## Check families

Each AC is classified into one family (or surfaced as residual judgment):

`command` · `file_presence` · `text_invariant` · `json_contract` ·
`archive_inventory` · `markdown_links` · `generated_artifact_command` ·
`runtime_reference_scan` · `residual_judgment` (explicitly not deterministic in
v1 — carries a reason + suggested review).

## Worked examples

Two committed dogfood fixtures under `examples/`, shaped like jig's
`046-scaffold-artifact-fidelity` and `047-install-contract-verification`. Running
`oracle_plan.py classify` against them:

**`examples/046-scaffold-fidelity.md` — scaffold/doc fidelity** (3 deterministic, 1 residual):

| AC | Statement (abridged) | Family |
|---|---|---|
| AC-046-01-1 | stocktake command works from the scaffold target (tempdir) | `generated_artifact_command` |
| AC-046-01-2 | local Markdown links in generated docs resolve | `markdown_links` |
| AC-046-01-3 | onboarding prose reads well / appropriately worded | `residual_judgment` (taste) |
| AC-046-01-4 | generated manifest contains the version string | `text_invariant` |

**`examples/047-install-contract.md` — install-contract validator** (4 deterministic, 0 residual):

| AC | Statement (abridged) | Family |
|---|---|---|
| AC-047-01-1 | `install-contract.json` is valid JSON with required key `schema_version` | `json_contract` |
| AC-047-01-2 | release zip contains required entries, excludes dev-only files | `archive_inventory` |
| AC-047-01-3 | verifier script present + executable bit set | `file_presence` |
| AC-047-01-4 | verifier command runs and exits 0 | `command` |

Validator / doc / install-contract specs land mostly in deterministic families —
exactly the spec shapes servo dogfoods first. Product-taste ACs ("reads well")
stay visible as residual judgment instead of being auto-passed.

## Freeze & approval semantics

The installed component runs `checks.py --enforce-freeze` and refuses (`rc=2`)
unless the overlay is approved and unmodified. The distinct refusal `reason`s:

| `reason` | Meaning |
|---|---|
| `spec_oracle_unapproved` | `approval_status` is not `approved` (draft) |
| `spec_oracle_stale` | `approval_status` is explicitly marked `stale` — re-plan |
| `spec_oracle_artifact_modified` | generated `checks.py` / `oracle.sh.fragment` was edited |
| `spec_oracle_plan_modified` | the approved checks in `checks.json` were relaxed |

These are tripwires against honest drift; a frozen overlay must be re-planned and
re-approved (not hand-edited) to change. See `docs/architecture.md`
("Spec-oracle freeze & approval") for the full threat model.
