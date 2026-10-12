# Unpriced component frame, round 1 (2026-10-12)

Independent `jig:reviewer` unpriced-budget-frame returned **needs-changes** for
Proposed ADR0041 and DRAFT033-08.

The monetary-risk premise is grounded, but installation-only registration misses
a supported lifecycle: already-installed API/CLI components can receive native
configurations and re-freeze without reinstalling. A structurally valid absent
marker could then let a USD-bounded caller fund unpriced native judging.

Revised proposal: supported re-freeze must synchronize the same registration,
marking before native approval activates and clearing after successful non-native
approval, or refuse activation pending registration. Do not register uninstalled
standalone definitions just because they freeze. Verify both transport directions
and failed-freeze behavior. No arbitrary configuration scan or historical API
accounting repair is required.
