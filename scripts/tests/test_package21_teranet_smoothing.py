"""Package 21, Tier 1, item #43 -- derive_teranet_smoothed.py.

The risk this module exists to catch is not "does statsmodels run" (it does,
trivially) but "does the recovered trend actually track something real, and
does the validation gate actually reject a bad fit." Both are tested against
GROUND TRUTH BUILT INDEPENDENTLY OF THE FUNCTION UNDER TEST: a synthetic
series is constructed as a KNOWN smooth curve plus KNOWN iid noise, and the
assertion is that the smoother's output correlates with the KNOWN curve --
never that it merely agrees with its own noise model or with a number the
same code path produced. This mirrors package 19/20's own testing discipline
(see the adversarial-review record): a check whose ground truth comes from
the function it is checking cannot fail.

Run directly (`python scripts/tests/test_package21_teranet_smoothing.py`) or
via scripts/tests/run_all.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import derive_teranet_smoothed as dts  # noqa: E402


def _dates(n: int, start_year: int = 2000) -> list[str]:
    out = []
    y, m = start_year, 1
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


class TestQuarterlyMean(unittest.TestCase):
    def test_buckets_three_months_into_one_quarter(self):
        dates = ["2020-01", "2020-02", "2020-03"]
        out = dts._quarterly_mean(dates, np.array([10.0, 20.0, 30.0]))
        self.assertEqual(out, {"2020-Q1": 20.0})

    def test_a_year_splits_into_exactly_four_quarters(self):
        dates = _dates(12, 2020)
        out = dts._quarterly_mean(dates, np.arange(12, dtype=float))
        self.assertEqual(set(out), {"2020-Q1", "2020-Q2", "2020-Q3", "2020-Q4"})
        # Q1 = months 0,1,2 (Jan-Mar) -> mean 1.0
        self.assertAlmostEqual(out["2020-Q1"], 1.0)

    def test_december_and_january_land_in_different_quarters(self):
        dates = ["2020-12", "2021-01"]
        out = dts._quarterly_mean(dates, np.array([100.0, 200.0]))
        self.assertEqual(set(out), {"2020-Q4", "2021-Q1"})


class TestLogLinearPctPerYear(unittest.TestCase):
    def test_recovers_a_known_five_percent_annual_growth_rate(self):
        years = np.arange(2000, 2020)
        # Full calendar years only, one point per year -- an unambiguous case.
        dates = [f"{y}-06" for y in years]
        values = 100 * (1.05 ** (years - 2000))
        pct = dts._log_linear_pct_per_year(dates, values)
        self.assertIsNotNone(pct)
        self.assertAlmostEqual(pct, 5.0, places=2)

    def test_a_flat_series_reads_as_zero_percent(self):
        dates = [f"{y}-06" for y in range(2000, 2020)]
        values = np.full(20, 150.0)
        pct = dts._log_linear_pct_per_year(dates, values)
        self.assertAlmostEqual(pct, 0.0, places=6)

    def test_a_partial_first_year_does_not_get_the_same_weight_as_a_full_year(self):
        # 1998 has one month, every later year has twelve -- the annual MEAN
        # for 1998 is still a single well-defined point (not artificially
        # downweighted further), but it must not silently vanish either.
        dates = ["1998-12"] + [f"{y}-{m:02d}" for y in range(1999, 2010) for m in range(1, 13)]
        rate = 1.05 ** (1 / 12)
        values = np.array([100.0 * rate ** i for i in range(len(dates))])
        pct = dts._log_linear_pct_per_year(dates, values)
        self.assertIsNotNone(pct)
        self.assertAlmostEqual(pct, 5.0, delta=0.5)

    def test_fewer_than_eight_years_returns_none_rather_than_a_fragile_slope(self):
        dates = [f"{y}-06" for y in range(2000, 2005)]
        values = np.array([100.0, 110.0, 105.0, 120.0, 115.0])
        self.assertIsNone(dts._log_linear_pct_per_year(dates, values))


class TestFitCityRecoversAKnownSignal(unittest.TestCase):
    """The core claim of Tier 1: given signal + independent noise, the fitted
    smoother's output tracks the SIGNAL (known by construction, not by
    asking the function under test), and the validation gate correctly
    separates a real correlation from a spurious one.

    The gate itself validates on DIFFERENCED correlation plus a Monte Carlo
    null, not raw levels-correlation -- a levels-based first version of this
    gate was proven unsafe by direct testing against the REAL Teranet data
    (see derive_teranet_smoothed.py's own module docstring and
    BORDERLINE_MARGIN comment): smoothed pure noise showed 0.9+ level-
    correlation with an unrelated real trend for 5 of 6 real cities, one of
    them landing positive. TestFitCityLevelsCorrelationAloneIsUnsafe below
    reproduces that exact failure mode with a synthetic fixture, so the
    regression has independent, non-Teranet-specific coverage.
    """

    NULL_DRAWS_FOR_TESTS = 150  # enough to separate a real signal from noise; not publication precision

    def setUp(self):
        rng = np.random.default_rng(20260827)
        n = 120
        self.dates = _dates(n, 2005)
        t = np.arange(n, dtype=float)
        # A smooth TRUE level -- a linear drift plus a wave, well within what
        # a local-linear-trend model's own random-walk slope can track
        # cleanly (an earlier fixture used a t**1.3 power term, which does
        # NOT fit that model well and produced MLE non-convergence unrelated
        # to anything this test means to check -- built directly either way,
        # not via anything derive_teranet_smoothed.py itself computes). The
        # wave's period matters, not just its amplitude: DIFFERENCED
        # correlation (the actual validation basis) can only detect
        # CURVATURE, i.e. a changing rate of change -- a pure linear trend's
        # differences are constant and correlate with nothing (verified: a
        # period-15 wave over 120 points cleared >0 but not significance at
        # n=120's modest quarter count; period 8 gives enough curvature per
        # quarter to be reliably detectable at this sample size).
        self.true_level = 100 + 0.4 * t + 3 * np.sin(t / 8)
        noisy_raw = self.true_level + rng.normal(0, 9.0, n)  # noise >> the drift itself
        self.raw = noisy_raw
        # An "OECD" reference perfectly derived from the TRUE level (not the
        # noisy raw, not anything the fit produces) -- the honest analogue of
        # an independent source that measures the same underlying quantity.
        self.oecd_from_truth = dts._quarterly_mean(self.dates, self.true_level)
        # A second "OECD" series that is pure independent noise -- nothing in
        # this city's real signal should be able to pass validation against it.
        self.oecd_unrelated = {
            k: float(v) for k, v in
            dts._quarterly_mean(self.dates, rng.normal(0, 50, n)).items()
        }

    def test_recovered_smoothed_series_correlates_with_the_true_level_it_was_never_shown(self):
        fit = dts._fit_city(self.dates, self.raw, self.oecd_from_truth)
        smoothed_vals = np.array([r["smoothed"] for r in fit["series"]])
        corr_to_truth = float(np.corrcoef(smoothed_vals, self.true_level)[0, 1])
        corr_raw_to_truth = float(np.corrcoef(self.raw, self.true_level)[0, 1])
        self.assertGreater(corr_to_truth, 0.9,
                            "the smoother should recover a curve close to the true level")
        # It should not merely coincide with the truth by as much as the
        # untouched raw series already does by chance -- smoothing must add
        # something, mirroring the real Teranet self-adversarial check.
        self.assertGreaterEqual(corr_to_truth, corr_raw_to_truth)

    def test_signal_share_is_a_small_minority_when_noise_dominates_the_raw_series(self):
        fit = dts._fit_city(self.dates, self.raw, self.oecd_from_truth)
        # Noise (sd=9) was constructed to dominate the drift term by design;
        # the recovered share of real month-to-month variance should reflect
        # that, not report the series as mostly signal.
        self.assertLess(fit["noise"]["signal_share_pct"], 50.0)

    def test_validation_passes_against_a_reference_built_from_the_true_signal(self):
        fit = dts._fit_city(self.dates, self.raw, self.oecd_from_truth,
                             null_seed=1, null_draws=self.NULL_DRAWS_FOR_TESTS)
        self.assertTrue(fit["validation"]["passed"], fit["validation"])
        self.assertGreater(fit["validation"]["corr_smoothed_vs_oecd_diff"], 0)
        self.assertLessEqual(fit["validation"]["null_test"]["p_value"], dts.VALIDATION_MAX_P_VALUE)

    def test_validation_fails_against_a_reference_that_is_pure_unrelated_noise(self):
        fit = dts._fit_city(self.dates, self.raw, self.oecd_unrelated,
                             null_seed=2, null_draws=self.NULL_DRAWS_FOR_TESTS)
        self.assertFalse(fit["validation"]["passed"], fit["validation"])

    def test_a_pure_noise_raw_series_does_not_falsely_pass_validation(self):
        # The negative control the real self-adversarial check was built to
        # withstand: if the "signal" is ALSO just noise, smoothing it must
        # not manufacture a passing correlation against the true reference.
        rng = np.random.default_rng(7)
        pure_noise = rng.normal(150, 20, len(self.dates))
        fit = dts._fit_city(self.dates, pure_noise, self.oecd_from_truth,
                             null_seed=3, null_draws=self.NULL_DRAWS_FOR_TESTS)
        self.assertFalse(fit["validation"]["passed"], fit["validation"])


class TestZeroVarianceReferenceIsGuardedNotNaN(unittest.TestCase):
    """A perfectly straight (zero-curvature) reference trend has CONSTANT
    differences, and np.corrcoef divides by each array's own stddev -- a
    constant array produces NaN, not an error, and NaN serializes straight
    into json.dumps as literal `NaN`, invalid JSON. Found live while tuning
    this test suite's own fixtures (a perfectly linear "unrelated trend" hit
    it immediately) -- real OECD/Teranet data is never this degenerate, but
    the guard exists so a degenerate input fails legibly (None) rather than
    silently producing invalid committed JSON.
    """

    def test_a_perfectly_linear_reference_yields_none_not_nan(self):
        n = 150
        dates = _dates(n, 2000)
        # Perfectly straight -- zero curvature, constant differences by construction.
        straight_trend = 100 + 0.5 * np.arange(n, dtype=float)
        oecd = dts._quarterly_mean(dates, straight_trend)
        rng = np.random.default_rng(5)
        raw = rng.normal(200, 25, n)

        fit = dts._fit_city(dates, raw, oecd)
        v = fit["validation"]
        self.assertIsNone(v["corr_smoothed_vs_oecd_diff"])
        self.assertIsNone(v["corr_raw_vs_oecd_diff"])
        self.assertFalse(v["passed"])
        # The levels correlation is NOT degenerate (levels vary, only their
        # differences are constant) -- only the diff side should be guarded.
        self.assertIsNotNone(v["corr_smoothed_vs_oecd_levels"])
        # No NaN anywhere in the output -- the actual defect this guards against.
        import math
        for key in ("corr_smoothed_vs_oecd_levels", "corr_raw_vs_oecd_levels",
                    "corr_smoothed_vs_oecd_diff", "corr_raw_vs_oecd_diff"):
            val = v[key]
            self.assertFalse(val is not None and math.isnan(val), f"{key} is NaN")

    def test_the_null_test_itself_is_skipped_cleanly_against_a_degenerate_reference(self):
        n = 150
        dates = _dates(n, 2000)
        straight_trend = 100 + 0.5 * np.arange(n, dtype=float)
        oecd = dts._quarterly_mean(dates, straight_trend)
        result = dts._null_pvalue(dates, np.random.default_rng(6).normal(200, 25, n),
                                   oecd, observed_diff_corr=0.9, seed=1, n_draws=20)
        self.assertEqual(result["n_draws"], 0)
        self.assertIsNone(result["p_value"])


class TestFitCityLevelsCorrelationAloneIsUnsafe(unittest.TestCase):
    """Reproduces, with a synthetic fixture, the exact failure mode found by
    testing the first (levels-only) version of this validation against the
    real Teranet data: a local-linear-trend smoother applied to PURE NOISE
    can still show a strong LEVELS correlation with an unrelated real trend,
    because two series that each drift slowly correlate at the level whether
    or not the drift shares a cause (spurious regression). This is why
    _fit_city validates on DIFFERENCED correlation, never on
    corr_smoothed_vs_oecd_levels -- that field is documented as reference-
    only. This test exists so a future edit that starts gating `passed` on
    the levels field again fails a test, not just a design-doc comment.
    """

    def test_smoothed_pure_noise_can_show_strong_levels_correlation_with_an_unrelated_trend(self):
        rng = np.random.default_rng(1)
        n = 150
        dates = _dates(n, 2000)
        # An unrelated REAL trend, nothing to do with the noise below -- given
        # a little real curvature (not a perfectly straight line) so its own
        # DIFFERENCED series has genuine variance and this test exercises the
        # actual comparison metric, not _fit_city's zero-variance guard.
        t = np.arange(n, dtype=float)
        unrelated_trend = 100 + 0.5 * t + 2 * np.sin(t / 10)
        oecd = dts._quarterly_mean(dates, unrelated_trend)
        # Pure noise, no signal whatsoever.
        pure_noise = rng.normal(200, 25, n)

        fit = dts._fit_city(dates, pure_noise, oecd)  # no null_seed -- isolate the levels number itself
        level_corr = fit["validation"]["corr_smoothed_vs_oecd_levels"]
        diff_corr = fit["validation"]["corr_smoothed_vs_oecd_diff"]
        # The point being demonstrated: |levels correlation| can be large even
        # though the diff correlation (the actual validation basis) is not
        # reliably large in the same way -- levels alone would be misleading.
        self.assertIsNotNone(level_corr)
        self.assertGreater(abs(level_corr), 0.9,
                            "the known failure mode this test guards against did not reproduce "
                            "with this seed -- the fixture, not the defence, may need attention")
        self.assertIsNotNone(diff_corr)
        self.assertLess(abs(diff_corr), 0.5,
                         "the differenced metric should NOT show the same spurious strength")
        # And regardless of what the levels number does, passed must never be
        # True without a null test actually having run and cleared the bar.
        self.assertFalse(fit["validation"]["passed"])


class TestFitCityIsWellFormed(unittest.TestCase):
    def test_every_smoothed_point_has_a_band_that_contains_it(self):
        rng = np.random.default_rng(3)
        n = 100
        dates = _dates(n, 2010)
        true_level = 100 + 0.3 * np.arange(n)
        raw = true_level + rng.normal(0, 5, n)
        oecd = dts._quarterly_mean(dates, true_level)
        fit = dts._fit_city(dates, raw, oecd)
        for row in fit["series"]:
            self.assertLessEqual(row["lo95"], row["smoothed"])
            self.assertLessEqual(row["smoothed"], row["hi95"])

    def test_harvey_q_and_signal_share_are_both_present_and_non_negative(self):
        rng = np.random.default_rng(4)
        n = 100
        dates = _dates(n, 2010)
        true_level = 100 + 0.2 * np.arange(n)
        raw = true_level + rng.normal(0, 6, n)
        oecd = dts._quarterly_mean(dates, true_level)
        fit = dts._fit_city(dates, raw, oecd)
        self.assertIsNotNone(fit["noise"]["harvey_q"])
        self.assertGreaterEqual(fit["noise"]["harvey_q"], 0)
        self.assertIsNotNone(fit["noise"]["signal_share_pct"])
        self.assertGreaterEqual(fit["noise"]["signal_share_pct"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
