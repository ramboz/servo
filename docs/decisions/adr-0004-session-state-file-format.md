---
status: Accepted
date: 2026-05-19
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0004 — Session-state file format on disk

## Context

Spec 003 (`/servo:agent-loop`) ships `loop.py`, a headless iteration driver that subprocesses `claude -p --output-format json` against a target under hard guardrails (iteration cap, cumulative cost ceiling, context-fill refusal gate, stuck-loop detection). Slice 003-04 (checkpoint-resume) adds the resume primitive: `loop.py --resume <run-id>` picks up an interrupted or capped run from where it left off. That requires servo to persist enough state across `loop.py` invocations to (a) hand the right `session_id` back to `claude -p --resume`, (b) carry cumulative counters and oracle-score history forward, and (c) refuse resume cleanly when the on-disk format or Claude Code version has drifted in an incompatible way.

The shape of that state file was open until the spec 003 [pre-spec research spike](../specs/003-agent-loop/spike.md). A naive sketch had servo storing the full conversation transcript alongside its own counters — the spike verified that **Claude Code already owns the transcript** at `~/.claude/projects/<slug>/<session-id>.jsonl` (one JSONL per session, project-slugged by absolute path). Re-storing that content in servo's state file would force servo to parse an Anthropic-internal format, couple servo to Claude Code's release cadence, and duplicate gigabytes of disk across long-running races (spec 005).

The remaining decision is therefore not "how do we serialize a conversation" but "what does the loop-driver scoreboard look like, where does it live, and how do we keep it forward-compatible." Three other downstream specs (004 oracle-hook, 005 variant-race) and a potential cross-plugin reader (jig's `slice-land prepare`) all stand to consume this format once it's fixed. Decide once, write it down.

## Decision

Servo's per-run loop-driver state lives at **`<target>/.servo/runs/<run-id>/state.json`**. The path is reserved in `docs/architecture.md` "Runtime artifacts." The file references the Claude Code conversation by `session_id` only and carries the scoreboard that Claude Code does not own.

**Run-id format.** `run-id` is a millisecond-precision timestamp prefix + short random suffix, e.g. `20260519T143205-a3f1`. Human-readable, sortable across runs without parsing, collision-resistant under spec 005's parallel-variant scenario.

**Run-id collision policy.** When `loop.py` attempts `mkdir(<target>/.servo/runs/<run-id>/, exist_ok=False)` and fails because the directory already exists, the loop driver regenerates the random suffix (timestamp prefix stays the same to preserve sortability within the millisecond) and retries — up to **3 attempts total** (initial + 2 retries). After 3 failed attempts, the run refuses with rc=2, `reason=run_id_collision`, and a stderr breadcrumb naming the colliding run-id(s). 3 is the cap rather than open-ended retry because three collisions on the same millisecond are pathological for a 16-bit suffix space (~65k entropy) — much more likely a stuck clock, a hostile filesystem, or a logic bug in the caller than legitimate concurrency. A bounded retry surfaces the underlying problem instead of masking it.

**Schema.** The file is a single JSON object with the following fields (canonical list, per spec 003-04 AC #2):

- `state_schema_version` (int, currently `1`)
- `run_id` (string)
- `started_at`, `last_updated_at` (ISO8601 strings)
- `target_path` (absolute path string)
- `current_session_id` (string — the Claude Code session ID to pass to `--resume`)
- `iteration_count`, `max_iterations` (int)
- `cost_ceiling_usd`, `cumulative_cost_usd` (float)
- `cumulative_input_tokens`, `cumulative_output_tokens` (int)
- `context_fill_threshold`, `last_context_fill_ratio` (float)
- `oracle_score_history` (list of `{iteration, composite, threshold, status}`)
- `last_terminal_reason` (string — last `claude -p` or loop-driver terminal reason)
- `claude_version` (string — captured via `claude --version` on the first iteration)

**Atomic write contract.** State is written by writing the full new payload to `state.json.tmp` and then `os.replace`-ing it onto `state.json`. `os.replace` is atomic on POSIX and on NTFS, so a Ctrl-C, SIGTERM, or power loss mid-write can never leave a torn `state.json` on disk. The state file is written **after every iteration** (not just at exit), so interruptions lose at most the in-progress iteration. This is the substrate that spec 003-04 AC #9's signal handler relies on: the trap finalizes the state file, emits a summary line, and exits 130 — and the finalize step is just one more atomic write, so the trap itself can be interrupted without corruption.

**Schema versioning.** Following [ADR-0002](adr-0002-gate-caller-contract.md)'s `schema_version` mechanism explicitly: `state_schema_version` starts at `1`. Any field rename, type change, or semantic shift bumps it. Pure additive changes (a new optional field with a documented default for old consumers) MAY keep the version at 1, but the bias is "bump on any doubt" — silent mis-decoding of a resumed run is worse than a noisy refusal. On `--resume`, `loop.py` refuses to load a state file with `state_schema_version` different from the version it knows: rc=2 with `state_schema_mismatch` and a stderr breadcrumb naming both versions. `--resume-anyway` escapes the refusal but is documented as risky in the SKILL.md surface that lands in slice 003-05.

**`claude_version` capture.** First iteration of every run captures `claude --version` and persists it in the state file. On `--resume`, the loop refuses (rc=2 / `claude_version_mismatch`) if the current `claude --version` differs from the recorded one; `--resume-anyway` also escapes here. This is forensics-grade defense against Claude Code releases that silently change the JSON shape or the `session_id` consumption semantics between when a run was checkpointed and when it's resumed.

**Coupling with Claude Code.** Filesystem-only, mirroring [ADR-0001](adr-0001-reuse-jig-test-detector.md)'s framing. Servo never imports Claude Code's session JSONL parsing, never reads `~/.claude/projects/<slug>/<session-id>.jsonl` itself, never depends on the JSONL's schema. The only coupling is: servo persists the `session_id` string returned from `claude -p`'s JSON output, and hands it back to `claude -p --resume <session_id>` later. If Claude Code drops session persistence, garbage-collects an old session, or changes the JSONL shape, the worst case is a refused resume — never a corrupted servo run.

## Consequences

**Positive.**

- **Smallest possible scoreboard.** Servo stores only fields Claude Code doesn't own. No transcript marshaling, no Anthropic-format compatibility burden, no duplicated disk footprint across long-running races.
- **Forward-compat baked in from day one.** `state_schema_version` lets future schema evolutions land cleanly: old consumers refuse loudly rather than silently mis-decoding. Mirrors the same mechanism specs 003–005 already trust on `gate.py --json`.
- **Atomic write means signal-safe.** No torn writes, no recovery code needed, no half-finalized state files. Ctrl-C / SIGTERM mid-iteration always leaves a consistent `state.json` on disk. Spec 003-04 AC #9's signal-handling contract is built on this substrate.
- **Greppable, diffable, version-controllable.** JSON is plain text. A user who wants to commit `state.json` to inspect or share a run can. `jq` works. `git diff` is meaningful. None of this is true for SQLite.
- **Soft cross-plugin contract.** jig's `slice-land prepare` could one day read `<target>/.servo/runs/*/state.json` to emit "found a paused servo run — resume?" hints. This ADR fixes the format so that integration is *possible* without making it a requirement. jig stays an optional consumer; servo doesn't depend on jig reading the file.
- **Per-worktree isolation.** Path under `<target>/.servo/runs/<run-id>/` (not `<plugin-root>/.servo/`) means spec 005's parallel-variant race has natural per-worktree isolation — each variant's worktree carries its own `.servo/runs/` tree.

**Negative.**

- **Depends on Claude Code retaining the JSONL.** If `~/.claude/projects/<slug>/<session-id>.jsonl` is garbage-collected, manually deleted, or made unreadable by a Claude Code upgrade, the `session_id` in servo's state file becomes a dangling reference. `--resume` will fail when `claude -p --resume <id>` rejects it. Acceptable: the failure mode is loud (Claude Code refuses, servo reports it) and the user's recourse is to start a fresh run, not corrupt data.
- **Two version gates to clear on resume.** Both `state_schema_version` and `claude_version` are checked, both can refuse. A user resuming a run after upgrading either servo or Claude Code may hit a refusal and have to either accept the loss or invoke `--resume-anyway`. The cost is real but small — checkpoint/resume across version upgrades is genuinely fragile and the noisy refusal is the right default.
- **Cross-machine portability lost.** State files are valid on the machine they were written on. A `session_id` is meaningless on a different machine because the JSONL doesn't travel with the state file. Documented as out-of-scope in spec 003.
- **`oracle_score_history` grows unbounded.** A very long-running resumed loop accumulates one entry per iteration in the history list. At one entry per iteration and ~80 bytes per entry, even 10,000 iterations is well under a megabyte — not a real cost today, but flagged.

**Neutral.**

- **`run-id` is not globally unique by construction.** The millisecond + 4-hex-char-suffix shape gives ~65,000 distinct IDs per millisecond, which is enough for any plausible parallel race but not a UUID. Directory-creation collisions trigger the bounded retry described in the Decision section (3 attempts then refuse); the same millisecond getting hit three times is treated as pathological rather than something to grind through silently.
- **JSON has no schema-validation step on read.** `loop.py` accesses fields directly and would `KeyError` on a malformed state file. The `state_schema_version` check is the first line of defense; field-level validation is not in scope. Could be added later under a future schema bump.
- **No deprecation policy pinned for old `state_schema_version` values.** When `state_schema_version=2` lands, the policy (refuse old versions outright, or accept-with-warning, or migrate-on-read) is a future call. Today's audience is internal — slice 003-04 is the first writer — so the question doesn't bind yet.

## Alternatives considered

- **Copy the conversation transcript into the state file.** Rejected: Claude Code already owns the transcript at `~/.claude/projects/<slug>/<session-id>.jsonl`. Re-storing it would force servo to parse and re-serialize an Anthropic-internal format that's not under our control, couple servo to Claude Code's release cadence, and duplicate disk footprint across long races (spec 005). The spike (see [spike.md](../specs/003-agent-loop/spike.md) "ADR-0005 implications") settled this: servo stores only the scoreboard and references the conversation by `session_id`.
- **Embed servo-only state in Claude Code's session JSONL via additional events.** Rejected: requires writing to a file we don't own, breaks the filesystem-only-coupling promise, and ties servo's release cadence to Claude Code's. Any Claude Code upgrade that re-parses or compacts the JSONL could destroy servo's state.
- **Store state at `<plugin-root>/.servo/runs/<run-id>/` (inside the servo plugin install).** Rejected: state is per-project, not per-plugin-install. Spec 005's variant-race needs per-worktree isolation, which the target-relative path provides naturally. A plugin-relative path would also lose cross-machine portability anyway (same as the chosen design), so it gets the worst of both worlds — and it would put project-specific artifacts inside the plugin's own directory, which is the wrong layering.
- **SQLite (or another embedded database) for the state.** Rejected: dependency weight is wrong for the use case. JSON is greppable with `jq`, diffable with `git`, and inspectable with `cat`. SQLite needs a CLI tool, a schema migration story of its own, and on-disk durability tuning. The state file is one object updated once per iteration — there's no query workload to justify a database.
- **No state file; require the user to pass `session_id` manually on `--resume`.** Rejected: cumulative counters (cost, tokens, oracle history) have to live somewhere too, and asking the user to manage them by hand defeats the unattended-operation posture spec 003 was built for. The UX is materially worse and the contract gets blurry — what counts as "the same run" if the user is providing IDs manually?

## Verification

- **Slice 003-04 AC #1** verifies the per-iteration atomic-write contract via `StateFilePersistenceTests` in `skills/agent-loop/test_loop.py`: tear the loop down mid-run with SIGTERM after iteration 2 and assert the state file reads back as a complete, parseable JSON object with `iteration_count=2`, `current_session_id` set to the iteration-2 session, and `cumulative_cost_usd` reflecting both iterations.
- **Slice 003-04 AC #2** verifies the canonical schema field set via `StateFileSchemaTests`: assert every named field is present after a normal run, with the correct type.
- **Slice 003-04 AC #5** verifies the `state_schema_version` and `claude_version` refusal paths via `ResumeRefusalTests`: hand-edit a state file to bump or drop `state_schema_version`, hand-edit to mismatch `claude_version`, and assert resume refuses with rc=2 and the documented `reason` strings. `--resume-anyway` is tested to escape both.
- **Slice 003-04 AC #9** verifies the signal-handler-finalize contract via `SignalHandlingTests`: SIGINT during `claude -p` and during `gate.py`, assert the state file is consistent and the summary line carries `terminal_reason=interrupted` with exit code 130. Confirms the atomic-write substrate is signal-safe end-to-end.
- **Slice 003-04 AC #10** verifies the run-id collision retry policy via `RunIdCollisionTests`: seed `<target>/.servo/runs/` with directories matching the next-generated run-ids (forced via a deterministic random seed in the test harness); assert the loop retries up to 3 times and refuses on the 4th conflict with rc=2 / `reason=run_id_collision`. A single-collision case verifies the retry succeeds and the loop proceeds with the second-attempt run-id.
- **Spec 003 spec-level DoD scenario #3** (resume path) dogfoods the full flow: run a capped loop, then `loop.py <tmp> --resume <run-id> --max-iterations 5` continues from iteration N+1 with cumulative counters preserved.

## References

- [Spec 003 — agent-loop](../specs/003-agent-loop/spec.md), slice 003-04 (checkpoint-resume) ACs #1, #2, #5, #9.
- [Spec 003 pre-spec research spike](../specs/003-agent-loop/spike.md), section "ADR-0005 implications (session-state file format)" — the sketch this ADR formalizes. (Spike uses the historical "ADR-0005" hint number; the project's numbering rule allocates the next sequential ADR number at acceptance, which is 0004 here.)
- `docs/architecture.md` — "Runtime artifacts" section reserves `<target>/.servo/runs/<run-id>/`; "Decisions" table lists this ADR.
- [ADR-0001](adr-0001-reuse-jig-test-detector.md) — filesystem-only-coupling framing this ADR mirrors for the Claude Code session JSONL relationship.
- [ADR-0002](adr-0002-gate-caller-contract.md) — `schema_version` mechanism this ADR mirrors explicitly for `state_schema_version`.
