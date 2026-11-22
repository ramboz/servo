---
status: DRAFT
skill: spec-oracle
use_cases: []
---

<!-- jig self-defining vocabulary (soft, forward-only): expand each acronym on first use and link the term to docs/memory/glossary.md (or jig's lexicon). See docs/workflow.md "Self-defining vocabulary". -->

# Spec 045: Base-anchored freeze

> Implements [ADR-0051](../../decisions/adr-0051-base-anchored-freeze.md)
> (Proposed). Investigation record:
> [R-002](https://github.com/ramboz/jig/blob/main/docs/research/R-002-claude-code-verification-assessment.md).
> **Status: recorded, not yet built** — reserved alongside the ADR so the
> decision has a home for its build; the ADR must be Accepted before 045-01
> moves past DRAFT. Sibling for jig's gates:
> [jig ADR-0068](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0068-base-anchored-gate-definitions.md)
> / [jig spec 123](https://github.com/ramboz/jig/blob/main/docs/specs/123-base-anchored-gate-definitions/spec.md)
> (not merged yet).

## Overview

"If a change can modify the check that judges it, the check is broken." Servo's
freeze today reads the values it checks against from the same working tree the
runner edits, so a run that relaxes a check and rewrites its recorded hash, or
deletes `--enforce-freeze` from the spliced block in `oracle.sh`, is scored as
if nothing happened (ADR-0051 Context, facts 1–2).

This spec moves the **expected values** to the base commit for every tracked
gating artifact, in three slices:

- **045-01** — the spec-oracle freeze (`checks.py --enforce-freeze`) reads its
  approval record from the base copy of `checks.json`. It also introduces the
  anchor resolver the other two slices reuse.
- **045-02** — unattended scoring refuses when `oracle.sh` differs from its base
  copy, which pins the threshold default, component weights and list, and the
  spliced score functions (including the freeze flag itself).
- **045-03** — eval-authoring components' `validate_freeze` reads its frozen
  definition from the base copy of the tracked spec-dir config; preset evals
  with no tracked definition are stamped as worktree-anchored.

**Anchor resolution (all slices).** A configured base (`SERVO_FREEZE_BASE`, or
`loop.py --freeze-base`), else the merge-base of `HEAD` with the default branch
from local refs (`origin/HEAD` → `main` → `master`), else no anchor. No network
call in the score path. Every result names its anchor:
`freeze_anchor: {kind: base, ref, source}` or `{kind: worktree, reason}`.

**What this means for the workflow.** The base copy is authoritative when it
exists. To loop on a branch against an anchored oracle:

1. Plan, install and approve the oracle, and **commit the approval on the base**
   (in practice, land the spec and its approved oracle before the
   implementation branch), or
2. pass `--freeze-base <ref>` naming a reviewed commit that carries the
   approval. The choice is recorded in every result, so it is visible in review.

An oracle that exists only on the branch still runs, anchored to the worktree,
and says so on stderr and in its evidence. An approved oracle on the base that
the branch has modified is refused.

**Non-goals.**
- A sandbox. Bypassing the anchor needs a git ref write, which the runner is told
  not to do (`agents/runner.md:92`) and the reflog records; it is not prevented.
- Changing *what* is hashed (ADR-0022, ADR-0005 clause 2 stay as they are).
- Untracked `.servo/` copies (installed `score.py` / `fidelity_eval.py`,
  `install.json`, `required-policy.json`): no base copy exists; they stay
  tripwire-only and are named as the residual in `docs/architecture.md`.
- Version skew of the referenced, unvendored `checks.py`
  (`docs/refinement-todo.md:719`: "a subsequent servo plugin upgrade that changes
  `checks.py`'s behavior silently changes what an *already-approved* oracle
  runs"). Plugin files have no base copy; that entry stays open. A *vendored*
  `checks.py` is tracked and does get anchored (045-01).
- Test files the checks invoke. They are code under change, not gating config;
  required mode already pins them through `assertion_closure`
  (`skills/quality-gate/required_runtime.py:342-365`).
- Binding evaluation evidence to commits — that is
  [spec 046](../046-commit-bound-eval-evidence/spec.md), which records this
  spec's `freeze_anchor` when present.

## Assumptions

<!-- Spec 064-02 / ADR-0020 — grounding-by-probe (risk-gated). -->

- **Probed 2026-11-21 (code read):** the spec-oracle approval record lives
  inside the `checks.json` it protects (`skills/spec-oracle/oracle_overlay.py:508-522`);
  `freeze_violation` reads its expected values from that same file
  (`skills/spec-oracle/checks.py:929-970`); the spliced fragment carries
  `--enforce-freeze` as plain text (`oracle_overlay.py:79-92`); nothing pins
  `oracle.sh` on the ordinary path (`skills/agent-loop/loop.py:1872` only checks
  it exists; `skills/quality-gate/gate.py` hashes nothing); eval-authoring
  freezes a tracked copy under `<spec_dir>/eval/` and copies it into the
  git-ignored `.servo/<component>/` without recording where it came from
  (`skills/eval-authoring/eval_authoring.py:1375-1381`, `:1404-1446`); the
  design-eval and content-fidelity presets keep their frozen config only under
  `.servo/` (`skills/design-eval/design_eval.py:82`,
  `skills/content-fidelity/content_fidelity.py:69-70`).
- **Probed 2026-11-21 (git 2.43, scratch repo):** `git show <rev>:./<path>`
  reads a repo-relative path from a subdirectory target and from a linked
  worktree. A missing path and an unknown rev both exit 128, so the resolver
  verifies the rev before testing the path.
- **Unverified:** targets resolve a default branch from local refs.
  `skills/heartbeat/heartbeat.py:471-473` records that `origin/HEAD` is unset on
  many clones; `main`/`master` covers the common case, and anything else falls
  back visibly.
- **Unverified:** CI checkouts that run servo fetch the base commit. A depth-1
  clone falls back to the worktree anchor; 045-01's stderr line makes that
  visible.

## Decomposition

SPIDR (Spike / Paths / Interfaces / Data / Rules — see the jig glossary):

- **Spike:** none needed. The git mechanics were probed (Assumptions) and the
  decision is ADR-0051's.
- **Interfaces** (the split axis): one slice per place a freeze is verified —
  `checks.py --enforce-freeze` (045-01), the gate and its unattended callers
  (045-02), the shared eval harness `validate_freeze` (045-03).
- **Paths** (inside each slice): base copy present and matching / present and
  differing / present but not approved / absent / no anchor at all.
- **Data:** tracked artifacts are anchored; untracked `.servo/` copies are
  stamped and named as the residual.
- **Rules:** the base copy is authoritative when present; the fallback is
  explicit and recorded.

**Anti-horizontal-phasing.** 045-01 alone stops a branch or a loop run from
relaxing an approved spec-oracle and rewriting its hash. 045-02 alone stops a run
from editing its own `oracle.sh`, and closes the `--enforce-freeze` deletion
bypass that 045-01 leaves open. 045-03 alone does the same for judged eval
definitions. Each ships a refusal a user can observe.

## Slices

- [045-01 — spec-oracle-base-anchor](slice-01-spec-oracle-base-anchor.md) — anchor resolver + spec-oracle freeze reads its approval record from the base copy; explicit worktree fallback.
- [045-02 — oracle-sh-base-anchor](slice-02-oracle-sh-base-anchor.md) — unattended gate calls refuse an `oracle.sh` that differs from its base copy; threshold source recorded.
- [045-03 — eval-freeze-base-anchor](slice-03-eval-freeze-base-anchor.md) — eval-authoring definitions anchored to their tracked base copy; presets stamped worktree-anchored.
