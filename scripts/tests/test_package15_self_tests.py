"""Package 15 — wire every statistical harness's own self-test into CI.

Each package-15 script ships a `--self-test` that constructs a violation for
every rule it implements and asserts the rule FIRES. That is the whole basis
for trusting this package's several "no defect found" conclusions: a check
never observed to fail is not evidence.

Those self-tests were runnable by hand but nothing ran them automatically,
so they could rot silently -- which is precisely the failure mode they exist
to prevent. This runs all five as part of the normal regression suite, so a
change that quietly disables a check fails CI instead of passing it.

Each is invoked as a subprocess rather than imported, because that is how a
human runs them and because it also catches import-time and CLI-level
breakage that an in-process call would not.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent

HARNESSES = [
    ("profile_data", "distributional profiling: shape, tails, heaping, outlier-rule disagreement"),
    ("audit_statistical", "estimator error, BCa bootstrap, Bland-Altman, Deming, injected-noise, Benford"),
    ("classify_titles", "title classifier, including the label-permutation leakage control"),
    ("dedupe_postings", "near-duplicate normalisation and blocking"),
    ("rederive_postings_pay", "software-only re-derivation and bootstrap CI"),
]


class TestPackage15SelfTests(unittest.TestCase):
    def _run(self, name):
        p = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py"), "--self-test"],
                           capture_output=True, text=True, timeout=1800)
        return p

    def test_every_harness_self_test_passes(self):
        for name, what in HARNESSES:
            with self.subTest(harness=name):
                p = self._run(name)
                self.assertEqual(
                    p.returncode, 0,
                    f"{name}.py --self-test failed ({what}).\n"
                    f"stdout:\n{p.stdout[-3000:]}\nstderr:\n{p.stderr[-2000:]}")
                self.assertIn("0 failure(s)", p.stdout,
                              f"{name}.py --self-test did not report zero failures:\n{p.stdout[-2000:]}")

    def test_self_tests_actually_assert_something(self):
        """A self-test that ran no checks would also print '0 failure(s)'.
        Each must report at least four PASS lines, so an empty or
        short-circuited harness cannot masquerade as a clean one."""
        for name, _ in HARNESSES:
            with self.subTest(harness=name):
                p = self._run(name)
                n_pass = p.stdout.count("PASS")
                self.assertGreaterEqual(
                    n_pass, 4,
                    f"{name}.py --self-test reported only {n_pass} PASS lines; a self-test that "
                    f"checks nothing would still print '0 failure(s)'.\n{p.stdout[-2000:]}")


if __name__ == "__main__":
    unittest.main()
