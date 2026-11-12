---
slice: 040-01 — outcome line
pass: craft
verdict: pass
reviewer: general-purpose (pr-review baseline)
reviewed_at: 2026-11-12T18:42:10Z
prompt_source: review.py pr-review ... --richer-skill none
substrate: non-interactive
---

VERDICT: pass (re-review, after the revision resolved the round-1 `needs-changes` blocker)

Round 1 (`needs-changes`): the SKILL.md `--background` paragraph documented
outcome-line capture that the code never wired (`_build_detached_child_argv` did
not forward `--outcome-line`; the parent `_detach_summary` emits no outcome line),
so `--background --outcome-line …` silently produced nothing. The foreground
feature was clean, correctly scoped, and well-tested.

Round 2 (PASS): verified by reading the changed code and running the tests.
`_build_detached_child_argv` now forwards `--outcome-line <value>` into the
detached child's argv when the global is armed; the child (a `--driver goal`
re-exec) arms its own `_OUTCOME_LINE_TARGET` and writes the record at its halt,
while the parent's `_detach_summary` stays unhooked — exactly one write. All four
loop.py copies byte-identical; rebuilt SKILL.md describes exactly this. 23/23
outcome tests green.

Attacks run, all clear: no double-write (parent emits only the launch summary;
child writes once; the e2e test asserts parent stdout has no `servo_outcome`); no
relative-path cwd divergence (Popen inherits cwd, setsid doesn't change it); the
global is armed in main() before the `--background` route reads it; the tests are
non-vacuous (the argv `index()` raises if forwarding is deleted; the e2e
`_await_outcome_file` times out if the flag isn't inherited) and the fresh-module
load confines the argv test's global mutation.

Strengths: the forwarding is the right fix (the child owns the real terminal, so
it owns the outcome) with exactly-once semantics preserved; the e2e background test
is a genuine real-detached-child witness of both the forwarding and the
no-double-write invariant.

Nits (non-blocking, deviation-log material): the `--background --outcome-line -`
(→ background.log) mode is documented but only `<path>` is covered end-to-end — the
`-` value rides the same forwarding path, covered by the argv unit test, so a
low-risk coverage note, not a gap. The `cost_usd: null` under `--host copilot`
limitation is now noted in SKILL.md; schema stays spec-faithful to AC3 (not widened
in this slice).

Reviewer: general-purpose subagent (read-only), pr-review baseline buckets, two rounds.
