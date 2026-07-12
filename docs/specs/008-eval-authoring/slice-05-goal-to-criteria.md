---
status: DRAFT
dependencies: [008-01, 015, 006, adr-0027, adr-0001]
last_verified:
---

## Slice 008-05 — goal-to-criteria

**Goal:** Expand a free-form **goal** into a *proposed* acceptance-criteria set,
each AC tagged `deterministic | judged | human-only` with a rationale; have a fresh
**independent-reviewer subagent** check the frame; let the human curate and approve;
then emit a spec-shaped AC artifact that re-enters the pipeline at `edd-suitability`
(015) → `spec-oracle classify` (006) → 008-01 triage. The opt-in front-end that
closes servo's goal-vs-spec impedance, gated so it cannot manufacture a false
criterion ([ADR-0027](../../decisions/adr-0027-goal-to-eval-assisted-authoring.md)).

### Acceptance criteria

- **AC1** `eval_authoring.py from-goal <goal>` expands a free-form goal into a
  proposed AC set; each AC carries a tag `deterministic | judged | human-only` and a
  one-line rationale.
- **AC2** A **fresh independent-reviewer subagent** (no access to the expansion
  conversation) reviews the proposal against the goal for **faithfulness**, **honest
  tagging**, **measurability**, and **gaps** — reliably on the *structural* forms
  (wording-obvious mis-tags, unmeasurable predicates, goal-restatement, surface-literal
  coverage gaps); faithfulness AND *implicit* coverage of intent are best-effort
  advisory reads only, since both are epistemic and the human's job (ADR-0027 Decision #2) — emitting advisory flags, not a
  rubber-stampable verdict. It reuses `jig:independent-review` when jig is co-installed (the ADR-0001
  filesystem-hint coupling), else a built-in servo eval-frame-review prompt — servo
  does not hard-depend on jig.
- **AC3** The proposal + reviewer flags are presented to the human, who edits /
  accepts / rejects / **adds** each AC (adding covers criteria the expansion
  omitted — the human is the backstop for coverage-of-intent). Only the curated set proceeds; **nothing is frozen
  without recorded human approval** (spec 008 goal 6; ADR-0005).
- **AC4** The curated AC set is emitted as a lightweight, project-owned, spec-shaped
  artifact that `edd-suitability` (015) and `spec-oracle classify` (006) consume
  **unchanged** — no downstream contract change.
- **AC5** Running the criteria-classification half of `edd-suitability` (015) on the
  emitted artifact surfaces the **evaluable-vs-human-residual split** over the ACs,
  so the author learns early whether the goal is mostly evaluable vs mostly taste.
  The **full** `suitable | needs_evidence | unsuitable` verdict is explicitly
  deferred until the target's signals + reference set exist (post-008-03) — an eval-able AC with no reference set resolves to
  `needs_evidence` (ADR-0015), and the reference set is collected only later
  (008-03; cf. ADR-0018 on not expecting a verdict from an inputs-missing synthesis), so goal→eval does not claim the full verdict here.
- **AC6** Goal→eval is **opt-in**: an author with hand-written ACs skips `from-goal`
  and enters at 008-01. The review + curation stay in the authoring layer and never
  invoke `gate.py`/`oracle.sh` (ADR-0021 / ADR-0011 / ADR-0005 boundary).
- **AC7** Tests cover: expansion producing tagged ACs; a **structurally** mis-tagged
  taste-call (one whose own wording marks it policy/taste — e.g. "requires a senior
  editor's sign-off" tagged `deterministic`) **flagged by the reviewer**; a plausible-but-unfaithful criterion NOT
  assumed caught — instead the **human-curation gate** is asserted to block any AC
  from freezing without a recorded per-AC approval, and the human can **add** a
  criterion the expansion omitted; the built-in reviewer path
  exercised with jig absent; the emitted artifact feeding 006 (and 015's criteria
  split) unchanged.

> This is the net-new capability the surveyed prior art deliberately refused — made
> safe by the independent-review + human-curation gate it was missing.
