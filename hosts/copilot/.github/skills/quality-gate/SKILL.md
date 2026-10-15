---
name: quality-gate
description: >-
  Run the scaffolded `oracle.sh` against a target project and surface a closed-contract result (0 = pass / 1 = evaluated failure / 2 = env error). Also exposes an `audit` subcommand that prints the servo install manifest without invoking the oracle. Fire this skill when the user wants to: - "score this code" / "score this project" / "run quality gate" - "run the oracle" / "what's the oracle score?" - "check the oracle" / "did the oracle pass?" - "show me the gate result" / "is the gate passing?" - "what does this servo install include?" (→ audit subcommand) Do NOT fire on: - "set up servo" / "scaffold oracle" / "install servo" — those are `/servo:scaffold-init`'s territory (a sibling skill, not this one). - "fix the failing test" / "make tests pass" / "debug this test" — out of scope. The gate reports; it does not modify code or tests. - "run my tests" / "lint this" — call the underlying tool directly; the gate is the composite scorer, not a single-tool runner. - "review my (full description in skill body)
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
> Run the scaffolded `oracle.sh` against a target project and surface a closed-contract result (0 = pass / 1 = evaluated failure / 2 = env error). Also exposes an `audit` subcommand that prints the servo install manifest without invoking the oracle. Fire this skill when the user wants to: - "score this code" / "score this project" / "run quality gate" - "run the oracle" / "what's the oracle score?" - "check the oracle" / "did the oracle pass?" - "show me the gate result" / "is the gate passing?" - "what does this servo install include?" (→ audit subcommand) Do NOT fire on: - "set up servo" / "scaffold oracle" / "install servo" — those are `/servo:scaffold-init`'s territory (a sibling skill, not this one). - "fix the failing test" / "make tests pass" / "debug this test" — out of scope. The gate reports; it does not modify code or tests. - "run my tests" / "lint this" — call the underlying tool directly; the gate is the composite scorer, not a single-tool runner. - "review my code" / "code review" — that's a separate workflow. When in doubt, ask which servo skill the user means rather than invent a trigger match.


# /servo:quality-gate

Run the scaffolded `<target>/oracle.sh` and surface a normalized result. The gate is the **truth-source** every other servo runtime skill consumes: closed 0/1/2 exit codes, structured stdout summary, optional one-line JSON for programmatic callers, and a bounded oracle runtime (default 5 min) so unattended loops can't hang.

## When to use this skill

Use when the user asks to **run** an already-scaffolded oracle. Scaffolding the oracle is a different skill (`/servo:scaffold-init`); this one only invokes it. The helper is at `$SERVO_ROOT/skills/quality-gate/gate.py`.

Default scalar calls remain stateless. Explicit approved required policy uses
schema 2 and preserves `.servo/gate-runs/<UUID>/gate.json`, binding immutable
component records from the same single invocation. See
[required policy and carrier](../spec-oracle/examples/required-policy.md).
Generation/installation alone never approve policy.

In enabled projects `0 = pass`, `1 = evaluated failure`, `2 = unavailable
evidence/environment refusal`. Status is `pass|fail|env_error`, with
`required_constraints_failed`, `quality_below_threshold`,
`required_and_quality_failed`, or `required_evidence_unavailable` as appropriate.
Quality policy remains independently authoritative; weights/threshold and
override provenance are preserved. A
contradiction veto cannot be averaged away or cleared by THRESHOLD=0.
Unknown takes precedence while retaining known failures. **Only the overall
gate record is completion authority**, not a component's passing envelope.
Default projects retain the v1 contract below. Supported loop/goal, hook advice
and heartbeat consumers preserve the original overall payload as `oracle` plus
exact `gate_ref: {path, hash}` and validate invocation-bound evidence without
reevaluation/rescore. Unknown versions and unavailable mandatory refs refuse.
Inspect required IDs/reasons and raw component evidence, repair implementation
on contradiction and rerun; repair acquisition/bindings on refusal. Policy
changes require explicit reviewed reapproval. Existing customized hooks need
explicit migration, not silent replacement. Source provenance is not
served-build attestation; native Copilot unattended autonomy remains unsupported.

## Two subcommands

### `gate.py <target>` — invoke the oracle

Runs `<target>/oracle.sh` under a timeout, parses its `composite=X threshold=Y` summary, and emits a normalized line on stdout. Exit code passes through `0/1/2`.

```bash
python3 "$SERVO_ROOT/skills/quality-gate/gate.py" <target>
```

Default output (single line on stdout):

```
gate: composite=0.9 threshold=0.5 status=pass exit=0
```

### `gate.py audit <target>` — print install manifest

Prints what was installed (tier, signals, components) without invoking the oracle. Useful for introspection.

```bash
python3 "$SERVO_ROOT/skills/quality-gate/gate.py" audit <target>
```

Sample output:

```
servo install at /path/to/repo
  tier:        tier-0
  installed:   2026-05-18T12:34:56Z
  signals:     tests=true lint=false ci=false language=python
  components:  (1)
    - pytest (weight 1)
```

## Options

| Flag | Applies to | What it does |
|---|---|---|
| `--json` | both subcommands | Emit one-line JSON (default schema 1; explicitly enabled required policy schema 2) instead of the human-readable text summary. |
| `--verbose` | `gate.py <target>` only | Default/v1: re-emit oracle stdout/stderr (or a `raw` JSON key). Enabled/v2: inspect the immutable bound evidence artifacts instead; unbound console output is not added to the preserved payload. |
| `--timeout <seconds>` | `gate.py <target>` only | Bound the oracle's runtime in seconds. `0` disables the timeout. Defaults to `SERVO_GATE_TIMEOUT` env var, else 300s (5 min). |

Example invocations:

```bash
# Default: human-readable summary
python3 gate.py /path/to/repo

# Structured JSON for programmatic callers
python3 gate.py /path/to/repo --json

# Tight timeout for a quick smoke check
python3 gate.py /path/to/repo --timeout 30

# Audit (no oracle invocation)
python3 gate.py audit /path/to/repo
python3 gate.py audit /path/to/repo --json
```

## Refusal handling

For required-policy installations, do not suggest `--force` or deletion as
recovery: re-scaffold refuses without writing. Review the per-item causes,
repair the environment, or explicitly revise/reapprove/install the overlay.
Enabled-empty projects stay v2 and still enforce quality. Unsupported customized
drivers and dynamic COMPONENTS arrays refuse upgrade without partial writes.

The gate uses a closed 0/1/2 exit contract (ADR-0002). When it exits 2, the `reason` field on the structured summary tells you why. **Do NOT silently retry** — surface the message verbatim to the user and offer the appropriate recovery.

| `reason` | Meaning | Recovery to suggest |
|---|---|---|
| `target_missing` / `target_not_directory` | Bad target path | Confirm the path; if it's a relative path, check the working directory. |
| `manifest_missing` | `.servo/install.json` absent | Run `/servo:scaffold-init` on the target first. |
| `manifest_malformed` / `manifest_invalid_key` | Manifest exists but isn't valid | Inspect `<target>/.servo/install.json`. Most likely re-scaffold with `/servo:scaffold-init` and `--force`. |
| `oracle_missing` | `oracle.sh` absent (but manifest is there) | Suspicious — manifest says there's a servo install but the oracle is gone. Re-scaffold with `/servo:scaffold-init --force`. |
| `oracle_not_executable` | `oracle.sh` lost its exec bit | Run `chmod +x <target>/oracle.sh` (the stderr message names the exact path). Never auto-chmod. |
| `timeout` | Oracle exceeded `--timeout` / env-var / 300s default | Surface the timeout. Offer to re-run with a longer `--timeout`. If the oracle is genuinely supposed to take >5 min, document it. |
| `unparseable_oracle_output` | Oracle exited 0 but produced no `composite=X threshold=Y` line | Likely a bug in the oracle. The raw oracle output is surfaced on stderr — show it to the user. Most likely the oracle was hand-edited; ask the user to fix or re-scaffold. |
| `unexpected_exit` | Oracle exited with a code outside `{0, 1, 2}` (signal kill, bash error 126/127, app bug returning 99, etc.) | Per ADR-0002 the gate's exit stays 2; the original code is in the `code` field. Likely a bug in a component or its tool. Surface and ask user. |
| `invocation_failed` | OS-level error invoking the oracle (rare) | Surface the OSError verbatim; usually permissions or filesystem state. |

## Examples

**Score a project (default)**:

```
user: score this project
assistant: → python3 .../gate.py /path/to/repo
        → "gate: composite=0.9 threshold=0.5 status=pass exit=0"
        → exit 0
```

**JSON for a programmatic caller**:

```
user: give me the gate result as JSON
assistant: → python3 .../gate.py /path/to/repo --json
        → {"schema_version": 1, "exit_code": 0, "status": "pass",
           "composite": 0.9, "threshold": 0.5, "missing": []}
```

**Audit — what's installed**:

```
user: what does this servo install include?
assistant: → python3 .../gate.py audit /path/to/repo
        → "servo install at /path/to/repo"
        → "  tier:        tier-0"
        → "  signals:     tests=true language=python"
        → "  components:  (1)"
        → "    - pytest (weight 1)"
```

**Refusal — missing manifest**:

```
assistant: → python3 .../gate.py /path/to/repo
        stderr: gate: .servo/install.json not found at /path/to/repo/.servo/install.json; run /servo:scaffold-init first
        stdout: gate: composite=null threshold=null status=env_error exit=2 reason=manifest_missing
assistant: [surfaces the message verbatim; offers to run /servo:scaffold-init; does NOT silently retry]
```

**Refusal — timeout**:

```
assistant: → python3 .../gate.py /path/to/repo --timeout 60
        stderr: gate: oracle timed out after 60.0s (killed via SIGTERM → SIGKILL)
        stdout: gate: composite=null threshold=null status=env_error exit=2 reason=timeout timeout=60.0s
assistant: [surfaces the timeout; offers to re-run with --timeout 300 or --timeout 0 (disable)]
```

## After invocation

The default scalar-only v1 gate is stateless: caller-owned per-call logs remain
separate (specs 003 / 005 own per-iteration / per-variant logging at
`<target>/.servo/runs/` and `<target>/.servo/races/`). Explicit required-policy
v2 invocations preserve their validated overall gate record at
`<target>/.servo/gate-runs/<run_id>/gate.json`, binding exact component evidence.
Pre-invocation missing-carrier refusal is not an attestable successful run.

## External-driver / bring-your-own-implementer contract

`gate.py` can be invoked **standalone by an external driver** — a CI pipeline, another agent, or a human — as the pass/fail authority over a Compiled oracle, fully independent of `/servo:agent-loop`. This is [ADR-0021](../../docs/decisions/adr-0021-oracle-first-agent-loop-optional-consumer.md)'s **oracle-as-a-service** flow: Compile produces the frozen, reviewable oracle; some driver performs the edits (see [`skills/agent-loop/SKILL.md`'s "Oracle-as-a-service / bring-your-own-implementer"](../agent-loop/SKILL.md#oracle-as-a-service--bring-your-own-implementer) for why the native loop isn't always that driver); `quality-gate` judges.

This already works today with **no new code** — it falls directly out of properties this skill already has:

- **Invocation-scoped** (see "After invocation" above) — every call evaluates
  current inputs without assuming who made the prior edit. Default v1 keeps
  no gate history; enabled v2 preserves that exact run, never borrowing an old
  successful result.
- **`--json`** — a structured, versioned (`schema_version`) one-line result any external caller can parse without depending on Claude Code's tool-call machinery.
- **A closed `{0, 1, 2}` exit-code contract** (ADR-0002) — `0` = pass,
  `1` = evaluated failure (below threshold in v1; quality and/or required
  failure in v2), `2` = environment/evidence refusal. External drivers must
  understand the opt-in schema before consuming its reasons/artifacts; the
  numeric exit remains a plain CI/human/agent integration point.

So the recipe for an external driver is: scaffold + freeze with `/servo:scaffold-init`, make your edits with whatever you have, then run `python3 gate.py <target> --json` (or the plain-text form) and branch on the exit code — exactly the invocation shown under "Score a project" / "JSON for a programmatic caller" above, just called by something other than `/servo:agent-loop`.
