---
status: DONE
kind: feature
dependencies: [036-01, adr-0044, adr-0045]
last_verified: 2026-10-20
frame_review: true
arch_review: true
---

## Slice 036-03 - static-source-contract-app

**Goal:** Consume an independently approved finite source contract, observe a
separate immutable application snapshot, and report named failures/refusals
through the ordinary required gate. This is not a whole-view fidelity or
application-completion verdict.

**Publication cleanup (2026-10-22):** At the owner's explicit request,
application-specific examples, identities and proof narratives have been removed
from this export, and their dedicated proof documents have been deleted.
Exact originals were archived privately before editing. This is a reduced
publication record, not the original reviewed or hash-bound document.
The historical lifecycle status is retained; no new evaluation, approval or
claim of current-file identity under a historical hash is made. Generic
implementation behavior, source policies, required checks and independent
synthetic/control tests are unchanged.

**DoR:**
- Keep source authority separate from application observation policy.
- Pin the approved `vellum-confirmed-source/0.2` / `static-css-subset/1`
  input and use identity-only source inspection, not recapture.
- Independently review exact APP normalizers, bindings, inventory, output
  closure and runtime before freeze/install.
- Review framing/readiness and independently approve a separately authored
  positive control before its result is produced.

**Acceptance Criteria (generic contract retained):**

1. **Finite inventory and independent observations.** Every approved required
   ID occurs exactly once. Source targets remain separate from captured APP
   observations. No application-specific runtime signature, source HTML
   substituted for APP, or source-only acceptance reported as APP success.
2. **Explicit APP interpretation.** A separately versioned finite computed
   family grammar preserves named/generic identity, case and fallback order.
   Source primitives, facts, comparisons, units and tolerances stay unchanged.
   Unknown grammar/escapes/units, missing policy, duplicate/extra/omitted IDs
   and unconfirmed bindings refuse. Expected text/style under test is not
   an acquisition prerequisite. Raw DOM text is not pixel or face evidence.
3. **Immutable snapshot delivery.** Independently manifest inputs, copy recipe,
   outputs and selected delivery. Verify every browser-loaded response body.
   Refuse unlisted/external/mutated resources, redirects, service workers,
   unsupported transport and candidate/delivery drift. Backend provenance is
   not backend authenticity; a URL or git label is not byte closure.
4. **Discriminating installed gate.** Observed contradictions and known
   absence/hidden/fully paint-clipped bindings fail (1); ambiguity, unavailable
   acquisition and unsupported properties refuse (2). Keep independent known
   contradictions beside unknowns. Required FAIL/UNKNOWN veto completion,
   including at threshold zero. A deterministic fraction is a measurement
   diagnostic, never visual/model quality.
5. **Independent positive control.** A separately authored control with its
   own approved source and pre-result APP policy can pass through the same
   installed gate. Mutations fail/refuse as typed; exact restoration restores
   the control. No fabricated approval or receipt.
6. **Preserved output and pure readback.** Use existing command/refusal/
   result-artifact and required-policy seams, not a registry/controller/scoring
   framework. Immutable UUID/nonce-bound output closes source/policy/runtime/
   evaluator/build/delivery/response identities, raw facts, all constraints,
   reasons and residuals. Generic output-reference validation and producer
   currentness checks preserve the original verdict without capture,
   comparison or rescoring.
7. **Honest boundaries and delivery.** Preserve ordinary install/uninstall,
   draft refusal, host packaging and mutation controls. Existing Jig input
   restrictions remain nonclearance for unsupported formats, not permission
   to relabel artifacts or change its allowlist. Dynamic data, pixels,
   interactions, actual font face, backend authenticity and full-app/Jig
   completion remain outside this finite contract.

**DoD:**
- [x] Generic observer/snapshot implementation and independent regression tests.
- [x] Required independent reviews, reconciliation and ordinary lifecycle gates
      recorded historically; this cleanup is not a replacement review.
- [x] Official host projections and public generic walkthrough.
- [x] [Ready-for-review delivery](https://github.com/ramboz/servo/pull/47)
      remains unmerged.

## Assumptions and kill criteria

Repeatable observations require closed local resources and explicit bindings.
Fixture-backed bodies do not establish live backend truth. Stop when exact
policy authority, runtime/input/output closure or independently approved
positive control is missing. Do not turn a witness for the expected value
into an acquisition guard, relax goals/tolerances, reuse foreign observations
or treat a static fraction as whole-view completion.

### Deviation log

- Reused ordinary generic required-policy and output-reference seams.
- Kept explicit APP grammar separate from source normalization.
- Atomic per-required-ID settlement ignores unrelated activity without
  hiding changes to required values or correspondence.
- Effective element/text-parent visibility, applicable clips and own-box
  versus contents suppression are distinct. Unsupported paint remains UNKNOWN;
  no general CSS renderer, pixel engine or quality model was added.
- [Bug006](../../bugs/006-required-pin-drift-duplicate-inventory.md) aligns
  pin-preflight authority before interpreting unavailable component evidence;
  it does not posthoc-deduplicate results.
- The recurring direct ownership/closure test remains the documented
  nonblocking [refinement follow-up](../../refinement-todo.md#static-app-pure-reader-needs-a-recurring-direct-ownershipclosure-regression).
  Mocked forwarding is not that missing direct regression.

### Reconciliation sweep

- Generic architecture, walkthrough and host packages retain the same behavior.
- Application-specific publication material was removed, not pseudonymized or
  converted into synthetic evidence. Historical originals and private runtime/
  pilot/worktree data remain preserved; current edited exports are not rebound.
- No convention, source approval, oracle, policy, comparison, model setting or
  accepted architectural decision was relaxed by the cleanup.
- Regional036-02 remains untouched and open. Unsupported downstream integration
  is not claimed complete. No merge is authorized.

### Close-out (post-DONE)

- [x] Preserve generic functionality and synthetic/control coverage.
- [x] Keep downstream/full-quality limits and the explicit test follow-up.
