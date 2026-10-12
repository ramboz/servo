---
status: DONE
dependencies: [031-02, adr-0039]
last_verified: 2026-10-12
arch_review: true
code_health_review: true
frame_review: true
---

## Slice 033-01 — diagnostic-handoff

**Goal:** An operator can read a dispatched run's real final score, stop reason,
and existing fix hint in heartbeat triage without changing its control policy.

**DoR:**
- [x] ADR-0039's optional-field/versioning decision has passed frame review and
      its acceptance gate.
- [x] The retrospective scope and external-consumer assumption have passed
      frame/spec-readiness review; no claim of spec-first execution is made.
- [x] Both driver summary shapes and the heartbeat writer/readers are grounded
      in source and existing fixtures.

**Acceptance Criteria:**

1. **Durable diagnostic handoff.** A parseable loop summary's nonempty string
   `terminal_reason` and optional nonempty string `terminal_breadcrumb` are
   preserved in the finding's sticky `outcome`. Their addition does not change
   its run ID, oracle status, cost, dispatch timestamp, or attempts counter.
2. **Correct score for both drivers.** The portable loop's last history entry
   remains authoritative. A goal summary without history uses its direct
   `oracle_composite`; zero is retained and an unavailable score remains null.
   A goal cap is not relabeled as a plateau.
3. **Immediate read-only human status.** `heartbeat.py status` displays recorded
   oracle results, stop reasons, and supplied fix hints without executing
   discovery/dispatch, shelling out, or mutating target files. `status --json`
   keeps its existing version/counts/open-candidates structure.
4. **Discovery-rendered handoff.** On the next discovery refresh, `inbox.md`
   includes the same recorded diagnostics and score. Rediscovery preserves
   the sticky outcome and existing non-open status. This does not claim the
   view is rewritten immediately by `dispatch`.
5. **Legacy and absent data.** Summaries without diagnostics retain the original
   five-field outcome shape/order. Old records without diagnostics, or with
   no outcome, remain readable. No field rename, required diagnostic, inbox
   schema-version change, or migration of existing outcomes is introduced.
6. **Control-policy preservation.** Passes remain `passed`; below-threshold
   goal turn/budget caps and permission-wall diagnoses remain `tried`. Only
   the existing genuine `oracle_plateau` terminal triggers quarantine.
   Candidate selection, retry limits, budgets, claim checks, and evidence-gated
   re-admission are unchanged.
7. **Runtime/documentation parity.** The canonical skill and architecture prose
   describe the actual write/read timing and optional fields. Regenerated
   Claude and Codex packages contain the same implemented behavior.

## Grounding

- Summary producers: `skills/agent-loop/loop.py::_summary_payload` and
  `_goal_summary` emit the two shapes and optional hint; portable summaries
  carry history, goal summaries carry a direct final composite.
- Bridge: `skills/heartbeat/heartbeat.py::_run_loop`, `_dispatch_one`,
  `_outcome_from_summary`, and `run_dispatch` connect summaries to sticky
  outcomes. `_select_candidates` and `_reconcile_quarantine` own admission.
- Readers: `run_status`, `_render_status_human`, and `_render_markdown`.
  The machine `status --json` shape comes from `_summarize_inbox`.
- Existing fixtures: `OutcomeSummaryHandoffTests`, `LoopDispatchOutcomeTests`,
  `OutcomeRecordingTests`, `StatusSubcommandTests`, and quarantine tests.

## Assumptions

Unknown external readers may require the exact old outcome key set.
In-repository compatibility is verifiable; external compatibility is not
claimed. The frame pass must evaluate this bounded scope and ADR-0039's
reconsideration trigger.

**DoD:**
- [x] All acceptance criteria verified; full repository suite and CI mirror green.
- [x] Regression tests cover both summary shapes, zero/null scores, absent
      diagnostics, actual dispatch/persistence, both human views, and controls.
- [x] Red/green or mutation evidence is recorded without falsifying chronology.
- [x] Independent compliance, craft, architecture, and code-health reviews pass
      with real verdict artifacts.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice.
- [x] Reconciliation sweep produced under this slice.
- [x] Reconciliation review passed.
- [x] ADR index, generated packages, and live prose are reconciled.
- [x] Memory-sync completed; no closed record rewritten without owner approval.

### Deviation log

**Implementation-first process deviation.** The code and original regressions
were committed as `ac06cec` and PR #38 was opened without the expected spec,
independent evidence, or reconciliation. The owner requested this recovery.
The final frame, compliance, craft, architecture, code-health, and reconciliation
passes are present-time work; they are not backdated or asserted to have
preceded the original implementation.

**Minimal workflow adoption.** A fresh clone had the existing spec/ADR corpus
but no scaffold sentinel. The installed Copilot helper's adoption dry run could
not find its package manifest; the canonical jig source helper's dry run then
validated the same corpus. `adopt-layout --docs-root docs` wrote only
`scaffold.json`. No runtime machinery, hook configuration, or project primer
was vendored, and no gate-disabling environment flag was used.

**Provisional identifier recovery.** The documented local reservation helpers
initially allocated 032/0038. The real ref-aware check revealed
`origin/claude/adr-0034-specs-028-jig-fe54d4` already contained
`032-copilot-third-host` and `adr-0038-copilot-third-host`. Our unpublished
reservations were retired, not imposed on that work; final 033/0039 were
allocated with the helpers after checking fetched refs. The provisional ADR
acceptance stamp was rescinded before any Accepted record was committed or
pushed. Both final artifacts received new frame reviews, explicitly pinned to
the author model; provisional verdicts are not their gate evidence. All
reservation and correction commits remain visible rather than being amended.

**Verification and durable coverage.** A fresh implementer verified the actual
ACs and isolated behavior-removal mutants without changing canonical runtime.
The first pass's five temporary boundary checks were then promoted into the
existing test module. The promotion preserves its earlier record rather than
rewriting old hashes. [Verification](verification.md) records the 70+5 initial
checks, 75 durable targeted checks, mutation assertions, and the later source
identities. [CI evidence](ci-evidence.md) distinguishes the initial 1,866-test
run from the later 1,871-test runs. Host-local path spelling was redacted for
publication, not experiment results or provenance.

**Architecture nit resolved.** The independent arch pass found live prose
still describing inbox v2. The current description now states the already-
implemented v3, `priority`, sticky `quarantined`, and quarantine reconciliation.
This corrects live prose; it does not change the schema version or amend an
Accepted historical ADR.

**Fixture-fidelity nit resolved.** The code-health pass found the mock's default
`oracle_passed` reason contradicted failed outcomes. Two existing end-to-end
tests first failed on that mismatch. Defaults now distinguish portable/goal
pass and failure reasons, and env-error; explicit supplied reasons still win.
The 21-test focused group passed afterward, followed by the full CI mirror:
1,871 passed plus the repeated 107 install-surface checks. This changes a fixture,
not runtime continuation, budget, or quarantine behavior.

**Accepted limits.** The scope guarantees inspected in-repository readers and
legacy records, not unknown exact-key external consumers. ADR-0039 retains the
reconsideration trigger. Human status is immediate; generated markdown remains
discovery-refreshed. The older ADR-0010's broad "every write" wording was noted
by frame review; no historical amendment or resolution of that wording is
claimed here. Source/review evidence is disclosed as UNINDEXED. Advisory
complexity, type, and duplication totals are disclosed, not declared clean or
universally pre-existing.

**Reconciliation review round 1 required changes.** The fresh reviewer rejected
stale live allocation advice, an interim board still showing `IN_PROGRESS`,
missing front-door/refinement dispositions, and unowned deferred rows.
Its real `needs-changes` verdict was recorded before corrections. The decision
README now defers allocation to helpers/fetched refs instead of a fixed next
number; the board is regenerated from the actual `REVIEWED` state, and the sweep
below includes the missing surfaces and explicit follow-up ownership. This is
not treated as a passing reconciliation until a new reviewer verdict clears.

### Reconciliation sweep

| Surface | Disposition | Actual result |
|---|---|---|
| Canonical heartbeat runtime | `no-op` after original implementation | Byte-identical to `ac06cec`; projection/display only, no new controls |
| Heartbeat tests | `updated` | Five durable boundary checks and status-consistent mock reasons |
| Heartbeat SKILL.md | `updated` in original implementation | Optional diagnostics, both score shapes, precise view timing |
| docs/architecture.md | `updated` | ADR/spec links and current v3 inbox contract; arch nit addressed |
| README.md | `no-op` | Front-door product/install framing remains accurate; handoff details belong in the skill/architecture contracts |
| docs/refinement-todo.md | `no-op` | Existing 031-02 resolution is historical; this follow-on enhancement is owned by spec 033, with no new retry decision |
| ADR-0039 and decision index | `updated` | Final decision, real frame verdict, gated acceptance, derived clean index |
| Decision README allocation prose | `updated` | Removed stale fixed-number/status narrative; helpers and fetched refs govern provisional allocation |
| Existing Accepted ADRs / closed slices | `no-op` | Preserved; no unauthorized amendment or rewritten history |
| Spec 033 and review artifacts | `updated` | Real retrospective scope, implementer evidence, required passing verdicts |
| Status board | `updated` | Helper-derived during recovery; final DONE regeneration is close-out |
| Claude/Codex packages | `updated` in original implementation | Runtime and skill parity; full drift/install checks passed |
| scaffold.json | `updated` | Supported metadata-only corpus adoption |
| docs/memory/learnings.md | `updated` | Full-ceremony/chronology and sibling-identifier lesson |
| Inbox / lightweight decisions | `no-op` | No new inbox item or separate lightweight product decision |
| Primer / scaffold templates | `no-op` | No tracked project primer and no template change needed |
| people.md bootstrap | `deferred` | Owner: maintainer; trigger: explicit bootstrap request or a reported need for contributor attribution; skipped for this focused PR |
| Historical every-write wording / index warnings | `deferred` | Owner: maintainer; trigger: explicit authorization for historical wording/Context cleanup; no closed-record rewrite in this slice |
| External exact-key compatibility | `deferred` | ADR-0039's real-consumer trigger, not a universal compatibility claim |

**Leanness:** one optional-field projection, one formatter shared by two human
views, and regressions/evidence. No new runner, retry policy, dashboard, or
coordination plane was added.

### Close-out (post-DONE)

- [x] Status board regenerated and audited after DONE; Notes retain the
      driver-shape and descriptive-only diagnostics invariants.
- [x] Primer hygiene checked; this clone has no tracked project primer to edit.
- [x] Existing PR updated with review, reconciliation, validation, and recovery links.

**Anti-horizontal-phasing check:** Driver summaries travel through persisted
outcomes to operator-visible triage in one independently usable slice.
