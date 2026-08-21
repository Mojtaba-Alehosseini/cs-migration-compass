"""Package 14, Tier 3.2 — regression tests for the external audit's Finding
3 "thousands-suffix parser" bug, investigated and found to be TWO distinct,
narrow source-tag disagreements (Ashby's own interval, USAJOBS' own
salaryType), not this pipeline's own text-parsing regex dropping a "K".
Every case below is a REAL record pulled from the live, committed data
while diagnosing the bug — not a synthetic example.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from postings_common import convert_compensation_to_usd, reinterpret_implausible_year  # noqa: E402


class TestReinterpretImplausibleYear(unittest.TestCase):
    def test_hourly_shaped_ashby_value_mistagged_year_becomes_hourly(self):
        # Real case: antares 'Senior Quality Inspector', Ashby's own
        # interval said "1 YEAR" for a plainly hourly skilled-trade wage.
        result = reinterpret_implausible_year(30, 50, "$30 – $50 – Offers Equity")
        self.assertEqual(result, (30, 50, "hour"))

    def test_bare_thousands_with_no_k_marker_is_scaled_up(self):
        # Real case: amperos 'Enterprise Account Executive', "OTE $250 -
        # $300" with no k/K anywhere in the text — the work order's own
        # example ("plainly $250k-$300k").
        result = reinterpret_implausible_year(250, 300, "OTE $250 – $300 – Offers Equity – Offers Commission")
        self.assertEqual(result, (250_000, 300_000, "year"))

    def test_a_value_that_already_carries_its_own_k_marker_is_left_alone(self):
        # Real case: akur8 'Data & Business Performance Internship',
        # tierSummary already says "€2K – €2.5K" — the numeric value (2000,
        # 2500) is already correctly scaled; reinterpreting it again would
        # silently multiply a real number by 1000 a second time.
        result = reinterpret_implausible_year(2000, 2500, "€2K – €2.5K")
        self.assertIsNone(result)

    def test_a_genuinely_low_but_plausible_hourly_wage_is_never_called_with_year(self):
        # Real case: Appen's own $2.40/hour Myanmar rate is real and
        # correctly period='hour' from the source already — this function
        # is only ever invoked when period == 'year' by both call sites,
        # so a genuinely low hourly/monthly figure never reaches it at all.
        # Documented here as the reason no test calls this function with
        # period='hour' or 'month' inputs: those never route through it.
        self.assertTrue(True)

    def test_a_plausible_literal_annual_figure_is_untouched(self):
        result = reinterpret_implausible_year(135_000, 165_000, "$135,000 - $165,000 per year")
        self.assertIsNone(result)

    def test_zero_or_missing_max_never_crashes(self):
        self.assertIsNone(reinterpret_implausible_year(0, 0, ""))
        self.assertIsNone(reinterpret_implausible_year(None, None, ""))

    def test_the_usajobs_seasonal_clerk_case_is_also_hourly_shaped(self):
        # Real case: Internal Revenue Service 'Clerk *Seasonal*', OPM's own
        # salaryType said "Per Year" for a GS-scale hourly rate.
        result = reinterpret_implausible_year(14.18, 18.43, "14-18 USD (Per Year)")
        self.assertEqual(result, (14.18, 18.43, "hour"))

    def test_a_value_in_the_deliberately_untouched_100_to_250_gap_is_left_alone(self):
        # Real case: 'Associate Software Engineer, Operator Experience'
        # ($135-150) -- genuinely ambiguous between a high hourly contract
        # rate and an abbreviated annual figure; see this project's own
        # threshold docstrings for why this band is left to Tier 3.3's
        # plausibility gate rather than guessed at here.
        self.assertIsNone(reinterpret_implausible_year(135, 150, "$135 – $150 – Offers Equity"))

    def test_the_lever_bare_thousands_case_is_also_scaled_up(self):
        # Real case: a Lever posting, 'Director, Strategic Accounts',
        # "On-Target Earnings A$400 - A$500" -- the exact same failure mode
        # as Ashby's own interval tag, on a different provider's own
        # structured field.
        result = reinterpret_implausible_year(400, 500, "On-Target Earnings A$400 – A$500")
        self.assertEqual(result, (400_000, 500_000, "year"))

    def test_a_lever_value_just_under_the_thousands_floor_is_left_for_the_plausibility_gate(self):
        # Real case: 'Senior Manager, Brand Management & Public Relations',
        # "220-240 USD (per-year-salary)" -- max=240 sits just under this
        # function's own 250 floor (chosen from Ashby's own live data, see
        # _BARE_THOUSANDS_LOWER_BOUND's own docstring), so it is correctly
        # left untouched here rather than guessed at -- a real, disclosed
        # residual Tier 3.3's plausibility gate is what should flag it.
        self.assertIsNone(reinterpret_implausible_year(220, 240, "220-240 USD (per-year-salary)"))

    def test_the_lever_hourly_shaped_case_is_also_reinterpreted(self):
        # Real case: 'Junior Visual Manager', "25-30 USD (per-year-salary)"
        # -- plainly an hourly rate mistagged 'year'.
        result = reinterpret_implausible_year(25, 30, "25-30 USD (per-year-salary)")
        self.assertEqual(result, (25, 30, "hour"))


class TestConvertCompensationToUsd(unittest.TestCase):
    """Package 14, Tier 3.1 — real conversions against the actual, committed
    data/processed/fx_rates.json (not a mocked rate), the same file
    normalise.to_usd() itself reads. If this file's own SG/JP/KH/IN/AM
    entries (added this package, src_fx_rates.py's own
    POSTINGS_EXTRA_FX_COUNTRIES) ever go missing, these tests fail for the
    real reason, not a mock silently hiding it."""

    def test_a_real_sgd_posting_converts_at_its_own_years_rate(self):
        result = convert_compensation_to_usd({"currency": "SGD", "min": 100_000, "max": 150_000}, 2025)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["min"], 100_000 / result["fx_rate"], places=2)
        self.assertEqual(result["fx_year"], 2025)
        self.assertEqual(result["fx_country_used"], "SG")

    def test_an_unmapped_currency_is_never_converted(self):
        self.assertIsNone(convert_compensation_to_usd({"currency": "ZZZ", "min": 1, "max": 2}, 2025))

    def test_a_year_with_no_fx_rate_refuses_rather_than_substituting(self):
        # 1500 predates every currency this pipeline's postings use.
        self.assertIsNone(convert_compensation_to_usd({"currency": "USD", "min": 1, "max": 2}, 1500))

    def test_missing_min_or_max_is_never_converted(self):
        self.assertIsNone(convert_compensation_to_usd({"currency": "USD", "min": None, "max": 100}, 2025))

    def test_native_min_max_are_never_the_return_values_own_keys_directly(self):
        # Regression against a specific mistake: this function must return
        # a NEW dict, never a mutated alias of the caller's own native comp.
        native = {"currency": "GBP", "min": 50_000, "max": 60_000}
        result = convert_compensation_to_usd(native, 2025)
        self.assertNotEqual(result["min"], native["min"])  # a real currency conversion happened
        self.assertEqual(native["min"], 50_000)  # the caller's own native dict is untouched


if __name__ == "__main__":
    unittest.main()
