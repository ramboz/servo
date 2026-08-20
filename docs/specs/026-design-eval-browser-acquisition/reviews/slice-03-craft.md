---
slice: 026-03 — ledger-browser-identity
pass: craft
verdict: pass
reviewer: jig:reviewer (pr-review shape)
reviewed_at: 2026-08-20T01:31:46Z
prompt_source: review.py pr-review (spec 026-03, round 2 after needs-changes)
substrate: non-interactive
---

Round 2, after a round-1 needs-changes. All four blockers closed with the right
fixes rather than the cheap ones.

The `fake_run` threading, the isinstance guard, the four live-arm tests, and the
removal of the unfailable assertion are all verified behavioural rather than
source-text. The `_live_row` helper drives the live arm for real and records the
`_capture_main`-reloads-a-fresh-module trap in its docstring so the next author
does not re-fall into it.

Deleting the JS `parseAttestation` was the correct resolution: it had no
production consumer, and the contract is now pinned at the one place it can
silently break (the ATTEST_MARKER parity test), with a comment in capture_lib.mjs
recording why no JS-side parser should be re-added.

Nits closed this round: `_ledger`'s `fake_run` is now keyword-only and REQUIRED —
a default was the same class of error as deriving it, since a future caller would
silently get the wrong token on a synthetic run; and the mid-file import in the
node suite is folded.

DEFERRED with reasoning: `per_screen` remains a 4-tuple rather than a NamedTuple.
The threading is correct and covered, so the remaining cost is readability only,
and restructuring the composite arithmetic under review against a landed 026-01 is
the worse trade. Trigger recorded: if a fifth element is ever added, land the
NamedTuple then — that is when the positional unpackings stop being scannable.
