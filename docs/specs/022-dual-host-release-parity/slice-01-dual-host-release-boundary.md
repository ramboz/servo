---
status: DONE
dependencies: [007-05, 009-02, 010-04, adr-0028]
last_verified: 2026-07-12
arch_review: true
code_health_review: true
frame_review: false
---

## Slice 022-01 — dual-host release boundary

**Goal:** A maintainer can install Servo natively in Claude Code or Codex and
publish one verified artifact per host through the same automated release
mechanism Jig uses.

**Acceptance Criteria:**

1. Root Claude and Codex manifests declare the same release-managed version.
2. One deterministic command generates committed, runtime-only
   `hosts/claude` and `hosts/codex` packages; a read-only `--check` fails with
   actionable paths when either package drifts.
3. Claude's root marketplace pointer resolves to `hosts/claude`; Codex's
   committed marketplace resolves to `plugins/servo`.
4. Codex skill rendering uses `${PLUGIN_ROOT}` for plugin-local helpers without
   falsely renaming genuine Claude-only runtime behavior.
5. CI runs the full suite at the Python floor/latest bracket, lint, manifest
   coherence, host-package drift, and install-surface verification; one
   repository command runs the same named gates locally in the same order.
6. Release-please synchronizes all four manifests. A created release builds,
   smoke-tests, and uploads `servo-claude-v<version>.zip` and
   `servo-codex-v<version>.zip`, with an explicit compatibility note for the
   deprecated Claude alias.
7. README keeps the public path compact and marketplace-first for both hosts,
   followed by fresh-session project setup through `/servo:scaffold-init`.
   CONTRIBUTING owns local checkout, generated-package, verification, and
   release detail. Architecture, product vision, roadmap, ADR index, and spec
   board agree with that boundary and with Claude-specific limitations.
8. Spec 008 is shown as complete/non-blocking in next-release overview docs,
   while its parallel-owned spec and implementation files remain untouched.

**DoD:**

- [x] Focused packaging, manifest, release, CI, and docs guards pass;
      consolidated install gate passes 106 tests.
- [x] Full pytest suite and ruff pass (1,526 tests; pinned Ruff 0.15.17 clean).
- [x] Both host packages regenerate without drift.
- [x] Both release archives build reproducibly and pass exact-inventory,
      byte-coherent host smoke tests; real Claude validation and an isolated
      Codex install/discovery probe also pass.
- [x] Superseding compliance, craft, architecture, code-health, and
      reconciliation reviews pass after the maintainer-requested correction.
- [x] Deviation log and reconciliation sweep are re-recorded after those
      reviews.

**Anti-horizontal-phasing check:** The slice ends with two installable plugins
and two publishable artifacts; it is a complete release boundary, not a builder
or documentation phase in isolation.

### Deviation log

- **One-cycle legacy alias.** The new primary artifacts are
  `servo-claude-v<version>.zip` and `servo-codex-v<version>.zip`. The former
  `servo-v<version>.zip` remains for one release as a byte-identical Claude
  alias, matching Jig's gentle migration rather than breaking existing links.
- **Codex rendering is semantic, not a global host rename.** Staged Codex
  `SKILL.md` files rewrite plugin-root paths and normalize skill frontmatter so
  Codex applies the `servo:` namespace exactly once. Genuine Claude runtime
  requirements (`claude -p`, `/goal`, Claude `Stop` hooks) stay explicit.
- **Codex discovery metadata is bounded without semantic truncation.** Each
  skill's first descriptive paragraph must fit within 1,024 characters or the
  host build refuses with an actionable error. Eval-authoring now carries a
  deliberately concise positive and Do-NOT-route boundary. A post-rebase
  isolated Codex 0.133.0 install discovered all 11 current skills, including
  `servo:eval-authoring`.
- **Remote and local Codex paths differ deliberately.** The root marketplace
  enables `codex plugin marketplace add ramboz/servo`; a checkout or extracted
  archive must use an absolute filesystem path because Codex interprets a
  relative path as a GitHub shorthand.
- **Adjacent release blocker fixed.** The full suite exposed content-fidelity
  leaking `PermissionError` when a generator command cannot start. Its contract
  requires `EnvError`; `gather_text` now normalizes launch-time `OSError`, and
  the existing honesty regression passes.
- **Spec 008 completed separately.** This release pass updates live overview
  docs to reflect the shipped goal→criteria/eval-authoring capability, while
  leaving spec 008's lifecycle and implementation files untouched.
- **Public install boundary corrected after maintainer review.** README now
  documents only remote marketplace install followed by fresh-session project
  setup through `/servo:scaffold-init`. Checkout, generated-package, archive,
  and compatibility details live in CONTRIBUTING/architecture. The correction
  also added `scripts/ci_check.py` with a code-owned pinned Ruff command and a
  workflow-parity regression, avoiding reliance on ignored local state.

### Reconciliation sweep

| Surface | Disposition | Result |
|---|---|---|
| README / CONTRIBUTING | `updated` | README follows the shared dual-host plugin narrative—why, capabilities, principles, start/install, extension points, verification, getting started, contributor structure, status—while remaining marketplace-first. Local mechanics and release detail live in CONTRIBUTING. |
| Architecture / product vision / roadmap | `updated` | Product vision owns purpose, audience, principles, and direction; architecture owns phase/skill mapping, topology, contracts, artifacts, and guardrails; roadmap owns live status and sequencing. Historical ADR/spec prose remains immutable. |
| CI / release workflows | `updated` | Python 3.9+3.12 bracket, Ruff, manifests, focused install, and drift use the same ordered roster in ci.yml and `scripts/ci_check.py`; release-please bumps four manifests and publishes two smoke-tested assets plus the compatibility alias. |
| Package contracts | `updated` | Root Claude and Codex marketplace pointers plus packaged Codex marketplace validated; generated host trees current. |
| Verification | `updated` | Post-rebase full pytest (1,526 tests), 106-test install gate, Ruff, manifest validator, drift guard, direct local/workflow command parity, hostile-archive path checks, generated eval-authoring packages, real Claude validation, isolated Codex install/discovery, and diff check pass. |
| Lightweight decisions | `no-op` | No out-of-spec product/UI/string decision; package topology is captured by ADR-0028. |
| Conventions | `no-op` | Contributor regeneration is documented in CONTRIBUTING and enforced mechanically; no standalone `docs/conventions.md` surface exists. |
| Inbox triage | `no-op` | Memory summary reports zero inbox items; no `docs/inbox.md` exists to reconcile. |
| Primer hygiene | `no-op` | No root `AGENTS.md`/`CLAUDE.md` or scaffold primer is present; the status board carries the release close-out note. |
| Memory-sync | `no-op` | No new term/learning beyond the ADR, spec, and deviation log. Team-check surfaced the pre-existing optional `people.md` nudge for five contributors; left for maintainer choice rather than changing team-memory policy here. |
| Closed-spec drift | `updated` | Live overview prose and status-board Notes were corrected inline; immutable historical specs/ADRs were not rewritten. |
| Use-case coverage | `no-op` | `workflow.py coverage` reports that the breadth layer is not adopted (`docs/product-vision.md` has no `## Use cases`). |
| Deferred decisions | `no-op` | Codex project-local scaffolding and native replacement of explicitly Claude-only runtime primitives remain explicit non-goals, not hidden follow-ups. |
