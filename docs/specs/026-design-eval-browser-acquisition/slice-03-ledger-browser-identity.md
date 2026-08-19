---
status: DRAFT
dependencies: [026-02, adr-0031]
last_verified:
frame_review: true
---

## Slice 026-03 — ledger-browser-identity

**Goal:** Record what actually rendered each score. Append the resolved
transport and browser name + version to every `ledger.jsonl` row, so a human
investigating a fidelity-score shift can see whether the engine changed.

**DoR:**
- ✅ 026-02 resolves a transport at runtime, so there is something to record.
- ✅ **The boundary is settled:** this is **observability, not a gate**. Browser
  identity is environmental — never hashed, never a staleness trigger. An
  advisory warning on change is permitted; a refusal requires a superseding ADR
  (ADR-0031).
- ✅ **The consumer is a human.** No programmatic reader of `ledger.jsonl` exists
  today and this slice adds none; ADR-0017 (Proposed) is where a programmatic
  trend consumer would be decided.
- ⚠️ **A2 unverified:** is a trustworthy browser name+version cheaply obtainable
  on both transports? Probe before implementing. If the string cannot be trusted,
  ADR-0031 kill criterion 2 says **omit it rather than record something
  misleading** — a wrong provenance record is worse than none.

**Acceptance criteria:**
1. Each `ledger.jsonl` row gains the resolved transport and the browser
   name + version.
2. The fields are **not** in `definition_hash` and **not** in `artifact_hashes`;
   changing browsers never raises `StaleError`. A test asserts this.
3. Ledger writing stays **best-effort** — a failure to resolve the version, or
   an `OSError` on write, must not fail the score (the existing writer already
   swallows `OSError`; this slice must not make provenance load-bearing).
4. If the version cannot be determined, the row records an explicit unknown
   rather than a guess or a silently-omitted field.
5. The reference-render engine is recorded where available, so reference-vs-app
   engine mixing is at least *visible* (it is structural and not fixed here).
6. Tests cover: identity present on both transports, unknown-version handling,
   and hash-invariance.

**DoD:**
- [ ] A2 probed; result and disposition recorded in the deviation log.
- [ ] Ledger rows carry transport + browser identity (or explicit unknown).
- [ ] Hash-invariance test green (no `StaleError` on engine change).
- [ ] Best-effort semantics preserved — a provenance failure never fails a score.
- [ ] `SKILL.md` ledger table documents the new fields and names the consumer.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Vertical?** Yes — an operator investigating "why did fidelity drop?" gains the
evidence to answer it.
