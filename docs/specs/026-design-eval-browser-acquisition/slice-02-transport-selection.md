---
status: DRAFT
dependencies: [026-01, adr-0031]
last_verified:
arch_review: true
frame_review: true
---

## Slice 026-02 — transport-selection

**Goal:** Let an adopter reuse an installed Chrome instead of downloading a
pinned Chromium, via an **unfrozen** `capture.transport` — with a **single
Python-side resolver** and an explicit rule for the reference-render path, which
is the one place a transport switch could invalidate a freeze.

**DoR:**
- ✅ **Freeze-neutrality of the config field is probe-verified, not assumed.**
  Ran `definition_hash` directly: adding a top-level `capture` block leaves the
  hash byte-identical; changing `capture.transport` leaves it byte-identical;
  control — changing `threshold` **does** move it, and `app_url` (documented
  environmental exclusion) does not. `definition_hash` serializes only named keys
  (`judge`/`samples`/`threshold` + `_EXTRA_HASH_FIELDS=("viewport",)` + the case
  set), so a new top-level key is excluded **by construction**.
- ✅ **Back-compat verified:** `capture.mjs:31` is a bare `chromium.launch()`
  with no channel, so **no existing adopter can be on system Chrome today**.
  "Absent block ⇒ assume bundled" therefore preserves behavior exactly, rather
  than guessing.
- ⚠️ **`capture.mjs` is ALSO the reference renderer** (`design_eval.py` runs
  `node capture.mjs --refs`), and reference PNGs **are** content-hashed into the
  freeze (`artifact_hashes` over `_CASE_FILE_FIELDS`). A transport switch on that
  path rewrites frozen bytes → `StaleError` → forced human re-approval, the exact
  cost the override exists to avoid. **AC4/AC5 exist to close this**; it was the
  frame-critique's primary finding.
- ⚠️ **A1 probe must use `playwright-core` (or browsers-not-downloaded).** Probing
  `channel:'chrome'` under the full `playwright` package does not test the
  footprint claim — the download happens at install time regardless of channel.
  Precondition confirmed on the dev machine: Google Chrome 151.0.7922.138 present.

**Acceptance criteria:**
1. `config.json` gains a `capture` block with `transport`; absent ⇒ **assume
   bundled**, warn **on stderr** (stdout carries only the composite float, which
   `oracle.sh` parses), never refuse.
2. `capture.transport` is excluded from `definition_hash`; changing it never
   raises `StaleError` **on the score path**. Test asserts hash-invariance.
3. **One resolver owns precedence.** A single Python function resolves
   env > config > bundled and passes the result to `capture.mjs` as an explicit
   `--transport <t>` argv. `capture.mjs` **never re-derives** transport from
   config or env — this prevents a Python/JS split-brain in which the preflight
   probes one browser and capture launches another (the files are copied into
   targets independently, so drift would be permanent).
4. **The reference-render path (`--refs`) does not silently follow the env
   override.** `capture_refs` resolves from **config only**; if
   `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` is set and differs, it **warns loudly
   and refuses** rather than re-rendering frozen references under a different
   engine.
5. Re-rendering references under a transport different from the one recorded at
   last freeze is surfaced as an explicit, actionable warning (it is a re-freeze
   decision, not an incidental side effect).
6. 026-01's preflight becomes transport-aware: it probes what the *resolved*
   transport needs and names that transport's remedy.
7. An invalid/unknown transport fails closed with a clear `env_error` **from the
   Python resolver** (before spawning), not as truncated JS stderr.
8. `SKILL.md` documents both transports and states plainly that BYO engine drift
   is real and unpoliced.

**DoD:**
- [ ] A1 probed **with `playwright-core`**; result + disposition in the deviation log.
- [ ] Single resolver implemented; `capture.mjs` takes `--transport` and derives nothing.
- [ ] Hash-invariance test green.
- [ ] Env override precedence tested, **and** the `--refs` refusal tested (AC4).
- [ ] Back-compat: pre-existing frozen config still scores, warns on stderr, no `StaleError`.
- [ ] Invalid-transport test asserts the Python-side error, not JS stderr.
- [ ] `SKILL.md` + `templates/config.example.json` updated.
- [ ] Compliance + craft + **arch** review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Fallback if A1 fails** (stated so the probe has a decision attached): ship the
`capture` block, resolver, preflight integration, and `--refs` guard anyway with
`bundled` as the only valid value — the schema and safety work stand on their
own — and record in the deviation log that BYO is not viable, per ADR-0031 kill
criterion 1. Do **not** force the transport through.

**Why `arch_review: true`:** changes the `config.json` schema, adds a
cross-language interface (`--transport` argv), and touches the freeze boundary.

**Vertical?** Yes — an adopter can score with the Chrome they already have.
