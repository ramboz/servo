# Implementation plan

1. Write the generic regression tests first and witness failure on default main.
   Selectively transplant generic required runtime and consumer changes from
   `f0041335`, including their existing negative controls; do not transplant
   pilot modules, old proof docs, source records, or generated packages.
2. Extract the exact used strict I/O and runtime primitives to
   `skills/design-eval/evidence_io.py` and `evidence_runtime.py`.
   Adapt static observer/snapshot imports and copied closure; preserve bounded
   public argv, schema, visibility, settlement and resource semantics.
3. Integrate the coordinator-supplied clean Vellum helper cut, pin the actual
   six-file transitive closure, and exercise two non-card approved fixtures
   through real preparation, policy review, sealed ordinary installation,
   native evaluation and pure readback. Use only new test-only approvals.
4. Update reusable product docs and architecture, record the authorized boundary
   decision prospectively, regenerate host packages, and verify distribution
   without pilot code present.
5. Run independent compliance/craft/architecture reviews, resolve findings,
   reconcile docs and records, and run a separate reconciliation review.
   Use workflow helpers for lifecycle transitions, never synthetic PASS records.
6. Commit and push only this feature branch; open a clean ready-for-review
   replacement pull request against main. Do not mutate old effort PRs.
