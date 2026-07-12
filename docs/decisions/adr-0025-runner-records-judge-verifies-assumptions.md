---
status: Accepted
date: 2026-07-11
deciders: ramboz
supersedes:
superseded-by:
last_verified: 2026-07-12
---

# ADR-0025: Runner records load-bearing assumptions; judge verifies them

## Status

Accepted (2026-07-12)

Decides spec 021 slice 02. Blocks that slice's DoR until Accepted.

## Context

servo's agent-loop is **headless**. `agents/runner.md` mandates *no clarifying
questions*: "Ambiguous prompt → make the most reasonable interpretation and
proceed." That keeps the loop unattended, but it also means an ambiguous or
under-specified prompt is resolved **silently** — the runner picks an
interpretation, acts on it, and nothing records that a load-bearing choice was
made. When the interpretation is wrong, the loop can iterate confidently toward
the wrong target, and neither the judge nor a later human sees the fork in the
road. This is the "confidently wrong from missing context" failure mode, in the
one place servo can't fall back on a human answering a question mid-run.

The verdict block is the loop's structured channel between runner, judge, and
`loop.py`. Per [ADR-0003](adr-0003-fresh-subagent-roster.md) it is **strictly
parsed**: `schema_version` must be the first field and the unquoted integer `1`;
`loop.py` refuses any block that is missing it, has a non-integer value, or a
value other than `1`, terminating the run with `verdict_schema_mismatch`.

The oracle boundary is fixed: [ADR-0021](adr-0021-oracle-first-agent-loop-optional-consumer.md)
(oracle-first; the agent-loop is one optional consumer), [ADR-0011](adr-0011-host-native-phase-hints.md)
(agent/host hints are advisory; `gate.py`/`oracle.sh` are authoritative), and
[ADR-0005](adr-0005-eval-oracle-component.md) (non-deterministic judgment enters
the composite only as a frozen score). Any assumption mechanism must live in the
**agent/consumer layer**, never in the oracle.

## Decision

1. **The runner records its load-bearing assumptions in the verdict block.**
   When the runner resolves a materially ambiguous prompt, it surfaces the
   assumption it acted on rather than interpreting silently. `agents/runner.md`'s
   "no clarifying questions" posture is amended to "no clarifying questions —
   surface the load-bearing assumption in the verdict block instead."
2. **The judge verifies those assumptions.** `agents/judge.md` checks each
   recorded assumption against the changed code and the oracle output and
   reflects an unsupported/violated assumption in its verdict and reasoning. This
   is judge-side, advisory review — it does **not** become an oracle gate
   (ADR-0021 / ADR-0011 / ADR-0005 boundary preserved).
3. **Carrier: a new `assumptions:` verdict-block field, risk-gated.** It carries
   only load-bearing assumptions (empty/omitted is the correct, common state — no
   boilerplate), mirroring jig's risk-gated assumptions discipline.

**Schema compatibility.** The 2026-07-12 pre-acceptance probe found that
`loop.py`'s `_parse_verdict_block` tolerates unknown fields after the first
`schema_version: 1` line. Therefore `assumptions:` is OPTIONAL under
`schema_version: 1`; no version bump is required. The strict schema gate remains
unchanged: missing / non-first / quoted / non-integer / wrong-version
`schema_version` values still refuse with `verdict_schema_mismatch`.

## Consequences

### Positive
- Silent misinterpretation in a headless run becomes a visible, judged artifact —
  the "confidently wrong" fork is recorded and checked.
- Reuses the existing verdict-block channel and the judge that already runs; no
  new component, no oracle change.
- Consistent with jig's clarify/assumptions discipline, adapted for an
  unattended loop.

### Negative
- Adds a field to a frozen, strictly-parsed contract (ADR-0003) — requires care
  and, in the strict-parser branch, a `schema_version` bump touching `loop.py`.
- Assumption quality depends on the runner's honesty; a runner that under-reports
  assumptions blunts the benefit (the judge mitigates, doesn't eliminate).

### Neutral
- `assumptions:` is risk-gated: the common state is empty, so most verdict blocks
  look unchanged.

## Alternatives considered

- **Do nothing (keep silent interpretation).** Cheapest, but leaves the headless
  confidently-wrong failure mode unaddressed — the reason this ADR exists.
- **Let the runner ask clarifying questions.** Contradicts the headless design;
  there is no human in the loop to answer, and blocking on a question stalls an
  unattended run.
- **Put assumption-checking in the oracle/`gate.py`.** Rejected — violates the
  ADR-0021 / ADR-0011 / ADR-0005 boundary that keeps `gate.py` deterministic;
  assumption verification is judgment and belongs judge-side, advisory.
- **A separate sidecar file for assumptions** (not the verdict block). Rejected —
  splits the runner↔judge channel and adds an artifact `loop.py` would have to
  learn to correlate; the verdict block already is that channel.

## Verification
- Preserve the probed `loop.py` verdict-block parser behavior: an optional
  `assumptions:` field at `schema_version: 1` parses successfully, while missing
  / non-first / quoted / non-integer / wrong-version `schema_version` still
  refuses with `verdict_schema_mismatch`.
- Surface tests assert the runner records and the judge verifies assumptions.
- A `loop.py` parse test proves the chosen branch: valid blocks (with and without
  `assumptions:`) accept; malformed/missing `schema_version` still refuses.

## References
- [ADR-0003](adr-0003-fresh-subagent-roster.md) — fresh-subagent roster + verdict-block contract (amended here)
- [ADR-0021](adr-0021-oracle-first-agent-loop-optional-consumer.md) — oracle-first; agent-loop is one optional consumer
- [ADR-0011](adr-0011-host-native-phase-hints.md) — agent/host hints advisory; gate.py authoritative
- [ADR-0005](adr-0005-eval-oracle-component.md) — non-deterministic judgment enters the composite only as a frozen score
- `agents/runner.md`, `agents/judge.md`, `skills/agent-loop/loop.py`
- spec [021](../specs/021-headless-agent-investigation/spec.md) slice 02
