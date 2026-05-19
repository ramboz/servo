---
status: Accepted
date: 2026-05-18
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0002 — Quality-gate caller contract: closed exit codes and versioned JSON schema

## Context

Spec 002 (`/servo:quality-gate`) ships `gate.py`, the runtime wrapper around the scaffolded `oracle.sh`. Specs 003 (agent-loop), 004 (oracle-hook), and 005 (variant-race) all consume the gate's output — three downstream skills (each itself reused by users) depending on a single uniform call shape.

During spec 002's pre-review clarify pass (`/jig:clarify`, 2026-05-18), two contract-shaping questions surfaced:

- **Q1.** What should `gate.py` do when `oracle.sh` exits with a code outside the 0/1/2 contract (e.g., signal-killed = 137, faulty oracle returning 99)?
- **Q3.** Should `gate.py --json` output (slice 002-02) carry a `schema_version` field from day one?

Both are decisions that, once shipped and consumed by downstream specs, become very hard to reverse — changing them later forces breaking schema/contract changes across three callers and any project that has wired its own automation around the gate. They share enough motivation (define the gate's outward contract before downstream specs lock in around it) that they belong in a single ADR rather than two near-duplicates.

## Decision

The gate's caller contract has two clauses.

**1. Closed exit codes.** `gate.py` exits **only** 0, 1, or 2:

- `0` — composite ≥ threshold (oracle passed)
- `1` — composite < threshold (oracle failed)
- `2` — any environment error: missing oracle, missing manifest, malformed manifest, timeout, unparseable oracle output, oracle exit outside 0/1/2

Specifically, if `oracle.sh` exits with any code not in `{0, 1, 2}` — including signal kills (128 + signo), bash errors (e.g., 126/127), or any user-introduced bug — `gate.py` remaps to exit 2 with structured stderr/JSON fields `status=env_error reason=unexpected_exit code=<N>`. The original oracle exit code is preserved in the `code` field so callers and humans can still see what happened, but the gate's own exit code stays inside the closed set.

**2. Versioned JSON output.** `gate.py --json` (slice 002-02 and 002-03 audit mode) emits a payload that includes a top-level integer field `schema_version`. Initial value: `1`. Any future field rename, type change, or semantic shift bumps this. Pure additive changes (a new optional field with a documented default for old consumers) MAY keep the version at 1 — but the ADR's bias is "bump on any doubt"; cheap field, expensive silent breakage.

The exact slice-by-slice JSON shape is in spec 002; this ADR fixes only the contract envelope (the `schema_version` field and the closed-exit clause).

## Consequences

**Positive.**

- Three downstream specs (003 / 004 / 005) can write `match exit_code: case 0 | 1 | 2 | other → bug` and trust the `other` arm is unreachable in practice. Removes one defensive branch per caller.
- JSON consumers can read `schema_version` before parsing the rest of the payload. Old consumers facing a future bump can refuse loudly (`schema_version mismatch, expected 1 got 2`) rather than silently mis-decoding fields they don't recognize.
- Internal evolution stays cheap: the gate can add new env-error reason strings, new optional JSON fields, or new stderr breadcrumbs without breaking the closed contract.
- Aligns with servo's existing oracle contract (0/1/2 was already promised by the scaffolded `oracle.sh`). The gate just enforces it for callers regardless of what the user's oracle does.

**Negative.**

- Remapping unexpected oracle exits loses surface information. The original code is preserved only via `reason=unexpected_exit code=<N>`, which callers must explicitly read. A naive grep-on-stderr workflow could miss it.
- Every JSON payload carries a 17-byte `"schema_version":1,` field even when no schema evolution is happening. Cost is negligible for a one-shot per-call payload; flagged here for completeness.
- Closing the contract means a future "useful" exit code (e.g., `3` = "ran but oracle is mid-edit, retry") needs a different surfacing mechanism (a stderr/JSON status string) rather than a new exit code. Acceptable: stderr/JSON are richer surfaces anyway.

**Neutral.**

- The `schema_version` field is just an integer counter, not a semver string. If servo's gate JSON ever needs `major.minor` semantics, the ADR will be superseded. Today the audience is internal callers (specs 003–005) and we don't need semver yet.
- Deprecation policy for old `schema_version` values is not pinned in this ADR. When `schema_version=2` lands, the gate may choose to keep emitting `1` under a `--legacy-json` flag, or refuse old consumers outright — that's a future call when the first bump actually has a reason.

## Alternatives considered

- **Pass-through exit codes verbatim.** Rejected: forces every downstream caller to defend against arbitrary codes, including signal-killed values that look meaningful (137 = SIGKILL = "ran out of memory or got OOM-killed") but shouldn't be acted on by the loop driver as if they were oracle verdicts.
- **Refuse on unexpected oracle exit (exit 2 with `oracle_contract_violation`, but with `--strict` flag to allow it).** Rejected as default: too brittle for unattended use; one buggy oracle would block a whole agent-loop run when remap-to-2 is a softer failure mode that preserves all the same diagnostic information.
- **No JSON version field; "0.x is unstable, callers shouldn't depend on it" policy.** Rejected: the policy doesn't survive contact with real consumers. Specs 003–005 *will* depend on the schema (they parse it), so pretending otherwise just defers the inevitable break.
- **JSON Schema URI (`"$schema": "https://servo/schemas/gate-output-v1.json"`).** Rejected: heavyweight for a single-line payload; the URI form anticipates third-party consumers and external validators we don't have. Plain integer `schema_version` is enough for the current audience.
- **Couple the JSON schema version to servo's plugin version (`schema_version = SERVO_VERSION`).** Rejected: forces a schema bump on every plugin release even when the JSON shape didn't change. Independent counters are the standard practice.

## Verification

- **Slice 002-01** verifies the closed-exit clause via `UnexpectedExitTests`: spawn an oracle that exits with codes outside `{0, 1, 2}` (signal-killed, `exit 99`) and assert `gate.py` exits 2 with the documented remap.
- **Slice 002-02** verifies the `schema_version=1` field is present in every `--json` payload via `JsonOutputTests.test_schema_version_present_and_equals_one`. The field is asserted across all three branches (pass, below-threshold, env error).
- **Spec-level dogfood (spec 002 DoD)** re-validates by running `gate.py --json` against servo's own repo (scaffolded by spec 001) and asserting `jq '.schema_version'` returns `1` on the pass path. The closed-exit clause is dogfooded by running against a tampered oracle that returns 99 and asserting `$?` is 2.

## References

- [Spec 002 — quality-gate](../specs/002-quality-gate/spec.md), `## Clarifications` Q1 + Q3.
- [Spec 001 — scaffold-init](../specs/001-scaffold-init/spec.md), slice 001-02 (where the oracle's 0/1/2 exit contract was first locked).
- `templates/oracle.sh.template` — the source of the 0/1/2 contract this ADR closes.
