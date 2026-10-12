---
status: Accepted
dependencies: [adr-0005, adr-0024, adr-0034, adr-0039]
last_verified: 2026-10-12
frame_review: true
---

# ADR-0040: Freeze explicit native-default decoding for Copilot judges

## Status

Accepted (2026-10-12)

## Context

Copilot judges need an explicit frozen policy for controls the CLI cannot set.

The retained [complete CLI help](../specs/033-copilot-installed-runtime/copilot-contract.txt)
on 1.0.96-2 exposes commanded model and attachment flags, but no temperature or
max-token flag. Existing generic/content/design configurations seed numeric
controls; their API consumers apply those controls. Their Claude CLI transports
have existing, documented API-only numeric-control semantics; this decision does
not rewrite those historical meanings.

Spec 033-05/06's first frame critique correctly blocked a positive native
scoring claim with undefined "required controls." Rejecting unsupported numeric
controls is safe but does not by itself deliver a supported positive path.
Successful numeric output alone is not proof that decoding controls were honored.

## Decision Options Considered

### Option A: Silently ignore native temperature/max_tokens
- **Pros:** Small diff; old config shapes work.
- **Cons:** Misrepresents the frozen judge definition. Rejected.

### Option B: Call all native scoring unsupported
- **Pros:** Safe while there is no explicit judge contract.
- **Cons:** Excludes model-commanded native scoring even when users deliberately
  accept a defined native-decoding policy. Valid interim refusal, not the target.

### Option C: Freeze a deliberate native-default policy and exact CLI version
- **Pros:** Describes the controls actually used, retains hashes/human approval
  and makes the different transport policy visible.
- **Cons:** Numeric decoding is not controllable; CLI/backend default decoding
  can be stochastic even at the same CLI version. Chosen only for explicitly
  created, reviewed and frozen native judge configurations.

## Recommended Decision

1. Native frozen judges require `judge.transport: "copilot"`,
   `judge.decoding_mode: "native-default"`, a commanded non-`auto` model and
   `judge.runtime_version` matching the executable queried with auto-update
   disabled. This freezes the deliberate use of native defaults, not numeric
   parameters that the host does not expose. The CLI version is a compatibility
   bound, **not** proof that server-side decoding defaults never change.
2. A native config containing `temperature` or `max_tokens` is rejected
   explicitly. Native emit/scaffold requires the deliberate decoding-mode choice
   and rejects explicit numeric-control arguments; it does not carry API defaults
   into a supposedly native definition.
3. Existing approved API/CLI/subagent artifacts remain untouched. Switching
   transport/model/decoding/version requires ordinary review, human approval and
   re-freeze. Selecting a new transport alone cannot override a frozen artifact.
4. Preserve reference/rubric/config hashes, sampling count, confidence lower
   bound, thresholds, manifest installation and ledger policy. The transport
   supplies independent judge replies, not an alternative scoring policy.
5. Query the exact runtime version before native scoring; mismatch is
   `env_error`. Invoke the configured model, never `auto`, with intended prompt
   input, effective tool restrictions and time bounds. Do not accept a subagent's
   self-reported identity as pinning. Auth/invocation/error/malformed-score
   failures refuse without fabricated/injected scores or provider fallback.
6. Vision requires real candidate and reference image attachments and an
   executed image-sensitive proof under a commanded vision model. Text success
   or attachment flag acceptance alone is insufficient.
7. Authoring is separate, attended and candidate-only. Expansion/review use fresh
   independent native calls, retain human per-AC authority and do not claim a
   frozen score or monetary guarantee from the authoring model choice.

No change to ADR-0039's hard-budget native autonomy refusal. This new choice
requires explicit artifact-level consent; it is never an automatic migration.

## Consequences

**Becomes easier:**
- Consumers can deliberately create a native judge whose definition is honest.
- Unavailable numeric controls and runtime drift have precise failure outcomes.

**Becomes harder:**
- Every native judge configuration must opt into native defaults and normal
  human approval/freeze; old API defaults cannot be reused as if enforced.
- A CLI update requires review/re-freeze. Backend default variability remains,
  so statistical evidence is retained rather than promising deterministic scores.

## Assumptions

Fresh native calls can command effective read-only/no-tool behavior and the
requested non-auto model. Native vision can ingest both images. Spec 033 requires
live evidence before those respective consumers become complete.

## Kill criteria

If a native invocation cannot command the frozen model/version/input contract,
or effective restrictions cannot be proved, keep that consumer unavailable.
If host-default variability invalidates the evaluation's accepted statistical
policy, re-review the component; do not substitute another judge or fabricate
success. Exact CLI version alone never guarantees server-side decoding stability.

## Open questions

None for the explicit policy. The native output/tools/image/model capabilities
are implementation prerequisites requiring executed evidence, not presumed facts.

## Verification

Spec 033-04/05/06 owns candidate authoring, frozen text and frozen vision.
Their first failed frame verdict remains part of history; subsequent readiness
needs a passing frame critique against this explicit native policy.
