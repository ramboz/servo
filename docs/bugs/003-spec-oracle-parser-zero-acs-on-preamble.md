---
status: DONE
tier: standard
severity: medium
claimed_by: main
regression_test: skills/spec-oracle/test_oracle_plan.py::ACPreambleToleranceTests
main_repro_checked_at: 2026-07-02
main_repro_ref: origin/main@45d8dc0
main_repro_result: reproduces
red_confirmed_at: 2026-07-02
green_confirmed_at: 2026-07-02
fix_class: local_patch
security_surface: false
escalated_to:
---

# Bug 003: spec-oracle-parser-zero-acs-on-preamble

> Reported from an external dogfood run (cwv-workbench spec 015, 2026-07-01).

## Symptom

`oracle_plan.py`'s acceptance-criteria parser returns **0 ACs** (0 deterministic
+ 0 residual) when a non-list line (e.g. an italic note or parenthetical) appears
**between** the `**Acceptance Criteria:**` header and the first numbered item.
It is **silent** — no warning that the section was found but yielded nothing —
which then makes `edd-suitability` block with `needs_evidence` for the wrong
reason (the spec looks AC-less when it is not).

## Repro

Put a note line immediately after `**Acceptance Criteria:**` and before `1.` in a
slice spec, then run `oracle_plan.py <target> <slice>`; observe
`planned … (0 deterministic, 0 residual)`. Move the note out (numbered list
immediately follows the header) → parsing is restored.

## Evidence

cwv-workbench spec 015-03 during the dogfood: a one-line rationale note between
the header and the list produced `(0 deterministic, 0 residual)` and a
`needs_evidence` suitability verdict. Removing the note restored `1 deterministic
/ 3 residual` and a `suitable` verdict.

## Hypotheses

- [x] **(leading)** The parser terminates the AC section on the first
  heading/bold-pseudo-heading line (`_HEADING_RE` / `_BOLD_LABEL_RE`), so a
  **bold-label** interstitial (e.g. `**Note:** …`) between the header and the
  first numbered item closes the section at zero items. *Confirm:* run
  `extract_acs` on bold- vs italic-note variants. *Falsify:* plain prose also
  zeroes it.
- [ ] The trigger is *any* interstitial non-list line (prose, italic,
  parenthetical). *Confirm:* those variants also yield 0. *Falsify:* they parse
  fine (only bold labels / headings terminate).

## Root cause

**Confirmed by direct repro** (`extract_acs`, `skills/spec-oracle/oracle_plan.py`).
The second hypothesis is **falsified**: plain prose, italic notes,
parentheticals, and blank lines between the `**Acceptance Criteria:**` header
and the numbered list all parse fine (2/2 ACs). The reproducing case is a
**bold pseudo-heading label** (`**Note:** …`), because `_BOLD_LABEL_RE`
unconditionally closes the AC section — the same mechanism that (correctly)
stops a sibling `**Definition of Done:**` list from being swept in. Applied
*before* the first AC item, that terminator zeroes the section, and the zero is
**silent**, so `edd-suitability` then blocks with `needs_evidence` for the
wrong reason. Fix must (a) not let a bold label terminate the section before any
item is collected, while still bounding a real DoD/sibling list that follows the
ACs, and (b) warn instead of silently returning 0.

## Fix class

`local_patch` — the AC-section scanner in `extract_acs` (`oracle_plan.py`).

## Fix

Two changes in `skills/spec-oracle/oracle_plan.py`:

1. **`extract_acs` tolerance.** Track `items_in_section` (reset on each opener,
   incremented per numbered item). A `**bold label**` line now closes the AC
   section only once ≥1 item has been collected; a bold label *before* the first
   item is skipped as interstitial prose. A real `#` heading still always
   closes. This fixes the `**Note:**`-before-`1.` case while keeping a sibling
   `**Definition of Done:**` list (which follows the ACs) correctly bounded out.
2. **Non-silent empty section.** New `_warn_if_empty_ac_section` writes a
   stderr warning when an AC opener is present but 0 ACs parse, called from both
   `plan_target` and `classify_only` (stderr only — never pollutes classify's
   stdout JSON).

Known narrow tradeoff: a *genuinely empty* AC section immediately followed by
another bold-label section (before any AC item) could now sweep that section's
list. This is a malformed spec (zero criteria) and rare; the warning is the
backstop for the truly-empty case (opener → heading/EOF). The deeper unification
of the suitability + spec-oracle AC grammar is spec 019-03 (ADR-0022 family).

## Already tried

n/a (reported).

## Regression test

`skills/spec-oracle/test_oracle_plan.py::ACPreambleToleranceTests` — three tests:
`test_bold_label_note_before_first_item_still_yields_acs` (the bug: `**Note:**`
before `1.` → 2 ACs, not 0), `test_dod_after_acs_is_still_bounded` (a trailing
`**Definition of Done:**` list is NOT swept into the ACs), and
`test_empty_ac_section_warns_not_silent` (present-but-empty section emits the
stderr warning).

## Proof

Red→green witnessed by the teeth gate (`red_confirmed_at` / `green_confirmed_at`);
RED proven against a `git checkout`-restored pre-fix `oracle_plan.py`
(2 failures), GREEN after restoring the fix. Full spec-oracle suite green
(201 passed); ruff clean.

## Learning

The AC-section grammar is an interface between the spec author (jig) and servo's
parser; small authoring variations (a rationale note) should not silently zero
the oracle. Consider a documented, shared AC grammar.

## Main recheck

- 2026-07-02 - `origin/main@45d8dc0` -> reproduces: HEAD==origin/main==45d8dc0; extract_acs (oracle_plan.py) closes the AC section on a bold-label line via _BOLD_LABEL_RE; a **Note:** interstitial before item 1 yields 0 ACs. New ACPreambleToleranceTests reproduces (RED).
