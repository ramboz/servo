---
status: DRAFT
dependencies: [adr-0031]
last_verified:
frame_review: true
---

## Slice 026-03 — ledger-browser-identity

**Goal:** Record what actually rendered each score — as an **attestation from the
capture process**, not a guess by the process that writes the ledger.

**DoR:**
- ⚠️ **026-02 is now DEFERRED** (blocked on the A1 probe), so this is the
  **actual** path, not a contingency: there is no
  `--transport` argv, no `capture` block, and one transport — `capture.mjs`
  attests the engine plus a constant `"bundled"`, which still satisfies AC2, and
  AC7's matrix collapses to a single transport. The engine attestation — the
  slice's real value — is unaffected, since it comes from the launched browser
  rather than from any transport machinery.
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
- ⚠️ **stdout is NOT free — corrected from an earlier ✅ that was false.**
  `capture.mjs` writes only to stderr *itself*, but on the `--screen` path it
  `import`s and runs the **adopter's** per-screen `setup` module **in-process**,
  and that module (or anything it imports) may `console.log` onto the same
  stdout. `setup` is a first-class authoring surface. So the channel must be
  **marker-delimited**, not "the JSON on stdout" — see AC1a. Note `score.py`
  already ships `_extract_json` (first `{` to last `}`), the helper an
  implementer would naturally reach for and the one that mis-parses hardest
  here: over mixed stdout it spans the adopter's logged object and the
  attestation, or returns the adopter's data *as* the attestation.

**Acceptance criteria:**
1. `capture.mjs` emits **one JSON line on stdout**, on the `--screen` path only,
   reporting the engine it actually launched (name + version) and the transport
   it was **instructed** to use (echoed — see AC2, it cannot diverge). `capture_app` parses it; a malformed/absent
   line is tolerated (AC4). Scoping to `--screen` matters because
   `design_eval.capture_refs` runs `capture.mjs --refs` **without**
   `capture_output`, so an unconditional line would print raw JSON into the
   author's terminal.
   *Oracle collision checked and clear:* `oracle.sh` parses **`score.py`'s**
   stdout, and `capture_app` runs the child with `capture_output=True`, so the
   child's stdout is absorbed by the parent and can never reach the oracle stream.
1b. **The attestation can never fail a score — guarded, not merely intended.**
   `capture.mjs` has exactly **one** `try`, whose `catch` sets
   `process.exitCode = 2`; `capture_app` maps any non-zero rc to `EnvError`, and
   `score()` then never reaches `_ledger`. So an engine accessor that *throws*
   (`browser.version()` unavailable on a `playwright-core`/channel build — A5 is
   still unprobed — or the browser dying between launch and query) would, under a
   naive implementation, turn a **successful screenshot** into no score and no
   row: provenance becoming load-bearing, in direct contradiction of AC4 and
   strictly worse than the pre-slice status quo, on the BYO path this spec
   exists to enable. Therefore the attestation block — accessor call,
   serialization, write — is wrapped in its **own** try/catch that on any error
   emits the marker line with `engine: null` **plus a short `error` string**, and
   **never assigns `process.exitCode`**. That `error` string is also what
   separates "A5 false, nothing to do" from "accessor threw, possibly transient".
1a. **The line is marker-delimited, scanned by marker, with a pinned position.**
   It carries a namespaced single-line sentinel (e.g. `##servo-capture:{…}`);
   the parser scans for **that marker's line** and explicitly **not**
   `_extract_json`. Any non-matching stdout (the adopter's own logging) is
   **discarded, not treated as failure**, so a rich `setup` script can never
   silently decay the field to `not_attested` and misattribute an adopter's
   `console.log` to a Playwright/A5 problem.
   **A marker cannot be made collision-proof** — `SKILL.md` documents its shape,
   and the setup author debugging "why is my provenance unattested" is exactly
   the person who might echo it. The defence is **determinism, not uniqueness**:
   servo emits the line **immediately after launch and before the `setup`
   import**, and the parser takes the **first** marker-matched line. A colliding
   line can then only ever appear later, and can only mis-record provenance —
   never fail a score (AC4 + AC1b) — so this is a correctness-of-evidence
   concern, bounded, not a reliability one.
   *Not contradicted by 026-02:* that slice rejected a "private marker protocol"
   on **drift** grounds, but that reasoning does not reach here. Its marker would
   have been between `design_eval.py` (plugin-side, auto-updating) and a
   `capture.mjs` frozen in the target; this one is between `score.py` and
   `capture.mjs`, which `init()` copies together in the same unconditional loop
   and which therefore cannot drift apart.
2. **Provenance is recorded PER SCREEN, because there are N attestations per
   row.** `score()` calls `capture_app` once per screen, each spawning its own
   `capture.mjs` with its own launch and its own emitted line — and the shipped
   `config.example.json` has two screens, so N>1 is the default shape, not an
   edge case. A single row-level engine field would silently report one of them.
   The row's `screens` array already carries per-screen `{id, samples,
   lower_bound}`, so the attested engine and `capture_transport` hang **there**,
   making disagreement visible by construction. A row-level convenience field may
   be included **only** if defined as "present when all screens agree, otherwise
   `mixed`". This matters because it is the ledger's **schema** — an append-only
   file a human reads, with no version field, so a later shape change leaves two
   shapes interleaved.
   *Why disagreement is real, not theoretical:* on the BYO path a system Chrome
   can update in place mid-run, and runs are long (up to 180s per capture plus n
   judge samples per screen), so a later screen genuinely can launch a different
   binary. Engine-changed-mid-run is the single most investigable event this
   field exists to surface.
2b. **Every provenance field comes from the attestation line or is explicitly
   unattested** — nothing re-derived writer-side; per-screen partial attestation
   (screen A attests, screen B hits AC1b's null-engine guard) is therefore
   recorded honestly per screen rather than collapsed. **Honest framing of the transport field:** given 026-02's single
   resolver + `--transport` argv, the value `capture.mjs` echoes is by
   construction the argv it was handed — so it is *the transport the launcher was
   instructed to use, echoed back as a mismatch canary*, **not** independent
   evidence of what launched. The engine name+version is the real attestation.
   `SKILL.md` (AC6) must say exactly that rather than implying both fields carry
   equal evidential weight.
2a. **The field is newly named, not overloaded.** The ledger row already has a
   top-level `transport` key meaning the **judge** transport (`"api"`/`"cli"`,
   documented in `SKILL.md`). The capture transport goes in a distinct **flat**
   key `capture_transport` — flat deliberately, to avoid a second `capture`
   namespace: 026-02 writes `capture.*` in **`config.json`**, and an identically
   named object in the **ledger row** with different semantics would confuse the
   very human doing this archaeology. So a human can still spot a judge-transport
   change, a likelier score-shift cause than a browser bump.
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
   `not_attested` (capture happened; identity unavailable). **"Always emits" is
   honestly scoped to "always, once a browser exists":** `chromium.launch()` is
   top-level and outside the `try`, so a launch failure — the no-browser case
   026-01 preflights — emits nothing, exits non-zero, and writes no row at all.
   The observable states are therefore exactly: no row / no line / null engine /
   attested. A third distinction
   is available **for free** and worth taking, because the remedies differ:
   `capture.mjs` **always** emits the line, with an explicit null engine when the
   accessor fails — so "line present + null engine" (A5 false / accessor threw)
   separates cleanly from "no line at all". **Honest cause for the no-line
   state:** *not* "a pre-channel `capture.mjs` copy", which the supported path
   cannot produce — `init()` copies `score.py`, `capture.mjs`, `capture_lib.mjs`
   and `fidelity_eval.py` in one unconditional overwrite loop and `install()`
   calls `init()`, so a marker-scanning `score.py` was written by the same loop
   that wrote the marker-emitting `capture.mjs`; they cannot skew. The reachable
   causes are a **hand-modified target, a partially-failed `init()`, or a write
   that never reached the parent**. The remedy (re-run `install`) is unchanged and
   correct; only the stated cause is fixed, because telling a human the wrong
   cause is the one thing this token exists to prevent. Never a silently-omitted
   field, and never an independently-probed guess presented as an attestation.
6. `SKILL.md` documents the fields, names the consumer (a human), and states that
   the value is an attestation from the capture process.
7. Tests: attested identity **and transport** on both transports; a **setup
   module that prints plain text *and* a JSON object to stdout still yields an
   attested identity** (the AC1a contamination guard — this is the test that
   would have caught the false "stdout is free" premise); a fake-scores run
   records `not_captured`; a malformed line records `not_attested` and still
   scores; hash-invariance; and no collision with the judge `transport` field in
   historical rows.

**DoD:**
- [ ] `capture.mjs` stdout report implemented (marker-delimited, emitted after
      launch and before the `setup` import); `capture_app` parses the **first**
      marker line, never `_extract_json`.
- [ ] **Accessor-throw test:** a stubbed accessor that *throws* still scores and
      still writes a row with `engine: null` + an `error` string (AC1b). This is
      distinct from the malformed-line test, which exercises only the Python parser.
- [ ] **Contamination test:** a `setup` module printing plain text *and* a JSON
      object to stdout still yields an attested identity (AC1a).
- [ ] Test: no-line and null-engine are recorded as **distinct** states, not merged.
- [ ] **Two-screen test where the second attestation differs** — per-screen
      provenance records both, and any row-level field reads `mixed` (AC2).
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
