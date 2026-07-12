---

name: edd-suitability
description: >-
  Decide whether an engineering spec is suitable for Evaluation-Driven Development before any unattended loop runs against it. Emits the ADR-0015 **suitability verdict** — a closed three-state gate (`suitable` / `needs_evidence` / `unsuitable`), fail-closed, with an actionable `missing_evidence` checklist — written to `<target>/.servo/suitability/<spec-id>.json`. A gate, not a score: the loop never optimizes toward a meaningless green oracle on work that cannot be evaluated.
---

# /servo:edd-suitability

The first step of **Servo Compile**: given an engineering spec, decide whether the
work is suitable for Evaluation-Driven Development and identify the evidence it is
missing — *before* an unattended loop spends budget. The worst unattended failure
mode is a **false pass**: a green oracle on work that cannot be meaningfully
evaluated (success is pure taste, the signals are vacuous, every AC is
human-residual). This skill refuses that work at the boundary with an auditable
verdict ([ADR-0015](../../docs/decisions/adr-0015-edd-suitability-gate.md)).

The helper lives at `${PLUGIN_ROOT}/skills/edd-suitability/`:

| Helper | Role | Spec |
|---|---|---|
| `suitability.py analyze` | spec + signals (001) + AC classification (006) → the verdict JSON at `.servo/suitability/<spec-id>.json` | 015-01 |
| `suitability.py analyze` (`missing_evidence`) | populate the actionable, blocking-flagged evidence checklist | 015-02 |
| `suitability.py analyze --explain` | ordered rule trace — which rules fired and why | 015-04 |

## When to use this skill

Use when the user wants to know **whether a spec is ready for EDD** and, if not,
**what's missing**. Scaffolding the oracle is `/servo:scaffold-init`; classifying
ACs is `/servo:spec-oracle`; running the loop is `/servo:agent-loop`. This skill
is the **gate upstream of all of them** — it judges the spec, consults 001's
signals and 006's classification, and emits a verdict the rest of Compile reads.

Where suitability sits ([ADR-0018](../../docs/decisions/adr-0018-suitability-gates-compile-not-heartbeat.md)):
the verdict gates the **Servo Compile** entry (Compile proceeds only on
`suitable`). It is **not** consulted by the heartbeat per finding — the heartbeat
keeps its own `gate.py` oracle preflight (heartbeat findings are spec-less, so the
spec-centric verdict has no input there).

This is a **host / Compile-phase tool**, like `/servo:spec-oracle` (whose
`oracle_plan.py` it consults) — it runs from the full servo plugin against a
target, and is **not** vendored into a scaffolded target's unattended runtime
(the heartbeat/loop never invoke it). It needs the spec-006 `oracle_plan.py`
sibling present; in the plugin that is the adjacent skill, or point
`SERVO_SUITABILITY_ORACLE_PLAN` at a copy.

**Shared AC grammar.** `suitability.py::_classify` subprocess-delegates to
`oracle_plan.py classify` for AC extraction/classification — there is **one**
AC-parsing pipeline in servo, not two (slice 019-03). The grammar (header
shape, tolerated preamble, negative-behavior keyword families, the
`residual_judgment` catch-all) is documented once, canonically, in
[`skills/spec-oracle/SKILL.md`](../spec-oracle/SKILL.md#shared-ac-grammar-canonical--slice-019-03) —
this skill consumes that same classification rather than re-parsing ACs.

## Q&A before analyzing

Before running, confirm:

1. **Target path** — the repo whose `.servo/install.json` signals are read (and
   where the verdict artifact is written).
2. **Spec / slice path** — the Markdown spec whose acceptance criteria are judged.
3. **Output mode** — a human summary (default), the full JSON (`--json`), or the
   rule trace (`--explain`).

## Workflow

```bash
# Analyze — human summary by default (verdict + each blocking missing-evidence item).
python3 "${PLUGIN_ROOT}/skills/edd-suitability/suitability.py" \
    analyze <target> --spec <spec-path>
#   → writes <target>/.servo/suitability/<spec-id>.json (atomic), exit 0.

# Full ADR-0015 JSON (for a consumer / the Compile gate):
python3 ".../suitability.py" analyze <target> --spec <spec-path> --json

# Why did it decide that? Ordered, first-match rule trace:
python3 ".../suitability.py" analyze <target> --spec <spec-path> --explain
```

A non-`suitable` verdict is **exit 0** — an unsuitable spec is a *successful
analysis*, not an error. Exit `2` is reserved for environment errors (missing
spec / missing-or-malformed `install.json` / unreadable AC classification); there
is never an exit 1, and a failed analysis never leaves a torn artifact.

## The verdict (closed three-state gate)

| Verdict | Meaning | Next step |
|---|---|---|
| `suitable` | EDD-shaped **and** has a compilable test/CI signal | proceed to Compile |
| `needs_evidence` | EDD-shaped but missing **blocking** evidence | acquire it, re-analyze |
| `unsuitable` | not EDD-shaped (success is irreducibly human taste) | route to a human / jig |

Fail-closed: indeterminate input never yields `suitable`. The `missing_evidence`
checklist is load-bearing only for `needs_evidence`; each item is
`{kind, detail, blocking}` keyed to the closed taxonomy
`tests · lint · ci · oracle_signal · reference_set` (extended only by a schema
bump, never an open string).

## Re-run after acquiring evidence

The verdict is **re-runnable**: close a blocking gap and re-`analyze`, and the
item disappears and the verdict can flip. The dogfood fixture
`examples/needs-evidence-then-suitable.md` demonstrates the loop — its ACs
classify as evaluable, so against a target with **no** test/CI signal it is
`needs_evidence` (blocking `oracle_signal`), and after a test command is added it
flips to `suitable`:

```bash
# 1. No signal yet → needs_evidence (blocking: oracle_signal)
python3 ".../suitability.py" analyze <target> --spec examples/needs-evidence-then-suitable.md
# 2. Acquire evidence: add a test command (scaffold-init detects it into install.json)
# 3. Re-analyze → suitable
python3 ".../suitability.py" analyze <target> --spec examples/needs-evidence-then-suitable.md
```

> The artifact is written as `<target>/.servo/suitability/<spec-id>.json`, where
> `<spec-id>` is the spec file's **parent-directory name** (spec-006's
> convention). For the example above that is `examples.json`; for a real spec at
> `docs/specs/015-edd-suitability/spec.md` it is `015-edd-suitability.json`.

## Extension point — optional model-assist (documented seam, not built)

The v1 verdict is a **deterministic, ordered rule table** (explainable,
reproducible, byte-stable). Some suitability signals — "is success irreducibly
*taste*?" — resist deterministic rules. An optional **model-assisted pass** is the
documented extension point: it must be **flag-gated** and its non-determinism
**bounded** the way [ADR-0005](../../docs/decisions/adr-0005-eval-oracle-components.md)
freezes any eval non-determinism (frozen prompt + recorded inputs/outputs, a
falsifiable negative control). It is **not built here** — the rule table ships
first so the gate is auditable from day one.

## Waiver posture — human override (documented seam, not built)

A `needs_evidence` / `unsuitable` gate can block work a human judges fine. The
intended override is a **waiver**, borrowing `/servo:spec-oracle`'s approval
posture: an explicit, recorded, auditable human decision (never a silent flag) —
so a turned-away spec can proceed under a named owner and an audit trail. The
primary path stays *acquire the evidence and re-analyze*; the waiver is the
escape hatch, **not built here**.
