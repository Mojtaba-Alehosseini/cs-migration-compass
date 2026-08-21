"""Package 13, Tier 0/5 — regression test for docs/REGRESSION-CATALOGUE.md's
R18: build_wage_distribution.py's own _pick() used k.endswith(suffix), which
matches Norway's real avtalt_mean_nok_month when asked for mean_nok_month
(the LONGER key ends with the shorter one) — genuinely ambiguous between two
different real pay bases (bonus-included Manedslonn vs. bonus-excluded
AvtaltManedslonn), resolved only by accidental dict iteration order. Found by
adversarial review, not anticipated; _extract_no()/_extract_fi() already
worked around it for their own fields by not calling _base_obs() at all, but
the shared helper itself stayed unfixed — this tests the helper directly, so
a future extractor built the ordinary way (calling _base_obs(), the way
_extract_se/_extract_dk/others already do) can't inherit the same ambiguity.

Run directly (`python scripts/tests/test_wage_distribution_extraction.py`)
or via scripts/tests/run_all.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_wage_distribution as bwd  # noqa: E402


class TestPickIsExactNotSuffixMatched(unittest.TestCase):
    def test_the_original_ambiguity_reproduced(self):
        # Norway's own real shape: the SAME row publishes both bases.
        row = {"avtalt_mean_nok_month": 71000, "mean_nok_month": 77420}
        self.assertEqual(bwd._pick(row, "mean_nok_month"), 77420,
                          "must return the row's own exact key, not a longer key that happens to end with it")

    def test_key_order_does_not_change_the_result(self):
        # The old bug's own failure mode was iteration-order-dependent —
        # reversing insertion order must not change which value comes back.
        row = {"mean_nok_month": 77420, "avtalt_mean_nok_month": 71000}
        self.assertEqual(bwd._pick(row, "mean_nok_month"), 77420)

    def test_a_genuinely_missing_key_still_returns_none(self):
        row = {"avtalt_mean_nok_month": 71000}
        self.assertIsNone(bwd._pick(row, "mean_nok_month"))

    def test_base_obs_extracts_the_right_basis_for_a_norway_shaped_row(self):
        row = {"mean_nok_month": 77420, "avtalt_mean_nok_month": 71000,
               "median_nok_month": 75000, "avtalt_median_nok_month": 69500}
        obs = bwd._base_obs("month", "NOK", 2025, row, "nok_month")
        self.assertEqual(obs["mean"], 77420)
        self.assertEqual(obs["median"], 75000)


if __name__ == "__main__":
    unittest.main()
