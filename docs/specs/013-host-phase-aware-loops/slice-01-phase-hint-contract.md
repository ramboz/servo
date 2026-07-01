---
status: DONE
dependencies: [adr-0011]
last_verified: 2026-07-01
---

## Slice 013-01 - phase-hint contract

**Goal:** Define servo's host-neutral phase-hint contract (`plan`, `run`,
`evaluate`, `triage`) and document how it composes with `gate.py`,
`oracle.sh`, run state, and triage state.

**Resolution trigger:** Resume when jig lands an accepted host-mode adapter
decision/spec, or when a servo consumer needs phase hints before running an
autonomous loop.

**DoR:**
- [x] ADR-0011 Accepted (2026-07-01).
- [x] Current Codex and Claude phase-mode behavior re-verified (2026-07-01,
      web search — see `## Assumptions`).

**Assumptions (probe-grounded, 2026-07-01):**

- **Claude Code Plan Mode** — toggled with Shift+Tab twice; Claude drafts a
  numbered plan and will not edit files, run state-changing commands, or
  commit until the plan is approved. Maps to servo's `plan` intent.
- **Claude Code Routines** — a saved prompt + repo + connector set that runs
  on Anthropic-managed cloud infra on a schedule, webhook, or repo event;
  `/schedule` from the CLI. Already servo's ADR-0008/ADR-0012 scheduling
  primitive — no new surface, just confirmed current.
- **Codex CLI approval modes** — `auto` (default; read/edit/run inside the
  working dir, asks before touching outside it or the network), `read-only`
  (consultative — browse and propose, no changes without approval, maps to
  `plan`), `full-access` (unrestricted). Codex also shows an inline plan/step
  approval flow. No dedicated `evaluate` or `triage` mode surface on either
  host — those intents stay servo-side (`gate.py` / heartbeat), confirming
  ADR-0011's posture that the vocabulary is servo's, not borrowed from a host
  concept.

**Acceptance Criteria:**

1. **Small vocabulary.** Docs define `plan`, `run`, `evaluate`, and `triage`
   as advisory phase intent, not a new lifecycle.
2. **Authority preserved.** Docs state that `gate.py`, `oracle.sh`, run state,
   triage state, and frozen eval ledgers remain canonical.
3. **Graceful degradation.** The contract states that missing host-mode
   support falls back to plain prompts and existing loop behavior, never
   `env_error`.
4. **References updated.** `docs/architecture.md` or equivalent loop docs link
   the contract from the agent-loop, heartbeat, and design-eval sections.

**DoD:**
- [x] All ACs pass; docs/surface checks green where applicable.
- [x] Reviewed by the appropriate jig reviewer workflow.
- [x] Deviation log produced under this slice heading.
- [x] `docs/specs/README.md` regenerated.

**Anti-horizontal-phasing check:** After this slice, a user can understand how
servo will interpret host planning / implementation hints before any runtime
code exists.

### Deviation log (after reconciliation)

- **Re-verification method is search-based, not hands-on.** DoR item 2 ("current
  Codex and Claude phase-mode behavior re-verified") was satisfied via web
  search against current vendor docs (2026-07-01), not by toggling Plan Mode /
  approval modes live in each host. Confidence is good (primary vendor doc
  sources) but lower than a direct probe; flagged here per both reviewer
  passes so a future reader knows the verification depth.
- **`docs/specs/README.md` regenerated** via `workflow.py status-board .`
  (013-01 row flipped to `IN_PROGRESS`; Notes cell rewritten — the tool
  preserves Notes verbatim across regen, so the stale "ADR-0011 currently
  Proposed" text needed a manual rewrite).
- **Board-regen bug found, not fixed here (two failure modes).** `workflow.py
  status-board` blanked the `## Deferred slices` resolution-trigger cells for
  016-02/03/04 during this regen — its extractor apparently matches only the
  literal `**Resolution trigger:**` label, not this repo's
  `**DEFERRED — resolution trigger:**` phrasing used in the 016 slice files.
  Hand-restored those three cells. A compliance re-review then caught a
  **second, pre-existing** instance of the same underlying problem: the
  013-02/013-03 rows in the same table were already truncated mid-sentence in
  committed `README.md` (first-line-only capture of a wrapped multi-line
  trigger paragraph) — predating this session. Hand-restored those two as
  well. Out of scope to fix the tool itself here; both failure modes logged in
  `docs/refinement-todo.md`.
- **ADR-0011 decisions-table "(parked)" wording tightened** (craft-pass nit)
  to distinguish 013-01 (landed, this docs contract) from 013-02/03 (still
  `DEFERRED`).
- **`docs/decisions/README.md` staleness fixed in passing** (craft-pass nit,
  unrelated to this diff but caught while reviewing it): the ADR-numbering-note
  prose still called ADR-0011 "reserved (Proposed)" after `716e2da` accepted
  it — updated to "Accepted".
- **Third regen side-effect found, reverted, and recurring.** The same
  `workflow.py status-board .` invocation silently flipped
  `docs/specs/016-execution-planner/spec.md`'s frontmatter `status:` from
  `DRAFT` to `DONE` — a reconciliation-review catch, not something this
  session's own sweep noticed the first time. The rollup rule (spec DONE iff
  every *non-DEFERRED* slice is DONE) is mechanically correct per the tool's
  own documented semantics, but contradicts spec 016's own prose banner
  ("Status: DRAFT — 016-01 DONE + landed; 016-02..04 DEFERRED") and the status
  board (016-02/03/04 still shown DEFERRED). Reverted to `DRAFT`. **This
  recurred twice more**: this slice's own `transition ... DONE` (the expected
  mechanism for closing 013-01) flipped **spec 013's own** frontmatter to
  `DONE` for the identical reason (013-02/03 are `DEFERRED`, so 013-01 alone
  being DONE rolls the umbrella spec up), and a follow-up `status-board`
  regen re-flipped *both* specs' frontmatter back to `DONE` after the first
  hand-revert (and re-truncated the 013-02/013-03 + 016-02/03/04 Deferred-table
  cells a second time). Added a matching `> **Status: DRAFT — ...**` banner to
  spec 013 (mirroring 016's existing one) and reverted both frontmatters +
  re-fixed the board a second time. This is now a documented, reproducible
  tension between jig's rollup semantics and how servo uses `DRAFT` for
  mostly-parked umbrella specs — logged as its own
  `docs/refinement-todo.md` entry (distinct from the resolution-trigger
  extractor bug above) since it will recur on the *next* `transition` or
  `status-board` run against either spec until resolved upstream.

### Reconciliation sweep

- **Architecture impact** — `updated`. `docs/architecture.md` gained the
  "Host-native phase hints (spec 013)" section + the ADR-0011 decisions-table
  row + two reciprocal backlinks (agent-loop guardrails, heartbeat triage
  inbox). No module boundary or public contract changed (docs-only slice, no
  code).
- **Load-bearing decision (ADR trigger)** — `no-op`. The load-bearing decision
  is ADR-0011 itself (already Accepted, pre-existing); this slice only writes
  its docs consequence.
- **Lightweight decisions** — `no-op`. No UI/visual/copy calls made.
- **Conventions impact** — `no-op`. No `docs/conventions.md` in this project.
- **Inbox triage** — `no-op`. No `docs/inbox.md` in this project.
- **Primer hygiene** — `no-op`. Spec 013 is not closing (013-02/03 stay
  `DEFERRED`); no close-out compression applies.
- **Use-case coverage** — `no-op`. `docs/product-vision.md` has no `## Use
  cases` section; the breadth layer isn't adopted for this project.
- **Closed-spec drift** — `updated`. Fixed the `docs/decisions/README.md`
  numbering-note staleness above (live prose, fixed inline per ADR-0010's
  amendment-scope policy — not a closed spec/slice record, so no `##
  Amendments` entry needed).
- **Memory-sync** — `deferred` to the post-DONE step (`/jig:memory-sync`).
