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
3. **One resolver owns precedence, with an explicit mode flag.** A single Python
   function `resolve_transport(config, *, allow_env: bool)` is the only place
   precedence lives: the score path calls it with `allow_env=True`
   (env > config > bundled); `capture_refs` calls it with `allow_env=False`
   (config > bundled). Stating the mode explicitly prevents an implementer from
   satisfying this AC literally by having `capture_refs` call the env-honouring
   resolver and thereby defeating AC4. It resolves once and passes the result to
   `capture.mjs` as an explicit `--transport <t>` argv; `capture.mjs` **never
   re-derives** transport from config or env, so the preflight and the launch can
   never disagree (the runtime files are copied into targets independently, so
   any drift would be permanent). Placement: `score.py` — `design_eval.py`
   already loads it as a module and is itself never copied into targets, so both
   spawn sites reach it without a third copy.
3a. **`capture.mjs` fails closed when `--transport` is absent, and its header
   stops advertising direct `--refs`,** pointing at `design_eval.py capture-refs`
   instead. **No private marker protocol** — an earlier draft proposed one, but
   `design_eval.py` runs from the plugin dir and auto-updates while `capture.mjs`
   is *copied into the target* and frozen at the last `init`, so a marker would
   drift one-directionally and surface as a servo bug on the authoring path. And
   a plaintext constant inside a file in the adopter's own repo is a guard
   against accident, not a gate. **Stated honestly instead:** AC4's guarantee
   covers the supported path (`design_eval.py capture-refs`); someone invoking
   the copied `capture.mjs` directly bypasses it, exactly as they can today.
4. **The `--refs` guard keys on the FREEZE, not on the transport.** If the eval
   is frozen (`approval_status == "approved"` with non-empty `hashes` — the
   signals `validate_freeze` already uses) and `capture-refs` is about to
   overwrite files listed in `config["hashes"]`, it **refuses before writing
   anything** unless given an explicit `--allow-rerender`, and its message says
   *"this invalidates the freeze — re-run `freeze` and re-approve."*

   **Why keyed on the freeze rather than on which engine rendered the refs**
   (this replaced an earlier transport-keyed design, and the simplification is
   the point): re-rendering a frozen eval's references invalidates it *regardless
   of engine* — every `hashes[rel]` is recomputed and the next score raises
   `StaleError`. A transport string is **not a version**, so a transport-keyed
   guard would have been silent for the two *recurring* hazards — a
   `playwright@next` bump moving the bundled Chromium, and a system Chrome
   auto-updating 151→152 — while firing only on the one-time cross-transport
   switch. On the BYO path, the very path this slice enables and the one ADR-0031
   says carries "real, unpoliced engine drift", its discrimination power would
   have been close to zero. Keying on the freeze closes all three.

   It also removes, rather than specifies, a whole state machine: no persisted
   render-transport, no absent-key inference, no mixed-state marker, no clearing
   path, no new `config.json` writer on the authoring loop (and so no
   write-failure branch and no lost-update race against an author's open editor).

5. The `--allow-rerender` opt-in is the sanctioned route, and its output **must**
   name the next step (`freeze` + re-approve) — otherwise the author's next
   signal is an opaque rc 2 at score time, quite possibly first seen on CI.

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
- [ ] Env override precedence tested (score path honours it; `capture_refs` does
      not — the `allow_env` flag).
- [ ] AC4 refusal tested: a **frozen** eval refuses `capture-refs` before writing
      any bytes, and the message names `freeze` + re-approve.
- [ ] AC4 allow tested: an **unfrozen** eval renders normally (nothing to protect).
- [ ] `--allow-rerender` tested: it proceeds, and its output names the next step.
- [ ] Test: refusal happens **before** any PNG is written (no partial re-render).
- [ ] `capture.mjs` refuses without `--transport`; header no longer advertises
      direct `--refs`.
- [ ] Back-compat: pre-existing frozen config still scores, warns on stderr, no `StaleError`.
- [ ] Invalid-transport test asserts the Python-side error, not JS stderr.
- [ ] `SKILL.md` + `templates/config.example.json` updated.
- [ ] Compliance + craft + **arch** review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Fallback if A1 fails** (stated so the probe has a decision attached, and
aligned with the Accepted ADR rather than overriding it): **ship nothing from
this slice.** ADR-0031 kill criterion 1 says the decision "collapses toward
Option A (bundled) — leaving only the ledger identity record, which remains
independently worthwhile." Shipping the schema anyway would leave an irreversible
`config.json` surface whose only legal value is the existing default, a `--refs`
refusal that can never fire, and a "transport-aware" preflight with one transport
— and would make this slice's own verticality claim false. In that case: mark
026-02 ABANDONED with the probe result as the reason, and let 026-03 carry the
value (it depends on the *resolved* transport, which degrades cleanly to
"bundled"). Do **not** force the transport through.

**Abandonment would orphan three commitments — redirect them explicitly:**
(a) 026-03's dependency and its DoR item "026-02 resolves a transport Python-side"
become false; `capture.mjs` then attests a constant `"bundled"`, which still
satisfies its AC2, and its AC7 test matrix collapses to one transport. Resolve
the dep token rather than leaving it pointing at an ABANDONED slice.
(b) AC8's transport-choice guidance (inherited from the abandoned 026-04) loses
its home — move it to 026-01's or 026-03's `SKILL.md` update.
(c) 026-01's "inherited obligation" to update the hardcoded `'playwright'` probe
specifier becomes moot: `'playwright'` is then the intended permanent end state.

**Why `arch_review: true`:** changes the `config.json` schema, adds a
cross-language interface (`--transport` argv), and touches the freeze boundary.

**Vertical?** Yes — an adopter can score with the Chrome they already have.
