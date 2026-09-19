---
status: Accepted
dependencies: []
last_verified: 2026-08-27
frame_review: true
---

# ADR-0035: Manual human-supplied capture provider for design-eval

## Status

Accepted (2026-08-27)

## Context

[ADR-0032](adr-0032-design-eval-capture-providers.md) made app capture a
pluggable provider (`_CAPTURE_PROVIDERS` in `score.py:497-502`: `web`, `command`,
`android`, `ios`) and **explicitly deferred** the human-supplied path: *"This ADR
covers only capture for targets servo can drive. The human-supplied / manual path
for non-automatable targets (GitHub #29 — also a loop-cadence change, and it
overturns spike-findings' 'no manual screenshots' assumption) … [is a] separate
decision built on this seam."* It named the manual/human provider as "the next
provider family under this seam." This ADR is that decision.

The v0.9.0 field report is the motivating case. The target was an **in-game GW2
addon overlay** — ImGui rendered inside a game running under CrossOver. None of
the blessed providers can reach it: `web` needs a page, `android`/`ios` need
those platforms, and the `command` escape hatch still assumes an **automatable**
screenshot (it runs an argv that must drive + shoot + frame the app;
`_capture_command`, `score.py:264-286`). The only real capture here is a **human
taking an in-game screenshot**. With no first-class path for that, the run
degraded to `SERVO_DESIGN_EVAL_FAKE_SCORES` — the test/offline hook — which is
also the hook that makes an injected run hard to tell from a real one. So a target
that simply needs a human-supplied image was pushed onto the one path designed for
synthetic numbers.

ADR-0032's own **Assumptions** drew this boundary: *"The app runs where the
provider runs. The non-automatable case (a Mac host building a Windows-only
product, a Windows-only 3D game plugin) is out of scope here and is the
manual/human path (#29)."* Everything in ADR-0032's seam — the per-screen
provider contract returning `(png, attestation)`, fail-closed `env_error`, ledger
provenance, retained shots (`score.py:215-250`, 027-01) — is reusable; what is
missing is a provider whose "capture" is *consume a PNG a human staged*.

Two frictions ADR-0032 flagged must be faced head-on:

- **Loop cadence.** A manual provider means capture cannot proceed autonomously:
  something must wait for a human to produce the screenshot. This collides with
  the unattended score-time contract (ADR-0031/0032 §7: CI, Routines,
  `--background`).
- **Provenance / trust.** A human supplies whatever PNG they choose. Manual
  capture is the easiest possible place to feed a doctored image — one that
  matches the reference regardless of what the app actually showed.

## Decision

Add a **`manual` capture provider** that consumes a **human-supplied PNG** for
non-automatable targets, reusing the ADR-0032 seam and keeping every honesty
property explicit.

1. **The provider consumes a staged PNG; it does not drive or shoot.** For each
   screen, the human places the app screenshot at a declared path (e.g.
   `manual/<screen-id>.png` under the eval dir, or a `capture.manual.path`
   template). The `manual` provider validates the file exists and is a readable
   PNG, optionally applies the same stdlib chrome-crop the native providers use
   (`_crop_insets`/`pngcrop`, `score.py:344-356`), and returns it as the screen's
   shot. State-seeding and framing are the **human's** responsibility (as with the
   `command` provider, ADR-0032 §4/§5); servo does not run a `setup`.

2. **Absent / unreadable input fails closed to `env_error` (rc 2).** No staged
   PNG → `env_error`, never a silent 0.0 and never a fall-through to another
   provider. Consistent with every other provider (ADR-0032 §1).

3. **A loud stderr advisory on every manual run — the tell lives in the channel
   humans read, not only the ledger.** Symmetric to the Phase-0 fake-scores
   marking (and for the same reason `_emit_honesty_advisories` exists — "the ledger
   is not surfaced in a loop / CI / Routine log; stderr is"), every `manual` run
   prints a prominent **stderr** advisory: `MANUAL CAPTURE — the shot for screen
   <id> was human-supplied (sha256 …), not captured by servo; the score reflects
   whatever image was staged`. This is a **masquerade-prevention** tell: it marks
   the run's *class* — "not servo-captured, whatever was staged" — so a `manual`
   composite can never pass *as* an automated servo measurement. It is deliberately
   **not** a doctoring tell: it does not, and cannot, flag *this particular* image
   as fabricated (nothing can — §6). Note the base-rate difference from the
   fake-scores advisory it mirrors: fake-scores is rare, so its banner is an
   informative *anomaly*; `manual` is the *standing* mode for these targets, so its
   banner fires on ~100% of honest runs and carries no bit distinguishing an honest
   run from a doctored one — its whole job is the class tell, and it is subject to
   operator habituation (a named failure mode below).

4. **Honest, distinct provenance in the ledger too: `manual_capture`.** The ledger
   records the provider as `manual`, per-screen `provenance: manual_capture` (a
   **new token**, distinct from `not_attested`, `not_captured`, and `attested` in
   `_provenance`, `score.py:784-801`), the sha256 and mtime of the supplied PNG,
   and the retained shot (027-01) — the exact image judged, so a human can open it
   behind any score. The ledger is the durable audit trail; §3's stderr advisory is
   the *live* tell. Both, not either.

5. **Attended-only for staging; fails closed unattended — but a *pre-staged* run
   can score unattended.** The provider does not *block a run to solicit* a
   screenshot in an unattended context; it reads whatever is already staged.
   Two honest modes:
   - **attended**: the human stages shots as part of the run; the loop/authoring
     session pauses for them (a cadence change ADR-0032 anticipated).
   - **pre-staged**: a human stages shots out of band; a later unattended
     `score.py` consumes them and records their hashes and mtimes. This is
     honest but the shots may be **stale** relative to the current build — so the
     ledger records enough (hash, mtime) that a human can detect staleness, and
     freeze/docs warn that a `manual` eval cannot certify the shot matches the
     *current* app the way an automated capture does.
   Servo does **not** invent a "the human confirms this is the current build"
   guarantee it cannot enforce; it records provenance and names the residual.

6. **The doctored-image residual is inherent and NOT closed — the ADR does not
   claim auditing defeats a deliberate adversary.** A human can supply a PNG that
   flatters the reference regardless of what the app showed. This ADR does **not**
   argue that "eyeball the shot" defeats that: ADR-0032's eyeball mitigation
   addresses *accidental* state/substrate divergence in a servo-*driven* capture,
   a different threat model from a human who controls the bytes — a doctored image
   built to pass is precisely what an eyeball does not catch. What manual capture
   changes versus the fake-scores status quo is narrower and honestly stated: an
   adversary must now (a) produce a real *image* that survives being retained,
   hashed, and opened by any later auditor — not just type six numbers — and (b)
   do so while a **loud stderr advisory** announces on every run that the shot was
   human-supplied and unverified (§3). This is a **higher bar and a louder tell**,
   not a solved problem: fabrication remains possible, and the ADR claims only the
   raised cost + the restored loud channel, not "strictly better on every axis"
   and not adversary-proof. Selection bias (which real screen to shoot) and
   fabrication (doctoring pixels) are **different acts**; only the former is
   comparable to a normal human capture choice.

7. **`manual` is not the loop's default and never silent.** It must be explicitly
   selected (`capture.transport: "manual"` /
   `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT=manual`, per ADR-0032 §2), it emits the §3
   advisory on every run, and it is distinct from `SERVO_DESIGN_EVAL_FAKE_SCORES`,
   which stays a test/offline hook. Not reachable by accident, not quiet when used.

## Consequences

**Becomes easier / positive:**
- Non-screenshottable targets (in-game overlays, Windows-only plugins on a Mac
  host, anything servo cannot drive) get a **first-class, auditable** capture path
  instead of degrading to the fake-scores hook.
- The real vision judge scores a real, retained, hashed image — restoring the
  parts of the honesty chain that injection bypassed entirely.

**Becomes harder / negative:**
- **Manual staleness is real and only partly observable.** A pre-staged shot can
  lag the current build; servo records hash/mtime and warns, but cannot certify
  currency. Named residual, mitigated by observability, not eliminated.
- **The doctored-image residual** (§6) is inherent and remains. The ADR raises the
  cost of gaming (a real, retained, hashed image must be fabricated, not just
  numbers typed) and restores the loud stderr tell (§3) — it does **not** claim
  auditing defeats a deliberate adversary, and it is not "strictly better on every
  axis" than the loud fake-scores marking. A consumer that ignores the §3 advisory
  and treats a `manual` composite as a servo-captured measurement is the failure
  mode to guard against; the advisory must be unmissable and mutation-tested.
- Cadence: an attended `manual` loop pauses for human capture each iteration —
  usable for authoring / spot-checks, poor for high-iteration autonomous loops.
  ADR-0032 already flagged #29 as a cadence change; this makes it explicit.

**Neutral:**
- Reuses ADR-0032's provider seam, retained-shots plumbing, and fail-closed
  contract; adds one provider, one provenance token, and (optionally) an
  input-hash ledger field. `definition_hash` and the 0/1/2 contract are unchanged
  — capture stays environmental, never frozen (ADR-0031).
- Overturns spike-findings' "no manual screenshots" assumption for design-eval,
  exactly as ADR-0032 predicted.

## Alternatives considered

- **Do nothing; tell non-automatable targets to use `command`.** Rejected: the
  `command` provider assumes an automatable screenshot; a human-in-the-loop
  overlay has no such command. It leaves fake-scores as the only path — the
  reported failure.
- **Let `SERVO_DESIGN_EVAL_FAKE_SCORES` be the blessed manual path.** Rejected
  outright: fake-scores injects *numbers* with no image, no hash, no judge, no
  audit — it is the anti-pattern this ADR exists to replace. Conflating "human
  supplied a real screenshot" with "human supplied a score" is exactly the
  confusion that made the field-report run hard to spot.
- **Require a human to *confirm currency* ("this shot is of the current build")
  and treat that as a guarantee.** Rejected: servo cannot enforce it, and a
  self-attestation servo cannot check must not be dignified as a guarantee (same
  reasoning as ADR-0032's refusal to certify state equivalence). Record hash/mtime
  and name the residual instead.
- **Block unattended runs on `manual` entirely (attended-only, no pre-staged
  mode).** Rejected as too strict: a pre-staged shot consumed in CI is honest so
  long as its staleness is observable (§4). Forbidding it would push users back to
  injection for the "score what I already captured" case.
- **A richer interactive capture UI (prompt the human, ingest a paste/upload).**
  Deferred: a UX layer on top of §1's staged-file contract; the file contract is
  the primitive and can be driven by a UI later without re-deciding this.

## Assumptions

- The ADR-0032 seam (`capture_app(base_dir, screen, run_id, provider, config)` →
  `(png, attestation)`; retained shots; `_provenance` tokens) accommodates a
  provider that reads a staged file with no subprocess — verified by reading
  `score.py:493-534` and `_provenance` (`score.py:784-801`); `manual` returns
  `(png, None)` like the native providers and adds one provenance token.
- Non-automatable targets are a real, recurring class (the report's GW2/ImGui
  overlay; ADR-0032's Windows-only-plugin-on-Mac case), not a one-off.

## Kill criteria

- If, for real adopters, the pre-staged mode's staleness proves undetectable in
  practice (humans restage rarely; the mtime/hash signal is ignored) and the
  scores drift from reality without anyone noticing, drop the pre-staged
  unattended mode and make `manual` strictly attended — capture is then always
  contemporaneous with a human in the loop.
- If a UI-driven capture path (deferred alternative) proves necessary before the
  file-contract primitive is useful on its own, this file-only decision is
  revisited under that UX ADR.
- If the §3 advisory decays to noise through **habituation** — firing on every
  honest `manual` run, it is easy to tune out, at which point even the class tell
  (don't mistake a `manual` composite for an auto-captured one) stops working —
  the class distinction must move somewhere a consumer cannot tune out (e.g. the
  oracle/gate refusing to treat a `manual` composite as a gating measurement
  without explicit opt-in), rather than relying on the banner alone.

## Open questions

1. **Staged-path convention.** Fixed `manual/<screen-id>.png` under the eval dir
   vs. a `capture.manual.path` template vs. a per-screen `manual` field — how does
   it compose with retained-shots naming (`shots/app-<id>-<run_id>.png`)?
2. **Crop ownership.** Does `manual` offer the optional stdlib chrome-crop (§1) or
   insist the human supplies an already-framed PNG (like `command`)? The overlay
   case may have no fixed chrome to crop.
3. **Interaction with [ADR-0034](adr-0034-design-eval-subagent-judge-transport.md).**
   A non-automatable target in the Desktop app is the intersection case: `manual`
   capture *and* a `subagent` judge, both attended. Specify the two together so
   that end-to-end path is coherent (capture by human, judge by session subagent).

## References

- **[ADR-0032](adr-0032-design-eval-capture-providers.md)** — the provider seam
  this extends; it explicitly defers the manual/human path (#29) as the next
  provider family and drew the non-automatable boundary this ADR crosses.
- **[ADR-0031](adr-0031-design-eval-browser-acquisition.md)** — capture stays
  environmental (never frozen); `manual` is a transport, not part of the hash.
- **[ADR-0005](adr-0005-eval-oracle-component.md)** — fail-closed honesty
  (`env_error`, never silent 0.0) kept for the absent-input case.
- **[ADR-0034](adr-0034-design-eval-subagent-judge-transport.md)** — the attended
  judge sibling; OQ3's intersection case.
- **GitHub #29** — manual/human capture, recorded against ADR-0032; realized here.
- **field report** (`/servo:design-eval` v0.9.0, 2026-08-27) — the GW2/ImGui
  overlay and the fake-scores degradation this replaces.
