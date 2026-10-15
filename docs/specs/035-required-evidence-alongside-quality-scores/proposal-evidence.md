# Proposal authoring evidence

This is pre-implementation evidence for Proposed ADR-0044 and DRAFT specs
035/036, not implementation compliance, accepted policy or pilot success.

## Grounding and reservations

On 2026-10-14 the personal GitHub account confirmed push/admin permission,
unprotected default main, no branch rules and no open Servo PRs. Main was
`067ef5092d3c3ebe7d55a4e27610d7fe1d688463`. No global account was switched or
token written. Installed Jig helpers reserved stubs on origin/main:

| Artifact | Helper | Reservation commit |
|----------|--------|--------------------|
| ADR-0044 | `adr.py new required-constraints-cannot-be-averaged-away --title "Required constraints cannot be averaged away"` | `b44cc7d` |
| Spec 035 | `workflow.py new required-evidence-alongside-quality-scores` | `4b2a70b` |
| Spec 036 | `workflow.py new deterministic-design-evidence` | `dc56bd3` |

The feature worktree fast-forwarded to these stubs with `git merge --ff-only
origin/main`; no main-checkout files were read or written. A session-local
prepare-commit hook appended the required Co-authored-by trailer to helper
reservation commits; no repository/global hook configuration was changed.
The publication preflight re-fetched main at `dc56bd3` and found only the
unrelated release-please PR #39 open; no competing proposal/number owner appeared.
Root workflow/conventions/AGENTS/glossary files were absent; current
scaffold.json, vision, architecture, status boards, CONTRIBUTING, refinement
items and relevant existing owners supplied project framing. The vision has
no Use cases section, so no new vision entries were invented.

The new specs cite inspected canonical code seams rather than asserting new
measurement/gating capability exists. Parent supplied the Vellum source-
grounding corrections and draft owner IDs; this session did not inspect or
edit sibling checkouts. Those upstream artifacts require published revision
pins and approval before implementation readiness.

## Fresh frame critique

Installed `workflow.py frame-review-needed` returned `true` for ADR-0044 and
each of 035-01, 035-02, 036-01 and 036-02, matching their declared flags.
`review.py frame-critique` built one target-specific prompt for each; the four
spec invocations supplied spec/plan/tasks as deliverables. One fresh-context,
read-only `jig:reviewer` (`servo-proposal-frame`) applied all five prompts to
the cohesive proposal, without author conversation or implementation work.

| Target | Verdict | Load-bearing assumption examined |
|--------|---------|----------------------------------|
| ADR-0044 | pass | Consumers must retain required authority alongside scalar scores. |
| 035-01 | pass | Single-invocation structured results must be complete and race-safe. |
| 035-02 | pass | All authority-bearing consumers must preserve the veto and references. |
| 036-01 | pass | Live card observations must bind to the actually served build. |
| 036-02 | pass | Portable raster engine and meaningful thresholds need independent validation. |

No specific framing issues were reported. Passing the frame does not resolve
the named assumptions. Durable per-target verdicts are recorded by
`review.py record-review --pass frame-critique` in the standard review paths;
no acceptance or implementation lifecycle transitions were performed.

After the critique, parent supplied Jig's provisional ADR-0065/spec119 IDs,
then their publication in draft
[ramboz/jig#242](https://github.com/ramboz/jig/pull/242) at
`c118595ca122351f4f213d29ff5f06302321c2b0`. Pending-owner references were updated
to that published PR/pinned snapshot; output semantics, scope, assumptions and
acceptance criteria were unchanged. The consumer remains Proposed/DRAFT and
must be reconciled before owner acceptance.

## Authoring validation

Runtime root used: `/Users/ramboz/.copilot/installed-plugins/jig/jig/.github`
(`JIG_ROOT` in these command recipes).

```bash
python3 "$JIG_ROOT/scripts/spec_lint.py" \
  docs/specs/035-required-evidence-alongside-quality-scores/spec.md --strict
python3 "$JIG_ROOT/scripts/spec_lint.py" \
  docs/specs/036-deterministic-design-evidence/spec.md --strict
python3 "$JIG_ROOT/skills/spec-workflow/workflow.py" status-board .
python3 "$JIG_ROOT/skills/spec-workflow/workflow.py" check-board .
python3 "$JIG_ROOT/skills/adr-workflow/adr.py" index docs/decisions
python3 "$JIG_ROOT/skills/adr-workflow/adr.py" check-index docs/decisions
git diff --check
```

Both strict spec lints found no acceptance-criterion contradictions; board and
index audits were clean. Index regeneration emitted pre-existing no-description
warnings for ADR-0024/0026, which were not edited. The existing spec-oracle
`markdown_links` primitive checked all 17 new proposal/review Markdown files;
all local links resolved. The four `review.py check-reviews <spec.md> <slice>
--stage READY_FOR_REVIEW` commands validated recorded frame evidence and cleared
for 035-01, 035-02, 036-01 and 036-02; **the slices were not transitioned**.
Artifact-only scope was checked against refreshed main;
source, generated hosts, conventions, Accepted ADRs and closed specs were
unchanged. No unrelated full source suite or plugin installation was performed.

Helper compatibility notes: the initial spec frame prompt invocation required
explicit deliverable arguments (corrected); the installed `subagent-type`
command does not accept `frame-critique` (the available native `jig:reviewer`
was selected directly). No helper or global plugin was changed to work around
these authoring-interface differences.

## Remaining readiness decisions

Parent reconciles Vellum's published approved input-contract revision and
Jig's attestation owner, plus exact Servo output field names and distinct
version namespaces. Vellum must supply fresh approved closed/open card captures
and complete bindings; the pilot must prove live observations/served-build
identity. Regional engine/license/portability/calibration are later 036-02
readiness work, not a blocker for publishing this draft or a selected dependency.
Native Copilot unattended Servo execution remains explicitly unsupported.
