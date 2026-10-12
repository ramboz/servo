---
status: IN_PROGRESS
kind: feature
dependencies: [034-02, 034-05, 034-06, adr-0041]
last_verified:
arch_review: true
frame_review: true
---

## Slice 034-08 - unpriced-oracle-budget

**Goal:** Newly installed native judged components cannot silently escape USD
budgets through an otherwise supported Claude loop/heartbeat.

**DoR:**
- ADR-0041 framed and Accepted; native registration exposes one manifest marker.

**Acceptance Criteria:**

1. Native generic/content/design install names appear in optional manifest
   unpriced_components; native helper/ledger cost_usd is null. Reinstall/uninstall
   updates only the affected marker; non-native empty-marker shape stays compatible.
   Already-installed non-native→native re-freeze marks before activation; reverse
   re-freeze clears only after successful non-native approval, or activation
   refuses until registration is repaired. Failed freezes cannot activate an
   unmarked native definition; uninstalled standalone freeze does not register.
2. USD-bounded loop/goal/background/Routine and heartbeat run/dispatch refuse
   registered unpriced components BEFORE any gate/model invocation or launch
   writes. Direct loop/goal/background entrypoints cannot bypass this boundary.
3. Validate marker as a unique list of nonempty component names contained in the
   registered components list. Malformed/incompatible metadata produces explicit
   env_error; no zero-valued limit, resume override or missing-price-to-zero bypass.
4. Standalone attended native quality-gate/scoring remains supported. Existing
   Claude/API defaults and normal manifests stay compatible; no historical
   config/state/record migration or unrelated API-accounting repair.
5. Docs distinguish this guard from native-loop completion and from a security/
   exhaustive-financial boundary over arbitrary project-owned oracle code.

**DoD:**
- [ ] Witnessed red-to-green marker/entrypoint/registration tests pass.
- [ ] Frame, compliance, craft, architecture and reconciliation reviews pass.
- [ ] Existing loop/heartbeat/scoring suites and final full CI clear.

## Assumptions

Project-owned registration accurately names Servo-managed unpriced components
through install/re-freeze/removal; opaque custom oracle code is not exhaustively
classified by this marker.

**Anti-horizontal-phasing check:** A caller gets a safe actionable refusal rather
than funding unpriced native oracle calls inside an apparently USD-bounded run.

### Deviation log (after reconciliation)

1. Added optional registered unpriced marker/null native spend. Native install/
   already-installed re-freeze marks before activation; reverse/removal updates
   only affected entries without altering old empty manifest shapes.
2. Upfront guards extend to direct launch entrypoints and every oracle gateway.
   Initial red138 to green146, compatibility regressions red2 to green4, then
   in-flight activation red20 to green170.
3. Independent compliance found actual child spend discarded and raw Goal/
   Routine gate calls unguarded. Corrected with real outcome persistence and
   opt-in --usd-budget-context on actual self-contained vendored commands.
   Follow-up red53 to green223; combined loop/heartbeat/gate992 tests passed.
4. All generated hosts were refreshed; independent propagation review passed.
   Craft's vacuous goal-summary assertion was replaced with real null composite/
   threshold assertions. Architecture's live reason/marker/flag docs were fixed.
5. Gate checks its already-loaded manifest inline to stay clone-portable. This
   is the justified narrow third-client exception to ADR-0041's extraction nudge,
   not a third full orchestration parser or new runtime dependency. Historical
   API accounting and arbitrary-oracle/security attestation remain excluded.

### Reconciliation sweep

| Surface | Disposition | Rationale |
|---------|-------------|-----------|
| Registry/install/re-freeze/remove | updated | Correct lifetime ordering; null nativeUSD, no silent unknown-to-zero path. |
| Loop/goal/background/Routine | updated | Upfront/direct/per-gateway refusal; actual emitted gate commands carry USD context. |
| Heartbeat run/dispatch/outcomes | updated | Refuse before calls; preserve actual child spend/outcomes, no synthetic predispatch records. |
| Gate contract / standalone scoring | updated | Two accounting reasons/opt-in context; default attended0/1/2 remains compatible. |
| Generated hosts / docs / board / index | updated | Source-owned propagation and precise current accounting bounds. |
| Closed API-accounting records / opaque oracle code | no-op | Not rewritten or falsely financially attested. |
| Full CI / reconciliation | deferred | Final integrated gates and independent reconciliation required before DONE. |
