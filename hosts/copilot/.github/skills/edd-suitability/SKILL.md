---
name: edd-suitability
description: >-
  Decide whether an engineering spec is suitable for Evaluation-Driven Development before any unattended loop runs against it. Emits the ADR-0015 **suitability verdict** — a closed three-state gate (`suitable` / `needs_evidence` / `unsuitable`), fail-closed, with an actionable `missing_evidence` checklist — written to `<target>/.servo/suitability/<spec-id>.json`. A gate, not a score: the loop never optimizes toward a meaningless green oracle on work that cannot be evaluated. Fire this skill when the user wants to: - "is this spec/work suitable for EDD?" / "should this go through servo?" - "what evidence is this spec missing?" / "why isn't this ready to compile?" - "why won't Compile proceed on this spec?" / "explain the suitability verdict" - "re-check suitability after I added tests" / "is <spec> EDD-shaped yet?" Do NOT fire on: - "scaffold the oracle" / "install servo" / "detect signals" — that's `/servo:scaffold-init` (001). Suitability *reads* the signals it detects; it (full description in skill body)
---

> **`$SERVO_ROOT`** — servo's runtime root (this plugin's own directory).
> Copilot exposes no plugin-root environment variable, and servo's Copilot
> package ships no hook to publish one. In a fresh shell, resolve it with
> the locator:
> `SERVO_ROOT="$(p="$PWD"; while :; do f="$p/.github/scripts/servo_root.py"; if [ -f "$f" ]; then python3 "$f"; exit $?; fi; [ "$p" = / ] && break; p="$(dirname "$p")"; done; for f in "${COPILOT_HOME:-$HOME/.copilot}"/installed-plugins/*/*/.github/scripts/servo_root.py; do [ -f "$f" ] && python3 "$f" && exit 0; done; printf '%s\n' 'servo_root: no servo runtime found. Install the plugin or invoke its .github/scripts/servo_root.py directly.' >&2; exit 1)"`
> The result is the runtime `.github` directory; the package's `.plugin/plugin.json`
> is one parent higher. For a live local-marketplace or `--plugin-dir` package,
> invoke `python3 "/absolute/package/.github/scripts/servo_root.py"` directly.
> That fallback uses the known package path, not live-install config discovery.

> **Full description** (Copilot's skill loader caps a frontmatter `description` at 1024 characters; the summary above is shortened — this is the complete original text, preserved so no routing/trigger guidance is lost):
>
> Decide whether an engineering spec is suitable for Evaluation-Driven Development before any unattended loop runs against it. Emits the ADR-0015 **suitability verdict** — a closed three-state gate (`suitable` / `needs_evidence` / `unsuitable`), fail-closed, with an actionable `missing_evidence` checklist — written to `<target>/.servo/suitability/<spec-id>.json`. A gate, not a score: the loop never optimizes toward a meaningless green oracle on work that cannot be evaluated. Fire this skill when the user wants to: - "is this spec/work suitable for EDD?" / "should this go through servo?" - "what evidence is this spec missing?" / "why isn't this ready to compile?" - "why won't Compile proceed on this spec?" / "explain the suitability verdict" - "re-check suitability after I added tests" / "is <spec> EDD-shaped yet?" Do NOT fire on: - "scaffold the oracle" / "install servo" / "detect signals" — that's `/servo:scaffold-init` (001). Suitability *reads* the signals it detects; it does not synthesize the oracle. - "classify the acceptance criteria" / "map ACs to check families" — that's `/servo:spec-oracle` (006). Suitability *consults* that classification; it does not reclassify. - "run the loop" / "iterate on this" / "let claude fix it" — that's `/servo:agent-loop` (003). Suitability is the *precondition*, not the run. - "score this code" / "what's the oracle score?" — that's `/servo:quality-gate` (002). Suitability judges the *spec*, not a build. When in doubt, ask which servo skill the user means rather than invent a trigger match.


# /servo:edd-suitability

The first step of **Servo Compile**: given an engineering spec, decide whether the
work is suitable for Evaluation-Driven Development and identify the evidence it is
missing — *before* an unattended loop spends budget. The worst unattended failure
mode is a **false pass**: a green oracle on work that cannot be meaningfully
evaluated (success is pure taste, the signals are vacuous, every AC is
human-residual). This skill refuses that work at the boundary with an auditable
verdict ([ADR-0015](../../docs/decisions/adr-0015-edd-suitability-gate.md)).

The helper lives at `$SERVO_ROOT/skills/edd-suitability/`:

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
python3 "$SERVO_ROOT/skills/edd-suitability/suitability.py" \
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
| `suitable` | EDD-shaped **and** has a compilable signal — a test/CI signal **or** a reviewed, frozen eval component ([ADR-0036](../../docs/decisions/adr-0036-frozen-evals-satisfy-suitability-signal.md)) | proceed to Compile |
| `needs_evidence` | EDD-shaped but missing **blocking** evidence | acquire it, re-analyze |
| `unsuitable` | not EDD-shaped (success is irreducibly human taste) | route to a human / jig |

Fail-closed: indeterminate input never yields `suitable`. The `missing_evidence`
checklist is load-bearing for `needs_evidence` **and** for the judged-only
`suitable` case (ADR-0036): a reviewed, frozen eval as the *sole* signal still
yields `suitable` but carries a standing **non-blocking advisory** recommending a
deterministic counterweight (the ADR-0033 reward-hacking lesson). **Blocking
items still never appear on `suitable`**, and `unsuitable` still carries an empty
list. Each item is `{kind, detail, blocking}` keyed to the closed taxonomy
`tests · lint · ci · oracle_signal · reference_set` (extended only by a schema
bump, never an open string).

## The eval-signal leg (ADR-0036 / spec 030-01)

`has_signal` is a test/CI signal **or** a reviewed, frozen eval component **or**
a live required-policy check (spec 044-02, below). The
eval leg is read purely from the two manifests servo already writes — never by
parsing `oracle.sh`:

1. **Installed** — the component name is in `<target>/.servo/install.json`'s
   `components` list (written by `fidelity_eval.register_manifest`, removed
   symmetrically at uninstall).
2. **Approved + frozen, with reviewed provenance** — the component's frozen
   `<target>/.servo/<dir>/config.json` carries `approval_status: "approved"`,
   `approval_provenance: "reviewed"`, `approved_content_hash`, and a non-empty
   `hashes` map. The dir alias is closed: `design_fidelity` →
   `.servo/design-eval/`, `content_fidelity` → `.servo/content-fidelity/`, else
   `.servo/<component>/` (eval-authoring, dir == name).

**Only `reviewed` provenance credits.** A `self_approved` or provenance-less
freeze (today's `content_fidelity` / eval-authoring stamps), an unapproved or
unfrozen config, an unregistered component, or an unreadable/malformed
`config.json` all contribute nothing — fail-closed, never an env-error (ADR-0036
guardrail 4). Suitability reads the *recorded* approval facts; it never re-hashes
the frozen artifacts (staleness stays score-time authority via `validate_freeze`).

**Judged-only advisory.** When a reviewed frozen eval is the *sole* signal (no
tests, no CI), the verdict is still `suitable`, but the artifact carries a
non-blocking advisory recommending a deterministic counterweight, and the
deciding reason code is `evaluable_acs_with_eval_signal` (distinct from
`evaluable_acs_with_signal`) so `--explain` / `reasons` make the judged-only
case auditable.

**Scope boundary.** This widens only the *signal* leg. `suitable` still requires
`n_evaluable >= 1`, which `oracle_plan classify` derives from the AC *text* by a
token-based family match. A design-led target benefits iff it carries ≥1 AC the
classifier recognises as deterministic (e.g. "the built `dist/index.html` file
is present" → `file_presence`); a spec whose ACs are all residual
(visual-fidelity, or behavioural prose that misses the keyword families) is
refused — never `suitable` via the AC leg — because an all-judge oracle with no
deterministic anchor is the reward-hacking case ADR-0015 and ADR-0036 guardrail
5 stay cautious about. An all-residual *design* spec can instead earn
evaluability from its own deterministic required-policy fidelity floor — see the
next section ([ADR-0050](../../docs/decisions/adr-0050-eval-is-signal-not-evaluability.md)
/ spec 044).

## The required-policy evaluability leg (ADR-0050 / spec 044)

`n_evaluable` is satisfied by at least one deterministic **AC** (above) **or** a
deterministic, **spec-attributed required-policy check** — the judge-free
static-source-contract observer (`family: command`, ADR-0046), which renders the
built app and compares computed CSS against the redline within tolerance. This is
how a pure build-to-redline design target (all fidelity ACs, `n_evaluable == 0`
from AC text) earns evaluability: it pairs its reviewed, frozen eval (the
`has_signal` fidelity *signal*, 030-01) with its own static-source-contract check
(the deterministic `n_evaluable` fidelity *floor*).

**The stochastic `design_fidelity` judge NEVER satisfies `n_evaluable`** (ADR-0050
rejects crediting the judge): it stays a `has_signal` source and fidelity
component only. The evaluability credit reads only the deterministic
required-policy check plan, never `install.json`'s quality `components`.

**Attribution — a spec declares its own floor.** A design spec attributes the
floor to itself with a frontmatter binding, a target-relative path to the sealed
static-source-contract dir:

```yaml
fidelity_contract: spec/oracle/static
```

The credit fires **iff** the analyzed spec declares `fidelity_contract` **and**
the declared path resolves to a **live, enforceable** floor — a committed seal
pinned to the current `oracle.sh` (L1) **and** installed as a required component
in `.servo/required-policy.json` (L2), mirroring what the score-time oracle
enforces (`driver_seal` / `required_runtime`). A committed
`approval_status: "approved"` label alone never suffices; a missing / draft /
unsealed / stale-`oracle.sh`-pin / not-installed floor fails closed, so a
`suitable` verdict never admits a loop whose oracle would env-error or green on
the judge alone. An **undeclared** spec is never credited (no target-global
credit a spec inherits for free). The declaration is **per-spec opt-in**, an
affirmative, reviewable attribution under servo's honest-author model — sound by
construction within the single-redline-per-target (vellum) closure; a spec that
deliberately mis-declares another spec's redline is caught by **spec review**,
not the gate (the gate cannot — and by the judge-exclusion must not — compute
whether a redline corresponds to a spec's fidelity goals). The synthetic
`spec_id: "static"` / `source_spec_path: "spec/static.md"` in the static
`checks.json` play **no** part in attribution.

A `suitable` verdict reached this way names its evaluability source in the
decided reason code (`evaluable_required_policy_with_signal`, used whenever
evaluability comes only from the policy check) and in the `--explain` trace
(`policy_evaluable=True`), so the case is auditable.

**The same live check also satisfies `has_signal` (spec 044-02).** `has_signal`
is a test/CI signal **or** a reviewed frozen eval (030-01) **or** a **live,
enforceable required-policy check** — the same `fidelity_contract` + L1/L2 floor
that satisfies `n_evaluable`. A live required-policy check is a deterministic
executable gate the score-time oracle runs, strictly safer than the stochastic
eval signal, so a **static-contract-only** target (no tests/CI, no eval, a live
floor, all-residual ACs) is `suitable`, with the message "supplies both the
evaluability and the oracle signal". One `policy_evaluable` boolean supplies both
legs, so it never satisfies the signal leg while leaving evaluability unmet; a
non-live floor yields no signal; the judge never credits it. Because the policy
check is itself the deterministic counterweight, the judged-only advisory does
not fire when it is live (the vellum pairing keeps `suitable`, with code
`evaluable_required_policy_with_signal`). Specs with no `fidelity_contract` are
unchanged.

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
