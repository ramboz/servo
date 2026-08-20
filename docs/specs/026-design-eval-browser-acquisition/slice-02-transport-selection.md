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
3a. **`capture.mjs` fails closed when `--transport` is absent.** Its header
   documents direct invocation (`node capture.mjs --refs`), and it ships as an
   executable file inside the adopter's `.servo/design-eval/`. Silently defaulting
   would re-render references under bundled Chromium while config says otherwise
   — bypassing AC4 with no warning. It therefore errors with a clear message
   naming the Python entry point, and the header docs are updated to match.
4. **The `--refs` guard keys on STATE, not on which door set it.** Before
   re-rendering, `capture_refs` compares the **resolved** transport against the
   **transport that rendered the current frozen references** and, on a mismatch,
   **refuses before overwriting anything** — regardless of whether the change
   came from the env override or from editing `config.json`. The config door is
   the headline feature and the *more likely* path, so guarding only the env door
   (as an earlier draft did) left the real hazard open: `capture.mjs --refs`
   loops every screen and overwrites each `reference` in place with no staging,
   invalidating every `hashes[rel]` entry and forcing a full human re-approval.
5. A **sanctioned route exists** for the author who deliberately wants to
   re-render under a new engine (an explicit `--allow-transport-change` opt-in),
   so the refusal in AC4 is a speed bump with a documented way through, not a
   dead end.
5a. **`capture_refs` records the render transport** into an unfrozen `capture.*`
   key when it writes references — this is the state AC4 compares against, and
   nothing records it today (`freeze()` writes only `hashes`,
   `approved_content_hash`, `approval_status`, `approved_at`). A test pins that
   this new key stays out of `definition_hash` (it will by construction, but it
   is added on the *freeze* path rather than the config path, so it earns its own
   assertion).
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

**Why `arch_review: true`:** changes the `config.json` schema, adds a
cross-language interface (`--transport` argv), and touches the freeze boundary.

**Vertical?** Yes — an adopter can score with the Chrome they already have.
