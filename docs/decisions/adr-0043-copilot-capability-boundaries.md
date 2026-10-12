---
status: Accepted
dependencies: [adr-0002, adr-0004, adr-0012, adr-0021, adr-0038]
last_verified: 2026-10-12
frame_review: true
---

# ADR-0043: Copilot capability boundaries preserve Servo guarantees

## Status

Accepted (2026-10-12)

## Context

Installing Servo must not silently remove its execution safeguards.

PR #37 already implements the generated Copilot package under Accepted
[ADR-0038](adr-0038-copilot-third-host.md) and closed spec 032. The October
proposal on `servo-copilot-port` at `230baa74` described overlapping delivery
work and additional native execution/evaluation work before that implementation
was discovered. This follow-up reuses the existing package rather than replacing
its historical records or repeating its implementation.

Executed on 2026-10-12, `copilot version` reports **1.0.96-2** (the executable
has updated since the coordinator's 1.0.93-1 probe). `copilot help limits`
describes `--max-ai-credits` as a **soft** cap with minimum **30** credits:
usage is observed after a response, which can exceed the cap. Complete
`copilot --help` exposes no `--max-budget-usd`. Credits are not dollars.
This is not evidence for Servo's requested hard monetary ceiling.
Captured command output:
[copilot-contract.txt](../specs/034-copilot-installed-runtime/copilot-contract.txt).

The existing adapter in `skills/agent-loop/loop.py:1914-1965` normalizes unknown
USD spend to `0.0`, and its launch path merely warns that the monetary/context
brakes do not apply. It also invokes `--allow-all-tools` and reuses the version-1
Claude state shape. Packaging is supported; those choices cannot satisfy the
new native execution contract. The target-side `agentStop` adapter remains
advisory: static registration is not proof of per-turn continuation.

The package runtime is `<package>/.github`, whereas its manifest lives at
`<package>/.plugin/plugin.json`. `skills/scaffold-init/scaffold.py:108-115`
currently reads only a Claude manifest when writing the availability marker.
The standalone locator already distinguishes these roots; the scaffolder must
do so as well, without giving an unrelated Claude environment precedence over
the executing Copilot package.

## Decision Options Considered

### Option A: Keep the native loop enabled with a warning
- **Pros:** Preserves the September prototype.
- **Cons:** A requested USD ceiling becomes inert, unknown usage becomes zero,
  and broad tool approval is implicit. Rejected.

### Option B: Convert credits to USD or weaken the budget contract
- **Pros:** Makes apparent parity easier.
- **Cons:** Neither conversion nor weaker policy is owner-authorized. Rejected.

### Option C: Deliver the installed deterministic workflow; refuse unsupported execution
- **Pros:** Consumers can compile and score project-owned oracles without Claude
  or Jig, while unsupported native autonomy fails before spending or mutation.
- **Cons:** This is explicitly not full native execution/evaluation parity.
  Chosen for the current supported delivery.

## Recommended Decision

1. Keep the generated host mechanism, manifest, loader-safe skills, native
   agents, marketplace and release archives from ADR-0038. No new runtime
   dependency on Jig. Keep the standalone locator, not an unverified new
   SessionStart publisher.
2. Resolve the executing Copilot runtime independently of the source/package
   root. Read its actual native manifest for availability metadata. Preserve
   Claude/Codex behavior, project-owned oracle scripts and the 0/1/2 gate.
3. Refuse public `--host copilot` autonomous launch/resume with a structured
   `env_error`, before subprocess calls or target writes. Use output version 2
   and explicit backend identity; unavailable spend/context are `null`, not
   zero. Neither zeroing flags nor `--resume-anyway` enables an unsafe run.
   Existing Claude version-1 behavior is unchanged.
   New Claude state carries additive backend identity. Legacy unmarked version-1
   state retains the historical Claude interpretation for compatibility; the
   September prototype did not persist a discriminator, so its origin cannot
   always be recovered. Do not claim universal recovery or migrate that state.
4. Do not make a refusal-only path count as native-loop completion. Keep
   native loop, backend-safe checkpoints, planner/heartbeat propagation,
   independent native authoring, frozen text/vision scoring and per-turn
   continuation separately tracked and incomplete. No silent provider fallback,
   automatic approved-config migration, or permission escalation.
5. An owner decision on an enforceable native budget contract is required
   before enabling native autonomy. Live output/error/tool/model/attachment
   evidence is separately required for each authoring or judging consumer.
   Existing API, Claude CLI and advisory subagent meanings do not change.

This adds a current support policy; it does not amend the Accepted ADR-0038 or
closed spec 032. Their September findings remain historical provenance.
The decision is not approval of the still-proposed full backend design.

## Consequences

**Becomes easier:**
- Installed helper commands work from clean consumer directories.
- An unsupported host fails without creating state or billing a model call.

**Becomes harder:**
- Full native-loop parity remains blocked on a genuine capability/owner decision.
- A successful install or static hook check cannot stand in for native runtime proof.

## Assumptions

None for the supported paths. Model-command, image-ingestion, effective
read-only tools and per-turn continuation remain unverified native capabilities,
not claims of delivered parity.

## Kill criteria

Revisit the refusal when an executed native contract proves the requested
guarantees, or the owner accepts a separately recorded budget policy.
Do not infer that contract from the presence of a limit flag.

## Open questions

Which enforceable budget unit and overrun policy, if any, will the owner accept
for Copilot-native autonomy? Full native parity cannot be declared resolved
without that answer and the remaining runtime evidence.

## Re-baselining manifest and coverage floor

The new CLI help/limits evidence is authoritative for this follow-up, not the
September invocation prototype. The authority-bearing classes were inspected
at the following bounded granularity:

| Class | Read and disposition |
|-------|----------------------|
| Decisions | ADR-0002/0004/0012/0021/0027/0037/0038: preserve records; this ADR adds the current capability boundary. |
| Specs | Closed 032 and all its slice goals/criteria: preserve. Draft commit `230baa74` delivery, guarded-execution and evaluation slices: translate remaining scope into 033's incomplete/deferred entries. Other specs are excused: no host-contract change is proposed for their historical behavior. |
| Live docs | README, architecture and product vision: rewrite current Copilot support claims; preserve monetary/evidence principles. Workflow and conventions: no changed lifecycle/convention. |
| Skills | Agent-loop and scaffold-init: retrofit in spec 033. Oracle-hook, eval-authoring, content/design fidelity: retain current transport meanings, make unsupported native scope visible. Other skill bodies remain generated without host-name substitution. |
| Primers | No root CLAUDE.md or AGENTS.md exists; no primer mutation. |
| Generated packages/releases | Regenerate all three hosts, run existing manifest/install/drift and zip gates; runtime-only packages remain free of Jig machinery. |

This is a targeted corpus read, not a claim of exhaustive semantic coverage.
Dynamic/external consumers and native CLI runtime semantics remain a residual.
No closed record is amended, re-verified or superseded by setup.

## Verification

[Spec 033](../specs/034-copilot-installed-runtime/spec.md) owns the supported
installed workflow and the fail-closed launch boundary. Its native follow-up
entries preserve incomplete requirements rather than disguising them as DONE.
