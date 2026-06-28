---
status: DEFERRED
dependencies: [015-01, 015-02, 011, adr-0015, adr-0010]
arch_review: true
frame_review: true
last_verified:
---

## Slice 015-03 — pipeline-gate

**Goal:** Make the verdict a **gate**, at its grounding consumer. The heartbeat
(011, DONE) consults the suitability verdict **per finding**, *before* the 011-03
oracle-gated dispatch: a non-`suitable` finding is recorded `skipped` with a
machine `actionable_reason` and is **never dispatched** into a worktree loop. The
same verdict is also the Servo Compile precondition (Compile proceeds only on
`suitable`). This is the slice that turns ADR-0015 from a document into a refusal
the unattended system actually performs — the worst failure mode (a meaningless
green oracle on un-evaluable work, dispatched on work *no human chose*) is
refused at the boundary, before any budget is spent.

> **Boundary with 015-01 / 015-02 and 011-03.** 015-01/02 *produce* the verdict +
> evidence list; this slice *consumes* them at two call sites. It does **not**
> change candidate *fingerprinting*, retention, or the oracle preflight — it
> inserts a gate **between** candidate selection (`actionable AND open`) and the
> `gate.py` oracle preflight in `heartbeat.py`. Landing/merging a worktree result
> stays out of scope (as in 011-03).

**Resolution trigger:** Re-open when **either** (a) spec 016 (execution-planner)
lands a **Servo Compile entry point** that AC5's precondition can actually gate,
**or** (b) a **finding→spec linkage** (and a finding-shaped suitability input) is
specced for the heartbeat — so a heartbeat finding can map to a verdict the
analyzer can produce.

> **⚠️ DEFERRED 2026-06-28 (pre-implementation frame-critique).** Both of this
> slice's grounding consumers are missing today, so it cannot be implemented
> faithfully:
>
> 1. **Heartbeat per-finding gate (AC1–4, AC6) is incoherent for spec-less
>    findings.** The 015-01/02 verdict is *spec-centric*: `decide()` keys off AC
>    classification (`oracle_plan.py classify` over a `spec.md`). A heartbeat
>    finding (CI / issue / commit — [`heartbeat.py:638`](../../../skills/heartbeat/heartbeat.py),
>    framed directly as a `loop.py --prompt` at
>    [`heartbeat.py:1537`](../../../skills/heartbeat/heartbeat.py)) carries **no
>    spec and no ACs**. There is nothing to pass to
>    `suitability.py analyze --spec`, so AC4 (fail-closed on an unavailable
>    verdict) would fire for *every* finding → every finding recorded `skipped`
>    with `suitability_unavailable` → the heartbeat dispatches **nothing, ever**.
>    A gate that refuses all work is an off switch, not a gate. No finding→spec
>    linkage exists anywhere in the repo (grep-verified).
> 2. **Compile precondition (AC5) has no Compile to gate.** There is no Servo
>    Compile entry point implemented (`/servo:compile` / `run_compile` absent);
>    the `/servo:edd-suitability → Compile` handoff is the unbuilt skill (015-04)
>    feeding the unbuilt planner (016, DRAFT/parked). Gating a phase that doesn't
>    exist is not a vertical slice.
>
> The 015 spec.md activated this slice "against its grounding consumer: the
> heartbeat (011, DONE)"; the frame-critique shows 011 being *done* doesn't make
> it able to *consume* a spec-centric verdict for spec-less findings. ADR-0015's
> heartbeat-mapping claim is amended accordingly (see its `## Amendments`). The
> verdict + evidence artifact (015-01/02) is shipped and inspectable; only its
> *gating wiring* is parked.

**DoR:**
- ✅ **015-01 + 015-02 DONE** — `suitability.py analyze <target> --spec <path>`
  emits the verdict + populated `missing_evidence` at
  `<target>/.servo/suitability/<spec-id>.json`; subprocessed (never imported),
  mirroring 011-03's `gate.py` / `loop.py` seam (`SERVO_HEARTBEAT_*` env hook).
- ✅ **011 DONE** — `heartbeat.py` selects the candidate set = `actionable == true
  AND status == "open"` (ordered `discovered_at`, `finding_id`) at the dispatch
  call site; the locked (`fcntl.flock`) + atomic (`tmp` + `os.replace`) merge
  writes `status` / `actionable_reason`; `STATUS_SKIPPED = "skipped"` and the
  `actionable_reason` machine-code convention (`REASON_*`) already exist
  ([`heartbeat.py`](../../../skills/heartbeat/heartbeat.py) L153-189). The gate
  inserts at the candidate-selection → oracle-preflight seam.
- ✅ **ADR-0015 Accepted** — explicitly sanctions the heartbeat mapping: a
  `unsuitable` / `needs_evidence` finding is "recorded back to the triage inbox
  (mapping naturally onto the existing `skipped` lifecycle with an
  `actionable_reason`) rather than spawning a loop."
- ✅ **ADR-0010 Accepted** — the `skipped` status + `actionable_reason` field are
  the recorded surface this slice writes through.

## Assumptions

- **A1 (load-bearing) — `skipped` becomes auto-settable.** 011-02 recorded
  `skipped` as **human-only** ("`skipped` is never auto-set"). This slice makes
  the suitability gate the **first automated setter** of `skipped`, which
  ADR-0015 sanctions but 011-02's prose predates. Treated as a contract
  *evolution*, not a contradiction: reconciliation must amend the 011-02 record
  (closed-spec drift, ADR-0010 amendment policy) to read "human-only **except**
  the ADR-0015 suitability gate," and the new reason codes must be visibly
  suitability-scoped so a reviewer can tell a gate-`skipped` from a human-`skipped`.
  *To verify at implementation:* re-read the exact 011-02 invariant in
  `heartbeat.py` + `test_heartbeat.py` and confirm no test asserts "no automated
  skipped writer exists" (which would need updating, not bypassing).
- **A2 — new reason codes, not a reused one.** The gate writes new
  `actionable_reason` machine codes (`suitability_unsuitable` /
  `suitability_needs_evidence`) rather than overloading an existing CI/issue
  reason, so triage stays auditable. *To verify:* the `REASON_*` set has no
  collision.

**Acceptance Criteria:**

1. **Per-finding gate before dispatch.** For each candidate (`actionable AND
   open`), `heartbeat.py` consults the suitability verdict for that finding's spec
   **before** the 011-03 oracle preflight / worktree creation. A `suitable`
   verdict proceeds to the existing dispatch path unchanged; a non-`suitable`
   verdict is gated out (AC2). The insertion changes neither candidate
   fingerprinting nor retention. *Test:* `SuitabilityGateOrderingTests`.

2. **Non-`suitable` ⇒ `skipped`, never dispatched.** A finding whose verdict is
   `unsuitable` or `needs_evidence` is recorded `status = "skipped"` with
   `actionable_reason ∈ {suitability_unsuitable, suitability_needs_evidence}`
   through 011-02's locked atomic merge, and **no worktree is created and no
   `loop.py` runs** for it. The finding leaves the candidate set on the next pass
   (resume discipline). *Test:* `SuitabilityGateSkipTests`.

3. **`skipped` provenance is auditable (A1/A2).** A suitability-`skipped` finding
   is distinguishable from a human-`skipped` one by its suitability-scoped
   `actionable_reason`; the `inbox.md` render shows the reason so a reviewer sees
   *why* it was turned away. No existing `REASON_*` code is overloaded. *Test:*
   `SkipProvenanceTests`.

4. **Fail-closed on an unavailable verdict.** If `suitability.py` cannot produce a
   verdict (exit 2 / no artifact / unparseable), the finding is **not** dispatched
   — it is treated as non-`suitable` and recorded `skipped` with a distinct
   `suitability_unavailable` reason (refuse, don't optimistically dispatch). A
   broken suitability analyzer never opens the dispatch gate. *Test:*
   `SuitabilityGateFailClosedTests`.

5. **Compile precondition.** The Compile entry path (the documented
   `/servo:edd-suitability` → Compile handoff) proceeds only on a `suitable`
   verdict; a non-`suitable` verdict halts Compile and surfaces `reasons` +
   `missing_evidence` as the next step (no oracle synthesis, no run). *Test:*
   `CompilePreconditionTests`.

6. **Spine-safe + idempotent.** The `skipped` write reuses 011-02's
   `flock` + `tmp` + `os.replace` discipline (no torn inbox under a concurrent
   `discover`); re-running the gate on an already-`skipped` finding is a no-op
   (it is no longer `open`, so not a candidate). *Test:* `GateSpineSafetyTests`.

**DoD:**
- [ ] All ACs pass; `test_heartbeat.py` + `test_suitability.py` extended;
      `ruff check .` clean.
- [ ] Reviewed by jig compliance + craft + **arch** passes (arch: inbox-contract
      change); record review evidence.
- [ ] Deviation log produced under this slice heading.
- [ ] **Reconciliation: amend the 011-02 record** for the `skipped` human-only →
      gate-settable evolution (ADR-0010 amendment policy), and sweep
      `heartbeat.py` SKILL.md for the same prose.
- [ ] `docs/specs/README.md` regenerated.

### Close-out (post-DONE)
- [ ] Migrate the suitability `actionable_reason` codes into the board Notes /
      memory so the heartbeat reason taxonomy stays discoverable.
