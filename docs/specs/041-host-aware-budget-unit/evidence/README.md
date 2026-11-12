# Spec 041-01 — Copilot contract probe: raw evidence

Billed `copilot -p --usage-output-file` runs executed **2026-11-11** to settle
ADR-0048's assumptions A1–A6 (owner-authorized at ≤150 AI credits; ADR-0048 open
question 4). CLI `copilot` **1.0.110-1**, version pinned (`COPILOT_AUTO_UPDATE=false`,
`--no-auto-update`). Worker model **gpt-6.1-sol** (administrator-pinned — the CLI
printed *"An administrator-managed setting replaced model claude-sonnet-5.5 with
gpt-6.1-sol for this session"*).

## Account spend (within the ≤150 budget)

Per-invocation **new** credits, summed from each run's own OpenTelemetry `chat`
spans (the per-invocation signal — see A2; the resumed run's usage-file total is
session-cumulative and must not be summed):

| Run | Session | What it settles | New credits |
|-----|---------|-----------------|------------:|
| 0 — smoke/calibrate | fresh | usage-JSON shape + OTel A5 gate | 5.351 |
| A — fresh | fresh (pinned UUID) | A1, A5 (Σ=total), model/prices | 12.893 |
| B — resume | resume of A | **A2** (scope), overrun headroom | 24.283 |
| D — overrun | fresh | **A6** (cap crossing) | 31.005 |
| C — kill | fresh, SIGKILL mid-run | **A3** (no usage file on kill) | 11.482 |
| **Total** | | | **85.013** |

## Probe harness (all runs)

- Isolated scratch working dir (`-C <dir>`), path verification on (writes confined),
  no network/URL grants, `--allow-all-tools --no-ask-user` (headless), **no `--fleet`**
  (single-threaded worker).
- `--usage-output-file <f>` for the end-of-session usage JSON.
- OTel file export pinned on every run: `COPILOT_OTEL_EXPORTER_TYPE=file` +
  `COPILOT_OTEL_FILE_EXPORTER_PATH=<f>` (ADR-0048 part 3 requires both pinned so an
  inherited/managed setting cannot redirect the stream). Content capture left at the
  default `NO_CONTENT`, so spans carry only metadata (no prompts/responses/paths).

## Files

- `run{0,-a,-b,-d}-usage.json` — the `--usage-output-file` JSON per run.
- `run{0,-a,-b,-d,-c}-otel.jsonl` — the OTel JSON-lines export per run (spans + metrics).
- `run-c-usage.json.EMPTY` — a **0-byte** file: Run C's usage file was pre-created
  empty (mirroring servo's `tempfile.mkstemp`) and **stayed empty after SIGKILL** —
  the usage JSON is never written for a killed invocation (A3). The empty marker *is*
  the evidence.
- `cli-help/` — unbilled `copilot help {billing,limits,monitoring,permissions,parallel-work}`
  captures that ground the CLI facts.

## Redaction

Account identifiers removed from every file (verified: 0 residual):
- OTel span attributes replaced with `<redacted>`: `enduser.pseudo.id`,
  `gen_ai.conversation.id`, `gen_ai.response.id`, `github.copilot.{interaction_id,
  turn_id,service_request_id,initiator}`, and the private-environment context keys
  (`context.{mcp_server_names,skills,custom_agent_names}`).
- `codeChanges.filesModified` absolute paths relativized to `./work-*/…`; username,
  home and scratch paths scrubbed throughout.
- Numeric cost/token fields (`github.copilot.nano_aiu`, `github.copilot.cost`,
  `gen_ai.usage.*`) are preserved — they are the measurement.

Session UUIDs that appear are ones the probe generated (`--session-id`), not account
identifiers.

## gpt-6.1-sol facts measured

- **Context window:** 272K tokens (from interactive `/model`).
- **Prices (credits per 1M tokens)**, solved from 11 observed calls (max residual
  0.0002 cr — exact): **cache-read 10, cache-write 250, output 1000**. Uncached-input
  price unobserved (a continued session re-sends ~3 fresh tokens/call); conventionally
  ≥ cache-write, so 250 is a floor for the input side.
- **`aiCreditsStatus`** field present on every usage JSON (value `complete` throughout)
  — the CLI's own partial/unavailable self-marker.

See `../slice-01-copilot-contract-probe.md` **Findings** for the full analysis and the
worked overrun bound.
