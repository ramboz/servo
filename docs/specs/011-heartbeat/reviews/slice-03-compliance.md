---
slice: 011-03 — candidate-dispatch
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-06-15T20:09:00Z
prompt_source: jig:reviewer subagent (worktree-read, uncommitted slice) — docs/specs/011-heartbeat/slice-03-candidate-dispatch.md skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py
---

VERDICT: pass

REASONING:
All 10 ACs are genuinely implemented in `heartbeat.py` and meaningfully exercised by the
named test classes against a real git repo + the real `gate.py` (with only `loop.py`
stubbed via the disclosed `SERVO_HEARTBEAT_LOOP_PY` env hook — a faithful stand-in, not a
string-match shim). The load-bearing security property (AC5 / Guardrail #4) is real:
discovered text is only ever placed inside a delimited untrusted block by
`_build_dispatch_prompt`, the servo-authored task/preamble are module constants with no
interpolation, and `test_injection_text_only_inside_untrusted_block` proves an `IGNORE ALL
PREVIOUS INSTRUCTIONS` payload never lands in instruction position. AC2 defers to gate.py's
exit-2 taxonomy with no reimplementation (verified end-to-end against the real gate for all
three refusal reasons), AC3/AC4 exercise the real nested-`.servo/dispatch/` worktree path
with the genuine provisioning-then-verify self-check, and AC7/AC8 correctly produce the
ADR-0010 outcome shape under the reused 011-02 flock + atomic write with canonical v2 key
order. The implementer's calls (hold-lock-across-pass, env-error→`tried`,
provision-`.servo`-minus-volatile-dirs) are within the spec's stated latitude and disclosed
in the deviation log.

SPECIFIC ISSUES:
- [strength] skills/heartbeat/heartbeat.py — `_DISPATCH_TASK` / `_UNTRUSTED_PREAMBLE` are
  constants and `_build_dispatch_prompt` places `title`/`detail`/`evidence` only inside the
  BEGIN/END block; no f-string interpolates discovered text into the task. Guardrail #4 is
  structurally enforced, not merely asserted.
- [strength] skills/heartbeat/heartbeat.py — preflight reads gate.py's stdout JSON for every
  exit code and keys solely off `exit_code == 2`; the reason string is echoed from the gate,
  never recomputed. `OraclePreflightRefusalTests` runs the real gate for
  `manifest_missing`/`oracle_missing`/`oracle_not_executable`, proving deference.
- [strength] skills/heartbeat/heartbeat.py — the candidate set is re-selected under the lock
  from a re-read of the inbox, closing the TOCTOU window between the unlocked precheck read
  and lock acquisition. More careful than AC8 strictly requires.
- [nit] skills/heartbeat/heartbeat.py — the `idx is None` "finding vanished mid-pass" branch
  is `# pragma: no cover` and genuinely unreachable given the lock is held across the pass.
  Harmless defensive code; asserted-uncovered by design.
- [nit] skills/heartbeat/heartbeat.py — `_dispatch_one` re-checks target git-ness and
  recreates the worktree per candidate; correct under serial dispatch + whole-pass lock. A
  future bounded-parallel variant (out-of-scope) would need the per-`finding_id` worktree
  paths to remain collision-free (they are). No action for this slice.
