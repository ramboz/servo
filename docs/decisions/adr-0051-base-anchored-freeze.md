---
status: Proposed
dependencies: [adr-0005, adr-0022, adr-0023, adr-0024]
last_verified: 2026-11-21
frame_review: true
---

# ADR-0051: Freeze verification anchors to the base ref

## Status

Proposed (2026-11-21). Investigation record:
[R-002](https://github.com/ramboz/jig/blob/main/docs/research/R-002-claude-code-verification-assessment.md)
(jig). Implemented by [spec 045](../specs/045-base-anchored-freeze/spec.md).
Sibling for jig's own gates:
[jig ADR-0068](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0068-base-anchored-gate-definitions.md)
/ [jig spec 123](https://github.com/ramboz/jig/blob/main/docs/specs/123-base-anchored-gate-definitions/spec.md)
(not merged yet; numbers provisional).

## Context

The Claude Code team's verification write-up states the principle plainly:
"If a change can modify the check that judges it, the check is broken." Their
review reads its gating config from the base branch, never from the change.

Servo's freeze stores the values it checks against **beside the thing they
protect**, in the same working tree the runner edits:

- **Spec-oracle.** `approve()` writes `approval_status`, `approved_artifacts`
  and `approved_content_hash` into the very `checks.json` it hashes
  (`skills/spec-oracle/oracle_overlay.py:446-522`). `checks.py --enforce-freeze`
  then compares the working-tree file against values read from that same
  working-tree file (`skills/spec-oracle/checks.py:929-970`, `:1048-1054`).
- **Eval components.** `validate_freeze` compares an installed config against
  hashes stored in that config (`skills/_common/fidelity_eval.py:275-299`); the
  installed copy lives under the git-ignored `.servo/<component>/`
  (`skills/eval-authoring/eval_authoring.py:1375-1381`).
- **`oracle.sh`.** On the ordinary path nothing pins it: the `THRESHOLD`
  default (`templates/oracle.sh.template:25`), the `COMPONENTS` weights
  (`:28-30`) and the spliced score functions — including the `--enforce-freeze`
  flag itself (`oracle_overlay.py:79-92`) — are plain text. The loop checks only
  that `oracle.sh` exists (`skills/agent-loop/loop.py:1872`) and that the tree
  is clean *at start* (`loop.py:4447`). Required-policy mode does pin `oracle.sh`
  and the threshold default (`skills/quality-gate/required_runtime.py:432-485`,
  `:740-745`), but against records that also live in the working tree.

`docs/architecture.md:282` is honest about this: the hashes are "tripwires for
honest drift … not a sandbox — a runner that writes arbitrary files could
rewrite both an artifact and its recorded hash." The defense is the
`agents/runner.md:96` instruction plus human approval.

Five facts shape the options:

1. **An in-file integrity value is forgeable by a writer of that file**
   (`checks.py:907-912` says so). A run that relaxes a check and recomputes
   `approved_content_hash` passes the freeze today.
2. **The cheapest bypass skips `checks.json` entirely.** Deleting
   `--enforce-freeze` from the spliced block in `oracle.sh` disables the freeze,
   and nothing pins `oracle.sh` on the ordinary path.
3. **The tracked artifacts already have an anchor outside the working tree: the
   commit graph.** ADR-0023 colocated spec-oracle artifacts with the spec so "a
   spec and its oracle travel together in git/review"
   (`docs/architecture.md:262`); eval-authoring freezes a tracked spec-dir copy
   before installing (`eval_authoring.py:1404-1446`); `oracle.sh` is tracked
   (`docs/refinement-todo.md:516`). Read-only git reads a base copy from a
   linked worktree or a subdirectory target (probed — see Assumptions).
4. **Not everything is tracked.** `.servo/` is git-ignored
   (`docs/architecture.md:261`, `:701`), so installed runtime copies, the preset
   eval configs (`skills/design-eval/design_eval.py:82`,
   `skills/content-fidelity/content_fidelity.py:69-70`), `install.json` and
   `required-policy.json` have no base copy.
5. **The loop never commits.** `agents/runner.md:92` ("Don't commit or push")
   and `loop.py:2186-2187` ("The loop performs no git writes"), so every runner
   edit during a run is uncommitted — out of reach of any committed copy.

## Decision Options Considered

### Option A: Status quo — worktree tripwires plus runner instruction and human approval
- **Pros:** no change; zero workflow cost; catches honest drift (an incidental
  edit to an approved artifact).
- **Cons:** facts 1 and 2 — a run that edits the oracle and its hash, or the
  spliced block, is scored as if nothing happened. The only barrier against a
  deliberate rewrite is a prose instruction, which servo's own record shows
  cannot fail on its own.

### Option B: Base-ref anchoring — expected values read from the base commit (chosen)
For tracked gating artifacts, read the approval record from the copy at a base
ref (`git show <base>:<path>`, read-only) instead of the working-tree copy, with
an explicit, recorded fallback to the working tree when no base copy exists.
- **Pros:** closes facts 1 and 2 for every tracked artifact with no new
  infrastructure — git is already a hard dependency of the loop's brakes;
  matches the post's mechanism directly; oracle changes become ordinary diffs
  against the base that a reviewer sees.
- **Cons:** workflow cost — an approval or install must land on the base before
  a run on a branch can rely on it; covers tracked files only (fact 4); needs a
  resolvable base (shallow clones and unset default branches fall back); still
  not a sandbox (a process that can write git refs can move the base).

### Option C: Sign the approval record with an HMAC key held outside the worktree
Approval signs the frozen record with a keyed hash (HMAC, hash-based message
authentication code); verification needs the key from user config or the OS
keychain.
- **Pros:** covers untracked `.servo/` files too; works without git history.
- **Cons:** the runner runs as the same OS user, so a key in `~/.config` or a
  keychain the scorer can read is readable by the runner — the protection is
  nominal without privilege separation servo does not have. Adds key
  distribution for teams and CI. ADR-0049 reached the same conclusion for
  host-driven campaigns: there is no servo-held secret to anchor to.

### Option D: External approval store (service, pushed git notes, or a forge check/status)
- **Pros:** the anchor genuinely sits outside the change's reach; can carry
  reviewer identity.
- **Cons:** a network dependency in the score path; breaks offline and
  plugin-first operation (`docs/product-vision.md:173-175`); forge-specific;
  heavy for a single-developer target.

### Option E: Read-only mounts or a runner sandbox
- **Pros:** real enforcement — the runner cannot write the oracle at all.
- **Cons:** servo does not own the runner's sandbox; Claude Code, Codex and
  Copilot CLI each have different sandbox models, and macOS/Windows have no
  portable equivalent. Worth adopting opportunistically where a host offers
  it, not as servo's contract.

## Recommended Decision

**Option B**, with six load-bearing constraints. The exact mechanism (resolver
home, field names, environment plumbing) is spec 045's work, under test.

1. **Expected values come from the base copy.** Where a tracked gating artifact
   has a copy at the anchor ref, its approval record — status, recorded hashes,
   and in required mode `approved_required_binding` — is read from that copy.
   The working tree's own recorded values are not consulted. *What* is hashed
   does not change (ADR-0022, ADR-0005 clause 2).
2. **Anchor resolution uses no network.** In order: an explicitly configured
   base (recorded with the result; a configured base that does not resolve is
   an error, not a fallback); else the merge-base of `HEAD` with the default
   branch, resolved from local refs only (`origin/HEAD`, then `main`, then
   `master`); else no anchor. Unlike `heartbeat.py:466-509`, the score path
   never calls `gh`.
3. **Fallback is explicit, never silent.** With no anchor, or no copy at the
   anchor, today's working-tree check runs and every result says so
   (`kind: worktree` plus a reason, and one stderr line). An oracle introduced
   on a branch is therefore worktree-anchored, visibly, until it reaches the
   base.
4. **The base is authoritative when present.** A base copy that is draft,
   stale, or approved with different hashes wins over the branch. Workflow
   implication: **commit the approval on the base before a run on a branch
   relies on it**, or configure the base explicitly to a reviewed commit.
5. **`oracle.sh` is anchored on unattended scoring only.** Servo-owned
   unattended callers (the loop, heartbeat and campaign re-checks, the
   meta-judge) ask the gate to compare `oracle.sh` with its base copy. An
   attended bare `gate.py` run keeps today's behaviour: "The dev's `oracle.sh`
   is theirs" (`docs/product-vision.md:176`).
6. **Scope is stated, not implied.** Tracked artifacts only; untracked `.servo/`
   copies stay tripwire-only. This is still not a sandbox: bypassing the anchor
   now means writing a git ref, which the runner is told not to do
   (`runner.md:92`) and which the reflog records. The guarantee is strongest
   where the base comes from a remote the change cannot write (a CI checkout).

### Relationship to existing ADRs

Nothing is superseded.

- **ADR-0022** (freeze against parsed ACs) — unchanged. It fixes *what* is
  hashed; this ADR fixes *where the expected value is read from*.
- **ADR-0023** (colocated spec-oracle artifacts) — a prerequisite, not amended.
  Colocation is what gives a spec-oracle a base copy.
- **ADR-0005** clause 2 / **ADR-0024** (frozen eval harness) — extended: for
  eval-authoring components, the definition-hash expected values come from the
  tracked base copy; the change lands in the shared harness.
- **ADR-0002** (gate contract) — anchored refusals are exit 2 with distinct
  reasons; the anchor is an additive payload field (clause 2).
- **ADR-0008** / slice 003-07 dirty-tree preflight — complementary: the
  preflight guards the start of a run, the anchor guards the middle.
- **ADR-0049** (campaigns) — the persisted per-item base sha is a natural
  configured base; Option C is rejected here for the same reason ADR-0049 found
  no servo-held secret.
- **ADR-0001** — `docs/architecture.md:282` cites its "filesystem-only trust
  model". ADR-0001's subject is jig coupling; this ADR keeps the posture it is
  cited for (filesystem plus read-only git, no new trust infrastructure).

## Consequences

**Becomes easier:**
- A run that edits `checks.json` and its recorded hash, an anchored eval
  definition, or `oracle.sh` is refused instead of scored.
- Every freeze result names what it was anchored to, which spec 046 can carry
  into evaluation evidence.
- Changes to an oracle show up as ordinary diffs against the base, so review
  sees them.

**Becomes harder:**
- Approving or installing an oracle becomes a change that has to reach the base
  (or the base is configured explicitly) before an anchored run trusts it.
- CI checkouts must fetch the base (a depth-1 clone falls back to the worktree
  anchor).
- Each enforced score adds a few read-only git processes per component.
- The threat-model paragraph in `docs/architecture.md` has to be rewritten to
  match.

## Assumptions

- **Probed 2026-11-21 (git 2.43):** `git show <rev>:./<path>` resolves a
  repo-relative path from a subdirectory target and from a linked worktree. A
  missing path and an unknown rev both exit 128, so the resolver must verify the
  rev (`rev-parse --verify <rev>^{commit}`) before testing the path
  (`cat-file -e`).
- **Unverified:** every host servo supports runs the oracle with git on `PATH`
  and the object database readable. A host sandbox without git gets the
  worktree fallback.
- **Unverified:** typical targets resolve a default branch locally.
  `heartbeat.py:471-473` notes `origin/HEAD` is unset on many clones; the
  `main`/`master` heuristic covers the common case.
- **Unmeasured:** the per-score cost of the extra git calls is small next to
  component runtime.

## Kill criteria

- **The fallback dominates.** If most anchored evaluations in practice come out
  worktree-anchored (oracles living on branches, bases unresolvable), the
  anchor protects nothing; revisit, for example by defaulting the configured
  base to the loop's start commit, or by Option C or E.
- **The base is routinely configured to the branch tip** to get past
  refusals. Anchoring has then degenerated to the status quo with extra steps.
- **A supported host cannot run read-only git** in the scoring process.

## Open questions

- Should unattended surfaces refuse a worktree anchor instead of stamping it?
  Proposed: stamp first, decide from the evidence spec 046 records — the same
  observe-before-enforce rollout as
  [jig ADR-0070](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0070-gate-modes-off-observe-enforce.md).
- Should the loop default the configured base to its recorded `start_head`
  (`loop.py:4501`) when no default-branch merge-base resolves?
- Untracked `.servo/` copies (preset eval configs, installed runtime): give them
  a tracked home (ADR-0023-style), or pin them from the base-anchored
  `oracle.sh`? A follow-up, not this ADR.
- Version skew of the referenced, unvendored `checks.py`
  (`docs/refinement-todo.md:719`) is orthogonal: plugin files have no base copy.
  It stays open.
