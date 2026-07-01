---
slice: 015-03 — compile-precondition (re-scoped)
pass: craft
verdict: pass
reviewer: maintainer-self-review
reviewed_at: 2026-06-30T00:00:00Z
prompt_source: code-quality review of the _format_refusal enrichment + 015-03 tests; maintainer self-review
---

VERDICT: pass

REASONING:
A small, well-contained enrichment: `_require_suitable` delegates the
non-`suitable` message to a new pure `_format_refusal(data, verdict)` helper that
walks the artifact's `reasons` + `missing_evidence` defensively (tolerates missing
keys / non-dict entries, `.get` throughout) and appends the re-run instruction.
The `EnvError.reason` stays `suitability_not_suitable`, so the closed reason
taxonomy and 016-01's existing precondition test are both preserved; only the
human message got richer. No new exit code, no schema change, no new dependency.

SPECIFIC ISSUES:
(none blocking)
- The refusal message is multi-line on stderr — appropriate for a
  human-actionable next step, and it does not disturb the machine-readable reason
  prefix (`servo: suitability_not_suitable: …`).
- `_format_refusal` is only reached on the non-`suitable` path, so a `suitable`
  compile pays nothing for it.

CROSS-CUTTING:
- Test hygiene: the AC3 boundary test greps `heartbeat.py` source for
  `"suitability"` (lowercased) — precise enough to catch an import/subprocess
  without a false positive on the unrelated `"stderr-suitable"` substring (which
  does not contain the full token).
- The `_write_suitability` fixture gained optional `reasons` / `missing_evidence`
  params (backward-compatible defaults), keeping the 016-01 tests unchanged.
