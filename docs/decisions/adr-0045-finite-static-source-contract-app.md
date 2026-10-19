---
status: Accepted
dependencies: [adr-0044]
last_verified: 2026-10-19
frame_review: true
---

# ADR-0045: Finite static-source-contract APP evidence

## Status

Accepted (2026-10-19)

## Context

Real design inputs need application observations without pretending a small
static contract proves visual quality. Approved10 carries twenty source facts
under `vellum-confirmed-source/0.2`, while the closed card pilot consumes
`vellum-design-input/0.1-pilot`. Changing that pilot or silently widening its
normalizer would change an accepted contract.

An executed 2026-10-19 identity-only `confirmed_source.inspect()` probe accepted
approved10 input SHA-256
`385f73c2d2736c316d170b1b74eeb23ad891d1556745c3e3e0df7ecaded52eef`
and all twenty IDs. A separate frozen-runtime probe launched Chromium
156.0.8078.4 without changing its environment. These establish prerequisite
identity/availability, not APP matching. `confirmed_source.py:415-473` checks
identity/closure; `:512-515` additionally rerenders source and therefore is not
a pure consumer readback API.

## Decision Options Considered

### Option A: Extend the accepted card/source v0 grammar in place
- **Pros:** Fewer apparent versions.
- **Cons:** Reprices accepted C0 semantics and risks relabelling unsupported
  source inputs. A source package is not an APP observer.

### Option B: Separate finite APP observation policy over existing generic seams
- **Pros:** Explicit source/APP ownership, truthful mismatch/refusal, no second
  evaluator controller or model-quality claim.
- **Cons:** Requires separate reviewed APP approval and exposes current Jig
  0.2 incompatibility instead of manufacturing clearance.

### Option C: General browser/backend provenance or pixel-fidelity framework
- **Pros:** Could address broader future applications.
- **Cons:** Unsupported authority and scope; unnecessary for this static
  consumer experiment. Backend/data identity and visual quality stay residual.

## Recommended Decision

Propose B, with `static-source-contract-app/1` policy and a separate schema1
`static_source_contract_evidence` output. The exact
[protocol](../specs/036-deterministic-design-evidence/static-app-contract.md)
names the APP family grammar, policy fields, output-reference and pure
readback contract. Source facts/normalizers and accepted C0 remain unchanged.
Unquoted supported generic tokens are correctly typed; quoted generic names
remain named, fallback order and named case/quoted spacing remain significant.
Unsupported syntax refuses, not a guessed family or actual-face match.

The APP is a separately declared immutable multi-resource local snapshot,
including real frozen API response bodies where needed, served only on
read-only loopback. Its output is compared with independently hashed selected
delivery. This proves snapshot delivery, not a backend or arbitrary HTTP app.
All source inventory members remain required ordinary commands; the native
pass fraction is only a static measurement diagnostic. Overall preserved
required-gate verdict, not a fraction or source-only acceptance, governs
this bounded contract.

Settlement observes the approved required properties plus correspondence and
visibility in atomic DOM snapshots. Unselected counters/pulses and unrequired
root-height changes remain residuals, not hidden readiness conditions.
Instability in a required observation still refuses. Reusing a whole-card
descendant-stability walk for this finite APP inventory is not the chosen
boundary.

Provisional local ADR number; no main publication or acceptance is implied.
Engineering direction approval is not exact-policy/pre-result approval.

## Consequences

**Becomes easier:**
- Repeatable named real-APP declaration mismatches and honest refusal.
- Generic gate output-reference readback without capture or re-scoring.

**Becomes harder:**
- App bindings, effective policy and positive fixture need explicit independent
  pre-result review. Unclosed backend/full-view/Jig gaps remain nonclearance.

## Assumptions

- The unchanged real APP can be measured repeatably from the closed snapshot;
  acquisition/settlement and actual installed controls must prove this.
- Exact APP policy and separately authored positive fixture will receive
  independent pre-result approval; source approval is insufficient.

## Kill criteria

- A role witness requires the same expected text/style under test to acquire
  the observation, hiding legitimate contradictions.
- Snapshot preservation requires changing source APP/design or inventing data.
- Success requires relabelling 0.2, bypassing required policy or treating the
  static fraction as whole-view/visual-quality/completion evidence.

## Open questions

Exact-policy acceptance, approved independent positive-control inputs and
downstream Jig compatibility remain separate gates. No pixel engine or
model-quality policy is selected here.
