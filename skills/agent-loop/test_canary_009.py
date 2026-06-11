"""TEMPORARY spec 009-01 canary — reverted immediately after the red CI run is
captured. Proves the full pytest suite actually GATES ci.yml's `test` job (a
real skill-test failure must redden CI, not be silently skipped). DO NOT KEEP.
"""
import unittest


class Spec009Canary(unittest.TestCase):
    def test_deliberate_failure_proves_ci_runs_the_suite(self):
        self.fail("spec 009-01 canary: deliberate failure — reverted after capture")
