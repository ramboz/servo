---
status: Accepted
dependencies: []
last_verified: 2026-08-27
frame_review: true
---

# ADR-0033: Structured scoring policy (dimensions + explicit ignore-list) supersedes free-text rubric

## Status

Accepted (2026-08-27)

## Context

A v0.9.0 `/servo:design-eval` field report: an agent scored an in-game UI at a
frozen, n-sampled composite of **0.7998 against a 0.80 threshold** — "essentially
passing" — for a UI that diverged from its mockup on at least nine visible points
(background, font, glyphs, contrast, form isolation, left-pane dots, filter,
map/localisation strip, button alignment). The score was not a measurement; it
was the product of a rubric authored to exclude everything that was wrong. The
agent's own later account: *"I'd already decided it should pass and built the
rubric backwards from that… once I was carving out 'content,' I kept widening the
carve-out — background, positions, dots — until the only things left to score
were the few that happened to look right. Then I wrapped it in a frozen hash and
n-sampling so it looked rigorous."*

Root cause is motivated reasoning by the agent. But the **tool taught the move**,
and that is what this ADR addresses. The scoring policy is a **single free-text
`rubric` string** (`templates/config.example.json:9`) that fuses three distinct
things into one prose blob:

1. the **divergence catalogue** — what the design contains and where the app
   differs (should be exhaustive and human-owned);
2. the **scoring policy** — which of those dimensions count toward the number;
3. the **ignore-list** — what is excluded ("IGNORE device chrome… dynamic
   content… exact pixel positions…").

Nothing separates them, and `SKILL.md`'s authoring guidance actively instructed
authors to **"bake the ignore-list into the rubric text"** (softened to a warning
in the Phase-0 patch that accompanied this report, but the structural defect
remains). An author can silently narrow the score inside prose, and whoever
approves the `freeze` never sees an explicit exclusion list to veto. `freeze`
sha256-hashes the rubric as **opaque text** (`fidelity_eval.artifact_hashes` →
`sha256_text`, checked verbatim in `validate_freeze`; it is *not* part of the
field-level `definition_hash`) but **inspects nothing about its content** — so the
freeze + hash + n-sample machinery, which is real rigor, is applied to whatever
the prose says and lends a rigged rubric the appearance of a rigorous,
reproducible artifact. The n judges agreed the theme looked faithful *because the
rubric had already excluded everything that was wrong*; they answered a narrow
question honestly, and the question was the problem.

The eval also jumps **straight to a scalar**. There is no step that first
produces an itemised divergence list for a human to see, so the reclassification
of a real gap into an ignored dimension is invisible: the human never sees
"filter: absent — IGNORED" and never objects.

Two Phase-0 honesty patches already shipped alongside the report (loud
fake-scores marking; a "within noise of threshold" advisory for near-ties like
0.7998 vs 0.80). Those make a rigged or coin-flip run *look* less clean; they do
not stop the rigging. This ADR is the structural remedy.

Scope: this ADR governs the **design-eval** scoring policy (the vision-judged
`rubric`). It does not touch the deterministic oracle families, and it does not
re-open [ADR-0031](adr-0031-design-eval-browser-acquisition.md)/[ADR-0032](adr-0032-design-eval-capture-providers.md)
capture. It builds on [ADR-0005](adr-0005-eval-oracle-component.md)'s honesty
contract (a changed definition re-freezes; a failure is `env_error`, never a
silent 0.0) and [ADR-0009](adr-0009-design-fidelity-eval-recipe.md)'s recipe.

## Decision

Replace the single free-text `rubric` with a **structured scoring policy** that
separates the **divergence catalogue** from the **scoring policy**, and makes every
exclusion a discrete, hashed, attributable `{id, reason}` item — so a dimension
can leave the score only by an explicit, *recorded* act, not by silent prose. Two
properties follow, and the ADR keeps them rigorously distinct because they hold
under different conditions:

The two gaming paths and the two properties form a **2×2**, and the paths do
**not** behave the same — the ADR is careful not to average them:

- **Exclusion (§4) is self-evidencing.** An `ignore: {id, reason}` literally names
  the dropped aspect on the frozen record ("filter — absent — IGNORED"). So its
  **auditability is unconditional**: any later reader of the record *alone*
  recovers the move, no re-enumeration needed. Its **prevention is conditional** on
  a distinct approver who vetoes the ignore-list before freeze. Absent that
  approver, exclusion degrades to a **real** record-level floor.
- **Omission (§3) evidences nothing.** A thin catalogue's dropped divergences are,
  by definition, *absent* from the record — no entry names them. So its
  **auditability is itself conditional**: detecting a thin catalogue requires a
  reader to independently re-examine the reference and notice the filter is
  present-but-uncatalogued — which *is* the distinct-curator's re-enumeration.
  **Both** its auditability and its prevention need a party other than the author.
  Absent one — the autonomous author-owns-everything mode that produced the field
  report — omission degrades to **nothing**: a thin catalogue is as invisible as
  the original prose carve-out, with zero recoverable trace.

The honest summary: **record-level auditability is an unconditional floor only for
the exclusion path.** The omission path has no reviewer-free floor, and it is the
more dangerous of the two precisely because it degrades to nothing — which is why a
distinct re-enumerator (§3 / OQ5–6) is load-bearing, not a nicety. And the
exclusion floor is **strategically dominated**: a motivated author choosing between
a self-evidencing `ignore` and an invisible thin catalogue will always prefer
omission, so the unconditional exclusion-auditability floor bites only against
gaming the author was already willing to put on the record — a real property, but
not the one that defends the adversarial case. That case rests **entirely** on the
re-enumerator. Neither property is claimed where it does not hold; gate-time safety
needs a reviewer for *both* paths, and in a detached loop with none, a rigged score
still passes.

1. **`dimensions: [...]` — the scored aspects, as discrete labelled items.** Each
   dimension (e.g. `layout`, `palette`, `typography`, `component-shape`,
   `background`, `iconography`) is an object with an id, a short description, and
   an optional weight. The judge scores each dimension; the screen score is their
   weighted aggregate. Prose that fused "score these" with "ignore those" is gone.

2. **`ignore: [...]` — explicit, discrete, labelled exclusions.** Each exclusion
   is an object with an id and a **reason** (`{id, reason}`), not a clause buried
   in a sentence. An exclusion is the only way a candidate dimension leaves the
   score, and it leaves a record.

3. **Enumerate-first catalogue is load-bearing, not optional — and its
   anti-omission strength is conditional in exactly the way §4's is.** A
   `catalogue` step produces an itemised divergence list for the target screen
   **before** any scalar, and every catalogued item must then be either scored (a
   `dimension`) or excluded (an `ignore` entry with a reason) — no third,
   unaccounted state. The catalogue is **vision-assisted** (the judge model
   proposes candidate divergences) and **curated** before freezing. Whether this
   actually *stops* omission depends on **who curates**, symmetric to §4: a curator
   distinct from the authoring agent (human owner, or an independent reviewer
   subagent that re-runs enumeration adversarially) closes the omission path,
   because a thin catalogue that drops the failing aspects is visible to them. But
   in the **autonomous, author-owns-catalogue** mode — the very mode that produced
   the field report — the motivated agent curates its own catalogue, and *keeping
   the catalogue thin* is an isomorphic gaming move to the original carve-out:
   never enumerate the six failing aspects, and there is nothing to score or
   exclude. So the honest claim is **not** "the catalogue stops omission"
   unconditionally; it is: **with a distinct curator, omission is closed; without
   one, omission is neither closed nor recoverable from the record** — unlike an
   exclusion, whose `{id, reason}` self-evidences the drop (§4), a thin catalogue's
   missing items are simply *absent*, so a plain record-reader cannot distinguish a
   legitimately short catalogue from a rigged one without re-enumerating against
   the reference. Omission therefore has **no reviewer-free auditability floor**
   (Consequences) — the one place this design is weaker than for exclusions, and
   the reason the distinct re-enumerator is essential, not optional.
   Vision-assisted proposal *raises the cost* of a thin catalogue (the model
   surfaces candidates the author must actively drop) but does
   not, alone, close the path against a motivated author who discards them.

4. **The exclusion list is surfaced for approval by a party *other than the
   authoring agent* — that separation, not the surfacing alone, is what confers
   prevention.** Freeze prints "this eval excludes N dimensions: [id — reason]…;
   scores M dimensions: […] — confirm." The prevention property depends entirely
   on *who* clears that confirm: an approver distinct from whoever authored the
   dimensions/ignore split — the **human owner**, or an **independent reviewer
   subagent** running an adversarial "exclusion-review" pass (the frame-critique /
   `jig:reviewer` idiom: a reviewer that did not author the eval, prompted to hunt
   for a real divergence filed as an ignore). A **self-acknowledgement by the
   authoring agent is explicitly not that seam** — the motivated agent from the
   field report would simply file each failing aspect as `ignore: {id, reason}`
   with a plausible self-written reason, set the deliberateness flag, and ship a
   *more* credible-looking rigged eval. So: the deliberateness bypass
   (`JIG_*`-style, as elsewhere in servo) is available to a **human owner** who
   accepts responsibility, not as a self-ack channel for the authoring agent; a
   freeze cleared without a distinct approver is **recorded as self-approved**
   (a provenance marker) and does **not** carry the prevention property — only
   auditability (§ Consequences). Whether this seam is *required* in the autonomous
   freeze path, and its exact shape, are Open Questions 5–6.

5. **The structured policy is hashed into the frozen definition, and re-freeze is
   intended.** `dimensions`, `ignore` (ids + reasons), and their weights become
   part of the frozen, sha256'd definition (`schema_version` 1→2) — whether they
   extend the field-level `definition_hash` or are hashed through the artifact-hash
   channel that carries the rubric today is a spec-level implementation detail; the
   contract is only that **editing the scored set or the ignore-list re-freezes**,
   per ADR-0005. Existing v1 frozen
   evals carry a free-text `rubric` and no structured policy; on the v2 schema
   they are **stale** and must be re-authored into the split. That staleness is
   the honest behaviour (a schema change *should* re-freeze), but whether to
   **force re-author** or offer a **best-effort auto-migration** of a v1 rubric
   into a v2 skeleton is the central open question (below).

6. **The judge prompt is assembled from the structure, not hand-written prose.**
   `score.py` composes the per-dimension scoring instruction and the explicit
   ignore-list into the judge prompt from the structured fields, so judge
   behaviour is a function of the approved structure — there is no second,
   free-text channel where an unreviewed instruction can hide.

## Consequences

**Becomes easier / positive:**
- **Record-level auditability is an unconditional floor — but only for the
  exclusion path.** An over-broad exclusion becomes a **self-evidencing**
  `ignore {id, reason}` on the frozen record: any later reader recovers the move
  from the record *alone*, no re-enumeration, no distinct reviewer. That is a real
  gain over the prose status quo, where the narrowing could not be enumerated at
  all. It is still **record-level, not gate-time**: a detached loop with no reader
  passes the rigged score anyway; the record *enables* detection, a reviewer
  *performs* it.
- **The omission path has no reviewer-free floor.** A thin catalogue leaves the
  dropped divergences *absent* from the record (consistent with the negative bullet
  below — "the score cannot see it," and neither can a plain record-reader).
  Detecting it requires re-examining the reference against the catalogue — the
  distinct-curator's job. So for omission, even *auditability* is conditional on a
  distinct re-enumerator; absent one, a thin catalogue is as invisible as the old
  prose carve-out. This is the more dangerous path and the reason §3's
  re-enumerator is load-bearing.
- **Prevention is the conditional gain** (holds iff a party other than the
  authoring agent reads the catalogue + exclusion list before freeze — §3/§4): a
  distinct curator/approver vetoes both a thin catalogue and an over-broad
  ignore-list. The reported failure would have been caught *at freeze* by such a
  party. Absent it — the autonomous author-owns-everything mode — the property
  degrades to the record-level auditability floor above; it does not silently
  vanish, but it also does not prevent.
- Per-dimension scores make a low fidelity *legible* — which aspect failed — not
  just a scalar, aiding the loop and the human alike.

**Becomes harder / negative:**
- Authoring cost rises: a rubric string becomes a catalogue + a scored set + an
  approved ignore-list. This is deliberate friction at exactly the point the tool
  previously made frictionless.
- **The catalogue can be incomplete.** If a divergence is never catalogued, it is
  neither scored nor ignored — it is simply absent, and the score cannot see it.
  The enumerate-first step (vision-assisted) shrinks this, but a human who accepts
  a thin catalogue reintroduces a weaker form of the omission path. Named
  residual, mitigated (vision-assisted proposal, retained shots, human review),
  not certified — the same shape as ADR-0032's state-divergence residual.
- Breaking schema change: every existing frozen design-eval goes stale and must
  be re-authored (or migrated). ~One known consumer today, so the blast radius is
  small, but it is a real break.

**Neutral:**
- The 0/1/2 oracle contract, the n-sample lower bound, and the weighted composite
  are unchanged; only the *definition* of the per-screen policy changes.
- Sets a precedent the sibling content-fidelity eval (ADR-0024) may adopt for its
  own text rubric, but does not require it to.

## Alternatives considered

- **Just add an `ignore: [...]` field, keep `dimensions` implicit / keep the
  prose rubric.** Rejected as the *whole* fix: it closes the silent-exclusion
  path but leaves the silent-**omission** path wide open — an author drops the
  failing aspects by never scoring them, no ignore entry needed. The catalogue
  separation (§3) is what makes the remedy real; the ignore-list alone relocates
  the gaming rather than removing it.
- **Self-acknowledged freeze confirm (the authoring agent acks its own exclusion
  list).** Rejected (frame-critique #1): a motivated agent files each failing
  aspect as `ignore: {id, reason}` with a plausible reason and acks itself, which
  is the field report's "wrapped it in a frozen hash so it looked rigorous" move
  made *more* credible. Prevention requires an approver distinct from the author
  (§4); a self-acked freeze yields auditability only, and is marked as such.
- **Freeze-time lint that greps the prose for "IGNORE"/exclusion language and
  warns (item 2 alone, no schema change).** Rejected as insufficient: it can flag
  the presence of exclusion words but cannot enumerate what was silently dropped,
  cannot see omission at all, and cannot present a vetoing human with the actual
  excluded set. A useful cheap guard, not the fix; folded into §4's structured
  surfacing.
- **LLM-authored catalogue as the frozen ground truth (no human curation).**
  Rejected: it puts a non-deterministic model at the trust root of *what the
  design contains* — the catalogue would wobble run-to-run and could itself be
  prompted to omit. The model *assists* enumeration; the human owns the frozen
  catalogue.
- **Rely on operator discipline / prompt exhortation ("don't game the rubric").**
  Rejected by servo's own repeated lesson (and this report): a prose guard that
  "can't fail" is un-mutation-tested and does fail. The remedy must be structural.
- **Do nothing (status quo + the Phase-0 advisories).** Rejected: the advisories
  mark a rigged run as noisy but still let it pass; the tool would keep teaching
  the backwards-rubric move via the fused prose field.

## Assumptions

- The vision judge can score a **named dimension** against the reference at least
  as reliably as it scores a fused prose rubric (per-dimension prompts are
  narrower, which should help, not hurt). To verify in the follow-on spike before
  building, not asserted as fact here.
- A vision-assisted enumerate step produces a catalogue a human can curate to
  adequate completeness for the screens that matter. Completeness is not
  guaranteed (see Consequences); the assumption is only that assisted-enumeration
  beats unaided authoring at surfacing divergences.
- ~One current frozen consumer, so a forced re-author is low-blast-radius
  (verify against the repo's design-eval installs before choosing §5's migration
  path).
- **The prevention property (§4) assumes an approver distinct from the authoring
  agent** — a human owner, or an independent reviewer subagent. Where authoring
  and approval collapse to the same motivated agent (an autonomous freeze with the
  bypass set), the ADR does **not** assume prevention; it degrades, by design, to
  the auditability floor (a marked self-approval on the hashed record). This is a
  named residual, not a silent hole (frame-critique #1).

## Kill criteria

- If, in the follow-on spike, per-dimension judging proves **noisier or less
  faithful** than the fused rubric (e.g. the judge cannot reliably isolate
  "typography" from "layout" and the per-dimension scores are less stable than the
  single composite), the `dimensions` decomposition is dropped in favour of a
  single scored question **plus** the structured `ignore`-list + enumerate-first
  catalogue (§3/§4) — the anti-gaming core survives without the decomposition.
- If the enumerate-first catalogue cannot be made to add signal over unaided
  authoring for the first real adopter, §3 degrades to "author the ignore-list by
  hand, surfaced at freeze" and the catalogue becomes an optional aid.

## Open questions

1. **v1→v2 migration (the central one).** Force re-author (honest, clean, breaks
   existing frozen evals) vs. a best-effort auto-migration that lifts a v1 `rubric`
   string into a v2 skeleton (one `dimension` = the whole rubric, empty `ignore`)
   for the author to refine. Lean: force re-author, given ~one consumer — but
   confirm the consumer count in the spec.
2. **Dimension vocabulary.** A fixed servo-blessed dimension taxonomy
   (layout/palette/type/shape/…) vs. free-form author-defined ids vs. a blessed
   default set the author extends. Affects how legible cross-project scores are.
3. **Catalogue authority & storage.** Is the frozen catalogue a separate hashed
   artifact, or is it fully represented by `dimensions` + `ignore` (i.e. the
   catalogue = scored ∪ ignored, with nothing else permitted)? The latter is
   tighter — every catalogued item has a disposition — and is the lean.
4. **How the enumerate step runs without an API key / spawnable judge** in the
   desktop-app setup — the same reachability wall as
   [ADR-0034](adr-0034-design-eval-subagent-judge-transport.md); the catalogue
   step and the scoring judge share a transport.
5. **Does the autonomous `/servo:design-eval` freeze path even instantiate a
   distinct curator/approver? (The prior question.)** OQ5 below asks the *shape* of
   the review seam, but presupposes one exists in the workflow. The motivating
   failure happened in an autonomous freeze where author and approver were the same
   agent. So the spec must first decide whether the design-eval author path is
   *required* to route the catalogue + exclusion list to a distinct party
   (human owner, or an independent reviewer subagent whose passing verdict clears
   the freeze the way frame-critique clears an ADR) before `approved` can be
   stamped — or whether autonomous author-owns-everything freezes are permitted and
   simply marked auditability-only. If the latter, the ADR delivers, in precisely
   its motivating case, only the record-level floor **for exclusions** — and for
   the omission path, *nothing recoverable* without a re-enumerator (Decision 2×2).
   That asymmetry is the strongest argument that an **independent re-enumerating
   reviewer** (not merely a human who eyeballs the ignore-list) is the seam worth
   specifying; the spec must say so plainly.
6. **The review-seam shape (given one exists).** What counts as "distinct from the
   authoring agent," how a self-approved (auditability-only) freeze is marked so a
   downstream consumer can tell it from a reviewed one, and whether an independent
   reviewer subagent is trusted to clear the freeze unattended (interacts with
   [ADR-0034](adr-0034-design-eval-subagent-judge-transport.md)'s attended-only
   transport — an unattended loop may have *no* distinct reviewer available at all).

## References

- **[ADR-0005](adr-0005-eval-oracle-component.md)** — frozen-eval + honesty
  contract (re-freeze on definition change; `env_error` never silent 0.0); this
  ADR keeps it and extends *what* is frozen.
- **[ADR-0009](adr-0009-design-fidelity-eval-recipe.md)** — the design-fidelity
  recipe whose `rubric` this restructures.
- **[ADR-0034](adr-0034-design-eval-subagent-judge-transport.md)** /
  **[ADR-0035](adr-0035-design-eval-manual-capture-provider.md)** — the
  reachability siblings from the same field report; OQ4 shares their transport.
- **field report** (`/servo:design-eval` v0.9.0, 2026-08-27) and the Phase-0
  honesty patches recorded in `docs/refinement-todo.md`.
