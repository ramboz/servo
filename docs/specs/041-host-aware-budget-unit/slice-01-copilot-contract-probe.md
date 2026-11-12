---
status: DONE
kind: spike
dependencies: []
last_verified: 2026-11-11
frame_review: true
---

## Slice 041-01 — Copilot contract probe

**Goal:** Settle ADR-0048 A1–A5 with executed Copilot CLI runs, so the credit
brake's arithmetic rests on evidence rather than on help text.

**Question:** Does `copilot -p --usage-output-file` report per-invocation AI
credits (`totalNanoAiu`)? Specifically:
- does a report exist after a timeout or kill;
- on `--resume=<sid>`, are the cap and the report scoped to the session or to
  the invocation;
- does a report mark itself partial?

**Time-box:** 2 hours, and at most 150 AI credits of billed usage (ADR-0048
open question 4 shows the arithmetic).

**DoR:**
- The owner authorizes the billed probe (ADR-0048 open question 4).

**Acceptance Criteria:**

1. A fresh `copilot -p` run with `--usage-output-file` and
   `--max-ai-credits 30` records `totalNanoAiu`, `totalPremiumRequestCost`,
   `modelMetrics` and `agentMetrics`. Raw files are kept under
   `docs/specs/041-host-aware-budget-unit/evidence/`, redacted of any account
   identifiers.
2. A `--resume=<sid>` second run shows whether `totalNanoAiu` is the
   invocation's or the session's running total (A2), compared against the first
   run. It also shows whether `--max-ai-credits` measures the session total
   (cap set below the session total but above one call's cost).
3. A run killed by servo's timeout path shows whether a usage file is written
   (A3).
4. Subagent and compaction usage appear in `agentMetrics` / `totalNanoAiu` (A1),
   or are recorded as unobserved.
5. Legacy-billing behaviour (A4) is recorded as observed, or as unobservable on
   this account. For partial cost (A5), the probe records whether the
   OpenTelemetry file export gives per-call `github.copilot.nano_aiu` and token
   counts for a `-p` run, with the exporter env vars pinned. It also records
   whether Σ per-call `nano_aiu` matches `totalNanoAiu`, and whether span token
   sums match `modelMetrics`. If per-call telemetry is unavailable, ADR-0048's
   partial-cost kill criterion fires and 041-02 stays blocked.
7. **Worked bound.** Record the default worker model's `/model` "Credits Per 1M
   Tokens" and context window, and compute ADR-0048's (1 + c) × per-call bound
   as a number for the owner's Open question 1.
6. **Overrun (A6).**
   - On the run whose spend crosses its `--max-ai-credits` cap, record
     `spend − cap`, and the calls in flight at the crossing from the
     OpenTelemetry span timings.
   - Record whether a tool-denial flag stops subagent spawning in the worker
     invocation.
   - Compute the per-call maximum from `/model`'s "Credits Per 1M Tokens"
     (max of input and cache-write × context window, plus max output × output
     price), and compare the overrun with (1 + c) × that maximum.
   - A compaction crossing is expensive to force, so if it is not observed,
     record *c* as unobserved and keep the conservative *c* = 1.

**Findings:** Probe executed 2026-11-11, `copilot` **1.0.110-1** (version pinned),
worker model **gpt-6.1-sol** (administrator-pinned — the CLI replaced the account
default `claude-sonnet-5.5`). Raw redacted evidence under `evidence/`; **85.0 AI
credits** spent total, within the ≤150 authorization.

**A1 — per-invocation `totalNanoAiu` for completed `-p` runs — CONFIRMED.** Every
completed `-p` run wrote a usage JSON with `totalNanoAiu`, `totalPremiumRequestCost`,
`totalUserRequests`, `modelMetrics` (per model), `agentMetrics` (`main` + any
subagents), `providerModelMetrics`, `currentModel`, `aiCreditsStatus` and
`codeChanges`. Credits = `totalNanoAiu / 1e9` (Run 0: 5 350 600 000 → 5.3506,
matching the exit summary's "AI Credits 5.35"). Subagents were never spawned (no
`--fleet`; `agentMetrics` held only `main` on all four completed runs); compaction was
not forced (ADR-0048 keeps the conservative `c = 1`). Both fold into the model's
`totalNanoAiu` (`copilot help billing`: "Subagents and background work such as
compaction count").

**A2 — resume scope — CONFIRMED; the two cost signals have DIFFERENT scopes.** Run A
(fresh) spent 12.893 cr. Run B resumed A's session; its own OTel file summed to
24.283 cr (6 new calls), yet Run B's usage-file `totalNanoAiu` was 37.176 =
12.893 + 24.283. Therefore:
- the usage-file **`totalNanoAiu` is SESSION-cumulative on `--resume`** (carries prior
  invocations) — the Copilot analogue of Claude bug 007; the brake must take a
  per-iteration cost as a **difference from a session snapshot**, never read the field
  directly;
- the **OTel file export is per-invocation** (a fresh file holds only that
  invocation's spend) — an independent, invocation-scoped cost signal;
- **`--max-ai-credits` is INVOCATION-scoped** (by elimination: Run B's session reached
  cumulative 37 > its cap of 30 yet calls 4–6 still ran, so the cap ignored A's prior
  12.893; a session-cumulative cap would have halted it). Both scopes must be handled
  explicitly in 041-02.

**A3 — usage file after a kill/timeout — CONFIRMED absent → fail-closed required.**
Run C replicated servo's exact timeout path (`proc.kill()` = SIGKILL) against a live
`-p` run. The `--usage-output-file` target (pre-created empty, like servo's
`tempfile.mkstemp`) **stayed 0 bytes** — the usage JSON is written only at a clean
session end, which SIGKILL never reaches. A killed/timed-out invocation yields **no
usage report** — exactly the `credit_usage_unavailable` case ADR-0048 part 3 halts on
(spend `null`). Nuance: the OTel file retained per-call `chat` spans (partial spend),
and a surviving child kept flushing spans after the main PID's kill, so OTel-after-kill
is an **incomplete lower bound with no `invoke_agent` root span** — not a reliable
total; fail-closed stands.

**A4 — legacy billing — UNOBSERVABLE on this account.** The account bills in **AI
credits** (`totalNanoAiu` populated, `aiCreditsStatus` present), not legacy premium
requests, so legacy behaviour cannot be exercised here. Observed: `totalPremiumRequestCost`
is **also** populated alongside credits (Run B = 2), i.e. both unit fields appear on a
credit-billed account, but credits are the authoritative unit. ADR-0048 OQ2 (AI credits
are the sole unit) is unaffected; revisit only if a real legacy account cannot populate
`totalNanoAiu`.

**A5 — per-call cost telemetry for `-p` runs — CONFIRMED positive, and richer.** With
OTel file export pinned, each model call emits a `chat <model>` span carrying
`github.copilot.nano_aiu` (per-call credits), `github.copilot.cost`, and per-call token
counts (`gen_ai.usage.{input,cache_read.input,cache_write.input,output}_tokens`),
tagged with `gen_ai.response.model`. **Σ per-call `nano_aiu` reconciles with the session's
`totalNanoAiu` exactly**: for a fresh run the per-invocation OTel Σ equals that run's
usage total (Run A 4 calls = 12.893; Run D 5 calls = 31.005); for the resumed **Run B
the per-invocation OTel Σ (24.283) plus the prior-session snapshot (12.893) =
the session-cumulative usage total (37.176)** — the same split as A2. Residual 0 across
11 calls. **Span token sums also match `modelMetrics` exactly** (Run A Σoutput 5 249 /
Σinput 98 920; Run D 21 287 / 157 218), so part 3's per-call partial check **and** its
`modelMetrics` cross-check both run. *Additional finding:* the usage JSON already self-marks
completeness via **`aiCreditsStatus`** (top-level, per-model, per-provider; `copilot
help billing` maps it to `complete` / `… (partial)` / `unavailable`) — a **simpler
primary partial signal** than ADR-0048 part 3 assumed existed. 041-02 should gate on
`aiCreditsStatus == "complete"` and keep the OTel Σ-vs-total as the cross-check.

**A6 — overrun bound — CONFIRMED; soft cap halts promptly; `c = 0` observed.** Run D
(cap 30, oversized task) crossed its cap: five sequential calls accrued 3.072 → 11.336
→ 20.627 → 28.856 → **31.005**; the fifth crossed 30 and the next call was blocked.
**Observed overrun = spend − cap = 1.005 cr** (one crossing call; calls strictly
sequential ⇒ **no background call in flight, observed `c` = 0**). stderr: *"Session
limit reached (31.01/30 AI credits used). Future model calls will stop …"*. A cap-halt
**exits 0** (detect it from `totalNanoAiu ≥ cap` / usage JSON / stderr, **not** the exit
code), and the **usage file IS written** on a cap-halt (`aiCreditsStatus: complete`).
Subagent clause: there is **no subagent tool to deny** — `copilot help permissions`
lists only `shell/write/read/memory/url/<mcp>` kinds, and `copilot help parallel-work`
shows subagents come only from `--fleet` ("No setting turns it on"). servo's
single-threaded worker is guaranteed by **omitting `--fleet`** — stronger than part 2's
"deny via tool-denial flags" wording.

**Worked overrun bound (AC7 / owner open question 1).** gpt-6.1-sol: context window
**272K**; prices **cache-read 10 / cache-write 250 / output 1000** credits per 1M tokens
(exact, 11 calls, residual 0.0002). ADR-0048 part 2's per-call maximum = `W ×
max(input, cache-write) + max_output × output`:
- input side `272 000 × 250 / 1e6 = 68.0 cr` (cache-write-priced full context; a floor,
  since uncached input ≥ cache-write);
- output side `max_output × 1000 / 1e6` — gpt-6.1-sol's max output is not exposed by the
  CLI `/model` view; largest **observed** single-call output was 12 812 tokens (12.8 cr),
  and a 16 384 / 32 768 cap gives 16.4 / 32.8 cr;
- **per-call maximum ≈ 81–101 cr; overrun bound `(1 + c) × per-call-max`, `c = 1`
  ≈ 162–202 credits.**

**Consequence — part 2's launch-refusal is the DEFAULT for this model, not a corner
case.** The bound (~160–200 cr) exceeds any ceiling below ~200, and the CLI minimum
ceiling is 30. So for an admin-pinned gpt-6.1-sol worker with no context brake,
`loop.py` must **refuse to launch at a 30-credit ceiling** and name a smallest sensible
ceiling of ≥ ~200 cr. (The observed overrun at a 30-cap was only 1 cr because the
crossing happened at small context; the bound is the worst-case guarantee of a
full-context crossing, which servo cannot prevent under Copilot — no context brake,
part 4.)

**No kill criterion fired.** Usable report for completed runs ✓ (A1); per-call partial
telemetry present ✓ (A5); observed overrun within the stated bound ✓ (A6); subagent
spawning structurally absent without `--fleet` ✓. ADR-0048 Option A stands.

**Refinements fed to 041-02 / 041-03:** (1) primary partial gate = `aiCreditsStatus ==
"complete"`, OTel Σ-vs-total as cross-check; (2) per-iteration cost = session-cumulative
`totalNanoAiu` **minus prior snapshot**, the invocation cap is a separate knob;
(3) cap-halt detection is not by exit code (exits 0); (4) killed invocation → no usage
JSON → fail closed `null`, OTel partial is a lower bound only; (5) subagent control =
omit `--fleet`, not a tool-denial flag; (6) the launch-refusal binds at any ceiling
below ~200 cr for gpt-6.1-sol — the "smallest sensible ceiling" message must carry a
real number.

**Outcome:** `spec 041-02 unblocked`.

**DoD:** findings recorded with raw evidence; ADR-0048's Assumptions updated
to cite them; compliance review passed.

**Anti-horizontal-phasing check:** the credit brake's per-iteration
arithmetic is chosen from observed CLI behaviour, the way bug 007's fix was
for Claude.

### Deviation log

- **Run plan.** The owner-approved sketch was three billed runs (fresh-overrun,
  resume, kill). gpt-6.1-sol's cache efficiency meant the fresh and resumed coding
  tasks *completed* under their 30-credit invocation caps (12.9 / 24.3 cr), so no cap
  crossing occurred there. Added a cheap smoke/calibration run (Run 0, ~5 cr — gated A5
  before the expensive runs) and a dedicated oversized run (Run D) to force the A6 cap
  crossing. Five runs total, **85.0 cr, within ≤150**.
- **ADR-0048 part 3 (partial detection).** The probe found `aiCreditsStatus`
  (top-level + per-model + per-provider) — a self-marking complete/partial/unavailable
  signal the ADR assumed did **not** exist. Re-scoped as the **primary** partial gate;
  the OTel per-call Σ-vs-total check is demoted to the cross-check. Beneficial; recorded
  in ADR-0048 A5.
- **ADR-0048 part 2 (subagent denial).** There is no subagent tool-kind to deny;
  subagents are gated solely by the `--fleet` launch flag (never passed). Control is
  **omission**, stronger than the ADR's "tool-denial flags" wording. Recorded in ADR A6.
- **A2 sharper than framed.** The ADR called A2 "either answer is workable"; the probe
  found the usage report (session-cumulative) and the cap/OTel (invocation-scoped) have
  **different** scopes — both must be handled.
- **Worked bound — one unexposed input.** gpt-6.1-sol's max output tokens is not shown
  by the CLI `/model` view; the bound is stated with observed (12 812) and conventional
  (16 384 / 32 768) output caps. The input term alone (68 cr) exceeds the 30-credit
  minimum, so the launch-refusal conclusion is robust to the output term.
- **A4 unobservable** — the account bills in AI credits, not legacy premium requests.

### Reconciliation sweep

- **Code:** none — a `kind: spike` slice; deliverable is findings + evidence + the ADR
  Assumptions update. No tests owed. `git status` touches only
  `docs/specs/041-host-aware-budget-unit/**` and `docs/decisions/adr-0048-*.md`.
- **slice-01:** Findings recorded with raw-evidence pointers; Outcome `spec 041-02
  unblocked`; `last_verified: 2026-11-11`.
- **ADR-0048:** Assumptions A1–A6 updated to cite the probe (Accepted ADR — Assumptions
  block only, per the DoD). No Decision/Consequences change; part 2 / part 3 wording
  refinements are flagged in A6 / A5 for 041-02 to implement.
- **evidence/:** five runs' redacted `*-usage.json` + `*-otel.jsonl`, `README.md`,
  `commands.md`, `cli-help/` captures, and the 0-byte `run-c-usage.json.EMPTY` marker;
  PII sweep clean (0 identifier hits; sensitive OTel attrs `<redacted>`).
- **Reviews:** compliance **pass** + craft **pass** (independent `jig:reviewer`, every
  number re-derived from the raw evidence). Frame critique was done at authoring
  (`frame_review: true`); the slice entered working state via READY_FOR_IMPLEMENTATION,
  so no separate READY_FOR_REVIEW frame-critique evidence file was produced — noted as a
  disposition, not a gap (the compliance pass covers evidence fidelity).
- **Board:** `docs/specs/README.md` regenerated after DONE.
- **Contract surface:** none added or changed by this spike (no inbox/contract review
  owed).
