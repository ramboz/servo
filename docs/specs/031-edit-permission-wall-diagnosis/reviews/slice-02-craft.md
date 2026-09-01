---
slice: 031-02 — goal-driver-relabel
pass: craft
verdict: pass
reviewer: jig:reviewer (fresh, read-only, pr-review skill)
reviewed_at: 2026-09-01T21:33:50Z
prompt_source: review.py pr-review --richer-skill pr-review
substrate: non-interactive
---

Craft review of slice 031-02 — goal-driver-relabel. VERDICT: **pass** (no blockers).

Strengths: `_relabel_terminal_reason` is genuinely ONE pure helper serving both
drivers (no fork) — the eligible set spans all four reasons and both call sites
pass the identical 4-kwarg signature; `_tree_snapshot` + `EDIT_PERMISSION_BREADCRUMB`
are the shared 031-01 assets (DRY/inline-mirror budget respected — only the ~7-line
exit-code wiring is inline-mirrored, justified by the drivers' differing exit
mechanisms). The whole-run bracket snapshots before `_invoke_claude_goal` and after
it but before the authoritative gate, correctly excluding gate writes. The relabel
keys the below-threshold conjunct on `gate_status` (not `gate_exit`), so an
env-error gate is not relabeled; `edit_signal_available` reads the snapshot-derived
flag, so a rev-parse-healthy tree whose `git status` transiently fails falls back.
The four goal test classes run a real git repo + real gate.py + real subprocess
(only `claude` mocked); each negative test kills a specific conjunct mutation —
non-vacuous, high-fidelity.

Non-blocking nits (folded in reconciliation):
- [nit][impl] cross-driver forensic-key inconsistency: goal persisted
  `ever_edited` while loop uses `runner_ever_edited`. **Folded:** unified the goal
  state key to `runner_ever_edited` (matches the shipped 031-01 key and
  docs/architecture.md's documented field; local var stays `ever_edited`). A
  state.json consumer now reads one name for one concept.
- [nit][impl] test symmetry: `test_created_file_keeps_iteration_cap_reached`
  omitted the `assertNotIn("terminal_breadcrumb", summary)` its sibling has.
  **Folded:** added.

Strengths worth propagating: the shared pure helper with per-conjunct mutation
coverage + inline-mirrored wiring is a good template for future driver
extensions; the goal tests exercise the real gate + real git rather than stubbing
the signal under test.
