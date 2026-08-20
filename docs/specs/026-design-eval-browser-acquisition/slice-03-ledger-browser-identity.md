---
status: REVIEWED
dependencies: [adr-0031]
last_verified:
frame_review: true
claimed_by: claude/jig-orient-6324de
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
   reporting the engine it actually launched (name + version) and the transport.
   **With 026-02 DEFERRED, the transport value is the literal `"bundled"`** — not
   a guess but a verified fact: `capture.mjs`'s `chromium.launch()` takes no
   channel, so bundled is the only engine source that exists today. It is
   therefore *not* `null` (which AC5 reserves for unattested states) and *not*
   re-derived from config (which AC2b forbids). If 026-02 later lands, this
   becomes the `--transport` argv echoed back as a mismatch canary — a note about
   the future, not the operative instruction. `capture_app` parses it; a malformed/absent
   line is tolerated (AC4). Scoping to `--screen` matters because
   `design_eval.capture_refs` runs `capture.mjs --refs` **without**
   `capture_output`, so an unconditional line would print raw JSON into the
   author's terminal.
   *Oracle collision checked and clear:* `oracle.sh` parses **`score.py`'s**
   stdout, and `capture_app` runs the child with `capture_output=True`, so the
   child's stdout is absorbed by the parent and can never reach the oracle stream.
1c. **The JS logic lives in `capture_lib.mjs`, because `capture.mjs` is
   structurally untestable.** `capture.mjs` imports Playwright at module load, so
   it "cannot be unit tested directly" — the repo already says so and already
   solved it: pure logic is extracted to `capture_lib.mjs` and covered by node's
   runner, with a delegation guard preventing re-inlining. Without this, the
   DoD's accessor-throw item has no honest implementation: with no Playwright
   resolvable here, the path of least resistance is to monkeypatch
   `subprocess.run` and hand `score.py` crafted stdout that *already contains*
   `engine: null` + `error` — which passes without a single line of the JS guard
   existing, and merely re-tests the Python parser the malformed-line item
   already covers. AC1b would then ship with **zero coverage while its checkbox
   is ticked** — the exact failure this whole review chain has been eliminating.
   So: `attestationLine({engine, transport, error})` and
   `safeAttest(getVersion)` are **pure functions in `capture_lib.mjs`**; the node
   suite covers the throwing-thunk case directly; and a delegation guard mirrors
   the existing `test_capture_mjs_imports_the_extracted_lib`.
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
2c. **The attestation is RETURNED alongside the PNG path, never stashed.**
   `capture_app` returns a `Path` today and has three dedicated failure-branch
   tests, so the low-friction move is a module-level `_LAST_ATTESTATION` that
   `_ledger` reads — which is last-write-wins and silently re-creates the exact
   single-field collapse AC2 exists to fix. Change the return, don't stash.
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
7. Tests — and each item states whether it is **CI-runnable (pytest)** or
   **node-skipped**, because a green CI does not mean the JS suite ran and a DONE
   gate satisfied by a skipped test is precisely the failure mode under review.
   Attested identity with the transport axis reduced to asserting the constant
   `"bundled"` (026-02 deferred); a **setup
   module that prints plain text *and* a JSON object to stdout still yields an
   attested identity** (the AC1a contamination guard — this is the test that
   would have caught the false "stdout is free" premise); a fake-scores run
   records `not_captured`; a malformed line records `not_attested` and still
   scores; hash-invariance; and no collision with the judge `transport` field in
   historical rows.

**DoD:**
- [x] *(CI-runnable)* `capture.mjs` stdout report implemented (marker-delimited, emitted after
      launch and before the `setup` import); `capture_app` parses the **first**
      marker line, never `_extract_json`.
- [x] *(node-skipped)* **Accessor-throw test — in the NODE suite (node-skipped in CI), against
      `capture_lib.mjs`'s `safeAttest`:** a throwing thunk returns a null-engine
      payload with an `error` string and never touches `process.exitCode`. A
      Python-side fake does **not** satisfy this item; it would re-test the parser.
- [x] *(CI-runnable)* Delegation guard: `capture.mjs` calls `capture_lib.mjs`'s attestation
      helpers rather than re-inlining them (mirrors the existing
      `test_capture_mjs_imports_the_extracted_lib`).
- [x] DoD **and AC7** items are each labelled CI-runnable or node-skipped.
- [x] **Contamination test:** a `setup` module printing plain text *and* a JSON
      object to stdout still yields an attested identity (AC1a).
- [x] *(CI-runnable)* Test: no-line and null-engine are recorded as **distinct** states, not merged.
- [x] *(CI-runnable)* **Two-screen test where the second attestation differs** — per-screen
      provenance records both, and any row-level field reads `mixed` (AC2).
- [x] *(CI-runnable)* Ledger rows carry attested capture-transport + engine under a distinct key
      (or a reason token), with no writer-side re-derivation.
- [x] *(CI-runnable)* Fake-scores row asserts `not_captured` — a synthetic score is never
      byte-indistinguishable from a real capture.
- [x] *(CI-runnable)* Hash-invariance test green.
- [x] *(CI-runnable)* Best-effort test: garbage on stdout still scores successfully.
- [x] *(CI-runnable)* `SKILL.md` ledger table updated.
- [x] *(n/a)* Compliance + craft review verdicts recorded under `reviews/`.
- [x] *(n/a)* Reconciliation verdict + deviation log + reconciliation sweep recorded.

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

### Deviation log

- **Two shipped bugs, found by review, not by my tests.** Both reviewers found
  both independently:
  1. `_provenance(att, fake_run=att is None)` passed a value **derived from the
     same predicate the function branches on**, making `not_attested`
     unreachable on the live path — a real capture whose marker line was missing
     or malformed was recorded as `not_captured` ("no browser ran at all"), the
     exact merge AC5 exists to prevent.
  2. A non-object JSON payload after the marker (`##servo-capture:123`) reached
     `att.get(...)` and raised `AttributeError`, which is **not** in `main()`'s
     catch tuple — a successful capture-and-judge run died on a provenance
     detail, contradicting AC4. AC1a explicitly anticipates an adopter echoing
     the marker, so this was reachable, not theoretical.
  Both fixed and **mutation-verified**: reintroducing either fails its test.
- **Root cause, worth recording:** every ledger test I wrote ran only the
  *fake-scores* arm, so the live path — where both bugs lived — had zero
  coverage. This is the same shape as 026-01's dead-elision defect: a test that
  looks like a guard but never enters the branch it guards. Four live-arm tests
  added.
- **`parseAttestation` deleted from `capture_lib.mjs`** — it had **no production
  consumer** (`capture.mjs` imports only `attestationLine`/`safeAttest`), making
  it a test-only shadow of the authoritative Python parser that would silently
  diverge. Replaced with a cross-language `ATTEST_MARKER` parity test: the marker
  is the *entire* contract between the two languages and had nothing holding the
  copies together.
- **Three vacuous assertions removed**, one unfailable by construction (its
  needle contained spaces its haystack had stripped) — it was the only guard for
  AC1b's "the emission must not sit in a catch that sets exitCode 2", and it
  guarded nothing.
- **AC1b narrowed in practice:** `safeAttest` cannot throw, so `capture.mjs`'s
  wrapper catch only ever sees a `console.log`/`JSON.stringify` failure. It now
  reports on stderr rather than emitting a null-engine line, which is a small
  deviation from AC1b's literal text ("on any error emits the marker line") and
  is recorded rather than silently taken.
- **`per_screen` stays a 4-tuple** (deferred, agreed with the craft reviewer):
  the threading is correct and covered, so the remaining cost is readability
  only, and restructuring the composite arithmetic under review against a landed
  026-01 is the worse trade. **Trigger:** if a fifth element is ever added, land
  the `NamedTuple` then.
- **`capture_app`'s Python signature changed** from `Path` to
  `tuple[Path, dict | None]`. ADR-0031 says "`capture_app`'s contract is
  unchanged" — that refers to its *failure semantics* (subprocess, fail-closed to
  `env_error` rc 2, never a silent `0.0`), which are preserved. Noting it so the
  two records do not read as contradictory.
- **026-02 deferred**, so `transport` is the literal `"bundled"` — verified, not
  assumed: `capture.mjs`'s `chromium.launch()` takes no channel.

### Reconciliation sweep

| Artifact | Disposition |
|---|---|
| `skills/design-eval/capture_lib.mjs` | **updated** — `ATTEST_MARKER`, `attestationLine`, `safeAttest` added as pure functions (testable, unlike `capture.mjs`); orphaned `parseAttestation` removed. |
| `skills/design-eval/capture.mjs` | **updated** — emission after launch, before the `setup` import; failure reported on stderr. |
| `skills/design-eval/score.py` | **updated** — `parse_attestation` (marker-first, dict-guarded), `capture_app` returns the attestation, `_provenance`, per-screen ledger rows. |
| `skills/design-eval/test_capture_lib.mjs` | **updated** — node suite covers `safeAttest` against a throwing thunk (node-skipped in CI). |
| `skills/design-eval/test_design_eval.py` | **updated** — attestation parsing, per-screen provenance, four live-arm tests, marker parity. |
| `skills/design-eval/SKILL.md` | **updated** — "Provenance in the ledger" incl. the evidential-weight statement. |
| `hosts/claude`, `hosts/codex` | **updated** — regenerated; drift check clean. |
| `docs/refinement-todo.md` | **no-op** — nothing new deferred by this slice beyond the in-slice `per_screen` note. |
| ADR-0031 | **partial — disclosed, not no-op.** The accepted ADR says "the spec should record the reference-render engine in the ledger so a mismatch is at least visible". This slice **deliberately dropped that** (see "Dropped from this slice"): at score time the reference is a frozen PNG carrying no engine, and for a hand-supplied reference the information never existed. With 026-02 DEFERRED and 026-04 ABANDONED, **nothing else will pick it up** — so it is recorded here rather than left as a false "fully implemented". |
| `docs/specs/.../spec.md` | **updated** — its non-goal claimed 026-03 "makes engine mixing visible"; false after the reference-engine drop, corrected. |
| `reviews/slice-03-{compliance,craft,reconciliation}.md` | **added** — the ceremony's own evidence. |
| `skills/design-eval/SKILL.md` (Files table) | **updated** — `capture_lib.mjs` now also owns the attestation channel, not just clip geometry. |
| `_common/fidelity_eval.py` | **no-op** — the attestation is design-eval-specific; no shared-harness change. |
