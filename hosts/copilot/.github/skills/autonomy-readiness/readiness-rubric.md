# Autonomy-readiness rubric — score the PROMPT itself

This is servo's **built-in** model-judge framing, used by
`/servo:autonomy-readiness` when jig's `clarify` skill is **not** co-installed.
It scores the *initial prompt* that is about to be handed to an unattended,
long-horizon agent loop — not any code, not any spec — on five dimensions. A
long run is only as safe as the premise it converges toward, so a vague or
unbounded prompt is the single most expensive failure mode.

Score each dimension `ok` or `concern`. Reply `concern` whenever the prompt is
deficient on that dimension; be conservative — when unsure, prefer `concern`.

## The five dimensions

1. **Precision.** Is the prompt specific and bounded, or is it a vague wish
   ("make it better", "improve the code", "clean things up")? A precise prompt
   names *what* changes and *what "done" looks like*. A one-line taste request
   with no concrete target is a `concern`.

2. **Scope-boundedness.** Does the prompt name what is **out** of scope? A
   long-horizon run needs a hard perimeter — without a stated boundary the loop
   will wander into adjacent code, refactors, or dependencies. If the prompt
   states no limits on where it may act, that is a `concern`.

3. **Stop / escalation conditions.** Does the prompt say **when to stop** rather
   than thrash — a definition of success, a give-up condition, or "escalate to a
   human when X"? A prompt with no stop condition can burn a full budget looping
   on an unreachable goal. Absent stop/escalation guidance is a `concern`.

4. **Safety surface.** Does the work touch secrets, credentials, deploys, data
   migrations, production systems, or other **external side-effects**? Such work
   requires human checkpoints; a prompt that walks into a safety surface without
   naming a checkpoint is a `concern`. Name the specific surface in the note so
   the human sees exactly what needs a gate.

5. **Internal contradiction.** Does the prompt ask for mutually incompatible
   things (e.g. "rewrite everything but change nothing", "be exhaustive but
   fast and cheap")? An internally contradictory prompt cannot converge — that
   is a `concern`.

## Independence

The scoring runs as **two** separate one-shot calls: an expansion pass that
proposes per-dimension verdicts, then a fresh **independent-review** pass that
sees only the prompt and the proposed verdicts (never the expansion's
reasoning) and may confirm or challenge them. The final verdict folds both.
This mirrors `eval-authoring`'s expand-then-independent-review pattern so no
single pass both proposes and self-blesses.
