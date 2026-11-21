---
status: DRAFT
skill: eval-authoring
use_cases: []
---

<!-- jig self-defining vocabulary (soft, forward-only): expand each acronym on first use and link the term to docs/memory/glossary.md (or jig's lexicon). See docs/workflow.md "Self-defining vocabulary". -->

# Spec 049: Verify skill as candidate gathering

> Consumes jig's repo-verify contract — jig
> [ADR-0073](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0073-repo-verify-skill-contract.md) /
> [spec 128](https://github.com/ramboz/jig/blob/main/docs/specs/128-repo-verify-skill/spec.md)
> (ADR Proposed, spec DRAFT). Investigation record: jig
> [R-002](https://github.com/ramboz/jig/blob/main/docs/research/R-002-claude-code-verification-assessment.md),
> item 4 ("Verification means running the change").
> **Status: recorded, not yet built** — no servo ADR of its own (see
> "Decision record" below); 049-01 does not move past DRAFT until jig
> ADR-0073 is Accepted and jig spec 128-01 is DONE.

## Overview

The Claude Code team codifies how to boot, drive and inspect an app in a
repo-owned `verify` skill under `.claude/skills/`, close to the code, and runs it
before committing. jig ADR-0073 / spec 128 make that a contract jig scaffolds.
servo has the matching hole on its side: running the system under test to get
the candidate a judge scores.

- **eval-authoring cannot run a live candidate.** `_gather_candidate`
  (`skills/eval-authoring/score.py:415-429`) raises "candidate-gather is not yet
  implemented", so a live API/CLI `score()` always env-errors (`:609-611`);
  only fake-score hooks and native `candidate_file` snapshots work.
  `docs/refinement-todo.md`, "eval-authoring — candidate-gather (running the
  system under test) is unbuilt", calls it "a documented, deliberately-unbuilt
  seam", with the resolution trigger "the first real eval-authoring consumer
  that needs to score a live (non-fake) candidate".
- **The two presets each have their own gather.** content-fidelity reads a file
  or runs a project command once per case per run, 180-second timeout, failures
  as env errors (`skills/content-fidelity/score.py:125-161`). design-eval's
  default web provider screenshots whatever is already served at `app_url`
  (`skills/design-eval/capture.mjs:80`); nothing in servo starts the app.

This spec lets those gathers use the project's verify contract when one is
declared: eval-authoring cases gain a `verify` source (049-01, which un-parks the
seam for verify-sourced cases), and content-fidelity can take its command from
the same contract (049-02). design-eval's running app is deferred (see
"Deferred" below). Projects without a verify contract see no change.

**Why this does not contradict spec 008's non-goal.** Spec 008 says "Not running
evals. This skill authors, freezes, and installs the `score_<name>` component …
**execution** is `gate.py`/`loop.py`." That stays true: the gather runs inside the
installed `score.py` when the gate calls it, the same place content-fidelity's
and design-eval's gathers run today.

**Trust boundary.** A verify skill is repo code, so a runner iteration can edit
it. That is already true of content-fidelity's `command` source and design-eval's
`command` provider, whose argv is pinned but whose scripts are not. 049 keeps
that posture: the declared source is pinned in the eval definition, the
contract's content is environmental and its sha256 is recorded in every ledger
row (as `capture_command` is, ADR-0032 §6). Stopping a change from rewriting the
check that judges it is servo [spec 045](../045-base-anchored-freeze/spec.md) /
[ADR-0051](../../decisions/adr-0051-base-anchored-freeze.md)'s territory. 045
anchors `checks.json`, `oracle.sh` and eval-authoring definitions to the base
ref — which covers the pinned `source` this spec adds — but not the verify
contract itself; whether it should join that list is a question for 045, not
decided here.

**Decision record.** 049-01 needs no servo ADR: it follows content-fidelity's
gather semantics, ADR-0005 clause 5 (env error, never a silent zero) and
ADR-0032 §6 (capture identity is environmental). 049-02 (content-fidelity's
`verify` source) needs none for the same reason. The deferred design-eval half
is different — it would have the oracle start and stop a served app, a process
lifetime servo has never owned at score time (today's subprocesses are
per-call, e.g. the gate's process-group kill, `skills/quality-gate/gate.py:195-221`),
so it needs a short servo ADR before it is built.

**Deferred: design-eval's served app.** Having design-eval's web provider start
the app, discover `app_url` from the contract, and stop the app on every exit
path was 049-02's second half. jig ADR-0073 point 3 defines one argument-free
command that exits pass / fail / environment error; it has no served-app
lifecycle and no URL. **Resolution trigger:** jig ADR-0073 (or a later revision)
grows a served-app/URL contract, **and** a short servo ADR on the oracle owning a
served app's lifetime at score time (start, bounded readiness, stop on every exit
path, interaction with the gate's process-group kill) is Accepted. Until then
design-eval reads `app_url` from `config.json` only, as today.

**Non-goals.** `source: file|command` for eval-authoring (the rest of the
refinement-todo entry, unchanged by this spec); constraint-DSL actual-value
extraction (`eval-authoring/score.py:494-529`); hashing the verify contract into
any freeze; booting apps for any capture provider (deferred above); changing the
verify contract itself (jig's).

## Assumptions

<!-- Spec 064-02 / ADR-0020 — grounding-by-probe (risk-gated). -->

- **Cited — the jig contract's shape (load-bearing; ADR-0073 still Proposed).**
  jig ADR-0073 point 3: the verify skill's frontmatter may declare one
  `verify-command:` — one command line, split like `.jig/test-command`, run from
  the repository root; exit `0` = pass, `1` = fail, `2` = environment error;
  stdout and stderr are the evidence; absent or empty means `not-run`, never
  pass. "A consumer must not pass extra arguments" — so 049 has no named
  scenario, no per-case input (an `{input}` placeholder is only an ADR-0073 open
  question), and no served app or URL. ADR-0073's own assumption, "servo 049 can
  work with a whole-app command", is what 049-01 tests. **Unverified:** that the
  command runs headless and non-interactively (no agent at score time —
  ADR-0032 §7); ADR-0073 does not say. 049-01's DoR re-checks this against the
  accepted text.
- **Cited — where the declaration lives.** jig ADR-0073 point 1 settles it: one
  host-neutral project skill, `.claude/skills/verify/SKILL.md` or
  `.agents/skills/verify/SKILL.md` (a second host links to the first); machine
  consumers look in project scope only, `.claude/skills/` then
  `.agents/skills/`, never a user-scope skill. servo's resolver follows that
  order. (ADR-0073's remaining open question — whether scaffold-init writes
  both folders — does not change a consumer's lookup.)
- **Probed — a new case field need not stale existing evals.** eval-authoring
  already pins an extra field only when it applies (`candidate_file` for
  Copilot transport, `_definition_fields`, `eval-authoring/score.py:158-161`), so
  pinning `source` only for evals that declare it leaves every existing
  `definition_hash` byte-identical.
- **Probed — content-fidelity pins `source` by value**
  (`_CASE_PIN_FIELDS = ("reference", "source")`, `content-fidelity/score.py:66`)
  and never hashes what it points to; a `verify` source fits that rule unchanged.
- **Probed — `app_url` is environmental** (relevant only to the deferred
  design-eval half). It is excluded from design-eval's
  hashed fields (`_EXTRA_HASH_FIELDS`, `design-eval/score.py:58`;
  `fidelity_eval.py:214-217`) and read only by the web provider, so discovering
  it from the contract re-freezes nothing.

## Decomposition

SPIDR: **Interfaces** — the contract enters through one shared resolver, then
spreads to the gathers that need it, simplest first.

- **049-01 (Interfaces: eval-authoring)** — a shared resolver for the declared
  verify entry point and a `verify` case source in `_gather_candidate`. End to
  end: an eval-authoring eval scores a live candidate produced by the project's
  own verify skill.
- **049-02 (Interfaces: presets)** — content-fidelity's `verify` source.
  design-eval's `app_url` and the app's start and stop are deferred (see
  "Deferred" above).

**Anti-horizontal-phasing.** 049-01 alone turns a dead seam into a working live
score for verify-backed projects; 049-02 alone lets content-fidelity reuse the
project's own run recipe instead of a second, hand-maintained command.

## Slices

- [049-01 — verify-candidate-gather](slice-01-verify-candidate-gather.md) — shared verify-contract resolver; eval-authoring `source: verify` live gather; today's behaviour otherwise.
- [049-02 — preset-verify-discovery](slice-02-preset-verify-discovery.md) — content-fidelity `verify` source; design-eval `app_url` (and app start/stop) deferred.
