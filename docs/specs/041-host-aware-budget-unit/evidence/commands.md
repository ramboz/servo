# Spec 041-01 — exact probe invocations

All runs set these environment variables (version pinned; OTel file export pinned
with BOTH vars so an inherited `COPILOT_OTEL_EXPORTER_TYPE` cannot redirect the
stream — ADR-0048 part 3):

```
COPILOT_AUTO_UPDATE=false
NO_COLOR=1
COPILOT_DISABLE_DESKTOP_NOTIFICATIONS=1
COPILOT_OTEL_EXPORTER_TYPE=file
COPILOT_OTEL_FILE_EXPORTER_PATH=<run>-otel.jsonl
```

Common flags: `-C <isolated-scratch-dir>` (path verification on, writes confined),
`--allow-all-tools --no-ask-user` (headless), `--no-auto-update`, **no `--fleet`**
(single-threaded), `--usage-output-file <run>-usage.json`. Session UUIDs are
probe-generated.

| Run | Prompt | Session flag | `--max-ai-credits` | Termination |
|-----|--------|--------------|-------------------:|-------------|
| 0 (smoke) | `Reply with exactly: PROBE_OK` | (fresh) | **30** | natural (1 call) |
| A (fresh) | miniexpr: tokenizer+parser+evaluator + ≥40 unittest, iterate to green | `--session-id=<A>` | **30** | natural (task completed, 12.9cr) |
| B (resume) | expand miniexpr: +functions/ternary/strings/boolean/bitwise, +≥150 tests, README | `--resume=<A>` | **30** | natural (completed, 24.3cr new) |
| D (overrun) | bigkit: ≥12 modules × ≥15 fns + ≥400 unittest across ≥25 files, iterate | `--session-id=<D>` | **30** | **soft-cap halt** at 31.005cr |
| C (kill/A3) | bigkit (same as D) | `--session-id=<C>` | 100 | **SIGKILL** after 55s (servo's `proc.kill()`); usage file pre-created empty like `tempfile.mkstemp` |

Full argv shape (Run A example; paths shown relative):

```
copilot -p "<prompt>" -C ./work-a --session-id=<A> \
  --allow-all-tools --no-ask-user --no-auto-update \
  --usage-output-file ./run-a-usage.json --max-ai-credits 30
```

`--resume=<A>` replaces `--session-id=<A>` for Run B. Run C launches the same way
(cap 100), then: `sleep 55; kill -9 <copilot-pid>` (direct-PID SIGKILL, matching
`loop.py` `_invoke_copilot`'s `proc.kill()` timeout path).

Prices and the Σ-reconciliation were derived from the per-call `chat <model>` spans in
the `*-otel.jsonl` files (see `README.md` and the slice Findings).
