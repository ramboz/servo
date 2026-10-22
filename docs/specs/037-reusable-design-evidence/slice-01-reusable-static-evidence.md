---
status: RECONCILED
dependencies: [adr-0046]
last_verified: 2026-10-22
arch_review: true
claimed_by: generic-design-evaluator
---

## Slice 037-01 - reusable static evidence

**Goal:** A project can prepare, independently approve, install, evaluate, and
read back a finite static source contract through the native required gate,
without shipping any pilot component implementation.

**DoR:**
- Owner-authorized retirement and clean replacement scope is recorded in spec 037.
- Base-main and original source cut have been inspected without changing old worktrees.
- Shared helpers and unchanged public command/output shape have been sent to
  the coordinating session for the Vellum and Jig successors.
- The clean producer helper cut must be verified before final pins and
  end-to-end source approval tests are sealed.

**Acceptance Criteria:**

1. **Required evidence is native and additive.** Ordinary overlay installation
   opts into the generic required policy; a required FAIL yields native exit
   1 even with perfect quality or threshold zero, and unavailable/unknown
   required evidence yields exit 2. No opt-in preserves pre-existing v1 gate
   behavior. Opaque command assertions, refusal codes, duplicate/missing
   inventory rejection, frozen code/argv/policy pins, and complete output
   references remain fail-closed.
2. **Consumers keep native authority.** Loop/checkpoint/resume, hook,
   planner, and heartbeat/triage paths consume the generic native verdict,
   including preserved immutable component/output references. Pure readers
   hash/read only, do not spawn subprocesses, acquire browser observations,
   compare values, rescore quality, or replace a prior claim with a new one.
   This strict boundary is the native `gate_consumer.read` seam. The separate
   auxiliary `verify-current` retains existing bounded local OS/interpreter
   metadata and fixed source-Git HEAD queries; it must not acquire, evaluate,
   compare, rescore or execute arbitrary commands. Producer freshness/runtime
   semantics and hashes remain unchanged.
3. **Static runtime is component-agnostic.** Static manifests determine IDs,
   roles, CSS-only bindings, resource inventory and environment. Only used
   strict I/O/hash/no-follow/closure helpers go into `evidence_io.py`; only
   used startup/native-link/run-id/summary helpers go into
   `evidence_runtime.py`. The copied static helper closure is precisely
   those two plus `static_contract.py` and `static_snapshot.py`.
   No runtime imports, copies, vendors, invokes, or packages a `card_*`
   module, pilot application, fixed normal/open/band/title/subtitle inventory,
   or fixed model/batch/quality-threshold policy. The existing general
   quality engine remains unchanged.
4. **Source authority remains live and exact.** The actual clean successor
   helper closure is pinned and copied, including all six named producer
   files in spec 037 and their import paths. `design_input.py` is a real
   neutral extraction, not an alias. The meanings of
   `vellum-confirmed-source/0.2`, `static-css-subset/1`, normalizers,
   tolerances, and original-source freshness are preserved. Changed helper
   bytes require a new approval epoch; no old approvals are relabelled,
   rebound or silently made archive-only.
5. **Two genuinely different non-card workflows work.** Tests use the
   actual public prepare -> independent review/approve -> ordinary native
   install -> evaluate -> accept/read path for two different non-card
   manifest/role/resource/environment shapes, with explicit test-only new
   source approvals. Each shape demonstrates native PASS/FAIL/UNKNOWN
   (0/1/2), required-vs-quality precedence, independent current delivery and
   original-source drift, output tampering, and no-subprocess native readback.
   Tests must not bypass preparation, approval, install, source inspection or
   runtime closure checks using mocks; small synthetic fixtures are allowed.
   No application-success, historical pilot-rerun or model-judge claim.
6. **Distribution is closed and honest.** Canonical, all generated host
   packages, and project-local vendoring retain a complete import closure
   with pilot modules/fixtures absent. Existing required+quality negative
   controls remain effective. Product docs describe the bounded reusable
   flow and residuals, not pilot archives. Original effort records, proof
   bodies, main, old pull requests and worktrees remain untouched.

**DoD:**
- [x] Every acceptance criterion is exercised by named tests, with witnessed
      red -> green behavior and substantive failure controls.
- [x] Targeted tests and repository CI gates preserve existing behavior.
- [x] Independent compliance, craft and architecture reviews pass.
- [x] Deviation log and reconciliation sweep are complete and honest.
- [x] Reconciliation review passes and relevant documentation is current.

**Anti-horizontal-phasing check:** One delivered path turns project-owned
approved source facts into immutable native verdicts and pure readback without
a pilot-specific runtime.

### Close-out (post-DONE)

- [ ] Status board regenerated and checked.
- [ ] Primer surfaces checked; no stale active-spec detail retained.

### Deviation log (after reconciliation)

1. **Prospective replacement, not a historical rewrite.** Generic canonical
   runtime and tests were selected from the inspected effort cut; old feature
   history, pilot modules, archived proof bodies, specs 035/036 and historical
   ADR-0045 were not imported or amended. The new decision uses ADR-0046 to
   avoid historical identity ambiguity. The owner explicitly accepted its
   exact proposed revision before the normal public acceptance transition.
2. **Minimal extraction and exact source ownership.** Twelve existing I/O
   function bodies and four used runtime helpers moved into two neutral modules.
   Static comparison, snapshot, visibility and resource semantics remain bounded.
   The six actual clean producer helpers match the reviewed Vellum cut; new
   installation checks the packet's approved tooling epoch rather than silently
   accepting a historical packet under new bytes. General quality engine unchanged.
3. **Reader premise clarified prospectively.** Initial extra probes and the
   first compliance pass interpreted auxiliary readback as subprocess-free.
   They exposed existing OS/interpreter and source-Git metadata queries.
   The coordinator clarified AC2/AC5 without changing accepted ADR text or
   runtime/source semantics: native readback stays strictly subprocess-free;
   auxiliary currentness remains read-only with bounded metadata queries and
   no acquisition/evaluation/comparison/rescoring. Original red results remain
   in `tasks.md`; this was an invalid test premise, not a claimed runtime fix.
4. **Actual native-reader defect repaired.** Subsequent independent review
   found cache writes and cached-code consumption in identity-helper imports,
   then transitive import cache writes. Cold/forged/transitive controls failed
   before repair. Verified source is now compiled in memory with transitive
   cache writes suppressed and the caller's policy restored even on failure.
   The existing pure content-hash helper remains the authority; no grading added.
5. **Project-file preservation repaired.** Craft found unconditional overwrite
   of `spec/static.md` and premature output creation. Destination/no-follow
   preflight, source/bindings/runtime validation before creation and exclusive
   writes now preserve project content. Publication is deliberately not a
   multi-directory transaction: I/O interruption or concurrent source change
   can leave unapproved partial output. Recovery uses a fresh target, never
   automatic deletion/overwrite; this residual is documented.
6. **Fresh synthetic epochs and honest coverage.** The changed static helper
   received fresh two-shape TESTONLY source/policy/native epochs. Earlier
   acquisitions were retained untouched, not rebound or retrospectively called
   reviewed. New positives exercise native 0/1/2, source/delivery drift, tooling
   changes, output tamper and reader controls through real public entry points.
   They establish product integration only, not real-app or visual approval.

### Reconciliation sweep

**Baseline and deliberate exclusions:** This worktree started at
`dc56bd3397c21224866cba639adb7c5a334bcec0` (`origin/main`), not the stale local
`main` ref. The review helper's automatic `git diff main...HEAD` inventory
therefore includes inherited changes and only committed reservations, while
omitting the then-uncommitted implementation. Its inherited set is precisely
`git diff --name-only main...dc56bd3397c21224866cba639adb7c5a334bcec0`;
those paths are excluded from this slice unless independently changed against
that starting point.

In particular, `CONTRIBUTING.md`, `CHANGELOG.md`, root plugin-version manifests,
marketplace/release configuration and release workflows, product vision,
refinement TODO, closed specs 028-034 and their accepted decision/review records
are inherited baseline, not transplanted or edited here. Targeted diffs against
the starting point verified the front-door/release/vision/refinement exclusions
are unchanged. The actual scope is the diff against that starting point plus
the enumerated new files, not the stale local-main inventory. The initial
provisional *new* ADR-0045 reservation was corrected to new ADR-0046; no
historical ADR-0045 record was imported or modified.

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `updated` | Routes reusable static evidence separately from visual quality; no pilot proof export. |
| `docs/architecture.md` | `updated` | Records native v2 opt-in authority, neutral closure, bounded runtime and reader distinctions with source citations. |
| `docs/product-vision.md` | `no-op` | Unchanged against the actual starting point; inherited local-main difference excluded. Existing framing remains correct; no use-case layer exists. |
| `docs/decisions/README.md` / ADR-0046 | `updated` | New owner-accepted prospective decision indexed; old records unchanged. |
| `docs/specs/README.md` | `updated` | Regenerated from actual lifecycle records; no hand-authored status. |
| Skill docs / static example / required-policy example | `updated` | Explain reusable preparation/approval/install/native authority, metadata-query boundary, fresh epochs and safe interruption recovery. |
| Generated `hosts/` / legacy vendor contract | `updated` | Regenerated all three hosts from canonical source; neutral and native import closure verified without pilot files. |
| Canonical runtime/check/consumer sources and tests | `updated` | Generic required/native consumers and four-helper static path, their directly related tests, and no pilot runtime. |
| New spec 037 and its review records | `updated` | Prospective scope, actual independent review/recovery evidence and derived lifecycle only. |
| `docs/memory/learnings.md` | `updated` | One bounded learning records historical IDs and fresh approval epochs. |
| Primer files / templates | `updated` | No root CLAUDE/AGENTS files exist; directly affected runner/judge and hook template carry native verdict authority. |
| `docs/inbox.md` | `no-op` | Absent; no unrelated inbox created. |
| `docs/refinement-todo.md` | `no-op` | Unchanged against actual starting point; inherited local-main difference excluded. Native actual-value/autonomy residuals remain separate. |
| `docs/conventions.md` | `no-op` | Absent in this plugin-only scaffold; no new convention file needed. |
| Team-memory advisory | `no-op` | Coordinator directed skip; no people file or suppression setting. |
| Old specs/decisions/PRs/worktrees | `no-op` | Preserved; no main push, original-PR mutation or history transplant. |
| Contributing/changelog/version manifests/release configs and workflows | `no-op` | Explicit inherited-baseline exclusions above; no release 39 or unrelated baseline work added by this slice. |
| Validation | `updated` | Final CI 2536 passed/8 external opt-ins skipped; actual runtime workflows and auxiliary/browser controls run separately, with synthetic-only claims. |

**Leanness:** No registry, language, state engine, sampler or quality-policy
expansion. The four-helper observer closure and existing generic gate/consumer
mechanisms are the delivered path; interruption recovery remains explicit.
