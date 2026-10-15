# Plan: required evidence alongside quality scores

Artifact-authoring proposal only. Both slices remain DRAFT; no implementation
or decision acceptance has started.

## Readiness

Accept ADR-0044 only after parent aligns the Vellum input owner, Servo output
version/names and Jig attestation consumer. Run the normal Jig framing and
readiness ceremony rather than treating this draft PR as approval.

## 035-01: installed required gate

Use existing checks and `checks.json` approval for required membership; extend
the approved content hash to all new policy fields. Reuse scalar functions,
component directories, SEED splicing and ledger primitives. Select a minimal
run-bound result carrier with atomic publication and validation; no new
registry/DSL, no command reruns, no latest-row lookup.

Cover template/scaffold and spec-oracle installers, shared/vendored engines,
gate summary/version selection and all generated installed packages. Preserve
existing no-policy oracles byte-for-byte where possible and behavior-for-
behavior where rendering differs; custom drivers require explicit supported
migration. Prove the high-score veto through the installed gate before 036-01
uses it.

## 035-02: consumers

Start from the bounded canonical inventory in spec.md, then enumerate actual
readers before edits. Cover loop/goal gate invocation and sentinel handling,
history/resume/plateau/final summaries, hook advice, execution-plan references,
heartbeat copy/verify/handoff/triage and agent prompts. Regenerate host packages
and validate supported project vendors. No native Copilot autonomy work.

## Verification and reconciliation

Use existing targeted gate/scaffold/overlay and consumer tests, plus installed
positive/negative controls. Record witnessed red-to-green and independent
compliance/craft/architecture evidence during implementation. Sweep live
architecture, README/skills, templates, package/install documentation and
report consumers; do not amend closed specs/Accepted ADRs in this proposal.
