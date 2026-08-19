---
adr: 0031
pass: frame-critique
verdict: pass
reviewer: jig:architect (adversarial frame-critique, 4 rounds)
reviewed_at: 2026-08-19T23:15:51Z
prompt_source: review.py frame-critique docs/decisions/adr-0031-design-eval-browser-acquisition.md
---

Adversarial frame-critique, 4 rounds, PASS on round 4.

Round 1 (needs-changes): the ADR's spine — "pin browser identity into the frozen
definition so drift refuses as stale" — was false. `validate_freeze` is
self-referential (never probes the environment) and `definition_hash`'s docstring
deliberately excludes environmental fields (naming `app_url`). A frozen version
string is inert; a live-probing variant is the exact anti-pattern the freeze
model rejects. Also: the ADR never established engine drift is even a material
score-noise source vs. the n-sample lower bound / plateau δ. → Option E rejected;
"footprint & reproducibility are dual" withdrawn (they are in tension); browser
identity moved to the ledger only.

Round 2 (needs-changes): the fix moved the environmental-pinning problem onto
`capture.transport`, justified by bare analogy to `judge.transport`. Transport is
environmental (the detection ladder probes the machine). → transport excluded
from `definition_hash` like `app_url`; env override added
(`SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT`).

Round 3 (needs-changes): unfreezing transport dissolved the entire rationale for
the `init` seam — detection is per-machine but `init` runs only on the author's
laptop, while the wall is hit at score time on CI/Routines. Also verified
`install()→init()` is unconditional (`design_eval.py:148`), so an interactive
`init` blocks `install` on stdin. → reframed: primary mechanism is a
non-interactive runtime preflight (G) on the failing machine; interactive
detect-ask-install (F) demoted to an opt-in authoring convenience kept out of the
`install()` path.

Round 4 (PASS): the D+G+F composition holds under strongest attack. Two
non-blocking notes folded into the ADR: (1) the node/library probe must live in
`score.py`, not `capture.mjs` (whose top-level import throws first); (2) softened
"primary/closes" framing — G closes the gap as ADR-0020 re-scopes it to
guidance-quality, and the hard-to-reverse commitments are D's schema + back-compat.

Load-bearing assumptions all verified against the code: freeze is
self-referential + excludes environmental fields; `app_url` is the exact
precedent (`config.example.json:4`); connector cannot serve channel-less
scoring; `install()→init()` unconditional; ADR does not rest on drift being
material (explicitly disclaimed). The two prior fatal findings are corrected
in-body without laundering.
