---
slice: 011-03 — candidate-dispatch
pass: reconciliation
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-06-15T20:09:00Z
prompt_source: jig:reviewer subagent (reconciliation lens) — docs/specs/011-heartbeat/slice-03-candidate-dispatch.md skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py docs/refinement-todo.md
---

VERDICT: pass

REASONING:
The deviation log honestly and completely reconciles the implementation against the ACs as
written. All eight known divergences are disclosed with accurate file-level behavior, and
each matches what the code actually does (verified against heartbeat.py and the test seam).
Assumptions A1/A2/A3 each carry a recorded resolution, and all five deferred items appear in
`docs/refinement-todo.md` with concrete resolution triggers. I found no undisclosed
divergence between the implementation and the ACs — the log's "No AC was dropped or reshaped"
claim holds up under independent check. (The two arch_review/independent-review DoD
checkboxes were unticked at review time, which is correct for a slice undergoing this very
review, not a deviation-log defect.)

SPECIFIC ISSUES:
- [strength] deviation-log faithfulness — the DoD bullet was itself amended to say the
  harness is "adapted to the `SERVO_HEARTBEAT_{GATE,LOOP}_PY` env-override test-hook (see
  deviation log)" rather than asserting the literal PATH-injected mock-binary; the deviation
  entry explains why (`python3 <abspath>`, loop resolves gate via `GATE_PATH` not PATH).
  Disclosed at both sites and matching `_resolve_helper` + the env-injecting harness.
- [nit] the deviation log says gate.py "runs for real … for AC2/AC4"; in practice the real
  gate.py runs on essentially every dispatch path (default `gate_py=None`), which
  *strengthens* the deference claim — no correction needed.
- [nit] the inbox.md-staleness + uncommitted-oracle deferral bundles two disclosed
  limitations into one refinement-todo entry; both have resolution triggers, so the DoD is
  satisfied. Cosmetic only.

RECONCILIATION NOTES:
No undisclosed deviations from spec observed. The deviation log, Assumptions resolutions,
Out-of-scope section, and the (now six) refinement-todo entries together form a complete and
faithful reconciliation. Material implementer's-latitude calls captured: (1) advisory lock
held across the entire dispatch pass; (2) per-candidate env-errors set `status=tried`
(no auto-retry under one-attempt-in-v1); (3) provisioning copies `.servo/` minus
{runs,races,triage,dispatch}; (4) dispatch writes only `inbox.jsonl`, leaving `inbox.md`
stale until the next `discover`; (5) `--cost-ceiling`/`--max-iterations` forwarded only when
provided; (6) no outer wall-clock timeout on `loop.py` or the gate preflight (both
self-bound); (7) an oracle whose live content/mode diverges from HEAD makes the worktree
dirty → loop.py records a per-candidate env-error (no `--allow-dirty` on the unattended
path). Post-review fixes (summary breadcrumb wording, gate-preflight self-bound note, chmod
mode sub-case, env-error↔worktree-clobber coupling) were folded into the deviation log +
refinement-todo after this pass.
