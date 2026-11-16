# Resume-after-kill probe — exact invocations

All runs set these environment variables (version pinned; OTel file export pinned with
BOTH vars so an inherited `COPILOT_OTEL_EXPORTER_TYPE` cannot redirect the stream —
ADR-0048 part 3):

```
COPILOT_AUTO_UPDATE=false
NO_COLOR=1
COPILOT_DISABLE_DESKTOP_NOTIFICATIONS=1
COPILOT_OTEL_EXPORTER_TYPE=file
COPILOT_OTEL_FILE_EXPORTER_PATH=<run>-otel.jsonl
```

Common flags: `-C <isolated-scratch-dir>` (path verification on), `--allow-all-tools
--no-ask-user` (headless), `--no-auto-update`, **no `--fleet`** (single-threaded),
`--usage-output-file <run>-usage.json`, pinned `--session-id=<UUID>`. Session UUIDs are
probe-generated (not account identifiers).

| Run | Prompt (abbrev.) | Session flag | `--max-ai-credits` | Termination |
|-----|------------------|--------------|-------------------:|-------------|
| S1 (control, fresh) | `Reply with exactly: PROBE_OK` | `--session-id=<S>` | 30 | natural (1 call) |
| S2 (control, clean resume) | `Reply with exactly: RESUME_OK` | `--resume=<S>` | 30 | natural (1 call) |
| A (kill) | open-ended multi-module build, "do not stop early" | `--session-id=<K>` | 40 | **SIGKILL** at t=19s (≥2 `chat` spans flushed) |
| B (resume-after-kill) | `Reply with exactly: RESUME_AFTER_KILL_OK` | `--resume=<K>` | 40 | natural (1 call) |

Fresh argv shape (Run A):

```
copilot -p "<prompt>" -C ./work-a --session-id=<K> \
  --allow-all-tools --no-ask-user --no-auto-update \
  --usage-output-file ./runA-usage.json --max-ai-credits 40
```

`--resume=<K>` replaces `--session-id=<K>` for Run B. The kill:

```
copilot -p "<prompt>" ... &          # $! is the `#!/usr/bin/env node` copilot PID
# poll the OTel file; once >=2 "chat " spans have flushed:
pkill -9 -P "$PID"; kill -9 "$PID"   # direct-PID SIGKILL == servo's proc.kill()
```

`totalNanoAiu` was read from each `--usage-output-file` JSON; per-invocation new spend was
Σ `github.copilot.nano_aiu` over the `type==span`, `name` startswith `"chat "` lines of the
OTel export — replicating `loop.py`'s `_parse_copilot_usage` + `_sum_otel_call_nano`.
