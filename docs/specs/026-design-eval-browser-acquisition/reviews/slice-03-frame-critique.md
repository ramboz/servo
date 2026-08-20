---
slice: 026-03 — ledger-browser-identity
pass: frame-critique
verdict: pass
reviewer: jig:architect (adversarial frame-critique, 7 rounds)
reviewed_at: 2026-08-20T00:50:52Z
prompt_source: review.py frame-critique docs/specs/026-design-eval-browser-acquisition/slice-03-ledger-browser-identity.md
---

Adversarial frame-critique, 7 rounds, PASS on round 7.

R1 — the ledger writer (score.py) is not the browser launcher (capture.mjs), so
any independently-probed version string attests what WOULD launch, not what did,
diverging exactly in the cases an investigator opened the ledger for. Replaced an
out-of-band probe with an attestation channel.

R2 — the fix covered only half the payload: the engine was attested while the
transport beside it was still writer-resolved, presented in one row with no
marker of which was which. Both now come from the attestation. Also: a distinct
ledger key, since `transport` already means the JUDGE transport in every
historical row; and reason tokens replacing a bare "unknown", since fake-scores
writes a row with no browser at all.

R3 — the DoR's "stdout is free" was a FALSE verified-claim: capture.mjs imports
and runs the ADOPTER's setup module in-process on the --screen path, so their
console.log shares that stdout, and score.py's _extract_json (first { to last })
is the helper an implementer would reach for and the one that mis-parses hardest.
Channel made marker-delimited, scanned by marker, explicitly not _extract_json,
with non-matching stdout discarded rather than treated as failure.

R4 — a throwing engine accessor would have killed a SUCCESSFUL screenshot's
score: capture.mjs has one try whose catch sets exitCode 2, so provenance would
have become load-bearing in contradiction of the slice's own AC4. The attestation
now has its own try/catch that never assigns exitCode. Marker determinism pinned
(emit after launch, before the setup import; take the first match) since a marker
cannot be collision-proof.

R5 — SCHEMA. capture_app runs once per screen, so a row has N attestations while
the slice assumed one; the shipped example config has two screens, making N>1 the
default. Provenance moved onto the existing per-screen array so a mid-run engine
change is visible by construction. Also corrected the third token's stated cause:
init() copies the runtime in one unconditional loop, so a pre-channel skew is
unreachable by the supported path.

R6 — the JS-side ACs were structurally UNTESTABLE (capture.mjs imports Playwright
at module load; node is skipped in servo's CI), so the accessor-throw DoD item
would have been satisfied by a Python-side fake testing the parser, leaving the
guard uncovered with a ticked checkbox. attestationLine()/safeAttest() moved to
capture_lib.mjs as pure functions with the node suite as their test and a
CI-runnable delegation guard. Transport value stated as the literal "bundled"
under 026-02's deferral. Attestation returned alongside the PNG path, never
stashed in a module global (which would be last-write-wins and re-create the
single-field collapse).

R7 — PASS. Three non-blocking implementer notes carried: re-tense AC2b's
present-tense reference to deferred machinery; bump the node suite's `# pass N`
floor so the new cases have a regression tripwire on dev machines; and make the
console.log call site its own statement in a bare catch so AC1b's guarantee is
literally true of the shipped line.

Carried risk, correctly hedged: A5 (a Playwright per-launch engine accessor)
remains unprobed — no playwright resolves in this worktree — but the design
degrades to a null engine plus an error string rather than failing a score, and
that degradation is the path the node suite tests directly.
