---

name: quality-gate
description: >-
  Run the scaffolded `oracle.sh` against a target project and surface a closed-contract result (0 = pass / 1 = below threshold / 2 = env error). Also exposes an `audit` subcommand that prints the servo install manifest without invoking the oracle.
---

# /servo:quality-gate

Run the scaffolded `<target>/oracle.sh` and surface a normalized result. The gate is the **truth-source** every other servo runtime skill consumes: closed 0/1/2 exit codes, structured stdout summary, optional one-line JSON for programmatic callers, and a bounded oracle runtime (default 5 min) so unattended loops can't hang.

## When to use this skill

Use when the user asks to **run** an already-scaffolded oracle. Scaffolding the oracle is a different skill (`/servo:scaffold-init`); this one only invokes it. The helper is at `${PLUGIN_ROOT}/skills/quality-gate/gate.py`.

The skill is **stateless**: each call is one subprocess. Persistence (per-iteration logs, race winners) is the caller's job (specs 003 / 005).

## Two subcommands

### `gate.py <target>` — invoke the oracle

Runs `<target>/oracle.sh` under a timeout, parses its `composite=X threshold=Y` summary, and emits a normalized line on stdout. Exit code passes through `0/1/2`.

```bash
python3 "${PLUGIN_ROOT}/skills/quality-gate/gate.py" <target>
```

Default output (single line on stdout):

```
gate: composite=0.9 threshold=0.5 status=pass exit=0
```

### `gate.py audit <target>` — print install manifest

Prints what was installed (tier, signals, components) without invoking the oracle. Useful for introspection.

```bash
python3 "${PLUGIN_ROOT}/skills/quality-gate/gate.py" audit <target>
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
| `--json` | both subcommands | Emit one-line JSON (with `schema_version=1` per ADR-0002) instead of the human-readable text summary. |
| `--verbose` | `gate.py <target>` only | Re-emit the oracle's raw stdout/stderr beneath the gate's summary (or under a `raw` JSON key). Without this, oracle output is captured and suppressed. |
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

The gate is stateless — nothing is written to disk by this skill. If a caller wants per-call logs, that's its job (specs 003 / 005 will own per-iteration / per-variant logging at `<target>/.servo/runs/` and `<target>/.servo/races/`).

## External-driver / bring-your-own-implementer contract

`gate.py` can be invoked **standalone by an external driver** — a CI pipeline, another agent, or a human — as the pass/fail authority over a Compiled oracle, fully independent of `/servo:agent-loop`. This is [ADR-0021](../../docs/decisions/adr-0021-oracle-first-agent-loop-optional-consumer.md)'s **oracle-as-a-service** flow: Compile produces the frozen, reviewable oracle; some driver performs the edits (see [`skills/agent-loop/SKILL.md`'s "Oracle-as-a-service / bring-your-own-implementer"](../agent-loop/SKILL.md#oracle-as-a-service--bring-your-own-implementer) for why the native loop isn't always that driver); `quality-gate` judges.

This already works today with **no new code** — it falls directly out of properties this skill already has:

- **Stateless** (see "After invocation" above) — every call is one self-contained subprocess with no session, no history, and no assumption about who or what made the prior edit. A CI job calling `gate.py` on commit N+1 is indistinguishable from this skill calling it on iteration N+1.
- **`--json`** — a structured, versioned (`schema_version`) one-line result any external caller can parse without depending on Claude Code's tool-call machinery.
- **A closed `{0, 1, 2}` exit-code contract** (ADR-0002) — `0` = pass, `1` = below threshold, `2` = environment error — is a plain process exit code, the universal integration point for a CI pipeline (`if`/`&&` on the shell, a CI step's pass/fail), a human's terminal, or another agent's own tool-call result, with no servo-specific client required.

So the recipe for an external driver is: scaffold + freeze with `/servo:scaffold-init`, make your edits with whatever you have, then run `python3 gate.py <target> --json` (or the plain-text form) and branch on the exit code — exactly the invocation shown under "Score a project" / "JSON for a programmatic caller" above, just called by something other than `/servo:agent-loop`.
