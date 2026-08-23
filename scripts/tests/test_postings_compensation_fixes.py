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
    """Package 14, Tier 3.2, second revision — an independent adversarial
    review found the original "bare thousands -> x1000" rule had already
    produced at least one real, wrong published value (HireHangar's own
    "Underwriter"/"Underwriting Analyst" postings, genuinely $500-700/month
    like ~90 sibling postings from the same employer, turned into a
    fabricated-looking $500,000-$700,000/year), and that the surviving
    hourly rule was being applied to non-USD currencies its own threshold
    was never validated against. The x1000 rule is gone; the hourly rule
    is USD-only. Every case below is a real record pulled from the live,
    committed data — not a synthetic example."""

    def test_hourly_shaped_ashby_value_mistagged_year_becomes_hourly(self):
        # Real case: antares 'Senior Quality Inspector', Ashby's own
        # interval said "1 YEAR" for a plainly hourly skilled-trade wage.
        result = reinterpret_implausible_year(30, 50, "$30 – $50 – Offers Equity", "USD")
        self.assertEqual(result, (30, 50, "hour"))

    def test_the_hirehangar_regression_a_bare_number_is_never_scaled_up_any_more(self):
        # Real case, and the reason the x1000 rule was removed entirely:
        # HireHangar's own "Underwriter" and "Underwriting Analyst"
        # postings read raw_text "$500 - $700", no "per month" suffix --
        # but every one of that employer's own ~90 OTHER postings uses the
        # identical "$X - $Y per month" shape at the same magnitude. The
        # old rule could not tell this apart from amperos' own genuine
        # "OTE $250 - $300" (thousands) case; both are a bare number with
        # no k/K marker in the 250-12,000 band. Now: never rescaled, at
        # any magnitude in that band, regardless of what the raw text says
        # beyond that -- it is left for Tier 3.3's own plausibility gate.
        self.assertIsNone(reinterpret_implausible_year(500, 700, "$500 – $700", "USD"))
        # amperos' own genuine OTE case -- previously scaled to
        # $250,000-$300,000, now ALSO correctly left untouched, on
        # principle: this function no longer tries to distinguish the two
        # real interpretations by magnitude alone, because it cannot do so
        # reliably (that is the whole finding).
        self.assertIsNone(reinterpret_implausible_year(250, 300, "OTE $250 – $300 – Offers Equity – Offers Commission", "USD"))

    def test_a_value_that_already_carries_its_own_k_marker_is_left_alone(self):
        # Real case: akur8 'Data & Business Performance Internship',
        # tierSummary already says "€2K – €2.5K" — the numeric value (2000,
        # 2500) is already correctly scaled and this function only ever
        # touches the hourly band regardless, but the case is kept as a
        # regression: a k-marked value must never be touched.
        result = reinterpret_implausible_year(2000, 2500, "€2K – €2.5K", "EUR")
        self.assertIsNone(result)

    def test_a_non_usd_hourly_shaped_value_is_left_for_the_plausibility_gate(self):
        # Real case, and the second adversarial-review finding: a Lever
        # posting, 'Customer Solutions Consultant, French Market' (Lyon),
        # "42-46 EUR (per-year-salary)" -- under the old currency-blind
        # rule this became EUR42-46/HOUR, a threshold (100) derived
        # entirely from Ashby's own USD data and never validated against
        # EUR. Now: the hourly rule only ever fires for currency == 'USD',
        # so this is left untouched -- and, once a USD conversion is
        # available for it, reaches Tier 3.3's own plausibility gate
        # instead of being silently reinterpreted on an unvalidated basis.
        self.assertIsNone(reinterpret_implausible_year(42, 46, "42-46 EUR (per-year-salary)", "EUR"))

    def test_a_degenerate_non_usd_placeholder_is_also_left_untouched(self):
        # Real case: 'AI Builders' / 'Senior Software Engineer - Open Data
        # Platform', "1-1 INR (per-year-salary)" -- a degenerate
        # placeholder value, not fixable by any period reinterpretation;
        # confirms the currency guard also protects INR, not just EUR.
        self.assertIsNone(reinterpret_implausible_year(1, 1, "1-1 INR (per-year-salary)", "INR"))

    def test_a_plausible_literal_annual_figure_is_untouched(self):
        result = reinterpret_implausible_year(135_000, 165_000, "$135,000 - $165,000 per year", "USD")
        self.assertIsNone(result)

    def test_zero_or_missing_max_never_crashes(self):
        self.assertIsNone(reinterpret_implausible_year(0, 0, "", "USD"))
        self.assertIsNone(reinterpret_implausible_year(None, None, "", "USD"))

    def test_currency_none_or_missing_never_reinterprets_as_hourly(self):
        # A caller that doesn't know the currency (or passes it as None)
        # must never fall through to a USD-calibrated threshold by
        # accident -- the comparison is `currency == "USD"`, not `currency
        # != <something>`, so an unknown currency is conservative by
        # construction, not by a special-cased check.
        self.assertIsNone(reinterpret_implausible_year(30, 50, "$30 – $50", None))

    def test_the_usajobs_seasonal_clerk_case_is_also_hourly_shaped(self):
        # Real case: Internal Revenue Service 'Clerk *Seasonal*', OPM's own
        # salaryType said "Per Year" for a GS-scale hourly rate. Always USD
        # (17 U.S.C. SS105 federal data) -- src_postings_usajobs.py's own
        # call site passes "USD" as a literal, not a guess.
        result = reinterpret_implausible_year(14.18, 18.43, "14-18 USD (Per Year)", "USD")
        self.assertEqual(result, (14.18, 18.43, "hour"))

    def test_a_value_in_the_100_to_12_000_band_is_left_alone(self):
        # Real case: 'Associate Software Engineer, Operator Experience'
        # ($135-150) -- previously in the "deliberately untouched 100-250
        # gap"; now the whole 100-12,000 band (for a USD value already
        # past the hourly threshold) is left alone the same way, since the
        # x1000 rule that used to act on part of that range is gone.
        self.assertIsNone(reinterpret_implausible_year(135, 150, "$135 – $150 – Offers Equity", "USD"))

    def test_the_lever_hourly_shaped_case_is_also_reinterpreted(self):
        # Real case: 'Junior Visual Manager', "25-30 USD (per-year-salary)"
        # -- plainly an hourly rate mistagged 'year'.
        result = reinterpret_implausible_year(25, 30, "25-30 USD (per-year-salary)", "USD")
        self.assertEqual(result, (25, 30, "hour"))


class TestConvertCompensationToUsd(unittest.TestCase):
    """Package 14, Tier 3.1 — real conversions against the actual, committed
    data/processed/fx_rates.json (not a mocked rate), the same file
    normalise.to_usd() itself reads. If this file's own SG/JP/KH/IN/AM
    entries (added this package, src_fx_rates.py's own
    POSTINGS_EXTRA_FX_COUNTRIES) ever go missing, these tests fail for the
    real reason, not a mock silently hiding it."""

    def test_a_real_sgd_posting_converts_at_its_own_years_rate(self):
        # L9, an adversarial review finding: asserting result["min"] against
        # 100_000 / result["fx_rate"] only checks the function's own return
        # is internally consistent with itself -- it would pass even if the
        # rate itself were wrong. 1.30745 is read directly from the
        # committed data/processed/fx_rates.json's own SG/2025 entry,
        # independently of this function, so a real drift in either the
        # rate or the arithmetic fails this test for the right reason.
        result = convert_compensation_to_usd({"currency": "SGD", "min": 100_000, "max": 150_000}, 2025)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["fx_rate"], 1.30745, places=5)
        self.assertAlmostEqual(result["min"], 100_000 / 1.30745, places=2)
        self.assertAlmostEqual(result["max"], 150_000 / 1.30745, places=2)
        self.assertEqual(result["fx_year"], 2025)
        self.assertEqual(result["fx_country_used"], "SG")

    def test_an_unmapped_currency_is_never_converted(self):
        self.assertIsNone(convert_compensation_to_usd({"currency": "ZZZ", "min": 1, "max": 2}, 2025))

    def test_a_year_with_no_fx_rate_refuses_rather_than_substituting(self):
        """The rule: never reach for a neighbouring year's rate.

        Package 16 — this used USD as its example currency, which stopped
        exercising the rule once USD-to-USD became an identity that needs no
        rate at all. The rule is unchanged and is now tested with a currency
        that genuinely requires one. 1500 predates every rate this pipeline
        holds; 2026 is the real, current case (the World Bank series ends at
        2025), and it must still refuse."""
        self.assertIsNone(convert_compensation_to_usd({"currency": "GBP", "min": 1, "max": 2}, 1500))
        self.assertIsNone(convert_compensation_to_usd(
            {"currency": "GBP", "min": 50_000, "max": 60_000}, 2026))
        self.assertIsNone(convert_compensation_to_usd(
            {"currency": "EUR", "min": 50_000, "max": 60_000}, 2026))

    def test_usd_needs_no_rate_because_it_is_the_identity(self):
        """USD to USD is x -> x, exact in every year, and requiring a published
        1.0 for it was doing real damage: the FX series ends at 2025, so every
        2026-dated US posting failed conversion and 1,566 US software postings —
        the whole current year — were dropped from the site's only published pay
        figure. What survived was 77% 2016-2017 federal listings. This is not a
        hole in the no-substitution rule; nothing is being substituted."""
        for year in (2024, 2025, 2026, 2030):
            with self.subTest(year=year):
                got = convert_compensation_to_usd(
                    {"currency": "USD", "min": 100_000, "max": 120_000}, year)
                self.assertIsNotNone(got)
                self.assertEqual((got["min"], got["max"]), (100_000, 120_000))
                self.assertEqual(got["fx_rate"], 1.0)
                self.assertIn("identity", got["fx_source"])

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
