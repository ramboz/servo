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

## Initial fresh frame critique

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
version namespaces at proposed C0; a published proposal is not executable input
approval. C0 also pins serialization/digest domains/test vectors, required
comparison inventory and served/current-delivery closure predicates, without
runnable-all-consumers proof. Vellum013-01 must supply C1 approved normal/open
source artifacts and bindings while it can remain IN_PROGRESS; upstream DONE
and the future observer are not readiness prerequisites. The observer and actual
served/current-delivery byte linkage are 036-01 implementation obligations.
Owners must approve the proposed per-property tolerance/normalization, missing-
tolerance refusal and controlled immutable local-bundle boundary. Regional engine/license/portability/calibration are later 036-02
readiness work, not a blocker for publishing this draft or a selected dependency.
Native Copilot unattended Servo execution remains explicitly unsupported.

## Alignment revision (2026-10-14)

The coordinating parent supplied a new bounded authoring assignment after
cross-repository review found circular readiness, incomplete pilot comparisons
and ambiguity over component-versus-overall completion authority. The earlier
frame passes describe the initial frame only; this revision receives new
evidence. No implementation, owner approval or lifecycle advancement occurred.

- Proposed order is now C0 contract/identity agreement, then independent
  standalone 035-01 and Vellum013-01 C1 input preparation, then 036-01 observer/
  local-bundle/overall-gate proof, Jig119 preserved-run attestation and Vellum
  integration close-out. Preparing open references does not complete 013-02.
- Parent verified source literals `Trailhead`, `hiking route planner`, `opened`.
  Exact normal/open text and normalized computed CSS-family declaration are
  required, without rendered-font-face inference. Derived DOM geometry proposes
  inclusive +/-1 CSS px; declared size/weight remain zero tolerance; normalized
  strings/colors are exact. Missing required tolerance/comparator refuses.
  All policy choices remain proposed pending owner review.
- Component `pass` is component-only. The installed overall gate-payload policy
  verdict binds immutable component records by run/digest and controls completion.
  Component-pass/quality-fail produces overall failure and Jig cannot attest it.
- Canonical source/policy approval and complete input/output closure are
  agreement prerequisites; actual browser-served bytes/current-delivery proof
  is implementation work under a proposed controlled immutable local-bundle
  transport. Checkout hashes or echoed manifest IDs do not prove that linkage.
- Live proposal reads confirmed Vellum draft
  [PinkException/vellum#50](https://github.com/PinkException/vellum/pull/50) at
  `7f4c06077318859c0aabec33d00c2eebd6cba74f` and Jig draft
  [ramboz/jig#242](https://github.com/ramboz/jig/pull/242) at
  `c118595ca122351f4f213d29ff5f06302321c2b0`. Neither pin is owner acceptance;
  pending sibling alignment amendments still require later reconciliation.

One new fresh-context read-only `jig:reviewer` (`servo-alignment-frame`) applied
five newly generated installed-helper frame-critique prompts. ADR0044 and all
four slices returned **pass**, with no specific framing issues reported.
The new verdicts replace the same standard evidence paths through
`record-review`; git preserves the earlier verdict history. Review confirms
the frame, not C0/C1 approval or live runtime success.

Post-revision validation reran both strict spec lints (all four slices clear),
all four `check-reviews --stage READY_FOR_REVIEW` checks (clear, no transitions),
board/index audits (clean, same pre-existing ADR0024/0026 warnings), existing
spec-oracle local-link checks (17 files pass), whitespace and 17-path artifact-
only scope checks. ADR remains Proposed; both specs/four slices remain DRAFT.
No unrelated source suite or plugin installation was performed.

## Required band-binding correction (2026-10-14)

Focused coordinator verification found one remaining comparison-identity
mismatch: Servo named card width while Vellum C0 requires band width.
This session retrieved and read the actual producer
[C0 appendix at `453945cdc0402841b6d1886b15fdbdcf81f74c98`](https://github.com/PinkException/vellum/blob/453945cdc0402841b6d1886b15fdbdcf81f74c98/docs/specs/013-design-to-oracle-handoff/input-contract-pilot.md).
Its proposed 14-ID inventory per state includes `normal-band-width` and
`open-band-width`; equal 240px declarations do not make band/card interchangeable.

Spec036, slice036-01 and its plan/tasks now require state-specific band width
through confirmed source `#band` and approved app bindings. Extra card width
is separately non-required diagnostic evidence, never required coverage.
Controls keep card240px/band242px and require failure, and require refusal for
missing band binding/card-only width evidence. Geometry boundaries measure
the band. Generic `sans-serif` and named `"sans-serif"` retain distinct token
semantics; no actual font-face claim or consumer-owned normalizer was introduced.
Vellum owns correction of its still-overbroad quoted-family vector and C0
revision approval.

A new fresh-context read-only `jig:reviewer` (`servo-band-binding-frame`) applied
the affected installed-helper 036-01 frame prompt against the revised files
and exact producer appendix: **pass**, no consumer-frame issues reported.
Its durable standard verdict replaces the prior 036-01 frame artifact; git
retains history. No other policy, readiness order, authority, lifecycle state
or implementation surface changed.

Affected validation passed: strict spec036 lint (both slices), 036-01
`check-reviews --stage READY_FOR_REVIEW` without transition, board/index
audits, all17 proposal/review local-link checks, whitespace, unchanged
Proposed/DRAFT states and the exact six-path artifact-only scope. Existing
ADR0024/0026 index warnings remain untouched; no source suite or dependency
installation was needed for this authoring correction.

## Owner-directed acceptance (2026-10-14)

The owner selected "Approve the ADRs and pilot contract; start implementation
(Recommended)", relayed by the coordinating parent, for Vellum ADR0011/C0 at
`a538a2b474a9f3e1119379aba44257d319e1c276`, ServoADR0044/proposal at
`91f8d97d2d6f7c358a5de93c22aa143fd417d07c` and JigADR0065/proposal at
`e83ad795e5bc692ea9ac4e2a25c9b6923e26522e`. The exact input appendix and Jig
proposal were retrieved at those immutable snapshots; no peer checkout or
global account was changed.

Installed `adr.py accept 0044` cleared against current genuine frame evidence.
A git comparison confirmed ADR0044's decision body was unchanged since the
reviewed alignment revision. The acceptance helper changed only frontmatter
status, status mirror and verification date; `adr.py index` regenerated the
derived status. No semantic amendment, helper bypass or PR merge occurred.
The new [owner-acceptance record](owner-acceptance.md) names the approval scope,
peer C0 reference, explicit exclusions and standalone035-01 readiness findings.

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s
skills/spec-oracle -p test_checks.py -k Command` passed all17 existing
command/generated-artifact tests. The035-01 frame evidence still clears
`check-reviews --stage READY_FOR_REVIEW`; no lifecycle transition was made.
Standalone035-01 needs concrete accepted-semantics carrier/field mapping and
normal readiness review, not completed Vellum, source captures, a future
observer or already-working installed-result/race proof.

Source-capture/C1 approval and live quality-policy approval remain separate
future actions. No source implementation began in this acceptance turn.

Acceptance metadata validation passed both strict spec lints, board/index
audits, all18 proposal/review local-link checks and whitespace checks. A byte
comparison against the approved Servo snapshot verified the ADR changed only
the three installed-helper acceptance metadata fields; decision content is
unchanged. Specs/four slices remain DRAFT and the complete change is five
metadata/documentation paths, including the new approval record. Existing
ADR0024/0026 index-description warnings remain untouched.
