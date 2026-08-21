---
status: DONE
dependencies: [adr-0032, 027-02]
last_verified: 2026-08-21
claimed_by: claude/027-01-342c59
---

## Slice 027-03 — custom-command provider (escape hatch)

**Goal:** Let a project declare an arbitrary capture command (invoked per screen
with the screen id + output path, responsible for driving to state, screenshot,
and returning a frame-normalized PNG), so **any** non-web stack can be scored via
a project-supplied script — the shortest path to cross-stack value and the first
real exercise of the seam on a non-web target. Failure fails closed to
`env_error`; the command identity is recorded in the ledger, unfrozen.

**Scope note:** the generic escape hatch, before the blessed Android/iOS
built-ins. Per-platform state seeding is provider-owned (ADR-0032 §4); only
references/rubric/judge are shared. This slice registers **one** new provider
(`command`) into the 027-02 seam; it does **not** add servo-side cropping or
seeding — those are the command's responsibility (ADR-0032 §5).

**DoR:**
- ✅ 027-02 shipped the selection + dispatch seam (`_CAPTURE_PROVIDERS`,
  `_resolve_capture_transport`, `capture_app` dispatcher, `capture_provider`
  ledger field). This slice plugs a second provider into it.
- ✅ Invocation convention decided: servo appends `--screen <id> --out <path>` to
  the project command, matching the built-in web provider's own spawn
  (`node capture.mjs --screen <id> --out <path>`) — one contract, not two. The
  command MUST write a PNG to the `--out` path and exit 0.
- ✅ ADR-0032 open questions resolved **minimally** for this provider: framing
  (Q1) is the command's responsibility (servo passes the frame implicitly via the
  references the command targets; no servo-side crop); identity granularity (Q2)
  is the **command string** (the resolved argv), recorded in the ledger.
- ✅ Shots retained + ledger-linked by the 027-01 plumbing (shared subprocess
  path), and provider identity unfrozen per ADR-0032 §6. No ADR needed.

**Acceptance Criteria:**

1. **A project command is selected and invoked per screen.** With
   `capture.transport: "command"` and `capture.command: [<argv…>]` in
   `config.json`, each screen's capture runs `[<argv…>, "--screen", <id>, "--out",
   <shot_path>]` (cwd = the eval dir, bounded timeout), and consumes the PNG the
   command writes to `--out`. The shot is retained and ledger-linked by the
   existing 027-01 plumbing (stamped filename under `shots/`, per-screen `shot`
   path), identical to the web path.
2. **The command owns state and framing.** Servo passes only the screen id and the
   output path; driving the app into that screen's state and returning a
   frame-normalized PNG are the command's responsibility (ADR-0032 §4/§5). Servo
   performs **no** seeding and **no** cropping for this provider — it does not read
   `setup`, does not run Playwright, and does not post-process the returned PNG.
3. **Fail closed on any command failure.** A command that exits non-zero, times
   out, is not found (`FileNotFoundError`), or writes no PNG raises `EnvError` →
   rc 2 `env_error`, with the command's stderr salience-surfaced — never a silent
   `0.0`. `capture.transport: "command"` with a **missing or empty**
   `capture.command` also fails closed to `env_error`, surfaced **before** any
   per-screen capture.
4. **Command identity recorded in the ledger, unfrozen.** A command-provider run
   records top-level `capture_provider: "command"` and `capture_command`
   (the resolved argv list) in the ledger row — advisory, never part of
   `definition_hash`. `capture.command` is environmental: adding/changing it does
   **not** re-freeze an eval (mirrors `capture.transport`, ADR-0032 §6). On a
   non-command run `capture_command` is `null`.
5. **Attestation stays honest for an unattested command.** A custom command that
   emits no `##servo-capture:` line records per-screen `provenance: "not_attested"`
   (capture happened, identity unavailable) — never a fabricated engine. If a
   command *does* emit the marker, it is parsed like any other provider's.
6. **Web path unchanged (additive).** Absent config / `capture.transport: "web"`
   still drives Playwright exactly as before; the composite, freeze/`StaleError`
   validation, the `env_error`-on-failure contract, and the 0/1/2 oracle contract
   are untouched. The change is a new registered provider + one new ledger field.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions). — `CaptureCommandProviderTests`
      9/9 green; 111/111 in `test_design_eval` bar the one pre-existing red
      (`CaptureLibNodeTests.test_capture_lib_node_suite_passes`, a Node
      output-format mismatch, red on a clean tree, unrelated); `test_skill_surface`
      25/25 green after the SKILL.md edits.
- [x] Implementer test coverage exercises each AC with at least one fixture
      (command spawn shape `--screen/--out`; missing/empty command → rc2 env_error
      before capture; non-zero/no-output command → rc2 env_error; ledger
      `capture_provider: "command"` + `capture_command` argv; unattested command →
      `not_attested`; web path unchanged).
- [x] Each new test shown to fail when the feature is removed (drop the `command`
      provider / the ledger `capture_command` field → tests go red). — demonstrated
      red before implementation (6 of 8 red; 9 after the post-review split). Honest
      caveat: `test_capture_command_not_in_definition_hash` is the one pure
      regression-guard (a `capture` key was already excluded from the hash, so it
      is green without the feature). Every other test is feature-bearing —
      including `test_web_run_records_null_capture_command`, which asserts
      `capture_command is None` and so goes red (KeyError) if the ledger field is
      removed.
- [x] Reviewed by `reviewer` subagent (compliance + craft passes). — `jig:reviewer`,
      independent, 2026-08-21; VERDICT: pass. Two test-tightness nits (spawn-shape
      order; an inert monkeypatch guard) were **fixed** post-review, not deferred
      (see deviation log).
- [x] Implementation review passed. — no blocking issues.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review passed. — `jig:reviewer` reconciliation pass,
      VERDICT: pass, 2026-08-21; deviation-log claims verified against `score.py`
      line-for-line, the 9-test class and both post-review tightenings confirmed,
      SKILL.md + refinement-todo confirmed. One caveat-accuracy nit (a mis-labelled
      regression-guard) corrected above.
- [x] `docs/refinement-todo.md` updated if any decisions were deferred. — added
      "design-eval capture timeout is a fixed 180s shared across all providers".

**Anti-horizontal-phasing check:** After this slice lands, a project on **any**
stack servo can drive — native, desktop, a game harness — can be scored by
pointing `capture.command` at a script that produces a frame-normalized PNG per
screen, with honest fail-closed behaviour and a ledger record of exactly which
command ran. End-to-end cross-stack value, not scaffolding.

**Deferred (candidate for refinement-todo):** the shared 180s capture timeout is
inherited from the web provider; a slow device/emulator screencap may need more.
A per-provider (or `capture.timeout`) knob is a candidate follow-up if a real
native target hits the ceiling — noted, not built, so it isn't a silent gap.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` regenerated by `workflow.py status-board` (only if it
      closes the spec — it does not; 04–05 remain).

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

- **Shared subprocess capture.** Both the web and command providers run through
  one `_run_capture_subprocess(base_dir, screen, run_id, command_prefix, *, label)`
  — the old `_capture_web` body was extracted verbatim, so retention (027-01),
  the `_judge_cli` cwd contract, salient stderr (026-01), and attestation parse
  (026-03) are identical across providers. Only the leading argv differs
  (`node capture.mjs` vs the project command) plus the `label` in the
  "unavailable for capture" message (`node/playwright` vs `capture command`).
- **Provider signature widened to `(base_dir, screen, run_id, config)`.** The
  command provider needs `capture.command` from config; web ignores it. `capture_app`
  gained a 5th param `config=None` and passes it through. The 2-arg external
  callers (`CaptureAppHonestyTests`, the `CaptureLibNodeTests` routing test,
  027-01/02 tests) keep working via the defaults.
- **`capture.command` validated twice, fail-closed.** `score()` calls
  `_capture_command_argv(config)` up front for the command provider (missing/empty
  → `env_error` before any capture, and it captures the argv for the ledger), and
  `_capture_command` validates again at spawn time (defence in depth for any direct
  caller). A non-list / empty / absent command is refused.
- **New ledger field `capture_command`** (top-level, required keyword-only in
  `_ledger`, mirroring `provider`/`fake_run`): the resolved argv on a command run,
  `null` otherwise. Kept out of `_EXTRA_HASH_FIELDS`, so `definition_hash` is
  unchanged (AC4).
- **Post-review test tightening (not deferred).** The independent review flagged
  two tests that did not enforce their claim: `test_command_spawn_shape` asserted
  flag *membership* not *order*, and `test_missing_command_fails_closed_before_capture`
  used a monkeypatch that never reached the module `_capture_main` loads. Both were
  fixed in this slice: the spawn test now pins the exact ordered tail
  (`… --screen <id> --out <path>.png`), and the missing-command test now drives
  `score.score()` directly so the "no capture before validation" guard is live,
  with a separate `test_missing_command_env_errors_through_main` retaining the
  rc-2/`main()` honesty check. (Test count 8 → 9.)
- **Beyond the letter of the ACs:** documented the `command` provider, the
  `capture.command` config, the `--screen/--out` invocation contract, the
  fail-closed behaviour, and the `capture_command` ledger field in `SKILL.md`.
- **Deferred:** the shared 180s capture timeout — noted in `docs/refinement-todo.md`
  as a candidate `capture.timeout`/env knob for slow native captures.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Root orientation; no surface it describes changed. |
| `docs/specs/README.md` | `deferred` | Status-board regen is post-DONE close-out; not run (spec not closed — 04–05 remain; and the known `workflow.py status-board` umbrella-frontmatter rollup bug). |
| `docs/product-vision.md` | `no-op` | No vision-level claim affected. |
| `docs/architecture.md` | `no-op` | Additive provider + one ledger field; no module boundary, contract, or artifact-path change. |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | None reference capture providers or the ledger shape. |
| `docs/inbox.md` | `no-op` | Nothing to hand off. |
| `docs/refinement-todo.md` | `updated` | Added "design-eval capture timeout is a fixed 180s shared across all providers" (deferred `capture.timeout` knob). |
| `docs/memory/**` | `no-op` | No durable cross-session fact beyond spec + code. |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR touched — ADR-0032 already Accepted and governs this seam. |
| `skills/design-eval/SKILL.md` | `updated` | Documented the `command` provider, `capture.command`, the `--screen/--out` contract, fail-closed behaviour, and the `capture_command` ledger field. |
