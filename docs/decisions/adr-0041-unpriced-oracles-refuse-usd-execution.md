---
status: Accepted
dependencies: [adr-0005, adr-0012, adr-0039, adr-0040]
last_verified: 2026-10-12
frame_review: true
---

# ADR-0041: Unpriced oracle components refuse USD-bounded execution

## Status

Accepted (2026-10-12)

## Context

Native judged components must not silently bypass a caller's USD budget.

ADR-0005 clause 6 says eval cost counts against the loop ceiling; ADR-0012
composes loop USD outcomes into a whole-heartbeat ceiling. Current heartbeat
(`skills/heartbeat/heartbeat.py:1985-1990`) defaults absent/non-numeric loop
spend to zero. Current loop reads coding-agent spend, not a priced native oracle
ledger. Native Copilot judges explicitly cannot supply a USD conversion.
Enabling native scoring as an installed oracle component without a caller guard
would therefore introduce a known incompatible combination.

This does not amend the historical records or claim to repair older API
accounting. It constrains the newly introduced native components. Standalone,
attended quality-gate/scoring remains useful; it does not promise a USD ceiling.

The existing common `fidelity_eval.register_manifest` installs component names
into `.servo/install.json`. Its three native consumers can expose a deterministic
accounting marker on that same surface rather than forcing callers to scan
opaque oracle shell scripts or guess native billing from configuration paths.

## Decision Options Considered

### Option A: Convert native credits to USD or default missing spend to zero
- **Pros:** Existing callers appear to work.
- **Cons:** Falsifies the budget contract. Rejected.

### Option B: Scan every configuration or inspect oracle shell commands
- **Pros:** Might identify some native scorers without registration changes.
- **Cons:** Dynamic/project-owned shell is not exhaustively inspectable; adds a
  parallel source of truth and false completeness. Rejected.

### Option C: Register unpriced components and refuse bounded execution up front
- **Pros:** Uses the existing installation boundary; no paid model/gate call is
  needed to diagnose a known incompatible monetary contract.
- **Cons:** Marker integrity is project-owned, not a security boundary; older
  callers/opaque custom components do not gain new accounting automatically.
- **Disposition:** Chosen.

## Recommended Decision

1. Native generic/content/design component installation requires an existing
   valid Servo manifest and adds its registered name to optional
   `unpriced_components: [names]`. All names must also be in `components`.
   Native helper/ledgers state `cost_usd: null`, never a fabricated zero.
2. Reinstalling a non-native definition removes only that component's marker;
   uninstall/deregister clears it. Omit the field when empty, preserving old
   non-native manifest shapes. Do not scan or silently migrate historical configs.
   Re-freezing an already-installed component must synchronize this same
   registration: mark before native approval can activate; clear only after
   successful non-native approval. Alternatively refuse native activation until
   registration is repaired. A valid but stale installation marker is not enough.
   Uninstalled standalone definitions are not registered merely by freezing.
3. Loop, goal, background/Routine and heartbeat run/dispatch refuse known
   unpriced components before their first gate/model invocation. Malformed
   marker data fails closed with an actionable accounting error. Do not offer a
   bypass, permit zeroing limits to enable that combination, or silently select
   another judge/provider. Direct programmatic loop/goal launch entrypoints
   enforce the same boundary.
4. Standalone quality-gate/score/authoring remain available without pretending
   to be USD-bounded execution. An owner-approved alternative accounting policy
   or actual enforceable monetary contract is required to enable that combination.
5. The marker is a deterministic installation/accounting record, not proof of
   all possible costs or a security boundary against a modified project oracle.
   Existing API accounting is outside this surgical change; do not claim its
   historical semantics were repaired by adding this native guard.
6. Keep the manifest protocol small. The two standalone orchestration clients
   may locally mirror the bounded marker validator, tested against identical
   protocol fixtures, rather than introducing a subprocess dependency/framework
   or importing another skill's runtime. A third client warrants extraction.

## Consequences

**Becomes easier:**
- Unknown native money is explicit in metadata/ledger and cannot become zero
  through a current USD-bounded orchestration path.
- Consumers get an actionable refusal without funding the oracle first.

**Becomes harder:**
- A native frozen gate cannot currently be used inside a USD-budgeted Servo
  loop/heartbeat, even when its coding agent is Claude.
- Registration and removal must maintain the marker; old callers and arbitrary
  custom oracle code are not automatically upgraded or financially attested.

## Assumptions

The manifest names registered Servo-owned components accurately at execution
time. All supported install/re-freeze/remove paths maintain that correspondence.
It is project-owned like oracle.sh and is not a new security boundary.

## Kill criteria

Revisit the refusal only when the monetary contract is enforceable and accounted,
or an explicit owner-approved replacement policy is adopted. Do not infer that
from numeric scores, native credits or a passing oracle.

## Open questions

Older API-eval cost accounting needs separate diagnosis/owner review if pursued;
this port neither silently weakens its policy nor amends its closed records.

## Verification

Spec 033-08 tests marker validation/removal and pre-dispatch refusals. Native
scoring slices 033-05/06 own actual registration and null native ledger spend.
