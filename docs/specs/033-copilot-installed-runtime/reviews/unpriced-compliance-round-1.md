# Unpriced monetary compliance, round 1 (2026-10-12)

Independent `jig:reviewer` unpriced-compliance returned **needs-changes**.
Upfront/direct refusals, marker validation and install/refreeze sequencing held;
two actual in-flight paths remained incomplete.

1. Heartbeat's unpriced terminal early return discarded an already-invoked
   child's actual outcome/known Claude spend. Persist that real outcome before
   halting, unlike a genuine pre-dispatch refusal with no child outcome.
2. Goal/Routine per-turn commands invoked raw vendored gate.py and bypassed loop
   gateway rechecks. Add explicit USD-context enforcement to those actual gate
   calls while preserving standalone attended gate behavior; final check is too
   late to prevent an intervening unpriced invocation.

The implementer is addressing both with regression tests; passing earlier
840 tests/17 subtests did not prove these missing call sites. No historical API
accounting, arbitrary-oracle financial attestation or native transport completion
was certified by this review.
