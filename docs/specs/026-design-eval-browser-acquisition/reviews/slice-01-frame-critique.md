---
slice: 026-01 — runtime-preflight-guidance
pass: frame-critique
verdict: pass
reviewer: jig:architect (adversarial frame-critique, 8 rounds)
reviewed_at: 2026-08-20T00:49:25Z
prompt_source: review.py frame-critique docs/specs/026-design-eval-browser-acquisition/slice-01-runtime-preflight-guidance.md
---

Adversarial frame-critique, 8 rounds, PASS on round 8.

The gate falsified four successive mechanisms and three spec-vs-prototype
divergences before this slice was buildable:

R1 — PREMISE FALSIFIED. The slice was built to eliminate the message
"node/playwright unavailable for capture". Probed: that fires ONLY when the node
BINARY is absent. A missing LIBRARY starts node fine, returns rc 1, and surfaces
head-truncated node internals. The slice was rewritten around the real taxonomy.

R2 — the replacement mechanism ("last non-empty line") falsified by the probe the
reviewer specified: the cause sits at line 4 of 18; the last non-empty line is
"Node.js v22.16.0"; stderr[-200:] is strictly worse than today's head. Also
found the AC1/AC6 contradiction — the probe must FAIL OPEN (token-confirmed
MODULE_NOT_FOUND only) or NODE_OPTIONS=--input-type=module is misreported as a
missing library on a machine where capture would have succeeded.

R3 — "first 2 + last 2" falsified: Playwright's remedy box is positionally
central, so any first-N/last-N reduction keeps box corners and discards the
remedy. Replaced with salience RANKING. Also: pin the probe cwd to base_dir, or a
token-confirmed false positive lands in the fail-CLOSED branch.

R4 — the rank predicate was falsified against its own AC text: a bare `install`
substring matches Playwright's "was just installed or updated" prose, which sits
ABOVE the command. The prototype passed only because it used a word-bounded
\binstall\b — the implementation was stricter than the spec. Replaced with
command-shape ranking.

R5 — the DROP stage falsified the same way. Node's frame header is a three-line
BLOCK; the AC granted an echoed-source-line drop only for the ^file:// variant,
so rank 1 became `throw new ERR_MODULE_NOT_FOUND(` — node internals as the
adopter's headline, the exact defect the AC removes. Verified by printing rank-1
rather than asserting it. Replaced with a block rule; DoD tightened from "the
cause survives" (satisfiable by presence anywhere) to exact-match on the emitted
FIRST line.

R6 — the newly added shared-helper AC wired a node-grammar parser to the
`claude -p` judge path, a different producer with no fixture, where the block
rule would have made a working path worse. Scoped to capture_app only; other call
sites deferred with a named owner.

R7 — the DoD still required the wiring AC4a had just been rewritten to forbid.
Since the DoD is what an implementer ticks and a compliance reviewer audits, the
stale line would have won. Inverted to guard score.py:157 as UNCHANGED. Budget
pinned at 400 with the arithmetic justifying it.

R8 — PASS. Reviewer verified each fix in the file. Two non-blocking implementer
notes carried forward: the parity test must join AC4's line-wrapped regex
precisely (loosening the comparison would gut the control built to stop code
being stricter than its AC), and the 400/200 asymmetry between the normal budget
and the zero-survivor floor is deliberate and needs a code comment so a future
cleanup does not unify them.

Load-bearing assumptions all probe-verified: the failure taxonomy, the
require.resolve/which(node) separation, the salience filter against real captured
stderr, and the 5-site [:200] enumeration.
