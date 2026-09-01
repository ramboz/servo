---
adr: 0037
pass: frame-critique
verdict: pass
reviewer: jig:reviewer subagent, fresh per round x5 (claude-fable-5), orchestrator-verified vs loop.py
reviewed_at: 2026-09-01T18:28:35Z
prompt_source: review.py frame-critique docs/decisions/adr-0037-agent-loop-permission-preflight.md
---

Frame-critique of ADR-0037 (agent-loop diagnoses a missing headless
edit-permission wall). Multiple fresh `jig:reviewer` subagents (claude-fable-5),
prompt built by `review.py frame-critique`, each round orchestrator-verified
against `loop.py`/`runner.md`/`judge.md`. Final verdict: **pass** after four
needs-changes rounds that each caught a distinct, code-verified defect and drove
the mechanism to converge (and simplify). The **policy** — refuse loudly on a
permission wall (ADR-0021) — was never in dispute; every round was about the
*mechanism*.

## Round 1 — two independent critics, both needs-changes

Both independently attacked the original **ex-ante probe** shape: cheap XOR
faithful (a real `claude -p` probe isn't cheap/deterministic; a cheap Python
write is meaningless since `loop.py` already writes the target), `_settings_args`
forwards only committed `settings.json` (not the `settings.local.json` grant the
ADR cited as its fix), and edit-capability is path/tool-scoped, not global — so
the probe could false-negative (block a capable run — a regression worse than
status quo) or false-positive. Both proposed the same alternative: post-hoc
detection. **Owner chose post-hoc/hybrid.**

## Round 2 — needs-changes: untracked-file blindness

Keying the post-hoc signal on `_dirty_tree_paths` was wrong: it excludes
untracked `??` files (`loop.py:1485`), so a capable runner *creating* new files
(the common oracle-driven shape, and the Bug 002 case) reads as zero-edit →
false refusal. Fix: a net-new per-iteration git-tree **delta including untracked
files**.

## Round 3 — needs-changes: judge-alternation padding

`_agent_for_iteration` (`loop.py:444`) alternates runner (odd) / judge (even),
and the judge is read-only by contract (`judge.md:18`), so judge iterations land
zero edits by design. Counting raw iterations, a single legit runner no-op
between two judges hits "3 consecutive zero-edit iterations" and mis-fires. Fix:
scope the signal to **runner iterations only**; cumulative-zero with
**disarm-on-first-edit** (any runner edit proves permission for the run).

## Round 4 — needs-changes: valuable-XOR-safe timing tension

A mid-run "M runner iterations" threshold cannot align with the plateau brake:
`_check_plateau` fires at total iteration `window+1`=4 and `break`s
(`loop.py:588,2328-2334`), but runner iterations are odd totals — so `M=3` →
total 5 is **dead code**, and `M=2` → total 3 fires *before* the plateau,
re-introducing the capable-run-blocking regression. Critic-supplied fix, adopted:
make it a **terminal-reason relabel** at the halt that already happens — never
earlier, so it can never lose a capable run; it only reports the correct reason.
Also flagged: the disarm flag must be **persisted** to survive `--resume`
(`loop.py:2095-2099`, 2037-2042).

## Round 5 — PASS

Attacked the new signal-isolation assumption (could stray `.servo/` / gate /
`claude` artifacts false-arm `runner_ever_edited` and suppress the relabel?) and
concluded the frame holds: the **oracle-below-threshold conjunct** confines every
signal blind-spot (edits-then-reverts, unobserved paths, missed edits, false-arm)
to *already-failing* runs — it can never block or mislabel a progressing/passing
run, and both error directions degrade to today's status quo (no false pass, no
blocked capable run). Core claim (relabel-at-existing-halt is always live, never
early) verified structurally against `loop.py`.

Two non-blocking reconciliation notes, **both folded into the ADR before
recording this pass**:
1. Over-stated parenthetical corrected: at `--plateau-window 1` / low
   `--max-iterations` a *single* runner no-op can be the halting state; the
   one-runner-iteration case is now absorbed by the graded residual, not a false
   multi-iteration guarantee.
2. Spec-guidance added: the snapshot must bracket the **runner invoke only**
   (exclude the gate call `loop.py:2247` and the `.servo/` state write
   `loop.py:2287`, filter cwd/test artifacts); tests must guard **both**
   directions (arm on a new source file; **no** false-arm from bookkeeping); and
   the oracle-below-threshold conjunct is now stated explicitly as the property
   that makes every blind-spot degrade to status quo.

## Final shape (for the accept decision — still Proposed, owner's call)

Mechanism: a persisted `runner_ever_edited` bool set by an untracked-inclusive,
runner-only, per-invoke disk delta; at the existing `oracle_plateau` /
`iteration_cap_reached` halt, if the flag is false and the oracle is red, relabel
the terminal reason to `edit_permission_unavailable` (rc=2) with a fix
breadcrumb. Goal driver: same relabel at its terminal point, plus an optional
advisory/fail-open ex-ante check. It delivers a *correct, actionable terminal
reason* — not earlier halting (the existing brakes already bound the run). Named
residuals: capable-but-stuck-from-first-iteration mislabel (run was halting
anyway); non-git targets uncovered (fall back to `oracle_plateau`); the
implementation must get the delta isolation and flag persistence right (the
load-bearing surfaces, with required fixtures named).
