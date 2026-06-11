"""TEMPORARY spec 009-02 canary — reverted immediately after the red CI run is
captured. The unused `os` import below is a deliberate F401 to prove the
`Lint (ruff)` step BLOCKS ci.yml. Not a test_*.py, so pytest never collects it,
which keeps the suite green and isolates the lint gate as the sole failure.
DO NOT KEEP.
"""
import os
