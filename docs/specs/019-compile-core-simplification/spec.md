---
status: IN_PROGRESS
dependencies: [001, 002, 003, 006, 015, adr-0021, adr-0022, adr-0023]
last_verified:
---

# Spec 019 — compile-core-simplification

> Simplify and decouple servo's Compile core, driven by findings from an external
> dogfood (cwv-workbench spec 015 ran 6/6 slices through servo's Compile + gate).
> Implements [ADR-0021](../../decisions/adr-0021-oracle-first-agent-loop-optional-consumer.md)
> (oracle-first / agent-loop optional), [ADR-0022](../../decisions/adr-0022-freeze-against-parsed-acs.md)
> (freeze against parsed ACs), and [ADR-0023](../../decisions/adr-0023-colocate-durable-spec-oracle-artifacts.md)
> (co-locate durable artifacts), plus the pure refactors those findings exposed.

> **Status: SPIDR-split (2026-07-02).** All three ADRs are now Accepted. The
> five vertical slices below have been split into `slice-NN-*.md` files
> (`docs/specs/019-compile-core-simplification/slice-01..05-*.md`) — this
> `spec.md` overview retains the original goals/notes as an index; each slice
> file carries the authoritative ACs, DoR, and grounded implementation notes.
> Closely related open items are already tracked in `docs/refinement-todo.md`
> (this repo) and the cwv-workbench dogfood memo.

## Why this spec

The dogfood exercised the Compile core hard and surfaced three classes of issue:
a **coupling** bug (the freeze is tied to the raw spec file, so a living-document
consumer trips `spec_oracle_stale` on every status transition), an **artifact
layout** problem (durable spec-oracle artifacts live away from the spec and the
~39 KB `checks.py` runner is copied per overlay — 6× in the run), and
**duplication/over-engineering** in the scoring path (a weighted-composite layer
that no real oracle used; suitability and spec-oracle each parse the ACs
separately, and the shared classifier under-recognizes behavioral ACs). The three
ADRs decide the contracts; this spec is the implementation umbrella.

## Goals (provisional)

1. Freeze survives a living-document consumer's lifecycle (no spurious
   `spec_oracle_stale` on a status bump). [ADR-0022]
2. A spec and its durable oracle artifacts live together; no per-overlay
   `checks.py` copies. [ADR-0023]
3. One AC-analysis pass feeds both the suitability verdict and the spec-oracle
   plan, and it recognizes behavioral / negative-behavior ACs. [F3]
4. `agent-loop` refuses loudly when it cannot function and can pass the target's
   permissions; the oracle-as-a-service flow is documented. [ADR-0021, Bugs 001/002]
5. The single-spec-oracle common case has no unused weighted-composite ceremony.

## Vertical slices

- **019-01 — freeze against parsed ACs:** `--enforce-freeze` compares the current
  parsed AC set against the approved one (via the existing `approved_content_hash`
  over `checks.json`) and **drops the raw spec-file hash check**. AC set is
  canonically normalized (whitespace + item order). **AC:** a `status:`
  frontmatter change or an appended deviation-log section on an approved spec does
  NOT trigger `spec_oracle_stale`; editing an AC does. [ADR-0022]
- **019-02 — co-locate durable artifacts + de-dup runner:** move `plan.md` +
  `checks.json` to live with the spec (e.g. `docs/specs/<spec>/oracle/<slice>/`);
  reference a single shared `checks.py` instead of copying it per overlay
  (vendor-copy only for the documented clone-portability path). Migrate the
  existing `.servo/spec-oracles/` layout + install / enforce-freeze path
  resolution. **AC:** no per-overlay `checks.py` copy; `spec-id`s no longer restate
  the spec path; `.servo/` holds only ephemeral state. [ADR-0023]
- **019-03 — unify AC analysis + behavioral-AC recall:** one AC-parse pass emits
  both the `edd-suitability` evaluable/residual split and the `spec-oracle` plan's
  check-family classification (today they parse separately). Improve recall so
  behavioral / negative-behavior ACs ("the lint *fails* when…", "returns…",
  "is excluded…") classify as `command`-checkable instead of `residual`. Tolerate
  interstitial prose between the `**Acceptance Criteria:**` header and the numbered
  list, and warn (not silently return 0) when the header is present but no items
  parse. **AC:** the dogfood's behavioral ACs classify deterministic without hand
  promotion; Bug 003's preamble case yields N ACs, not 0. [F3, Bug 003]
- **019-04 — agent-loop refuse-when-nonfunctional + BYO-implementer docs:** detect
  an errored `claude -p` result (`is_error`/`api_error_status`) and halt with
  `claude_invocation_failed`, not `oracle_plateau` (Bug 001); resolve + pass the
  target's `.claude/settings.json` (or `--permission-mode`) to the runner so a
  pre-authorized target runs unattended (Bug 002); refuse loudly when nested /
  permission-restricted. Document the oracle-as-a-service / external-driver flow on
  the skill surface. **AC:** an auth/permission failure surfaces a distinct
  terminal reason; the skill docs describe "Compile → your driver edits →
  `quality-gate` judges". [ADR-0021, Bugs 001/002]
- **019-05 — collapse the unused weighted-composite for the single-oracle case:**
  the default `oracle.sh` contract for a lone spec-oracle component is "checks +
  pass threshold"; the `COMPONENTS=("name:weight")` weighted-average machinery
  becomes opt-in for genuinely heterogeneous multi-component oracles. **AC:** a
  single-spec-oracle install has no weight/awk-average ceremony; multi-component
  weighting still works when explicitly used.

## Notes

- Every real oracle in the dogfood was a single component at weight 1.0,
  threshold 1.0 — motivating 019-05.
- 019-01/02 are the load-bearing decoupling; 019-03 fixes the recurring F3 recall
  gap in one place; 019-04 closes Bugs 001/002 + ADR-0021's follow-on; 019-05 is
  pure simplification.
