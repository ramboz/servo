# Full CI evidence for spec 033

Recorded on 2026-10-12 during the retrospective workflow recovery.
This is executed validation, not a substitute for independent review.

## Invocation and source identity

Command: `python3 scripts/ci_check.py` from the servo repository root.

Runtime implementation under test: commit
`ac06cec89e544e04ae22fa4c27d4516c7442db6a`. Subsequent working-tree changes at
this run were lifecycle/decision metadata and documentation, not heartbeat,
its tests, or generated runtime code. The independent implementer verification
records source hashes and mutation checks separately in `verification.md`.

## Observed results

| CI step | Actual result |
|---|---|
| Full repository suite | **1,866 passed**, no failures |
| Plugin manifests | Four manifests agree on servo `0.10.0` |
| Code-health floor | Pinned `ruff==0.15.17`: no findings |
| Install surfaces | Plugin/manifest/package checks passed; **107 tests passed** |
| Host-package drift | Both committed packages match canonical source |

The 107 install-surface tests repeat a subset of the repository suite; they are
not 107 additional unique tests. No live `claude -p` execution was claimed:
the repository's fixtures exercise subprocess contracts through controlled
mock runners and real isolated Git worktrees.

## Separate advisory health snapshot

Command: jig's `health.py check .`, executed by the orchestrator.
Normalized exit code: **0**.

- Ruff: clean.
- Complexity: 247 functions over advisory thresholds.
- Pyright: 469 advisory type diagnostics.
- Duplication: 35.3%, 693 clones, including package/manifest/document surfaces.

These advisory totals are not a claim of a clean whole-repository type check,
nor a proven baseline comparison. The code-health reviewer must judge the
bounded deliverable using the injected real summary; this change must not
expand into unrelated cleanup to silence those totals.

## Final rerun after durable test promotion

The implementer subsequently promoted five temporary boundary checks into the
existing `skills/heartbeat/test_heartbeat.py` and appended their actual evidence
to `verification.md`. The first run above remains historical pre-promotion
evidence; it is not relabeled as a run of the final test file.

The orchestrator then re-executed **`python3 scripts/ci_check.py`** against that
final test suite on Python 3.13.7 / pytest 9.1.1:

| Final CI step | Actual result |
|---|---|
| Full repository suite | **1,871 passed**, no failures |
| Plugin manifests | Four manifests agree on servo `0.10.0` |
| Code-health floor | Pinned Ruff clean |
| Install surfaces | Plugin/manifest/package checks and **107 tests passed** |
| Host-package drift | Both committed packages match canonical source |

Runtime code and generated runtime bytes still match `ac06cec`; the promoted
test-file hash is recorded in verification's later promotion section. Later
review, reconciliation, and lifecycle files are documentation/evidence, not
unreported runtime changes.

The final `health.py check .` snapshot exited 0: Ruff clean, 247 advisory
complexity findings, 474 advisory Pyright diagnostics, and 35.2% duplication
(693 clones). These remain advisory totals, not a claim of whole-repository
type cleanliness or a proven baseline classification for every diagnostic.

## Post-review nit closure

The orchestrator re-executed `python3 scripts/ci_check.py` after correcting the
fixture-fidelity nit and the live architecture contract. The result was again
**1,871 repository tests passed**, manifest validation and pinned Ruff passed,
**107 install-surface tests passed**, and both package drift checks passed.

Final identities for that runtime/test state:

- Heartbeat runtime SHA-256:
  `4a8e5fab7203a42b4fd70cf86f1573f85699743524ca21bf4b784536e506f542`
  (still byte-identical to `ac06cec`).
- Heartbeat test file SHA-256:
  `8b78d3b7a12a8b31cdac204b7273a86435c469f3a737a886208bce34179a7f20`.
- Live architecture document SHA-256:
  `f461816426d47770c46cb346b0e67ef0f79c201ff15b95fc821c70c767beb20d`.

The two existing failure-fixture tests were witnessed red before the default
reason correction (`oracle_passed` versus `claude_invocation_failed` /
`max_iterations_reached`), then the 21-test focused selection was green.
Earlier verifier hashes remain historical observations, not current-file
identity claims after test/doc reconciliation.
