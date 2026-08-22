---
slice: 027-01 — shot retention + ledger visibility
pass: reconciliation
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: reconciliation review of the deviation log / sweep / DoD vs disk
---

VERDICT: pass — reconciliation artifacts faithful to what was built.

Deviation-log honesty: every claim maps to a verified line in `score.py` —
`_run_stamp()` (local `%Y%m%dT%H%M%S` + 6-digit microsecond suffix), the stamped
filename directly under `shots/`, one stamp per run threaded into every
`capture_app`, the defaulted `run_id` param keeping the 2-arg callers working, the
`per_screen` 4→5 growth with all consumers updated, live records the relative shot
path / fake records `None`, ledger writes `"shot": shot`. No claimed change absent
from code; no real change undocumented.

Sweep completeness: the three non-no-op rows are correct — `docs/refinement-todo.md`
(unbounded `shots/` growth deferral added), `skills/design-eval/SKILL.md` (the
`shot` field documented in the ledger section), `docs/specs/README.md` (deferred to
close-out; spec not closed). Git working-set matched exactly; nothing silently
changed.

DoD accuracy: `SKILL.md` "Provenance in the ledger" accurately documents the `shot`
field (relative path, null on fake, retained/unhashed). The full-suite box is
ticked with an explicit, honest qualifier naming the single unrelated pre-existing
red test rather than masking it.
