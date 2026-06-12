# ADR-0008 V4 probe — can a Routine run the project-local oracle + meta-judge?

V4 asks whether **Routines** (scheduled, unattended runs on Anthropic-managed
cloud infra) can clone a target, run `servo:quality-gate`, and run the meta-judge
hook under the cloud env's hook policy. Unlike V1–V3, the cloud leg **cannot be
driven from a local script** — so this probe is: (1) discovery, (2) a FREE local
simulation of the executable parts, (3) a manual cloud checklist.

## 1. Discovery (this environment, 2026-06-12)

- `claude` 2.1.175 exposes **no `routine`/`schedule` subcommand**
  (`Commands:` = agents, auth, auto-mode, doctor, install, mcp, plugin, project,
  setup-token, **ultrareview**, update). The only cloud-exec surface in the CLI
  is `ultrareview`. **Routines are created/managed from the web app
  (claude.ai/code) or desktop, not this CLI** → V4's cloud leg is a manual
  console exercise, not automatable here.
- No managed-settings file on this machine, so `allowManagedHooksOnly` is not in
  force by default here (see V3 / `v3_audit_env.py`).

## 2. What the FREE local sim settled (`./v4_clean_clone_sim.sh`)

- A `git clone`d target runs `servo:quality-gate` (gate.py + oracle.sh +
  `.servo/install.json`) from a clean checkout. ✓
- **The meta-judge is clone-portable only if servo's `gate.py` is VENDORED** into
  `<target>/.claude/skills/servo-quality-gate/gate.py` (a path relative to
  `CLAUDE_PROJECT_DIR`). A non-vendored install bakes servo's **absolute local
  path**, which won't exist in a cloud clone → the hook fails open (never blocks).
  → **Action for the rebase:** Routines must vendor `gate.py` into the target
  (or install servo as a plugin at a known path) so the meta-judge resolves after
  a clone.

## 3. Manual cloud checklist (run once; record results below)

Create a minimal Routine (web/desktop) pointed at a servo-scaffolded repo whose
prompt runs the loop body (`servo:quality-gate` each turn, print the
`SERVO_ORACLE_VERDICT …` sentinel) under a `/goal` condition, then observe:

1. **Clone** — does the run check out `oracle.sh`, `.servo/install.json`, and the
   vendored `.claude/skills/servo-quality-gate/`?
2. **Oracle** — does the loop body run `servo:quality-gate` and surface the
   `SERVO_ORACLE_VERDICT …` sentinel? (capture one transcript line)
3. **Meta-judge Stop hook** — does the cloud env FIRE the project Stop hook? Look
   for a `Stop` hook event + `{"decision":"block"}` on a below-threshold turn.
   Absent → the env likely runs `allowManagedHooksOnly`/`disableAllHooks`.
4. **Hook policy** — if you have shell access in the routine, run
   `python3 v3_audit_env.py .` there to read the effective settings.
5. **/goal continuation** — does `/goal` continue across turns in the cloud as it
   does in headless `-p` (V2)?

### Pass / fail

- **PASS (V4 cleared):** clone + gate.py + sentinel all work in-cloud, AND either
  the cloud permits the project meta-judge hook (Stop fires) OR servo accepts
  running in-cloud *without* the meta-judge backstop — relying on the loop-body
  `gate.py` + a final authoritative `gate.py` as the deterministic authority
  (consistent with V1's residual note: the meta-judge is a backstop, not the
  driver, once `/goal` owns continuation).
- **FAIL → Kill-criterion 4 in the cloud:** the Routine env enforces
  managed-only / disabled hooks AND servo requires the meta-judge → neither it
  nor `/goal` work there. Mitigation: have the routine prompt invoke the
  hand-rolled `loop.py` directly (no hooks, no `/goal`) — scheduling then runs
  the fallback driver rather than the rebased one.

### Results

**Run 1 — LOCAL dry-run of the prompt (2026-06-12).** NOT an actual Routine and
NOT Stop-mediated (executed as a single continuous agent invocation) — so it is a
prompt / portability / policy check, not the Routine-execution test.

| Check | Result | Notes |
|------|--------|-------|
| 1. clone | n/a | ran in-place against the local repo (no cloud clone) |
| 2. oracle + sentinel | ✅ | `SERVO_ORACLE_VERDICT` printed each turn; the vendored relative `gate.py` ran |
| 3. meta-judge Stop fires | ❌ not observed | single continuous invocation (no Stop event) + a one-shot task (no failing stop to block) |
| 4. hook policy (audit) | ✅ permissive (LOCAL) | no `disableAllHooks` / `allowManagedHooksOnly`; `Stop-hooks=1` |
| 5. /goal continuation | ⚠ partial | reached `status=pass` in 2 turns, but as one invocation — not `/goal`-mediated turns |
| **Verdict** | **inconclusive for the cloud gate** | local-only, not Stop-mediated, not an actual Routine |

**Insight surfaced:** a Routine that runs the task as **one continuous invocation**
never engages the meta-judge (a `Stop` hook) at all — *independent of hook policy*.
The backstop engages only in a **turn-mediated** run (`/goal`-driven, or loop.py).
So servo's in-Routine authority is the loop-body `gate.py` + a final `gate.py`; the
meta-judge helps only when the Routine fires `Stop` per turn.

**Run 2 — LOCAL scheduled Routine trigger (2026-06-12).** An actual scheduled
trigger (real unattended execution ✓), but still **local** and still **not
Stop-mediated** — the task ran as one continuous agent session; the meta-judge was
**manually** invoked against a temp copy to show block-on-fail (same as V1 /
preflight, *not* a natural Routine `Stop`). Two findings:
- **State pollution:** the run inherited `greeting.py` already fixed (uncommitted)
  from Run 1's tree → a spurious immediate `status=pass`; the agent had to reset to
  the committed failing baseline. → scheduled runs reusing a persistent tree need a
  clean baseline each run; servo's **refuse-on-dirty-tree** guardrail is load-bearing
  here. (A remote fresh-clone Routine avoids this.)
- **Continuous invocation:** the Routine did not fire the meta-judge per turn →
  confirms Run 1's insight; in Routines, `gate.py` (loop-body + final) is the
  authority, not the `Stop` hook.

**Run 3 — REMOTE actual Routine (TODO).** The remaining gate: fresh clone, capture
`audit_env.py` (the *cloud* hook policy), confirm the oracle/test execute in-cloud.
Reset to the committed baseline at the start of each run.
