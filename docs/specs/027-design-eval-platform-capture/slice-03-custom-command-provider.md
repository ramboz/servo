---
status: IN_PROGRESS
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
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one fixture
      (command spawn shape `--screen/--out`; missing/empty command → rc2 env_error
      before capture; non-zero/no-output command → rc2 env_error; ledger
      `capture_provider: "command"` + `capture_command` argv; unattested command →
      `not_attested`; web path unchanged).
- [ ] Each new test shown to fail when the feature is removed (drop the `command`
      provider / the ledger `capture_command` field → tests go red).
- [ ] Reviewed by `reviewer` subagent (compliance + craft passes).
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred (e.g. a
      per-provider capture timeout knob, if the shared 180s proves wrong for slow
      device captures).

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

_TBD during reconciliation._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | _TBD._ |
| `docs/specs/README.md` | `deferred` | _TBD: status-board regen at close-out; spec not closed._ |
| `docs/product-vision.md` | `no-op` | _TBD._ |
| `docs/architecture.md` | `no-op` | _TBD: additive provider + ledger field, no module-boundary change._ |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | _TBD._ |
| `docs/inbox.md` | `no-op` | _TBD._ |
| `docs/refinement-todo.md` | `no-op` | _TBD: note the capture-timeout knob if deferred._ |
| `docs/memory/**` | `no-op` | _TBD._ |
| `docs/decisions/README.md` / ADR index | `no-op` | _TBD: no ADR touched (ADR-0032 already Accepted)._ |
| `skills/design-eval/SKILL.md` | `updated` | _TBD: document the `command` provider + `capture.command` + `capture_command` ledger field._ |
