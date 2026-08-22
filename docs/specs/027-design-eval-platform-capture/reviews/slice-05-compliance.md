---
slice: 027-05 — blessed iOS capture provider
pass: compliance
verdict: pass
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit 36f1aa9 against slice-05 ACs
---

PASS — all five ACs satisfied.

- AC1: `capture.transport: "ios"` captures via `xcrun simctl io <target>
  screenshot <shot_path>`; target precedence `capture.ios.udid` →
  `SERVO_DESIGN_EVAL_IOS_UDID` → `"booted"`; absent `xcrun` fails closed up front.
- AC2: crop in place by `capture.ios.crop` via the shared stdlib cropper;
  out-of-bounds / non-integer fail closed.
- AC3: optional per-screen `deeplink` → `xcrun simctl openurl`, bounded settle.
- AC4: fail-closed on xcrun-absent / non-zero screenshot / MISSING OUTPUT FILE /
  bad crop; ledger `capture_provider: "ios"` + resolved screenshot argv in
  `capture_command`; `not_attested` provenance.
- AC5: `capture.ios` proven out of `definition_hash`.

Tests feature-bearing; `test_capture_ios_not_in_definition_hash` is the one
regression-guard. The disclosed deferral (no Xcode/simctl on this machine →
stubbed simctl, live smoke deferred) is honestly reflected in the DoR and matches
the committed stub-level tests — not treated as a defect.
