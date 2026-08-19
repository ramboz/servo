---
status: DRAFT
dependencies: [adr-0031]
last_verified:
frame_review: true
---

## Slice 026-01 — runtime-preflight-guidance

**Goal:** Make the machine that actually fails say what to do about it. Add a
non-interactive preflight to `score.py` that probes the capture prerequisites
*before* spawning `capture.mjs`, and on failure emits a precise, actionable
instruction for *this* machine instead of the opaque
`node/playwright unavailable for capture`.

**DoR:**
- ✅ [ADR-0031](../../decisions/adr-0031-design-eval-browser-acquisition.md)
  Accepted; this slice implements its Option G, the primary mechanism.
- ✅ **Probe location is settled and grounded:** the probe must live in
  `score.py`, not `capture.mjs`. Verified — `capture.mjs:11` is a top-level
  `import { chromium } from 'playwright'`, the module's first executed
  statement, so no code inside it can run before that import throws. A module
  cannot preflight its own missing import.
- ✅ **Current failure shape verified:** `capture_app` catches
  `FileNotFoundError` → `EnvError("node/playwright unavailable for capture: …")`
  and non-zero rc → `EnvError("capture failed …")` (`score.py:105-111`).
- ⚠️ **A3 unverified** (see spec `## Assumptions`): that a `require.resolve`
  probe cleanly distinguishes "node missing" from "library missing". Confirm
  during implementation; if it cannot, report the two cases from the exit-code
  shape rather than guessing.

**Acceptance criteria:**
1. `score.py` runs a preflight before spawning capture: node present
   (`shutil.which("node")`), browser library resolvable, and the browser
   reachable for the resolved transport.
2. Each distinct failure produces a distinct, actionable message naming the
   exact remedy for this machine (e.g. install command, or the env override) —
   never the bare `node/playwright unavailable`.
3. The preflight is **non-interactive**: it never prompts, never reads stdin,
   and never installs anything. It runs correctly under CI / Routines /
   `loop.py --background` / the `oracle-hook` Stop hook.
4. The contract is unchanged: failures remain `EnvError` → rc 2, stdout stays
   empty (never a silent `0.0`). This slice changes the **message**, not the
   exit code or the oracle contract.
5. The preflight adds no measurable startup cost to the success path (probe
   results are computed once per run, not per screen).
6. Tests cover each failure branch and assert the message names the remedy.

**DoD:**
- [ ] Preflight implemented in `score.py`, invoked before the first
      `capture_app`.
- [ ] Unit tests for: node missing, library missing, browser unreachable, and
      the all-clear path.
- [ ] A test asserts stdout is empty and rc is 2 on every preflight failure.
- [ ] A test asserts the preflight never reads stdin (non-interactive).
- [ ] `SKILL.md` Prerequisites updated to reference the runtime guidance.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Vertical?** Yes — an adopter whose scoring run fails now receives a precise
remedy at the moment and place of failure. No config surface, no new transport,
no dependency on later slices.
