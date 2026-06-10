---
status: DRAFT
dependencies: [004-01, 004-02, 004-03, 004-04, adr-0006]
last_verified:
---

## Slice 004-05 — skill-and-dogfood

**Goal:** Ship the `/servo:oracle-hook` skill surface and prove the whole thing
works end-to-end against a real scaffolded target. The SKILL.md gives Claude the
trigger bounds, the Tier-2 explicit-opt-in framing, and the Q&A to run the
installer correctly; the dogfood test installs onto a scaffolded fixture, fires a
synthetic `Stop` event, and asserts block-with-hint (below threshold) vs
silent-pass (above threshold). End-to-end value: the skill is invocable by name,
behaves safely by default, and is demonstrated working — spec 004 is complete.

**DoR:**
- ✅ 004-01..04 DONE — install / judge / fail-open / backup / uninstall / status
  all exist and are tested.
- ✅ ADR-0006 Accepted (004-02) — the contract the SKILL.md documents is frozen.
- ✅ Skill-surface test pattern available (mirror `skills/quality-gate/`,
  `skills/spec-oracle/` `test_skill_surface.py`).

**Acceptance Criteria:**

1. **Skill exists and is discoverable.** `skills/oracle-hook/SKILL.md` defines
   `/servo:oracle-hook` with a `name` + `description` in the house style, and is
   listed in `.claude-plugin/install-contract.json` (so the runtime-install
   verifier knows about it).
2. **Trigger bounds.** The description fires on install/uninstall/status of the
   hook ("install the oracle hook", "add the Stop hook", "remove the meta-judge",
   "is the oracle hook installed?") and **does NOT fire** on the sibling skills'
   territory: `/servo:quality-gate` (run/score the oracle once),
   `/servo:agent-loop` (iterate headlessly), `/servo:scaffold-init` (set up
   servo). A surface test asserts the Do-NOT-fire boundaries.
3. **Tier-2 opt-in surfaced.** SKILL.md states the hook mutates
   `<target>/.claude/settings.json`, is backed up, and is offered explicitly —
   never auto-installed. It explains the fail-open posture and the
   one-nudge-per-sequence behavior so users aren't surprised.
4. **Q&A coverage.** SKILL.md documents: which target, that the target must be
   servo-scaffolded first, the block-vs-soft-context mode, how to uninstall, and
   how to read `status` (including the `inconsistent` state).
5. **Dogfood — below threshold blocks.** A test scaffolds a fixture target whose
   oracle scores below threshold, runs `install`, pipes a synthetic `Stop` event
   into the installed `meta-judge.sh`, and asserts a `decision: block` with a
   hint naming the composite and threshold (per the amended 004-01 AC4).
6. **Dogfood — above threshold passes silently.** The same flow against a target
   whose oracle passes asserts no `decision` and exit 0.
7. **Dogfood — round-trip clean.** `uninstall` after the dogfood leaves
   `settings.json` equivalent to its pre-install state (modulo the backup file),
   and `status` reports `not_installed`.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] `skills/oracle-hook/test_skill_surface.py` (trigger bounds) +
      `skills/oracle-hook/test_dogfood.py` (or equivalent) cover ACs.
- [ ] Reviewed by `reviewer` subagent (compliance + craft).
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred.

### Close-out (post-DONE) — spec 004 complete
- [ ] [README.md](../../../README.md) skills table: `oracle-hook` → DONE.
- [ ] [architecture.md](../../architecture.md): "Skill split" `future` row → spec
      004; "Runtime artifacts" gains the meta-judge-hook entry; "Decisions" lists
      ADR-0006.
- [ ] `scripts/verify_install_surfaces.sh` green (new skill + template included
      across all runtime-install surfaces, spec 007).
- [ ] [docs/specs/README.md](../README.md) status board reflects spec 004 DONE.
- [ ] `/jig:memory-sync` run to consolidate learnings.

**Anti-horizontal-phasing check:** This slice ships the user-facing entry point
(the named skill) and a live demonstration — the capstone that makes 004 a real,
invocable, proven feature rather than a pile of helpers.
