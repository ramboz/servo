---
status: IN_PROGRESS
dependencies: [001, 002, 003]
last_verified:
---

# Spec 011 — heartbeat

> The **scheduled front-end** of the servo loop. A Routine (cron / scheduled
> agent) wakes servo on an interval; servo runs a **read-only** discovery pass
> over the project's own signals (CI failures, open issues, recent commits),
> writes findings to a servo-owned **triage inbox**, and hands each *actionable*
> finding to the oracle-gated runtime (`loop.py`, spec 003) in an **isolated
> worktree**. The triage inbox is the **state spine**: it dedupes across runs
> and marks each finding `open` / `tried` / `passed` / `skipped`, so the next
> heartbeat **resumes** instead of re-discovering. `/servo:heartbeat` is a
> **Tier-2** surface — explicit opt-in only — because it lets a *schedule*,
> not a human, decide what servo works on.

> **Status: DRAFT.** Per the authoring decision (2026-06-12), this spec is
> reviewable at the **overview level** now, and slice **011-01 is fleshed to
> implementation-ready ACs** (it is the spike that validates the whole shape).
> Slices **011-02..05 are goals-only** in the slice index below — their
> acceptance criteria want grounding against (a) the spike's findings and (b) a
> real project that wants scheduled discovery, and are deliberately not pinned
> yet. Re-open a goals-only slice by SPIDR-splitting it into its own
> `slice-NN-*.md` file and transitioning it to `READY_FOR_REVIEW`. **Stop point:
> this is queued for plan review, not implementation.**

## Why this spec

Servo owns the **middle and tail** of the closed loop:

- **measure** — `gate.py` reads the oracle composite (spec 002);
- **adjust** — `loop.py` iterates `claude -p` against the target under hard
  guardrails (spec 003);
- **grade every turn** — the meta-judge `Stop` hook (spec 004);
- **scale** — N-worktree races pick the best result (spec 005);
- **judge against the spec** — deterministic AC overlays (spec 006);
- **persist** — per-run state at `.servo/runs/<run-id>/state.json` (ADR-0004).

Every one of those presupposes that **a human already decided what to work on
and kicked off a loop.** That is servo's current trigger model, stated plainly
in [product-vision.md](../../product-vision.md): "human kicks off a loop." There
is no surface that *surfaces work on a schedule* — nothing that wakes up, looks
at the project, and queues the loop. The loop has a body and a tail but **no
front-end.**

The heartbeat is that front-end: the **Routines-as-trigger** layer. It is what
makes "unattended" mean *un*attended — not "a human starts it and walks away,"
but "a schedule starts it and a human reviews the triage inbox later." It closes
the loop's front edge the same way spec 003 closed its control edge.

A servo (the control system servo is named for) needs a *set point* and a
*clock*. Specs 001–006 built the set point (the oracle) and the actuator (the
loop). The heartbeat is the clock.

## The trigger boundary: servo ships the heartbeat, the Routine triggers it

Servo does **not** own the scheduler. Consistent with the product vision's
competitive framing — *"GitHub Actions / CI recipes for agents — distribution
mechanism, not a scaffolder. Servo could feed into them, but isn't one"* — the
**Routine** (a cron entry, a scheduled cloud agent, a CI `schedule:` trigger,
`launchd`/systemd timer, whatever the project already uses) is the clock. It
invokes `/servo:heartbeat` (or `heartbeat.py run <target>`) on its interval.
Servo owns everything *downstream* of the wake-up: discovery, the triage inbox,
and oracle-gated dispatch.

This keeps servo's no-runtime-lock-in shape: the heartbeat is a plain command a
project can wire into any scheduler, the same way `oracle.sh` is a plain bash
script a project owns forever. Servo ships a **recipe** for wiring a Routine
(slice 011-05), not a daemon.

| Routine owns | Servo (heartbeat) owns |
|---|---|
| The schedule / cron expression | The read-only discovery pass |
| Waking the process | The triage-inbox state spine (dedupe, status) |
| Where it runs (laptop, CI, cloud) | Oracle-gated dispatch into isolated worktrees |
| Passing `--cost-ceiling` / target path | The whole-heartbeat cost ceiling enforcement |

## Distinct from jig's `inbox.md`

Servo's triage inbox is **not** jig's `docs/inbox.md`, and the two must not be
conflated:

| | jig `docs/inbox.md` | servo `.servo/triage/inbox.jsonl` (+ `inbox.md` view) |
|---|---|---|
| Purpose | **Cross-session continuity** — what a human/agent should pick up next session | **Scheduled-discovery triage** — what the project's *signals* surfaced this heartbeat |
| Written by | A session, at hand-off / memory-sync | The heartbeat's read-only discovery pass |
| Lifecycle | Human curates; consumed by the next session's recall | Machine spine: dedupe + `open`/`tried`/`passed`/`skipped` across runs |
| Trigger | Session boundary | A Routine's clock |
| Home | jig's docs tree, version-controlled | `<target>/.servo/triage/`, git-ignored runtime artifact |

They answer different questions ("where was I?" vs. "what does CI/issues/commits
say needs doing?"). Servo's inbox is a runtime artifact under `.servo/`, beside
`runs/` and `races/` — not a tracked doc. Keeping them separate avoids the trap
of a scheduled job stomping a human's continuity notes.

## Guardrails (servo's contract, applied to the heartbeat)

The task framing names three; each maps onto an existing servo invariant. A
**fourth** falls out of the unattended posture and was added at plan review
(2026-06-12).

1. **Discovery is strictly read-only — it proposes, it does not execute.**
   The discovery pass enumerates signals via `gh` / `git` (and, optionally and
   later, an LLM triage assist) and writes **only** under
   `<target>/.servo/triage/`. It never mutates target source, never runs a
   git-write command, never opens a PR/issue/comment, and never spawns a loop or
   a worktree. The *only* thing that executes is **dispatch** (011-03), and
   dispatch is separately gated. This is the read-only posture spec 006-01
   already holds for the planner (byte-snapshot the target tree outside the
   artifact dir; assert unchanged).

2. **The hard cost ceiling applies to the whole heartbeat, not per-loop.**
   `loop.py` (003-02) has a *per-run* ceiling (default $2). A heartbeat that
   dispatches five candidates would silently become a $10 pass under per-loop
   accounting — the same footgun [spec 005 flagged](../005-variant-race/spec.md)
   for per-variant ceilings. The heartbeat owns a **heartbeat-level** ceiling
   that bounds *discovery cost (if any) + the sum of every dispatched loop's
   cost*, and **fails closed** (halts the whole pass, leaves remaining findings
   `open` for the next heartbeat) when the budget is exhausted — never per-loop.

3. **Refuse-without-oracle still holds at the runtime boundary.**
   Discovery is oracle-*independent* (read-only enumeration needs no oracle). But
   **dispatch refuses** to spawn a loop for any candidate unless the target has a
   valid oracle + manifest — it defers to `gate.py`'s preflight refusal taxonomy
   (`manifest_missing` / `oracle_missing` / `oracle_not_executable`, ADR-0002).
   No finding crosses from "proposed in the inbox" to "a running loop" without
   passing the oracle gate. This is the existing **refuse-on-missing-prerequisite**
   principle, applied at the heartbeat's one execution edge.

4. **Discovered content is untrusted input — dispatch treats it as data, not
   instructions.** Discovery is read-only, but the text it ingests — issue
   titles/bodies, commit messages — is **attacker-influenceable** on any target
   whose repo accepts outside contributions, and the heartbeat's whole point is
   *unattended* dispatch (a human reviews the inbox *later*). So crafted issue or
   commit text can reach a tool-using `claude -p` loop **before** any human sees
   it. The blast radius is bounded — worktree isolation, the oracle gate on the
   *final* score (a prompt-injected loop still has to pass the project's oracle to
   "succeed"), and the whole-heartbeat ceiling — but the vector is real and shapes
   two downstream contracts: **011-03's dispatch prompt must frame discovered text
   as untrusted *data*, never instructions**, and **011-02's finding record may
   carry a provenance/trust marker** so dispatch can treat issue/commit-sourced
   findings differently from CI-sourced ones. This is the same threat-model honesty
   the spec-oracle freeze layer already applies (see
   [architecture.md](../../architecture.md) "Spec-oracle freeze & approval"
   threat model) — name the adversary and bound the blast radius rather than
   assume read-only discovery makes downstream dispatch safe. *(011-01 itself is
   discovery-only — no dispatch, no LLM — so the vector is inert here; this
   guardrail binds 011-02/011-03.)*

## Core model

```
Routine (cron / scheduled agent / CI schedule)      ← servo does NOT own this
  │  wakes servo on an interval
  ▼
heartbeat.py run <target> --cost-ceiling <usd>                        (spec 011)
  │
  ├─ discover   (READ-ONLY)                                           (011-01)
  │    probe  CI failures · open issues · recent commits   (gh / git, no LLM)
  │    → append/refresh findings in  .servo/triage/inbox.jsonl
  │
  ├─ triage     (STATE SPINE)                                         (011-02)
  │    dedupe across runs (stable finding_id) · status open|tried|passed|skipped
  │    → next heartbeat RESUMES; already-passed/tried findings are not re-run
  │
  └─ dispatch   (per actionable OPEN finding)                         (011-03)
       candidate
         → gate.py preflight ──── no oracle ────▶  REFUSE  (refuse-without-oracle)
         → isolated git worktree
         → loop.py <worktree>                       (spec 003 — oracle-gated)
         → record outcome back to inbox  (tried / passed)

  ┌──────────────────────────────────────────────────────────────────────────┐
  │ ONE hard cost ceiling bounds the WHOLE pass (011-04):                      │
  │ discovery (optional LLM assist) + every spawned loop — NOT per-loop.       │
  │ Fail-closed: halt the pass, leave remaining findings `open` for next time. │
  └──────────────────────────────────────────────────────────────────────────┘
```

- **Reserved state path** (to be added to `.gitignore`, like `runs/` / `races/`):
  `<target>/.servo/triage/` holds `inbox.jsonl` (the machine spine) and a
  generated `inbox.md` (the human-reviewable view) — the same machine-state +
  human-view split as `state.json` + `status-board`.
- **Heartbeat composes the loop; the loop doesn't know about the heartbeat**
  (the boundary spec 003 set). `loop.py` stays trigger-agnostic — it is invoked
  per candidate in a worktree exactly as a human would invoke it. The heartbeat
  adds discovery, triage state, and a wrapping ceiling around N loop runs, the
  same way spec 005's race driver wraps N loops.
- **Stateless gate, stateful caller** (architecture.md): `gate.py` writes
  nothing; the **inbox** is where the heartbeat persists cross-run state, exactly
  as `state.json` is where the loop persists per-run state.
- **Subcommands** mirror the house pattern (`gate.py invoke/audit`,
  `hook.py install/uninstall/status`): `heartbeat.py discover` (read-only,
  standalone — ships in 011-01), `dispatch` (011-03), `run` (= discover then
  dispatch under the ceiling — 011-04), `status` (read the inbox — 011-02).

## Out of scope (deferred to later specs or refused outright)

- **Owning the scheduler.** Servo ships a Routine-wiring *recipe* (011-05), not a
  cron daemon, a queue, or a long-lived process. The Routine is the project's.
- **Mutating remote state during discovery.** Discovery never opens issues/PRs,
  comments, labels, or pushes. It *proposes* via the inbox; a human (or a
  dispatched, oracle-gated loop) is the only thing that acts.
- **A new scorer.** Candidates are run by the *existing* `loop.py` and judged by
  the *existing* `gate.py` composite (optionally a spec-006 overlay). The
  heartbeat introduces no special-case scoring — same no-special-casing
  discipline 006-03 / 005 held.
- **Auto-install.** Tier-2, explicit opt-in only (architecture.md tier model).
  The heartbeat never lands without the user asking for it.
- **Replacing jig's `inbox.md`.** Different artifact, different purpose (see
  above). No migration, no merge.
- **Cross-machine / distributed discovery or dispatch.** Per ADR-0001's
  filesystem-only coupling: worktrees and the inbox are local to the machine the
  Routine runs on.
- **Remediation logic.** *What* a dispatched loop does to fix a finding is the
  loop's job (the prompt + the oracle). The heartbeat only decides *which*
  findings become candidates and hands them off.
- **A universal "is this actionable?" classifier.** v1 uses a documented,
  deterministic heuristic (see Open questions); a model-assisted triage pass is a
  flagged future extension behind the whole-heartbeat ceiling.

## SPIDR decomposition

Mirrors the spec 001 / 002 / 003 cadence (spike-shaped first slice → state spine
→ the execution edge → the wrapping guardrail → skill + dogfood last) because the
problem shape rhymes: ship a tool a Routine invokes, in vertical slices that each
deliver end-to-end value. After **011-01** alone, a project can already put
read-only discovery on a schedule and review the inbox — every later slice adds a
capability, not a prerequisite for "discovery works."

### Slice index

| Slice | Title | Goal | State |
|---|---|---|---|
| 011-01 | discover-and-inbox | **Spike-shaped, implementation-ready.** `heartbeat.py discover <target>` does a **read-only** probe of CI failures (`gh`), open issues (`gh`), and recent commits (`git`), and writes findings to `<target>/.servo/triage/inbox.jsonl` + a generated `inbox.md` view. Validates the scheduled-read-only-discovery→inbox assumption end-to-end. | Implementation-ready |
| 011-02 | triage-state-spine | The inbox becomes the **state spine**: a stable `finding_id` fingerprint dedupes across runs; a status lifecycle (`open`→`tried`→`passed`/`skipped`) is tracked; `heartbeat.py status` reads it back. The next heartbeat **resumes** — already-passed/tried findings are not re-surfaced as new work. | Goal only |
| 011-03 | candidate-dispatch | Each **actionable, `open`** finding becomes a candidate: `gate.py` oracle **preflight (refuse-without-oracle)** → an **isolated git worktree** → `loop.py` (spec 003) → the outcome (`tried` + final oracle status, or `passed`) is recorded back to the inbox. Nothing spawns a loop without passing the oracle. (Seam: `race.py` (005) as an alternate dispatch target when it lands.) | Goal only |
| 011-04 | heartbeat-cost-ceiling | A **heartbeat-level** hard cost ceiling bounds *discovery (any LLM assist) + the sum of all dispatched loops* — **not** per-loop. `heartbeat.py run` = discover → dispatch under this one ceiling; **fail-closed** halt of the whole pass leaves remaining findings `open` for the next run. Distinct from `loop.py`'s per-run ceiling (003-02). | RECONCILED |
| 011-05 | skill-and-dogfood | `/servo:heartbeat` SKILL.md — **Tier-2 explicit-opt-in** framing, the read-only-discovery promise, the whole-heartbeat-ceiling warning up front, the refusal table, and the **Routine-wiring recipe** (cron / CI `schedule:` / scheduled agent). Plus an end-to-end dogfood driving the real discover → triage → preflight → worktree → loop → record chain on a fixture target. | Goal only |

Five slices, sized to the spec 001 / 002 / 003 cadence. The vertical-value rule
holds — after every slice the heartbeat is end-to-end usable at its current
capability.

## Slices

- [011-01 — discover-and-inbox](slice-01-discover-and-inbox.md) — **DONE**
- [011-02 — triage-state-spine](slice-02-triage-state-spine.md) — *goals-only DRAFT stub; ACs pinned at SPIDR-split*
- [011-03 — candidate-dispatch](slice-03-candidate-dispatch.md) — *goals-only DRAFT stub*
- [011-04 — heartbeat-cost-ceiling](slice-04-heartbeat-cost-ceiling.md) — **RECONCILED**
- [011-05 — skill-and-dogfood](slice-05-skill-and-dogfood.md) — *goals-only DRAFT stub*

## Spec-level Definition of Done (forward-looking)

- [ ] All five slices DONE — each reviewed by `jig:reviewer` subagent.
- [ ] End-to-end dogfood (011-05): a fixture target with a scaffolded oracle is
      put through one full `heartbeat.py run` — discovery enumerates seeded
      signals, an actionable finding is dispatched through the oracle preflight
      into a worktree loop, the inbox records the outcome, and the
      whole-heartbeat ceiling halts a deliberately over-budget pass with
      remaining findings left `open`.
- [ ] `<target>/.servo/triage/` is **reserved in `.gitignore`** alongside
      `runs/` and `races/` (resolves the architecture.md "reserved paths" note;
      see the open refinement-todo "Scaffold-init does not write `<target>/.gitignore`").
- [ ] `docs/architecture.md` reflects the **shipped** surface. *Registered at
      spec authoring (2026-06-12):* the skill-split row, the Tier-2 classification,
      the project-vs-core split row, the reserved `.servo/triage/` runtime-artifact
      path, and the triage-inbox-schema ADR candidate. *Finalized at close-out:*
      the Runtime-artifacts inbox schema once slice 011-02 pins the `finding_id` +
      status contract (and its ADR is Accepted).
- [ ] [README.md](../../../README.md) skills table: the `/servo:heartbeat` row
      reads **DONE** (registered as **DRAFT** at spec authoring).
- [ ] [docs/product-vision.md](../../product-vision.md) backlog #7 + the
      schedule-triggered design principle reflect the shipped surface.
- [ ] ADR(s) recorded (see candidates below).
- [ ] [docs/specs/README.md](../README.md) status board reflects final state
      (via `workflow.py status-board`).

## ADR candidates

Two hard-to-reverse decisions this spec is likely to force (next free number is
**0008**; numbers are hints, not reservations):

- **Triage-inbox state-file schema + dedupe identity.** Reciprocal to
  [ADR-0004](../../decisions/adr-0004-session-state-file-format.md) (the per-run
  `state.json`). The inbox is append-and-update cross-run state; its
  `finding_id` fingerprint scheme (what makes two discoveries "the same finding"
  across runs) and its status lifecycle are a contract later tooling reads, and
  changing them after data exists is migration-shaped. Crystallizes at 011-02.
- **Heartbeat-level vs per-loop cost-ceiling semantics.** Whether the ceiling is
  whole-pass (this spec's position) or per-loop, and how a partially-spent
  heartbeat resumes, is a guardrail contract a footgun depends on (the $2→$10
  surprise). Could fold into the schema ADR or stand alone. Crystallizes at
  011-04. (Shares DNA with spec 005's per-variant-vs-per-race open question.)

## Open questions (not yet ADR-worthy)

- **What makes a finding "actionable"?** v1 needs a documented, deterministic
  rule (e.g., a CI failure on the default branch is actionable; a 2-year-old
  `wontfix` issue is not). Mis-triage is cheap to correct because the inbox is
  reviewable — perfect first-pass accuracy is not the bar (same posture as
  006-01's classifier). A model-assisted triage pass is a flagged extension
  behind the whole-heartbeat ceiling.
- **What is a commit-derived finding?** A CI failure maps cleanly to "fix this"
  and an open issue to "do this"; a *recent commit* maps to neither — it is
  history, not a request. v1 enumerates recent commits as findings (011-01 AC1,
  recorded `open`), but what makes one ever *actionable* — a revert? a commit
  touching code with no test? a message carrying `TODO`/`FIXME`? — is unpinned.
  Until 011-02 pins it (alongside "what makes a finding actionable?"),
  commit-findings may be inbox noise; resolve the two together against the
  spike's real output before 011-02's ACs are written. (Surfaced at plan review,
  2026-06-12.)
- **Finding fingerprint scheme.** What dedupes a CI failure across runs — the
  failing job name? the workflow + step? the error signature? Too coarse merges
  distinct failures; too fine re-surfaces the same one every heartbeat. Wants a
  real signal stream to tune (drives the 011-02 ADR).
- **Dispatch concurrency.** Serial candidates (smoother spend, simpler) vs.
  bounded-parallel (faster, but interacts with the whole-heartbeat ceiling and
  edges toward spec 005's territory). Default likely serial; the ceiling is
  easier to enforce deterministically against a serial sum.
- **loop vs race as the dispatch target.** 011-03 dispatches to `loop.py` (003,
  DONE). When spec 005 (`race.py`, currently parked) lands, a candidate could be
  raced instead of single-shot looped. Keep dispatch pluggable; don't hard-wire.
- **How does the Routine pass the ceiling / which signals?** Flags on the
  invocation vs. a `.servo/heartbeat.json` config the discovery reads. Leaning
  flags first (no new config surface), config later if flags get unwieldy.
- **Read-only *enforcement*, not just convention.** AC-level byte-snapshotting
  proves discovery didn't mutate the tree in tests, but is there a stronger
  runtime guarantee (run discovery with a no-write tool profile / in a read-only
  view)? Worth deciding before discovery ever grows an LLM assist.
- **Double-fire idempotency.** If a Routine fires twice (overlap, retry), two
  `heartbeat.py run`s hit the same inbox. Per-run isolation works for `loop.py`
  (003, Q10) but the inbox is *shared* cross-run state — 011-02 needs an
  advisory lock or an atomic update discipline so a double-fire can't corrupt it.

## References

- [docs/product-vision.md](../../product-vision.md) — the new
  *schedule-triggered* use-case + the design principle this spec implements;
  the "human kicks off a loop" model it extends; backlog #7.
- [docs/architecture.md](../../architecture.md) — the Tier-2 model, the
  project-vs-core split, the reserved `.servo/` runtime-artifact paths, and the
  stateless-gate / stateful-caller contract the inbox follows.
- [Spec 003 — agent-loop](../003-agent-loop/spec.md) — the dispatch target the
  heartbeat composes; its per-run cost ceiling (003-02) is the contrast the
  whole-heartbeat ceiling (011-04) is defined against; its out-of-scope note
  ("the loop doesn't know about variants") set the compose-don't-couple boundary.
- [Spec 002 — quality-gate](../002-quality-gate/spec.md) /
  [ADR-0002](../../decisions/adr-0002-gate-caller-contract.md) — the preflight
  refusal taxonomy dispatch defers to (refuse-without-oracle).
- [Spec 005 — variant-race](../005-variant-race/spec.md) — the per-variant-vs-
  per-race ceiling question 011-04 rhymes with; the optional alternate dispatch
  target for 011-03.
- [ADR-0004](../../decisions/adr-0004-session-state-file-format.md) — the
  per-run state-file precedent the triage-inbox schema ADR is reciprocal to.
- [ROADMAP.md](../ROADMAP.md) — sequencing rationale (011 depends on 003; it is
  the front-end the loop/race/state consume from).
- jig's `docs/inbox.md` — the cross-session-continuity artifact servo's triage
  inbox is deliberately **distinct** from.
