---
status: DEFERRED
dependencies: [016-01, 016-02, adr-0016]
last_verified:
---

## Slice 016-05 — prompt-render

**Goal (pre-SPIDR — no ACs):** Make the plan's `prompt_ref` a *usable seed prompt*.
Today 016-01 emits `prompt_ref = str(spec_path)` — a path to the whole `spec.md`
document — but `loop.py` feeds the seed **verbatim** to `claude -p` as the
per-iteration task instruction (`loop.py:1300`, `:464`), so a multi-slice planning
document is incoherent as an instruction. This slice makes `execution_plan.py`
*compile an actionable prompt* from the spec (read `spec.md`, extract the actionable
core, render a compact implement-this-until-the-oracle-passes instruction to a
target-relative artifact under the plan dir) and teaches `loop.py --plan` to seed
from it when `--prompt` is omitted — completing the Compile→Run prompt handoff that
[016-02](slice-02-run-consume.md) left explicit.

**DEFERRED — resolution trigger:** activates once **016-02 is DONE** (the plan
budget/driver read-seam exists) *and* a real Compile→Run wants the plan to supply the
task prompt rather than a hand-passed `--prompt`. Splitting it out was decided by the
016-02 frame-critique (2026-07-02): rendering a good prompt is a distinct capability
(a spec-section parse + a rendering contract, with defined behavior for specs that
don't match the expected shape), not a knob-read — pinning its ACs needs the
rendering rule chosen deliberately (embed the spec's actionable core vs. reference
it), not guessed.

> Open design question for DRAFT: **what does the rendered prompt contain?** Embed
> the spec's H1 title + overview (self-contained, reproducible) vs. a reference to
> the spec path (fragile if the spec moves); and what is the fallback when a spec
> lacks the expected section shape. The oracle already encodes the ACs, so the seed
> need only convey the high-level task + "make `oracle.sh` pass," not restate every
> criterion.
