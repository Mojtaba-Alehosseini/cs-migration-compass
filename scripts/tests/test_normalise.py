"""Package 13, Tier 0 — regression tests for scripts/normalise.py, covering
docs/REGRESSION-CATALOGUE.md's R4 (FX year-matching), R5 (sourced hours, not
2080), R6 (comparison_basis's bonus check), R7 (explicit_hours override).

Every test calls the real, currently-shipped function — none of this logic
is reimplemented here. Run directly (`python scripts/tests/test_normalise.py`)
or via scripts/tests/run_all.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import normalise  # noqa: E402


class TestFxYearMatching(unittest.TestCase):
    """R4 — converting a historical figure must use ITS OWN year's rate, not
    a generic/current one. Sweden 2023 median (51,000 SEK/mo), the exact
    case docs/REGRESSION-CATALOGUE.md and REPORT-P9.md cite: the 2023 rate
    (10.6102) gives $4,806.71; the 2025 rate (9.8207) gives $5,193.11 — an
    8.0% error the bug would have produced silently."""

    def test_fx_rate_returns_none_for_an_unmatched_year(self):
        # Rule 1's own contract: no nearby-year fallback exists at all.
        self.assertIsNone(normalise.fx_rate("SE", 1900),
                           "fx_rate() must refuse an unmatched year, never substitute the nearest one")

    def test_fx_rate_differs_by_year_not_flattened_to_one_rate(self):
        r2023 = normalise.fx_rate("SE", 2023)
        r2025 = normalise.fx_rate("SE", 2025)
        self.assertIsNotNone(r2023, "2023 SE rate must be committed for this test to mean anything")
        self.assertIsNotNone(r2025, "2025 SE rate must be committed for this test to mean anything")
        self.assertNotEqual(r2023["rate"], r2025["rate"],
                             "if these ever collapse to the same value, this test can no longer tell "
                             "year-matching apart from the bug it regresses against — replace the years")

    def test_to_usd_uses_the_figures_own_year_not_a_later_one(self):
        result_2023 = normalise.to_usd(51000, "SE", 2023)
        self.assertTrue(result_2023["ok"])
        rate_2023 = normalise.fx_rate("SE", 2023)
        self.assertEqual(result_2023["fx_rate"], rate_2023["rate"])
        self.assertEqual(result_2023["fx_year"], 2023)
        # The bug's own signature: silently using a later year's rate.
        rate_2025 = normalise.fx_rate("SE", 2025)
        self.assertNotEqual(result_2023["fx_rate"], rate_2025["rate"],
                             "to_usd(..., 2023) must not have used 2025's own rate")
        wrong_2025_rate_value = 51000 / rate_2025["rate"]
        self.assertNotAlmostEqual(result_2023["value_usd"], wrong_2025_rate_value, places=2,
                                   msg="the correct 2023-rate conversion must differ from the "
                                       "2025-rate-applied-to-2023-data bug this test regresses against")

    def test_to_usd_refuses_rather_than_substitutes_for_a_missing_year(self):
        result = normalise.to_usd(51000, "SE", 1900)
        self.assertFalse(result["ok"])
        self.assertIn("never substituted", result["reason"])


class TestHoursAnnualisation(unittest.TestCase):
    """R5 — an hourly figure must annualise via a real, sourced hours
    record for its own country and year, never the 2080-hour (40x52)
    convention. Denmark 2024, 470.53 DKK/hour: sourced hours (38.4h/week)
    give 939,554.30 DKK/year; the 2080 convention gives 978,702.40 —
    4.17% too high, the exact bug docs/REGRESSION-CATALOGUE.md's R5 and
    REPORT-P9.md gate 6 both cite."""

    def test_annualise_hour_uses_sourced_hours_not_2080(self):
        result = normalise.annualise(470.53, "hour", "DK", hours_year=2024)
        self.assertTrue(result["ok"], f"expected a sourced DK 2024 hours figure to exist: {result}")
        buggy_2080_convention = 470.53 * 2080
        self.assertNotAlmostEqual(result["value_annual"], buggy_2080_convention, delta=1000,
                                   msg="the sourced-hours result must differ meaningfully from the "
                                       "2080-hour convention this pipeline never uses")
        # The real, hand-verified figure from REPORT-P9.md gate 6.
        self.assertAlmostEqual(result["value_annual"], 939554.30, delta=5)

    def test_annualise_hour_refuses_without_a_sourced_hours_record(self):
        result = normalise.annualise(100.0, "hour", "ZZ-NOT-A-REAL-COUNTRY")
        self.assertFalse(result["ok"])
        self.assertIn("never assumed 2080", result["reason"])

    def test_annualise_month_uses_the_one_fixed_multiplier(self):
        result = normalise.annualise(5000, "month", "SE")
        self.assertTrue(result["ok"])
        self.assertEqual(result["value_annual"], 5000 * 12)

    def test_annualise_year_is_a_no_op(self):
        result = normalise.annualise(70000, "year", "SE")
        self.assertTrue(result["ok"])
        self.assertEqual(result["value_annual"], 70000)


class TestExplicitHoursOverride(unittest.TestCase):
    """R7 — Ireland's own CSO-matched hours (33.6/week) must be preferred
    over the generic cross-country Eurostat figure (40.8/week) when given
    explicitly — the gap that overstated Ireland's mean by a measured
    21.4% before this parameter existed."""

    def test_explicit_hours_changes_the_result_from_the_generic_lookup(self):
        generic = normalise.annualise(30.0, "hour", "IE")
        explicit = normalise.annualise(
            30.0, "hour", "IE",
            explicit_hours={"hours_per_week": 33.6, "year": 2022, "source": "CSO SES06, matched cell"},
        )
        self.assertTrue(explicit["ok"])
        self.assertEqual(explicit["hours_per_week"], 33.6)
        if generic["ok"]:
            self.assertNotEqual(explicit["value_annual"], generic["value_annual"],
                                 "explicit_hours must actually override the generic lookup, not be ignored")

    def test_explicit_hours_refuses_if_incomplete(self):
        result = normalise.annualise(30.0, "hour", "IE", explicit_hours={"hours_per_week": None, "source": None})
        self.assertFalse(result["ok"])
        self.assertIn("never assumed 2080", result["reason"])


class TestComparisonBasisBonusCheck(unittest.TestCase):
    """R6 — total_earnings requires irregular_bonus is True AND
    employer_social_contributions is False, not contribution-status
    alone. Sweden and Finland (bonus excluded) must never be granted
    total_earnings — the exact finding (package 9, F1) that let
    comparison_basis('salary_se', 'salary_es') wrongly report a shared
    total_earnings basis before the fix."""

    def test_sweden_and_spain_no_longer_share_total_earnings(self):
        result = normalise.comparison_basis("salary_se", "salary_es")
        if result["comparable"]:
            self.assertNotIn("total_earnings", result["common_bases"],
                              "Sweden's own bonus-excluded figure must never be treated as "
                              "equivalent to Spain's bonus-included one")

    def test_a_bonus_excluded_source_cannot_express_total_earnings(self):
        # Reads Sweden's own real pay_composition.json entry directly.
        comp = normalise._composition("salary_se")
        self.assertIsNotNone(comp, "salary_se must have a pay_composition.json entry for this test to mean anything")
        self.assertIs(comp.get("irregular_bonus"), False,
                       "this test's own premise (Sweden's bonus is excluded) must hold — "
                       "if pay_composition.json changed this, update the test's premise, not silence it")


if __name__ == "__main__":
    unittest.main()
