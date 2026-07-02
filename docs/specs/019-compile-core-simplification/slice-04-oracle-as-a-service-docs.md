---
status: DONE
dependencies: [003-08, adr-0021]
last_verified: 2026-07-02
frame_review: true
---

## Slice 019-04 — oracle-as-a-service-docs

**Goal:** Close ADR-0021's remaining gap once Bugs 001/002/004 are accounted
for: verify the loop's refuse-loudly contract is fully met by the already-
shipped fixes, then document the **oracle-as-a-service / BYO-implementer**
flow ("Compile → your driver edits → `quality-gate` judges") on the skill
surface, so it is a named, discoverable, supported mode — not just an
emergent property of `gate.py` happening to be stateless.

**DoR:**
- ✅ **ADR-0021 Accepted** (2026-07-02).
- ✅ **Bugs 001, 002, 004 DONE** (commit `4315187`) — grounded by direct
  code + test read, this already delivers the ADR's "refuse loudly… rather
  than silently plateauing" requirement for the two concrete, observable
  failure signatures the dogfood hit:
  - **Auth/API failure** (Bug 001 + its goal-driver twin, Bug 004): both
    `_invoke_claude` and `_invoke_claude_goal`/`run_goal_loop`
    (`skills/agent-loop/loop.py`) now detect an `is_error` envelope and
    halt `claude_invocation_failed` (a distinct `REASON_*`, exit 2) instead
    of scoring/plateauing. Regression:
    `ClaudeErrorEnvelopeTests`, `GoalDriverParityTests`.
  - **Missing edit permissions** (Bug 002 + Bug 004): both drivers now
    forward the target's own committed `.claude/settings.json` via
    `--settings` (`_settings_args`, loop.py) so a target that pre-
    authorizes its tools runs unattended. Regression:
    `LoopForwardsTargetSettingsTests`, `GoalDriverParityTests`.
- ⚠️ **Known, documented residual gap — not solved by this slice.** When a
  target declares **no** `.claude/settings.json` and the host's default
  (prompt-on-tool) policy silently denies edits, the spawned `claude -p`
  turn can complete "successfully" (`is_error: false`, real turns, real
  cost) with zero file changes — there is no error envelope to detect.
  Direct grep across `loop.py`, both bug records, and ADR-0021 confirms
  **no env var, parent-process signal, or other mechanism exists** to
  positively detect "I am nested inside a permission-restricted host" ex
  ante — ADR-0021's own Alternatives Considered explicitly rejects trying
  to defeat the host's classifier. This case degrades to the existing
  `oracle_plateau` path, which is the ADR's accepted fallback for a
  genuinely-stuck (vs. structurally-blocked) run. Recorded here rather than
  papered over with an unfounded heuristic; a future slice can revisit if a
  real detection signal materializes.
- ✅ **Grounded doc-gap**: `skills/agent-loop/SKILL.md` names the
  `--driver loop` path as "portable / external-driver… for hook-restricted
  and non-Claude-Code hosts" but never names the Compile→external-driver→
  gate workflow explicitly; `skills/quality-gate/SKILL.md` documents
  `gate.py` as stateless + `--json` but never frames "external driver /
  CI / another agent as the implementer" as a supported flow. Both
  confirmed by direct read — this is the slice's real, achievable scope.

## Assumptions

- **A1 — no nesting-detection signal exists today, and building one is out
  of scope.** Direct grep across `loop.py`, `docs/bugs/001-*.md`,
  `docs/bugs/002-*.md`, `docs/bugs/004-*.md`, and ADR-0021 itself found no
  env var, parent-process marker, or other mechanism that positively
  identifies "running nested inside another agent" or "host permissions are
  restricted" beyond the two *symptoms* Bugs 001/002/004 already handle
  (auth error envelope; no settings forwarded). This assumes that remains
  true — i.e. that inventing a heuristic now (e.g. sniffing an
  undocumented env var) would be speculative, not grounded, and therefore
  out of scope; the silent-denial case stays a documented residual gap
  (see DoR) rather than a built feature. *To verify:* this is inherently
  hard to falsify (absence of evidence); the check is "does a future
  Claude Code release document such a signal" — tracked via the
  refinement-todo entry this slice's DoD requires, not resolved here.

**Acceptance Criteria:**

1. **Refuse-loudly contract closure is verified, not re-implemented.** A
   reconciliation note (not new production code) confirms Bugs 001/002/004
   jointly satisfy ADR-0021's Decision bullet "`agent-loop` must detect
   when it cannot function… and refuse loudly… rather than silently
   plateauing" for the auth and permission-forwarding cases, citing the
   existing regression tests by name. No new `REASON_*` is invented for
   the undetectable silent-denial case (see DoR).
2. **Agent-loop SKILL.md names the oracle-as-a-service flow.** Add a
   named section (e.g. "Oracle-as-a-service / bring-your-own-implementer")
   describing: Compile produces a frozen, reviewable oracle; any driver
   (human, CI, another agent) may perform the edits; `quality-gate` is the
   pass/fail authority; the native loop is one optional driver, not a
   prerequisite. Cross-link ADR-0021. *Test:*
   `test_skill_surface.py::OracleAsAServiceDocsTests` asserts the section
   header + the three named actors (Compile / driver / quality-gate) are
   present.
3. **quality-gate SKILL.md documents the external-driver contract
   explicitly.** Add a short section naming `gate.py` as usable standalone
   by an external driver (CI pipeline, another agent, a human) as the
   pass/fail authority over a Compiled oracle, independent of the loop —
   pointing at the existing stateless / `--json` / closed-exit-code
   properties as *why* this already works. *Test:*
   `test_skill_surface.py::ExternalDriverDocsTests`.
4. **Cross-reference is bidirectional.** agent-loop's SKILL.md section
   links to quality-gate's, and vice versa, so a reader starting from
   either skill discovers the full flow. *Test:* same surface-test file
   asserts both cross-links resolve to real anchors/paths.
5. **No behavior change to `loop.py` or `gate.py`.** This slice is docs-
   only (plus the reconciliation note in AC1); the full `test_loop.py` and
   `test_gate.py` suites pass unmodified. *Test:* full suite green with
   zero production-code diff outside the two SKILL.md files.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions).
- [x] Implementer test coverage exercises each AC with at least one
      fixture (surface-test assertions).
- [x] Compliance review pass.
- [x] Craft review pass.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review pass.
- [x] `docs/refinement-todo.md` gains an entry for the documented residual
      "silent permission denial, no detection signal" gap (deferred, not
      silently dropped).

### Close-out (post-DONE)
- [x] `docs/specs/README.md` regenerated by `workflow.py status-board`.
- [x] Bugs 001/002/004 records gain a cross-link to this slice as the
      ADR-0021 doc follow-through they named.

**Anti-horizontal-phasing check:** an operator who cannot run servo's
native loop (nested host, CI, restricted permissions) can now find, in the
skill surface itself, the exact supported alternative — Compile, drive
edits with whatever they have, judge with `quality-gate` — instead of
having to reverse-engineer it from the dogfood's ADR.

### Deviation log (after reconciliation)

Original ACs preserved above; no deviations from the planned shape. Both
reviewers (compliance + craft) returned `pass` with only nits:

- AC1's "reconciliation note" was written inline in the slice's DoR section
  rather than as a separately-headed subsection. Left as-is — the DoR
  bullets already name the exact regression tests
  (`ClaudeErrorEnvelopeTests`, `LoopForwardsTargetSettingsTests`,
  `GoalDriverParityTests`) that prove the closure, which is the substance
  the AC asked for.
- Both reviewers flagged that Bugs 001/002/004 lacked a *reciprocal*
  cross-link back to this slice (bug 002 only had a forward mention).
  Fixed during reconciliation: `docs/bugs/001-*.md`, `002-*.md`, and
  `004-*.md`'s `## Learning`/`Scope` sections now link to
  `slice-04-oracle-as-a-service-docs.md`.
- The craft pass noted both new `test_skill_surface.py` classes use the
  same loose substring-assertion idiom already flagged as tech debt
  elsewhere in `docs/refinement-todo.md` for sibling test files. Not
  addressed here — pre-existing repo-wide pattern, out of scope for a
  single slice to fix.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Project front door unaffected — this slice only touches skill-surface docs + a refinement-todo entry. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board` after this slice transitions. |
| `docs/product-vision.md` | `no-op` | Checked — no scope/behavior drift; this slice documents an existing, already-shipped capability. |
| `docs/architecture.md` | `no-op` | Checked — no module-boundary or public-contract change (docs-only). |
| Primer surfaces (`CLAUDE.md`/`AGENTS.md`/scaffold templates) | `no-op` | Checked — none reference agent-loop/quality-gate's skill-surface docs directly. |
| `docs/inbox.md` | `no-op` | Checked — nothing in it is resolved by this slice. |
| `docs/refinement-todo.md` | `updated` | Added the "silent permission denial has no detection signal" entry during implementation (AC1/DoD requirement), deferred with a stated resolution trigger. |
| `docs/memory/**` | `no-op` | No new domain terms or dead-end learnings beyond what's already captured in `docs/memory/learnings.md`'s Bug 001/002/004 entries. |
| `docs/decisions/README.md` / ADR index | `no-op` | ADR-0021 already indexed as Accepted; this slice only cites it, doesn't change it. |
| `docs/bugs/{001,002,004}-*.md` | `updated` | Added reciprocal cross-links to this slice (see deviation log) — both reviewers flagged the missing reciprocal link. |
