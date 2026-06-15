---
slice: 011-03 — candidate-dispatch
pass: arch
verdict: pass-with-nits
reviewer: jig:reviewer
reviewed_at: 2026-06-15T20:09:00Z
prompt_source: jig:reviewer subagent (arch lens; arch_review:true gate) — docs/specs/011-heartbeat/slice-03-candidate-dispatch.md docs/specs/011-heartbeat/spec.md docs/architecture.md skills/heartbeat/heartbeat.py
---

VERDICT: pass-with-nits

REASONING:
The module boundary is right: heartbeat composes `loop.py`/`gate.py` purely by subprocess
(`sys.executable` + abspath, never imported), keeping the loop trigger-agnostic and the
dispatch target pluggable for `race.py`. Guardrail #3 is genuinely the only path from
proposed→running: `run_dispatch` runs `gate.py <target>` before any worktree/loop and
refuses the whole pass on `exit_code == 2`, deferring entirely to gate.py's numeric verdict
+ opaque `reason` with zero taxonomy reimplementation. Guardrail #4 is soundly bounded — the
imperative task and injection-resistant preamble are servo-authored constants, discovered
text is never string-interpolated into instruction position but only placed inside a
labelled delimited block, and loop.py passes `--prompt` verbatim (no sanitization), so the
dispatcher correctly owns the framing; the blast radius (worktree isolation + the *post-loop*
`gate.py` final-oracle authority + per-loop ceiling) is intact. Worktree isolation is
well-designed: A1 is probed, the target's own tree is never touched, and the AC4
post-provision `gate.py <worktree>` self-check genuinely de-risks A2 by surfacing an
incomplete copy as a skipped per-candidate env-error rather than a mis-score. The deviations
are architecturally defensible and the deferred items (worktree GC, does-loop-commit) are
correctly punted; nothing here exceeds ADR-0002/0004/0010, so no new ADR is warranted. The
nits are residual-risk disclosures, not blockers.

SPECIFIC ISSUES:
- [strength] `_run_gate_json` / `_is_refuse_without_oracle` — Guardrail #3 deference is
  exemplary: keys only on the numeric `exit_code == 2`, quotes gate.py's own `reason`, never
  re-lists the taxonomy; a None/uninvocable gate also fails closed.
- [strength] `_build_dispatch_prompt` + the task/preamble constants — sound bound on the
  injection vector: constants for instructions, discovered fields only inside the block,
  `evidence` is `json.dumps`'d (no raw-structure injection), both provenances framed.
- [strength] AC4 gate-verify self-check — running `gate.py <worktree>` after provisioning and
  mapping `exit 2` to a skipped per-candidate env-error is the design that makes A2 safe
  by-construction rather than by-enumeration. The load-bearing correctness argument; it holds.
- [nit → addressed] `_provision_oracle` overwrites the worktree's tracked `oracle.sh` and
  force-adds the exec bit; a content- OR mode-divergence from HEAD makes the worktree dirty →
  loop.py refuses `dirty_tree` → env-error (degrades safely). The deviation log now names the
  `chmod`-induced mode-divergence sub-case, not just the uncommitted-edit trigger.
- [nit] whole-pass lock hold — defensible (no completed outcome lost to a mid-pass discover),
  but with no outer loop timeout the worst-case hold is Σ(per-loop wall-clock); a concurrent
  scheduled `discover` backs off for that whole window. Self-correcting + disclosed; flagged
  for the 011-04 ceiling work where wall-clock bounding naturally belongs.
- [nit] stale `inbox.md` until the next `discover` — right minimal-write posture for AC10
  (`status` reads the jsonl), but asymmetric with the status-board generated-view convention
  (a reviewer-surprise vector). Adequately punted to refinement-todo.
- [nit → addressed] `_remove_worktree_if_present` clobber-safety depends on the env-error→
  `tried` deviation staying in place; if a future slice lets transient env-errors stay `open`
  for retry, teardown would clobber a worktree whose prior loop ran. The two deferred
  decisions are now cross-referenced in the deviation log + refinement-todo.
