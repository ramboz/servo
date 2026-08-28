---
status: IN_PROGRESS
skill:
use_cases: []
---

# Spec 029: design-eval reachability (manual capture + subagent advisory judge)

> Realizes [ADR-0034](../../decisions/adr-0034-design-eval-subagent-judge-transport.md)
> and [ADR-0035](../../decisions/adr-0035-design-eval-manual-capture-provider.md).
> Motivated by the v0.9.0 field report: the target was an in-game overlay servo
> could not capture, in a Claude Desktop app where neither judge transport was
> available — so the run degraded to `SERVO_DESIGN_EVAL_FAKE_SCORES`, the exact
> path that makes a rigged run hard to spot.

## Overview

Make design-eval runnable — honestly — where Claude Code actually runs and on
targets servo cannot drive, without letting either path masquerade as a frozen
measurement. Two new transports on existing seams:

- **`manual` capture provider** (ADR-0035, on the ADR-0032 provider seam):
  consume a human-supplied PNG for non-automatable targets, with a distinct
  `manual_capture` provenance and a **loud stderr advisory on every run**. Fails
  closed (`env_error`) when no shot is staged. The doctored-image residual is
  inherent and named, not closed — the advisory is masquerade-prevention, not
  doctoring-detection.
- **`subagent` judge advisory transport** (ADR-0034): let the orchestrating Claude
  Code session run the vision judge on its own subscription, shipped as a **loud,
  non-frozen advisory — not a frozen score** (the model is self-reported, not
  verifiable across the boundary). Non-gating is **structural**: on the oracle
  entrypoint a subagent-transport eval returns `env_error`, so it can never be
  consumed as a gate pass; the advisory read is reached only via an explicit
  non-oracle command.

Current state (probed 2026-08-27):
- Capture providers: `_CAPTURE_PROVIDERS = {web, command, android, ios}`
  (`score.py:497`); `capture_app` dispatch fails closed on an unknown provider
  (`score.py:518`); provenance tokens `not_captured`/`not_attested`/`attested` in
  `_provenance` (`score.py:784`); retained shots `_shot_out_path` (`score.py:215`).
- Judge transports: `judge()` dispatches exactly `cli`/`api` (`score.py:537`);
  `_judge_cli` needs a spawnable `claude` binary, `_judge_api` needs
  `ANTHROPIC_API_KEY`.
- The oracle component runs `python3 .servo/design-eval/score.py "$PWD"` and
  `oracle.sh` captures its stdout as the score (`design_eval.py` `_FRAGMENT`);
  `EXIT_ENV_ERROR = 2` maps to a missing component.

Non-goals: the scoring *policy* (spec 028 / ADR-0033), the frozen `web`/native
capture providers, and the deterministic oracle families are untouched.

## Assumptions

- The orchestrating Claude Code session can run a vision-capable subagent that
  reads two PNGs by path and returns a numeric score — demonstrated by the
  field-report user out of band, so this is grounded, not hypothetical (029-02
  still probes the concrete channel).
- **Motive assumption (ADR-0034):** the population helped by the subagent advisory
  has an *authoring/iteration read* need, not a *gating* need — the one documented
  user wanted a gate, which this deliberately does not serve. 029-02 must weigh
  this against real demand and record the finding; if demand is overwhelmingly for
  a gate, the honest answer is api/cli reachability, not this transport.
- A `score.py` subprocess can detect "no orchestrator present" reliably enough to
  fail closed without hanging or silently degrading (029-02 probes the detection).

## Decomposition

SPIDR — split by **Interface** (which transport/provider) then **Path**. No Spike:
ADRs 0034/0035 did the framing; each residual is probed inside its slice. 029-01
(manual capture) is lower-risk and self-contained, so it lands first; 029-02
(subagent advisory) carries the harder honesty machinery.

- **029-01 (Interface + Path)** — the `manual` capture provider: a staged-PNG
  provider on the ADR-0032 seam, `manual_capture` provenance + input hash/mtime, a
  loud stderr advisory every run, fail-closed when absent. Vertical: an author
  selects `capture.transport: manual`, stages a shot, and scores a
  non-automatable target end to end.
- **029-02 (Interface + Path)** — the `subagent` judge advisory transport: a real
  vision judge run by the session over the real shot, reached only via an explicit
  non-oracle advisory command, returning `env_error` on the oracle entrypoint,
  with a loud stderr advisory and self-reported (not attested) model in the ledger.

## Slices

- [029-01 — manual-capture](slice-01-manual-capture.md)
- [029-02 — subagent-advisory](slice-02-subagent-advisory.md)
