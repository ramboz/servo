---
status: DRAFT
dependencies: [028-03, 028-04]
last_verified:
# arch_review: true  # maps Claude-only execution primitives onto Copilot; ADR-0028 residual
---

## Slice 028-05 — execution-primitive-mapping

**Goal:** servo's *optional* unattended loop runs under Copilot. This is the
servo-specific slice with no jig analogue: servo's `loop.py` subprocesses
`claude -p --agent runner` and gates on the oracle. Map that to Copilot per the
spike's resolved findings, recording any true residual honestly.

**DoR:**
- ✅ 028-03 done (a Copilot `runner` agent renders, so `--agent runner` resolves).
- ✅ 028-04 done (target-side `agentStop` oracle hook + adapter).
- ✅ 028-01 resolved: Autopilot has **no** oracle-gated stop (only
  `--max-autopilot-continues`/`--max-ai-credits`); `copilot -p -s` needs
  `--allow-all-tools`; `--output-format json` = JSONL; `--usage-output-file`
  exposes cost + `codeChanges.filesModifiedCount`.

**Acceptance Criteria:**

1. **`claude -p`→`copilot -p -s` (loop driver).** `loop.py` gains a Copilot host
   mode: it invokes `copilot -p -s --agent runner --allow-all-tools` (+
   `--output-format json` for parseable output, `--usage-output-file` for cost)
   instead of `claude -p --agent runner`, selected by host, defaulting to Claude
   (no change for Claude users). A test asserts the Copilot invocation form is
   emitted (and the Claude form is unchanged for Claude host). The loop's own
   Python per-iteration oracle gate is unchanged — it does **not** use Autopilot.
2. **Cost + edit-signal parse.** The loop parses `copilot`'s
   `--usage-output-file` JSON for cost (`totalPremiumRequestCost`/`totalNanoAiu`)
   toward its ceiling, and reads `codeChanges.filesModifiedCount` as the native
   edit-signal (maps the ADR-0033/0037 "did the runner edit?" check). A test
   covers parsing a sample usage JSON (fixture from the spike's live run).
3. **`/goal`→Autopilot, honestly (resolved).** The goal driver's per-turn oracle
   gate maps via the **target-side `agentStop` oracle hook** (028-04), with
   Autopilot's `--max-autopilot-continues`/`--max-ai-credits` as the outer bound —
   **not** via any (nonexistent) Autopilot oracle-gated stop. Whether `agentStop`
   fully reconstructs the gate under Autopilot is **not headlessly verifiable**
   (jig 113-08) → the goal-driver-under-Copilot path is shipped behind the same
   host selection but its live fidelity is recorded as an explicit **residual**;
   the loop driver (AC1) is the fully-supported Copilot path. Captured explicitly,
   never a silently un-gated run.
4. **Preflight → Copilot permissions.** servo's ADR-0033/0037 edit-permission
   posture maps to `--allow-all-tools` (required for headless tool use) +
   `codeChanges.filesModifiedCount` as the post-hoc edit-signal; recorded in the
   execution-primitive inventory. Any primitive that does not port is listed in
   the ADR-0028-style inventory (extends 028-04's), never silently renamed.

**DoD:**
- [ ] All ACs pass; full suite green (venv pytest); new tests fail when the feature is removed.
- [ ] The Autopilot/goal-driver verdict + residuals documented in `docs/architecture.md`
      + refinement-todo.
- [ ] Reviewed by `reviewer` subagent (compliance + craft + arch).
- [ ] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice a Copilot user runs servo's
loop driver end-to-end (per-iteration `copilot -p`), and knows precisely what of
the goal driver stays a documented residual and why.
