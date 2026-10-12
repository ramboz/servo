# Native review corrections, round 2 (2026-10-12)

Independent native compliance re-review passes034-04/06;034-05 still
needs-changes because cyclic candidate symlink resolution escapes env_error on
Python3.9. Generic emitted/content/design live proofs, usage/injection/control/
snapshot corrections are now acknowledged separately from fake CLI fixtures.

Independent craft passes034-04/05, but034-06 needs-changes: relative executable
override can probe one binary and invoke another after cwd changes, recording
the wrong runtime identity. Resolve one absolute executable for both calls and
verify changed-cwd regression.

Nonblocking nits: native authoring test should enforce proposed/reused-session
protections; API hash compatibility needs a literal historic digest; legacy
generic acquisition prose must not claim all native real scoring still fails.
All are being addressed without weakening native safety or old API contracts.
