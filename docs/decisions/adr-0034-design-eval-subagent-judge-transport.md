---
status: Accepted
dependencies: []
last_verified: 2026-08-27
frame_review: true
---

# ADR-0034: In-harness subagent judge transport for design-eval

## Status

Accepted (2026-08-27)

## Context

design-eval's vision judge is reachable through only two frozen transports, and a
common Claude Desktop setup can run neither — so a score cannot be produced where
Claude Code actually runs. `score.py::judge` dispatches on a frozen
`judge.transport` with exactly two values (`score.py:537-546`):

- **`"api"`** — the Anthropic Messages API; needs `ANTHROPIC_API_KEY` in the
  environment (`_judge_api`, `score.py:599-603`).
- **`"cli"`** — a headless `claude -p` subprocess, which runs the vision judge on
  a Claude subscription with no API key, but needs a **spawnable `claude` binary**
  on `PATH` (or `SERVO_DESIGN_EVAL_CLAUDE_BIN`) (`_judge_cli`, `score.py:554-560`).

The v0.9.0 field report surfaced a common setup where **neither** works: Claude
Code running **inside the Claude Desktop app**. There, Claude Code is bundled in
an Electron app (`Claude.app/…/app.asar`) that exposes **no spawnable `claude -p`**
on `PATH`, and there is **no `ANTHROPIC_API_KEY`** in the environment. So
`_judge_cli` fails (no binary) and `_judge_api` fails (no key), and `score.py` can
only ever return `env_error`. The same user reported the eval "always worked" on
another machine — because that one happened to have the standalone CLI on `PATH`.
The skill treats a spawnable judge as a given; in a common desktop-app setup it is
not.

The consequence in the field is the dangerous part. With no runnable judge
transport, the user produced the six vision-judge samples **out of band** — by
asking the orchestrating Claude Code session's own subagents to judge the images —
and injected them via `SERVO_DESIGN_EVAL_FAKE_SCORES`, the **test/offline hook**
(`score.py:36`), so `score.py` ran its real aggregation over hand-supplied
numbers. That is precisely the path that makes an injected run hard to distinguish
from a real one (the Phase-0 patch now marks it loudly, but the *incentive* to use
it remains as long as no legitimate transport exists where Claude Code runs). The
capability the user actually had — a Claude Code session that can run a vision
model on its own subscription — is not exposed as a judge transport.

**The hard constraint this ADR must respect.**
[ADR-0031](adr-0031-design-eval-browser-acquisition.md) and
[ADR-0032](adr-0032-design-eval-capture-providers.md) §7 both insist that
score-time runs with **no agent / MCP / connector present** — CI, Routines,
`--background`, a Stop-hook — because that is where the oracle actually runs
unattended, and honesty (ADR-0005) requires a reproducible, pinned-model judge
there, not an interactive one. An "in-harness judge run by the orchestrating
session" is, by construction, an **agent at score time**. It therefore cannot be
the transport the unattended gate uses, and it raises two honesty problems:

1. **No orchestrator exists in unattended runs.** `oracle.sh` invokes
   `score.py <target>` as a plain synchronous subprocess and reads one float from
   stdout. In CI / `--background` there is no Claude Code session to delegate the
   judgment to, and even interactively, a subprocess has no channel back to the
   session that spawned the loop.
2. **Model pinning.** The freeze hashes `judge.model` and the n-sample lower bound
   assumes a fixed judge. A subagent "on its own subscription" runs whatever model
   the session is configured with, which need not equal the frozen
   `judge.model` — silently breaking the pinned-model guarantee.

So the question is not merely "add a third transport." It is: **can an in-harness
judge be exposed without eroding the agentless, pinned, reproducible score-time
contract — and if so, is it a *frozen scoring* transport at all, or an explicitly
attended, advisory one?**

## Decision

Add an **attended-only `judge.transport: "subagent"`**, but ship it as a **loud,
non-frozen advisory fidelity check — not a frozen score** — because the judging
model cannot be *verified* across the subagent boundary, only self-reported. The
inversion is deliberate: an unverifiable judge must not wear the frozen score's
authority (frame-critique #2). Frozen scoring via a subagent is deferred until a
real attestation-to-computation binding exists, which this ADR cannot name today.

1. **Why it can only be advisory: the model is commanded on api/cli, but merely
   self-reported on subagent.** On `api`/`cli` the harness *dictates* the model —
   it is a commanded input parameter (`--model config[judge][model]` in
   `_judge_cli`, `"model": j["model"]` in `_judge_api`, `score.py:569/619`) sent to
   a transport servo controls, so the named model *is* the model that ran. Across
   the subagent boundary the harness cannot command; it can only *receive* a score
   and whatever model string the subagent chooses to report. Nothing binds that
   string to the computation that produced the number: a subagent that guessed a
   score and stamped the frozen model string is indistinguishable from one that
   actually ran the frozen vision model. That is the fake-scores act with a
   protocol wrapper — so a subagent result **must not** be a frozen, gating score.

2. **Primary form — attended advisory, and "non-gating" is *structural*, not a
   label.** `subagent` transport runs the **real** vision judge (a session
   subagent) over the **real** captured shot and returns a fidelity read that is
   **loudly marked non-frozen** — a prominent **stderr** advisory on every run,
   `SUBAGENT JUDGE — self-reported model, an advisory read, NOT a verified frozen
   score`, on the channel a loop/CI/Routine log actually surfaces (the reason
   Phase-0 put the fake-scores tell on stderr, not the ledger). Crucially, the
   advisory is reached only through an **explicit non-oracle path** (an attended
   `design_eval.py`/skill "advisory read" command) and is **never emitted as the
   oracle's gating `[0,1]` composite**: in the `oracle.sh`/gate invocation a
   subagent-transport eval prints **no stdout score** and returns `env_error`
   (rc 2), so `oracle.sh` treats it as a missing component — it can *never* be
   consumed as a pass/fail. This is what makes "non-gating" real: the score-shaped
   number does not exist on the gating path, so there is no advisory number to
   quietly promote into the oracle. **The discriminator is the *entrypoint*, not
   attendance**: `score.py` invoked as the oracle component refuses subagent
   transport with `env_error` *regardless* of whether a live session is present, so
   even the **attended `/servo:agent-loop` gate** (where `oracle.sh`→`score.py`
   runs *and* a session exists) cannot consume a subagent number. Were the block
   attendance-based, that attended loop would revive the round-2 incentive
   migration; entrypoint-based closes it. The advisory read is produced *only* by
   the separate non-oracle command. The ledger records `judge.transport:
   "subagent"`, the **self-reported** model (labelled self-reported, never
   attestation), and the retained shot. It beats the fake-scores workaround not by
   claiming verification it cannot deliver, but by (a) running a real judge over a
   real retained image and (b) being *louder* about its own limits than a ledger
   token — an honest middle, explicitly and structurally below a frozen score.

3. **Attended-only; fails closed unattended.** Available **only** when a live
   orchestrating session is present to fulfil the judgment. In any unattended
   context — CI, a Routine, `--background`, a Stop-hook, or no session channel —
   it **fails closed to `env_error` (rc 2)**, naming `api`/`cli` as the frozen
   options; it never silently degrades and never returns a 0.0. This preserves
   ADR-0031/0032 §7: the unattended gate still has no agent. The fail-closed
   detection is the *safe*-direction risk (absence of channel → block → timeout →
   `env_error`); the dangerous direction (a subagent firing unattended) requires a
   live session in CI, which is absent by construction.

4. **Mechanism: a judge-request handshake, not a model call inside `score.py`.**
   `score.py` emits a structured **judge request** (the two PNG paths + the scoring
   instruction, per screen/sample) and blocks on a **judge response** through a
   session-provided channel (a request/response file pair under the eval dir, or an
   MCP/stdout protocol the harness answers). Absence of the channel is the
   "unattended" signal from §3. The advisory honesty properties hold regardless of
   the channel's shape.

5. **A frozen subagent score is deferred, not promised.** If a future mechanism
   can *bind* the attested model to the computation — not a self-report by the
   judged party (e.g. a harness-side transcript the session cannot forge, or a
   signed model receipt) — a spike may revisit promoting the subagent path to a
   frozen transport. Until such a binding is named and demonstrated, it stays
   advisory. `SERVO_DESIGN_EVAL_FAKE_SCORES` remains a loudly-marked offline/test
   hook, never a sanctioned judging path.

## Consequences

**Becomes easier / positive:**
- The real beneficiary is the **attended authoring / iteration** workflow: while
  building a UI toward its mockup in the Desktop app (no API key, no standalone
  CLI on `PATH`), a developer gets an **honest, real-judge fidelity read** to
  steer by — without pretending it is a frozen score, and without hand-producing
  numbers.
- For that authoring use, it removes the injection incentive honestly: a real
  judge over the real shot, loudly marked, replaces "type six numbers into the
  fake-scores hook." (See the negative below for the use it pointedly does *not*
  serve.)

**Becomes harder / negative:**
- **It does not meet the field-report user's actual need — a *gating* number —
  and that gap is deliberate.** The motivating user injected fake scores to drive
  `score.py`'s real aggregation and get a composite to compare against a threshold
  (0.7998 vs 0.80): a *measurement/gating* need, not a feedback-read need. This
  advisory transport does **not** serve it — by §2 a subagent-transport eval on
  the oracle path is `env_error`, never a gating score — so for the gating-motivated
  user the incentive to obtain a number some other way is **unchanged**; their
  honest path remains getting `api`/`cli` onto that machine. The ADR closes the
  *authoring-read* gap, not the *gating* gap, and must not be mistaken for the
  latter. (This is why "removes the incentive" is stated as motive-conditional in
  Assumptions, not as a general claim.)
- **The advisory must be *unmissable*, or it decays toward the fake-scores
  failure it replaces.** Its whole honesty rests on the loud stderr marking + the
  self-reported (not attested) labelling. That marking must be mutation-tested
  (servo's own lesson: a guard that cannot fail is untested), and no consumer may
  treat a subagent result as a measurement.
- **The attended/unattended split is load-bearing and must be enforced, not
  documented.** A subagent transport that silently ran in an unattended context
  would reintroduce an agent into the gate and break §7; fail-closed must be
  tested.
- New protocol surface (the judge-request/response channel) to design, secure (it
  passes file paths the session will read images from), and test.

**Neutral:**
- api/cli transports and the frozen `judge.model` hashing are unchanged; subagent
  is purely additive and strictly below them in authority.
- A subagent result never enters `definition_hash` reasoning as a frozen score;
  freezing `judge.transport: "subagent"` marks an eval as advisory-only.

## Alternatives considered

- **Do nothing; require api or cli.** Rejected: it declares the Desktop-app setup
  out of scope and leaves the fake-scores injection as the only path that "works"
  there — the exact failure mode the report documents.
- **Let the subagent judge run in unattended contexts too (a general third
  transport).** Rejected: reintroduces an agent at score time (violates
  ADR-0031/0032 §7), and there is no orchestrator to delegate to in CI /
  `--background` anyway — it would have to spawn one, which is the interactive
  dependency §7 forbids in the gate.
- **Advisory, loudly-non-frozen mode (now ADOPTED as the primary form).** The
  first draft made this a fallback and kept "frozen, model-pinned, verified score"
  as primary. Frame-critique #2 showed the pin cannot be *verified* across the
  subagent boundary — the attested model is a self-report by the judged party, so
  a "verified frozen score" is fake-scores with a protocol wrapper and a
  more-authoritative-looking ledger row. Inverted: advisory is the shipped form;
  frozen scoring is deferred (§5) until a real binding exists.
- **Frozen subagent score with a self-reported model attestation (the first
  draft's §3).** Rejected: an attestation the judged agent writes about itself
  binds nothing to the computation; it is strictly weaker than api/cli's commanded
  model and no stronger than the fake-scores hook it claimed to obsolete.
- **Auto-install / auto-locate a `claude` binary from inside the Electron
  bundle.** Rejected: brittle (bundle layout is not a contract, changes across
  Desktop versions), and it does not solve the no-API-key case cleanly; the
  subagent path uses the capability the session already has.
- **Freeze the judging model as "whatever the session runs" (drop the pin for
  subagent).** Rejected for a *frozen* score (breaks ADR-0005 reproducibility) —
  which is *why* the subagent path is advisory, not frozen; an advisory read need
  not be reproducible across sessions, and is marked as such.

## Assumptions

- The orchestrating Claude Code session can run a **vision-capable** subagent that
  reads two PNGs by path and returns a numeric score — this is exactly what the
  field-report user did out of band, so it is demonstrated, not hypothetical.
- **Motive assumption (load-bearing for the value claim).** The population this
  helps has an *authoring/iteration read* need, not a *gating* need. The one
  documented user (the field report) had a **gating** need (a number vs a
  threshold), which this transport deliberately does not meet (Consequences). So
  the "removes the injection incentive" benefit is asserted for the authoring
  population, **not** for that user — whose incentive is unchanged until they get
  `api`/`cli`. If, in practice, desktop-app design-eval users overwhelmingly want a
  gate rather than a read, the transport serves a smaller audience than the report
  implies, and the honest answer for the majority is api/cli reachability, not this
  ADR. To weigh in the spec against real demand.
- The self-reported model string is **not** treated as verification (§1): the
  advisory framing assumes precisely that it *cannot* be bound to the computation,
  so the ADR does not depend on attestation being trustworthy — it depends on the
  advisory being loudly marked. No spike is needed to "prove attestation"; the
  honest default is that it is unverifiable.
- A subprocess `score.py` can detect "no orchestrator present" reliably enough to
  fail closed (§3) — e.g. absence of the response channel within a bounded wait.
  To verify: the detection must not false-positive into a hang or a silent 0.0.

## Kill criteria

- If the advisory read **cannot be made unmissable** — the loud stderr marking is
  swallowed by some host, or downstream consumers treat a subagent result as a
  measurement despite the marking — the transport is shelved rather than ship a
  quiet, real-judge score that reads as authoritative (the very failure it
  replaces).
- If "no orchestrator present" cannot be detected without risk of a hang or a
  silent degrade in unattended runs, the transport is shelved — a subagent judge
  that might fire in CI is worse than none.
- Promotion to a **frozen** subagent transport is killed on arrival unless a
  concrete attestation-to-computation binding (§5) is named and demonstrated; a
  self-report never qualifies.

## Open questions

1. **The judge-request/response channel.** File-pair under the eval dir vs. an MCP
   tool the harness answers vs. a stdout/stdin protocol — which composes with
   `oracle.sh`'s "run `score.py`, read one float" contract without leaking the
   agent into the unattended path?
2. **Interactive-loop integration.** In `/servo:agent-loop` (attended, driver =
   goal/loop), does the loop's own Claude session fulfil the judge requests, and
   does that create a self-judging conflict (the session both fixing the UI and
   scoring it)? A different subagent, or an isolation boundary, may be required.
3. **Shared with [ADR-0033](adr-0033-design-eval-structured-scoring-policy.md).**
   The structured-policy enumerate step and the scoring judge use the same
   transport; specify them together so a desktop-app project has one coherent
   attended path.

## References

- **[ADR-0031](adr-0031-design-eval-browser-acquisition.md)** /
  **[ADR-0032](adr-0032-design-eval-capture-providers.md)** — the agentless,
  environmental score-time contract (§7) this ADR must not break; the subagent
  transport is carved out as attended-only to preserve it.
- **[ADR-0005](adr-0005-eval-oracle-component.md)** — honesty + pinned-model
  reproducibility; because the pin cannot be *verified* across the subagent
  boundary, this ADR keeps the subagent path advisory rather than frozen (§1/§5).
- **[ADR-0033](adr-0033-design-eval-structured-scoring-policy.md)** — shares the
  transport for its enumerate step.
- **field report** (`/servo:design-eval` v0.9.0, 2026-08-27) — the desktop-app
  no-transport case and the fake-scores injection it forced.
