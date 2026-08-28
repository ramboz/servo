---
status: DRAFT
dependencies: [adr-0035]
last_verified:
frame_review: true
---

## Slice 029-01 — manual-capture

**Goal:** Add a `manual` capture provider that consumes a human-supplied PNG for
non-automatable targets — with `manual_capture` provenance, the supplied PNG's
sha256 + mtime in the ledger, and a loud stderr advisory on every run — reusing
the ADR-0032 provider seam and failing closed when no shot is staged.

**DoR:**
- ✅ [ADR-0035](../../decisions/adr-0035-design-eval-manual-capture-provider.md)
  Accepted.
- ✅ Staged-path convention chosen (ADR-0035 OQ1): `manual/<screen-id>.png` under
  the eval dir vs `capture.manual.path` template — decided before AC1.

**Acceptance Criteria:**

1. **`capture.transport: manual` (or `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT=manual`)
   consumes a staged PNG and scores it.** A new `_capture_manual` provider is
   registered in `_CAPTURE_PROVIDERS`, validates the staged file exists and is a
   readable PNG, and returns it as the screen's shot via the existing seam
   (`(png, None)`, like the native providers). A test scores a screen from a staged
   PNG with no subprocess/browser.
2. **Absent / unreadable input fails closed to `env_error` (rc 2).** No staged PNG
   → `env_error` naming the expected path; never a silent 0.0, never a fall-through
   to another provider. Tested.
3. **Provenance is a distinct `manual_capture` token with the input hash + mtime.**
   `_provenance` gains `manual_capture` (distinct from `not_captured` /
   `not_attested` / `attested`); the ledger row records `capture_provider: manual`,
   per-screen `provenance: manual_capture`, the supplied PNG's sha256 and mtime, and
   the retained shot. Tested against the ledger output.
4. **A loud stderr advisory fires on every manual run.** `score.py` prints a
   prominent stderr line — "MANUAL CAPTURE — the shot for screen <id> was
   human-supplied (sha256 …), not captured by servo…" — on every `manual` run,
   symmetric to the Phase-0 fake-scores marking, on stdout-preserving stderr. A
   test asserts the advisory fires and stdout stays a single parseable float.
5. **`manual` is never reached by accident and is distinct from fake-scores.** It
   must be explicitly selected; `SERVO_DESIGN_EVAL_FAKE_SCORES` remains a separate
   test/offline hook. A test asserts the default transport is still `web` and that
   a `manual` run is not byte-identical to a fake-scores run (different provenance +
   advisory).

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Tests mutation-checked (esp. the fail-closed and the advisory — a guard that
      cannot fail is untested); host packages rebuilt + drift clean.
- [ ] Implementation + craft review passed.
- [ ] Deviation log + reconciliation sweep produced.

**Assumptions:**
- The ADR-0032 seam accommodates a no-subprocess staged-file provider — verified by
  reading `score.py:493-534` (dispatch signature) and `_provenance` (`score.py:784`);
  `manual` returns `(png, None)` and adds one provenance token. Grounded, not
  assumed, but re-confirm on implementation.
- Non-automatable targets are a real recurring class (the field report's GW2/ImGui
  overlay; ADR-0032's Windows-only-plugin-on-Mac). Grounded by the report.

**Anti-horizontal-phasing check:** After this slice, a developer can score a
non-screenshottable target (an in-game overlay) against its reference with the real
pinned judge, from a human-staged PNG that is retained, hashed, and loudly marked —
replacing the fake-scores degradation end to end.

### Deviation log (after reconciliation)

_TODO at reconciliation._

### Reconciliation sweep

_TODO at reconciliation._
