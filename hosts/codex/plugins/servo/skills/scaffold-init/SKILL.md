---

name: scaffold-init
description: >-
  Compile a target project's signals into an executable oracle — the first Servo Compile step of servo's Evaluation-Driven Development engine. Probes the target for signals (tests, lint, CI, language) and drops a tailored `oracle.sh`, `.servo/install.json` manifest, and `.servo/refinement-todo.md` deferred-decisions list.
---

# /servo:scaffold-init

Compile a target project's signals into a runnable Tier-0 oracle — the first **Servo Compile** step (servo is an Evaluation-Driven Development engine; see [docs/product-vision.md](../../docs/product-vision.md)). End state: the project gains a runnable `oracle.sh`, a machine-readable install manifest, and an explicit list of deferred decisions for the dev to resolve.

## When to use this skill

Use when the user is asking to **install servo on a project for the first time** (or re-install with `--force`). The helper is at `${PLUGIN_ROOT}/skills/scaffold-init/scaffold.py`. Tier 1 (agent-loop driver) and Tier 2 (hooks + worktree race) are forward-looking — only Tier 0 is shipped in spec 001.

This skill is the *scaffolder*. It does not run loops, install hooks, or score code at runtime. Those are future siblings (`/servo:agent-loop`, `/servo:oracle-hook`, `/servo:variant-race`, `/servo:quality-gate`).

## Q&A flow

Ask the following five questions in order. Each is **independently skippable** — if the user says "skip", says "I don't know", or doesn't give a clear answer, omit the corresponding flag and let the helper fall back to filesystem inference. **Never invent answers.** Skipping every question is a legitimate, supported path (see "Pure inference" below).

### 1. Project type

> "Is this project a service, a library, a plugin, or are you unsure?"

- **service** → component bias toward CI checks
- **library** → component bias toward test coverage
- **plugin** → component bias toward shape-of-installable
- **unsure** / skip → no bias; rely on filesystem signals alone

This answer is informational at slice 001-05 (the helper doesn't yet honor a `--project-type` flag). Recorded for future Tier-1+ slices where it will tune weight defaults.

### 2. Tier

> "Which tier do you want? Tier 0 only (oracle), Tier 0 + 1 (oracle + agent-loop driver), or all three (Tier 0 + 1 + 2 with hooks + worktree race)?"

- **Tier 0** → ships now. Drops `oracle.sh` + manifest + refinement-todo.
- **Tier 1** → future. If the user picks this, tell them: "Tier 1 templates ship in a future spec (003-agent-loop). Tier 0 will install now; come back when 003 lands."
- **Tier 2** → future, same handling — point at spec 004 (`oracle-hook`) and 005 (`variant-race`).
- **skip** → assume Tier 0.

### 3. Loop guardrails

> "Use default loop guardrails (max-iterations=5, cost-ceiling=$2), or set custom values?"

If the user picks **custom**, ask for the iteration cap and the cost ceiling separately. Record both. Tier 1 is not yet shipped, so the values are informational at this slice.

If the user picks **defaults** or **skips**, omit and continue.

### 4. Hook installation

> "Install the Claude Code hook now (Tier 2 only)? yes / no / skip"

Tier 2 is not yet shipped, so this is informational. If the user says **yes**, note that the hook installer will be implemented by spec 004 (`oracle-hook`) and install Tier 0 anyway. If **no** or **skip**, continue.

### 5. Existing servo install

If `<target>/.servo/install.json` already exists, ask:

> "An existing servo install was detected (`.servo/install.json` present). Proceed with `--force` (overwrite the oracle, rewrite the manifest, rewrite the refinement-todo) — or abort?"

- **proceed** → invoke with `--force`.
- **abort** → exit cleanly without calling the helper.

If `.servo/install.json` is absent, skip this question silently.

## Pure inference

If the user skips **every** question, invoke the helper with no flags:

```bash
python3 "${PLUGIN_ROOT}/skills/scaffold-init/scaffold.py" <target>
```

This is the **pure inference** path — equivalent to running the helper directly. The output is fully driven by what's on disk in `<target>`: detected test framework, lint configs, CI files, language. Skipping all is not a degraded mode; it's the documented baseline.

## Refusal handling

If the helper exits with `error: oracle.sh already present` (return code 1), **the install was refused — not failed**. The helper detected an existing scaffold and refused to clobber it.

When this happens:

1. **Surface the helper's stderr message to the user verbatim.** Do not paraphrase or summarize away the `--force` hint.
2. Ask the user whether to re-scaffold with `--force`. This overwrites `oracle.sh`, rewrites `.servo/install.json`, and rewrites `.servo/refinement-todo.md`. It does **not** delete the rest of `.servo/` (per slice 001-01's `--force` contract).
3. **Do NOT silently retry with `--force`.** Re-running automatically would destroy in-progress work without consent.

If the helper exits with return code 2 (environment error — target missing, target not a directory, template missing), surface the message verbatim and stop. `--force` will not help.

## How to invoke

```bash
# Pure inference — all questions skipped:
python3 "${PLUGIN_ROOT}/skills/scaffold-init/scaffold.py" <target>

# After question 5 = proceed (existing install present):
python3 "${PLUGIN_ROOT}/skills/scaffold-init/scaffold.py" <target> --force

# Audit only (no scaffolding) — useful for previewing detection results:
python3 "${PLUGIN_ROOT}/skills/scaffold-init/scaffold.py" detect <target>
```

`<target>` must be an existing directory. The helper does not create parent directories.

## After the install

When the helper exits 0, three files have landed in the target:

- `<target>/oracle.sh` — runnable, executable. The user can `bash oracle.sh` to score now.
- `<target>/.servo/install.json` — manifest the future runtime skills (002–005) will read.
- `<target>/.servo/refinement-todo.md` — explicit list of deferred decisions: at minimum a `Threshold` entry, plus `Weights` and `Ambiguous test runner` when applicable.

Tell the user where these landed and invite them to scan the refinement-todo before their next commit.

## Examples

**Pure inference**, no questions asked:

```
user: set up servo on this project
assistant: [asks Q1–Q5 in order, user skips each]
        → python3 .../scaffold.py /path/to/repo
        → "servo: installed tier-0 at /path/to/repo"
```

**Existing install, proceed**:

```
user: set up servo here
assistant: [asks Q5: existing install detected — proceed or abort?]
user: proceed
assistant: → python3 .../scaffold.py /path/to/repo --force
```

**Existing install, helper refuses (user didn't get question 5)**:

```
assistant: → python3 .../scaffold.py /path/to/repo
       stderr: error: oracle.sh already present at .../oracle.sh; re-run with --force to overwrite
assistant: [surfaces the message verbatim to the user, asks whether to --force, does NOT silently retry]
```
