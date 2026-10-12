---
slice: 034-01 - installed-oracle
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-10-12T16:56:29Z
prompt_source: review.py arch-review docs/specs/034-copilot-installed-runtime/spec.md 034-01 skills/scaffold-init/scaffold.py scripts/servo_root.py scripts/build_host_packages.py scripts/test_copilot_installed_runtime.py --richer-skill arch-review
substrate: not-shown
applied_skill: none
---

VERDICT: pass

REASONING:
Runtime/package/project-owned oracle separation, failure handling, compatibility
and leanness show no architecture blocker. Rendering stays source-owned without
runtime Jig coupling. Recorded native evidence is LIVE local loading and clean
consumer execution, whereas installed layouts/zips remain fixture/static proof.

SPECIFIC ISSUES:
- [strength][impl] Executing native runtime and parent manifest authority.
- [strength][impl] Explicit project/store/known-package fallback precedence
  without a live-config discovery framework or unproved SessionStart publisher.
- [strength][impl] Canonical helpers/unrendered templates use existing builder.
- [nit][impl] Architecture said two committed packages. Corrected to three.

RECONCILIATION NOTES:
No scoped implementation deviation. Preserve remote/cloned-store install
uncertainty rather than inferring it from local evidence.

Source: independent jig:reviewer delivery-architecture actual envelope.
