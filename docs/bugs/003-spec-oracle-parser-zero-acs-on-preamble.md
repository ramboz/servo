---
status: REPORTED
tier:
severity:
claimed_by: main
regression_test:
main_repro_checked_at:
main_repro_ref:
main_repro_result:
red_confirmed_at:
green_confirmed_at:
fix_class:
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

1. **(leading)** The parser anchors the AC list to the lines *immediately*
   following the header and treats the first non-list line as the section end,
   so an interstitial prose/note line terminates the section at zero items.
2. It should skip blank/prose lines between the header and the numbered list,
   collecting the list wherever it begins under the header (bounded by the next
   `##` or `**Field:**`), and warn — not silently return 0 — when the header is
   present but no items parse.

## Root cause

_Not yet diagnosed (REPORTED). See hypotheses._

## Fix class

_TBD (likely `local_patch` in the AC-section scanner)._

## Fix

**Direction (not yet implemented):** make the AC-section scan tolerant of
interstitial prose/blank lines between the `**Acceptance Criteria:**` header and
the numbered list; and emit a warning (not a silent `0`) when the header is found
but no numbered items are parsed. Relates to the shared "AC grammar" work in the
compile-core simplification spec (unify the suitability + spec-oracle AC parse).

## Already tried

n/a (reported).

## Regression test

_TBD — a slice fixture with a note line between the AC header and `1.` must still
yield its N ACs (not 0)._

## Proof

_TBD._

## Learning

The AC-section grammar is an interface between the spec author (jig) and servo's
parser; small authoring variations (a rationale note) should not silently zero
the oracle. Consider a documented, shared AC grammar.
