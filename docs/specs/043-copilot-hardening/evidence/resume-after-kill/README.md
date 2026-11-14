# Resume-after-kill billed probe — findings

Settles **refinement-todo item "Copilot cross-process resume — follow-ups
(spec 043-03) #1: Resume-after-kill grounding (billed probe)"**.

Billed `copilot -p --usage-output-file` runs executed **2026-11-14** (owner-authorized
at ≤150 AI credits, 041-style). CLI `copilot` **1.0.110-3** (version pinned,
`COPILOT_AUTO_UPDATE=false` + `--no-auto-update`). Worker model **gpt-6.1-sol**
(administrator-pinned — the CLI printed the admin-managed-setting notice). Measurement
only; **no production code changed.**

## The question

On a Copilot resume after an **interruption/kill**, does the resumed session's usage
telemetry (`totalNanoAiu`) **carry** the orphaned pre-kill spend (→ a sound baseline can
be recovered from the resumed read → 043-03's kill-path fail-closed could be lifted) or
**drop** it (→ an unavoidable under-count → fail-closed is permanently correct)?

ADR-0048 **A2** probed resume-after-clean-end; **A3** probed kill→no-usage-file but never
resumed the killed session. This probe resumes it.

## Verdict: **CARRIES — exactly. The empirical blocker is removed; fail-closed is liftable.**

The resumed session's `totalNanoAiu` reports the full session-cumulative total
**including the pre-kill spend that was orphaned from servo's persisted baseline**, to
the nano. So on a kill-halt resume servo *could* recover a sound credit baseline from the
resumed session's own usage read instead of its stale persisted `cumulative_credits_nano`.
This is a measurement, not a green light to lift unconditionally — see **Recommendation**.

## Numbers

Credits = `totalNanoAiu / 1e9`. `R` = resumed usage-file `totalNanoAiu` (session-cumulative);
`N` = that invocation's **new** spend from its per-invocation OpenTelemetry `chat`-span Σ
(041-01 A2: usage total is session-cumulative on `--resume`, OTel is per-invocation);
`inherited = R − N` = what the cumulative attributes to spend *before* this invocation.

### Kill experiment — session `<session-kill>` (runA ≡ runB, same `conversation.id`)

| Run | usage `totalNanoAiu` (R) | OTel Σ new (N) | inherited `R−N` | note |
|-----|-------------------------:|---------------:|----------------:|------|
| **A** (fresh, **SIGKILL** @ t=19s, after 2 completed calls) | **(none — file empty)** | **3.85454 cr** | — | usage file **0 bytes** → ADR-0048 **A3** re-confirmed; `3,854,540,000` nano is the pre-kill lower bound **P** (2 `chat` spans) |
| **B** (`--resume` of A, tiny turn) | **5.21083 cr** `5,210,830,000` | **1.35629 cr** `1,356,290,000` | **3.85454 cr** `3,854,540,000` | `aiCreditsStatus=complete`, model `gpt-6.1-sol` |

**`inherited (R−N) − P = 3,854,540,000 − 3,854,540,000 = 0`.** The resumed cumulative carries
the orphaned pre-kill spend **exactly** — not reset, not dropped, not double-counted.

### Clean-resume control — session `<session-smoke>` (also the auth gate)

| Run | usage `totalNanoAiu` (R) | OTel Σ new (N) | inherited `R−N` |
|-----|-------------------------:|---------------:|----------------:|
| **S1** (fresh) | 5.37035 cr | 5.37035 cr | — (fresh: R≡N, 041-01 A5 Σ=total) |
| **S2** (clean `--resume`) | 5.96913 cr | 0.59878 cr | **5.37035 cr** = S1 cumulative, exact |

Reproduces ADR-0048 **A2** end-to-end with this harness and validates the `R−N`
subtraction before the billed kill leg.

### servo-accounting reconciliation (why the data suffices)

servo's `_copilot_iteration_nano` (loop.py) computes `expected = R − prior` on a resumed
invocation and refuses unless `OTel Σ == expected`. For Run B, with the **true** prior
`P = 3,854,540,000`: `expected = 5,210,830,000 − 3,854,540,000 = 1,356,290,000 = N` — the
OTel Σ **exactly**. The accounting reconciles perfectly *when given the true prior*. The
only reason 043-03 fail-closes a kill-halt resume today is that servo's **persisted**
`cumulative_credits_nano` is a stale lower bound (the interrupt checkpoint finalizes
before the in-flight iteration's credits are applied), **not** that the data is missing.
The resumed read `R` is exactly the sound total servo needs.

## Total account spend: **≈ 11.18 credits** (of the ≤150 envelope)

`5.37035 (S1) + 0.59878 (S2) + 3.85454 (Run A pre-kill) + 1.35629 (Run B) = 11.17996`.
(Run B's `R` = `3.85454 + 1.35629 = 5.21083` is the kill session's own cumulative, not
additional spend.)

## Recommendation — file a follow-up slice; do **not** lift inline

The probe removes the empirical blocker, but lifting the refusal is real design work with
guardrails a follow-up slice must own:

1. **Recover the baseline from the resumed read**, not the stale persisted value: on a
   `copilot`-backend, kill-halt resume, treat the resumed usage-file `totalNanoAiu` (`R`)
   as the authoritative session-cumulative and the invocation OTel Σ as the iteration
   spend (they reconcile exactly, as shown).
2. **Keep fail-closed as the fallback**, not delete it: refuse if the resumed invocation's
   usage read is missing/partial (`aiCreditsStatus != "complete"` or `nano_aiu` absent) or
   if `--resume` itself errors. A kill *can* leave an unresumable/corrupt session; here it
   did not, but n=1.
3. **Robust to kill timing.** This kill landed *between* billed calls, so `P` was exact.
   A kill *mid*-call (server bills it, but the OTel span never flushes) would make the
   OTel lower bound `P` an under-estimate — yet `R` (the server-side session cumulative)
   still carries that spend, so recovery via `R` stays sound regardless of kill timing.
4. **Resolution trigger (unchanged):** a user needs interrupted/slept-machine Copilot
   resume. The grounding question this item posed is now answered **YES**.

## Harness (all runs)

- Isolated scratch `-C <dir>` (path verification on), `--allow-all-tools --no-ask-user`
  (headless), `--no-auto-update`, **no `--fleet`** (single-threaded), pinned `--session-id`
  (UUID), `--usage-output-file <f>`, `--max-ai-credits` as a per-invocation safety net.
- OTel file export pinned on every run: `COPILOT_OTEL_EXPORTER_TYPE=file` +
  `COPILOT_OTEL_FILE_EXPORTER_PATH=<f>` (both pinned — ADR-0048 part 3). Default
  `NO_CONTENT`, so spans carry only metadata (no prompts/responses/paths — verified:
  0 content residual).
- Kill = direct-PID `kill -9` of the `copilot` process (a `#!/usr/bin/env node` script, so
  `$!` is the worker PID), matching servo's `proc.kill()`. Fired once ≥2 `chat` spans had
  flushed (≥1 completed iteration) so pre-kill spend is real; 0 orphaned child processes.

## Files (redacted — see `commands.md`)

- `smoke-s{1,2}-usage.json`, `runB-usage.json` — the `--usage-output-file` JSON per run
  (clean: numeric telemetry only, `filesModified: []`, no paths/ids).
- `runA-usage.json.EMPTY` — **0-byte**: Run A's usage file, pre-created empty and **still
  empty after SIGKILL** (ADR-0048 A3; the empty marker *is* the evidence).
- `smoke-s{1,2}-otel.jsonl`, `runA-otel.jsonl`, `runB-otel.jsonl` — per-invocation OTel
  exports. Account-linked ids (`enduser.pseudo.id`, `gen_ai.response.id`,
  `github.copilot.{service_request_id,interaction_id,turn_id,initiator}`) → `<redacted>`;
  the probe-generated `gen_ai.conversation.id` → a per-session alias (`<session-kill>` /
  `<session-smoke>`) so A≡B continuity stays auditable. Numeric cost/token fields
  (`github.copilot.nano_aiu`/`cost`, `gen_ai.usage.*`) preserved — they are the measurement.
