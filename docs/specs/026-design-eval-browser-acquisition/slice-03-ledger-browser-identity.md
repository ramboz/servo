---
status: DRAFT
dependencies: [026-02, adr-0031]
last_verified:
frame_review: true
---

## Slice 026-03 — ledger-browser-identity

**Goal:** Record what actually rendered each score — as an **attestation from the
capture process**, not a guess by the process that writes the ledger.

**DoR:**
- ✅ 026-02 resolves a transport Python-side and passes it to `capture.mjs`.
- ✅ **Boundary settled:** observability, not a gate. Never hashed, never a
  staleness trigger. Advisory warning permitted; refusal needs a superseding ADR.
- ✅ **Consumer is a human** investigating a score shift. No programmatic reader
  of `ledger.jsonl` exists and this slice adds none (ADR-0017, Proposed, is where
  one would be decided).
- ⚠️ **The writer is not the launcher — this is the frame-critique's primary
  finding and it sets the whole design.** `_ledger` runs in `score.py`;
  the browser is launched by `capture.mjs`, a subprocess whose **stdout
  `score.py` already captures but discards**. Any version string obtained
  independently (a `--version` shell-out, or 026-01's preflight) attests what
  *would probably* launch — and diverges from reality exactly in the cases an
  investigator opened the ledger for. So this slice adds a **reporting channel**
  rather than an out-of-band probe.
- ✅ **The channel is free:** `capture.mjs` writes only to stderr today, so
  stdout is unused and already captured by `capture_app`.

**Acceptance criteria:**
1. `capture.mjs` emits **one JSON line on stdout**, on the `--screen` path only,
   reporting **both** the engine it actually launched (name + version) **and the
   transport it actually resolved**. `capture_app` parses it; a malformed/absent
   line is tolerated (AC4). Scoping to `--screen` matters because
   `design_eval.capture_refs` runs `capture.mjs --refs` **without**
   `capture_output`, so an unconditional line would print raw JSON into the
   author's terminal.
   *Collision checked and clear:* `oracle.sh` parses **`score.py`'s** stdout, and
   `capture_app` runs the child with `capture_output=True`, so the child's stdout
   is absorbed by the parent and can never reach the oracle's stream.
2. **No mixed-provenance rows.** Every provenance field in a row comes from the
   attestation or is explicitly unattested — the transport is *not* re-derived
   writer-side. This makes the slice immune to how 026-02 ends up resolving
   transport internally: whatever `capture.mjs` actually used is what gets
   recorded.
2a. **The field is newly named, not overloaded.** The ledger row already has a
   top-level `transport` key meaning the **judge** transport (`"api"`/`"cli"`,
   documented in `SKILL.md`). The capture transport goes in a **distinct** key
   (`capture_transport`, or a nested `capture` object) so a human doing exactly
   the archaeology this slice enables can still see a judge-transport change —
   a likelier score-shift cause than a browser bump.
3. Not in `definition_hash`, not in `artifact_hashes`; changing browsers never
   raises `StaleError`. Test asserts hash-invariance.
4. **Best-effort throughout** — a missing/unparseable report, or an `OSError` on
   ledger write, must never fail a score. Provenance is never load-bearing.
5. When identity cannot be attested the row records a **reason token**, not a
   bare `"unknown"` — because one string would merge materially different facts.
   In particular `not_captured` (no browser ran at all: `score()` skips
   `capture_app` under `SERVO_DESIGN_EVAL_FAKE_SCORES` yet still writes a ledger
   row, and the ledger has no other synthetic-run marker, so this field is the
   only place that fact could surface) must be distinguishable from
   `not_attested` (capture happened; identity unavailable — A5 false, a malformed
   line, or an adopter running a pre-channel `capture.mjs` copy). Never a
   silently-omitted field, and never an independently-probed guess presented as
   an attestation.
6. `SKILL.md` documents the fields, names the consumer (a human), and states that
   the value is an attestation from the capture process.
7. Tests: attested identity **and transport** on both transports; a fake-scores
   run records `not_captured` (not a plausible-looking engine); a malformed line
   records `not_attested` and still scores; hash-invariance; and the new key does
   not collide with the existing judge `transport` field in historical rows.

**DoD:**
- [ ] `capture.mjs` stdout report implemented; `capture_app` parses it.
- [ ] Ledger rows carry attested capture-transport + engine under a distinct key
      (or a reason token), with no writer-side re-derivation.
- [ ] Fake-scores row asserts `not_captured` — a synthetic score is never
      byte-indistinguishable from a real capture.
- [ ] Hash-invariance test green.
- [ ] Best-effort test: garbage on stdout still scores successfully.
- [ ] `SKILL.md` ledger table updated.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Dropped from this slice (was AC5 — recording the reference-render engine).**
At score time the reference is a frozen PNG and nothing on disk carries its
engine; the information exists only transiently during `capture-refs`, and not at
all for a hand-supplied reference (freeze checks only that the file exists, and a
Figma-exported PNG has no `referenceSource`). "Where available" would therefore
be vacuous — permanently blank for every eval frozen before this slice, i.e.
exactly the long-lived ones whose score shifts get investigated. Recording it
properly needs an authoring-side write path this slice does not scope. The
spec's non-goal on structural engine mixing stands alone instead.

**Vertical?** Yes — an operator investigating "why did fidelity drop?" gets
trustworthy evidence about the engine.
