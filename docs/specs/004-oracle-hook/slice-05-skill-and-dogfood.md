---
status: DONE
dependencies: [004-01, 004-02, 004-03, 004-04, adr-0006]
last_verified: 2026-06-10
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
- [x] All ACs pass; full test suite green.
- [x] `skills/oracle-hook/test_skill_surface.py` (trigger bounds) +
      `skills/oracle-hook/test_dogfood.py` (or equivalent) cover ACs.
- [x] Reviewed by `reviewer` subagent (compliance + craft).
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated if any decisions were deferred.
      (No *new* deferrals — the per-component-score hint gap remains owned by
      ADR-0006 / 004-01's existing refinement-todo entry; nothing to add.)

### Close-out (post-DONE) — spec 004 complete
- [x] [README.md](../../../README.md) skills table: `oracle-hook` → DONE.
- [x] [architecture.md](../../architecture.md): "Skill split" `future` row → spec
      004; "Runtime artifacts" meta-judge.sh entry enriched (decision table +
      install model); "Decisions" lists ADR-0006 (already present).
- [x] `scripts/verify_install_surfaces.sh` green (new skill + template included
      across all runtime-install surfaces, spec 007).
- [x] [docs/specs/README.md](../README.md) status board reflects spec 004 DONE.
- [x] `/jig:memory-sync` run to consolidate learnings (user-level memory:
      [[servo-spec-tracking-convention]] extended with the `transition` gaps).

**Anti-horizontal-phasing check:** This slice ships the user-facing entry point
(the named skill) and a live demonstration — the capstone that makes 004 a real,
invocable, proven feature rather than a pile of helpers.

### Deviation log (after reconciliation)

Original ACs above are preserved. Implemented as specified; the deviations and
disclosed scope decisions:

- **Deliverables.** `skills/oracle-hook/SKILL.md` (house-style surface, mirroring
  `quality-gate`/`agent-loop`: fire / Do-NOT-fire triggers + sibling pointers,
  Tier-2 opt-in, the ADR-0006 decision table, block-vs-soft-context knob, closed
  0/2 exit + refusal table, Q&A, examples); `skills/oracle-hook/test_skill_surface.py`
  (AC1-4, 26 tests) and `skills/oracle-hook/test_dogfood.py` (AC5-7, 4 tests);
  `.claude-plugin/install-contract.json` now lists the `oracle-hook` skill
  (`SKILL.md` + `hook.py`) and `meta-judge.sh.template`.

- **Dogfood fixture is a deterministic leaf stand-in (AC5/AC6).** The dogfood runs
  the *real* chain end-to-end — real `hook.py install` → the rendered
  `meta-judge.sh` → servo's own `gate.py` → the fixture `oracle.sh` → block/pass —
  but the fixture's `oracle.sh` is a hand-rolled real shell script that
  deterministically scores, **not** a `scaffold.py`-generated oracle running a real
  tool. Reason: the stock `pytest.sh.fragment` requires bare `pytest` on `PATH`,
  which is absent when the suite runs via `uvx pytest`, so a real-tool oracle would
  flake (env-error → fail-open → no block). Only the leaf oracle is stubbed; every
  other link is the real artifact. Both review passes judged this sound and
  well-disclosed. (Mirrors the seam `test_hook.py`'s existing
  `test_integration_real_gate_*` already used.)

- **AC7 "status reports not_installed" reconciled to `inconsistent` → removal.**
  `uninstall` deliberately leaves the project-owned `meta-judge.sh` on disk
  (004-04 AC2), and a script-without-entry is `inconsistent` (004-04 AC5). So the
  precise post-uninstall state is `inconsistent` (orphaned script); the dogfood
  asserts that, then removes the script to reach `not_installed`. This is a
  faithful inheritance of 004-04's deviation, not a new behavior. `settings.json`
  is restored to a JSON-equivalent of its pre-install state (modulo `.servo-bak`),
  which the round-trip test asserts directly.

- **Spec-007 verifier kept green across all surfaces.** Adding `oracle-hook` to the
  contract makes `scaffold_runtime.py` vendor `servo-oracle-hook/` (data-driven), so
  the vendored SKILL.md's `hook.py` command examples are picked up by
  `ScaffoldCommandClassificationTests`. `hook.py` is therefore registered in
  `scripts/test_scaffold_runtime.py`'s `ILLUSTRATIVE_COMMANDS` (install/uninstall
  mutate `settings.json` against an already-scaffolded oracle — not a bare-scaffold
  smoke command), alongside `gate.py`/`loop.py`. `verify_install_surfaces.sh` and
  the live plugin verifier both pass.

- **Review-driven fixes (craft pass, non-blocking nits, fixed not just logged).**
  (1) `SKILL.md` `--timeout` cell reworded — `--timeout` (Stop-hook timeout in
  `settings.json`) and `SERVO_META_JUDGE_GATE_TIMEOUT` (the script's gate bound,
  default 45s) are **independent** knobs; the old "bounds below this" wording only
  held at the defaults. (2) Surface-test docstring corrected to cite the sibling
  *surface tests*. (3) `DescriptionBoundsTests` strengthened to assert trigger
  *placement* (positive phrases before the Do-NOT boundary, negative phrases
  under it), closing the "phrase merely present" gap both reviewers flagged. One
  accepted-low nit left as-is: the dogfood's `assertIn("0.2"/"0.5", reason)` are
  substring checks, sound because the fixture pins exact `0.20`/`0.50` values.

- **No new deferrals.** The terse-hint / per-component-score gap remains owned by
  ADR-0006 clause 4 + 004-01's existing `docs/refinement-todo.md` entry.

- **Reviews (servo convention — recorded inline, no `reviews/` evidence files).**
  Compliance pass (`jig:reviewer`, independent-review prompt): **PASS** — all 7 ACs
  met, no blockers. Craft pass (`jig:reviewer`, pr-review prompt): **PASS** — no
  blockers; strengths called out (honest AC7 reconciliation, anti-vacuity test
  guards, correct ILLUSTRATIVE registration); the three nits above addressed.
  Reconciliation pass (`jig:reviewer`, reconciliation prompt): **PASS** — deviation
  log + close-out doc edits verified faithful to the code (decision-table summary
  matches ADR-0006 + the template; "independent knobs" timeout claim matches
  `hook.py` + the template); surfaced one stale doc, swept below.

- **Closed-spec drift swept (ADR-0010, live-prose-inline).** The reconciliation
  pass surfaced `docs/product-vision.md`'s backlog still listing `/servo:oracle-hook`
  as "*Future spec.*"; fixed inline to "*Spec 004 — DONE.*". Drive-by in the same
  edit: the adjacent `/servo:spec-oracle` entry was likewise stale ("*Spec 006 —
  DRAFT.*" → "*Spec 006 — DONE.*"; spec 006 was closed in a prior session, per
  README + git), corrected for backlog consistency.

- **Tooling note.** `workflow.py transition … REVIEWED` performed its DoD auto-tick
  and `claimed_by` clearing but did **not** persist the frontmatter `status:` write
  for this slice (reproducible). Status was driven by direct frontmatter edit per
  the [[servo-spec-tracking-convention]] ("prefer editing it directly"); dependency
  satisfaction for the `DONE` move was verified by hand (004-01..04 DONE; ADR-0006
  Accepted).
