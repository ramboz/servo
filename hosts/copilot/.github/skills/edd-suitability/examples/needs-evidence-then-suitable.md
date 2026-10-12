# Example spec — edd-suitability re-run dogfood (015-04)

A deliberately EDD-shaped spec used to demonstrate the
`needs_evidence → suitable` flip when evidence is acquired. Its acceptance
criteria classify into deterministic check families (so `n_evaluable >= 1`),
which means suitability turns on whether the target has a compilable test/CI
signal:

- with **no** test/CI signal → `needs_evidence` (the blocking `oracle_signal` gap);
- after a test command is added → `suitable`.

## Acceptance Criteria

1. The CLI exits 0 on a successful run.
2. The output file exists at the documented path after the command runs.
3. The generated manifest contains the version string.
