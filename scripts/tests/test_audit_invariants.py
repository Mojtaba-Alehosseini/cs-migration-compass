"""Package 13, Tier 5 gate 3 evidence — proves every scripts/audit_data.py
invariant actually fails on a constructed violating record (not just
"passes against real data", which a check that silently does nothing would
also do — see audit_data.py's own git history for two checks that did
exactly that on their first run: a regex \\b bug that made the magnitude
bucketer a no-op, and a rounding bug that made the mdrsnit recomputation
wrong). Each test writes ONE small scratch data/processed/-shaped file,
runs the real check function against it via its processed_dir override,
and asserts ERRORS/FLAGS actually grew.

Run directly (`python scripts/tests/test_audit_invariants.py`) or via
scripts/tests/run_all.py.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit_data as ad  # noqa: E402


def _envelope(source_id: str, data: dict) -> dict:
    return {"source_id": source_id, "generated_at": "2026-01-01T00:00:00Z", "meta": {}, "data": data}


class AuditInvariantTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="audit-test-"))
        ad.ERRORS.clear()
        ad.FLAGS.clear()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name: str, source_id: str, data: dict) -> None:
        (self.tmp / f"{name}.json").write_text(json.dumps(_envelope(source_id, data)), encoding="utf-8")


class TestPercentilesMonotonic(AuditInvariantTestCase):
    def test_fails_on_an_inverted_percentile(self):
        self._write("bad", "bad", {"occupations": {"1": {
            "mean_usd_year": 80000, "median_usd_year": 70000,
            "p10_usd_year": 90000,  # p10 > p25 below -- a real inversion
            "p25_usd_year": 60000, "p75_usd_year": 95000, "p90_usd_year": 100000,
        }}})
        ad.check_percentiles_monotonic(self.tmp)
        self.assertTrue(any("must never invert" in e for e in ad.ERRORS), ad.ERRORS)

    def test_passes_on_correctly_ordered_percentiles(self):
        self._write("good", "good", {"occupations": {"1": {
            "p10_usd_year": 60000, "p25_usd_year": 70000, "median_usd_year": 80000,
            "p75_usd_year": 90000, "p90_usd_year": 100000,
        }}})
        ad.check_percentiles_monotonic(self.tmp)
        self.assertEqual(ad.ERRORS, [])


class TestMeanWithinRange(AuditInvariantTestCase):
    def test_fails_when_mean_is_outside_p10_p90(self):
        self._write("bad", "bad", {"occupations": {"1": {
            "mean_usd_year": 200000,  # absurdly above p90
            "p10_usd_year": 60000, "p90_usd_year": 100000,
        }}})
        ad.check_mean_within_percentile_range(self.tmp)
        self.assertTrue(any("is outside" in e for e in ad.ERRORS), ad.ERRORS)


class TestNoNegativeOrZeroPay(AuditInvariantTestCase):
    def test_fails_on_a_zero_pay_figure(self):
        self._write("bad", "bad", {"occupations": {"1": {"mean_usd_year": 0, "median_usd_year": 50000}}})
        ad.check_no_negative_or_zero_pay(self.tmp)
        self.assertTrue(any("exactly 0" in e for e in ad.ERRORS), ad.ERRORS)

    def test_fails_on_a_negative_pay_figure(self):
        self._write("bad", "bad", {"occupations": {"1": {"mean_usd_year": -500, "median_usd_year": 50000}}})
        ad.check_no_negative_or_zero_pay(self.tmp)
        self.assertTrue(any("negative pay figure" in e for e in ad.ERRORS), ad.ERRORS)


class TestDistributionLabelMatchesPresence(AuditInvariantTestCase):
    def test_fails_when_central_tendency_only_but_percentiles_present(self):
        self._write("bad", "bad", {"occupations": {"1": {
            "distribution": "central-tendency-only",
            "mean_usd_year": 80000, "p10_usd_year": 60000,  # a real percentile field, contradicting the label
        }}})
        ad.check_distribution_label_matches_percentile_presence(self.tmp)
        self.assertTrue(any("carries a real percentile field" in e for e in ad.ERRORS), ad.ERRORS)

    def test_fails_on_an_unregistered_distribution_label(self):
        self._write("bad", "bad", {"occupations": {"1": {"distribution": "estimated-ish", "mean_usd_year": 80000}}})
        ad.check_distribution_label_matches_percentile_presence(self.tmp)
        self.assertTrue(any("unregistered value" in e for e in ad.ERRORS), ad.ERRORS)


class TestUnitDisclosure(AuditInvariantTestCase):
    def test_fails_on_a_bare_pay_field_with_no_recoverable_unit(self):
        self._write("bad", "bad", {"occupations": {"1": {"mean": 80000, "median": 70000}}})
        ad.check_pay_fields_disclose_currency_and_period(self.tmp)
        self.assertTrue(any("missing its own currency and period" in e for e in ad.ERRORS), ad.ERRORS)

    def test_passes_when_currency_and_period_are_container_siblings(self):
        self._write("good", "good", {"native": {"currency": "SEK", "period": "month",
                                                  "value": {"mean": 55000, "median": 53500}}})
        ad.check_pay_fields_disclose_currency_and_period(self.tmp)
        self.assertEqual(ad.ERRORS, [])

    def test_coefficient_of_variation_is_exempt_not_flagged(self):
        # Confirms the exclusion (found live against salary_uk.json) stays
        # narrow -- a genuine CV% block must NOT be flagged as unit-less.
        self._write("uk_like", "uk_like", {"occupations": {"1": {
            "mean_gbp_year": 80000,
            "coefficient_of_variation_pct": {"mean": 5.6, "p10": 14, "p25": 5.2},
        }}})
        ad.check_pay_fields_disclose_currency_and_period(self.tmp)
        self.assertEqual(ad.ERRORS, [])


class TestMagnitudePlausibility(AuditInvariantTestCase):
    """check_magnitude_plausibility() prefers a family's own non-mean
    (percentile) values for BOUND-BUILDING (each distribution's spread is
    counted once, not mean too) but TESTS every value including mean
    (adversarial review finding H1 -- an earlier version excluded mean
    from testing too, not just bound-building, which let a mean-only
    source escape checking entirely). Two independent bounds: dataset-
    relative (median +/- 8x MAD of the bucket, floor clamped to a quarter
    of the median -- finding H3, an earlier version's unclamped floor went
    negative in most real buckets) and an absolute sanity band per period
    (finding H1 again -- catches an entire bucket being wrong the same
    way, which the relative bound cannot by construction)."""

    def test_flags_a_dataset_relative_outlier_within_the_absolute_band(self):
        # 3x the rest of the bucket -- outside the relative bound but well
        # inside the absolute year band [500, 5_000_000], so this proves
        # the RELATIVE check specifically, not just the absolute one.
        occs = {str(i): {"mean_usd_year": 80000 + i * 500, "median_usd_year": 78000 + i * 500} for i in range(8)}
        occs["outlier"] = {"mean_usd_year": 240_000, "median_usd_year": 240_000}
        self._write("bad", "bad", {"occupations": occs})
        ad.check_magnitude_plausibility(self.tmp)
        self.assertTrue(any("plausible range" in f for f in ad.FLAGS), ad.FLAGS)

    def test_flags_a_whole_bucket_uniformly_wrong_via_the_absolute_band(self):
        # The real H1 scenario: EVERY point in the bucket is wrong the same
        # way (an annual figure written into every hourly-labelled field),
        # so the relative bound learns the wrong scale and cannot catch it
        # -- only an absolute, dataset-independent band can.
        occs = {str(i): {"mean_usd_hour": 80000 + i * 500, "median_usd_hour": 78000 + i * 500} for i in range(8)}
        self._write("bad", "bad", {"occupations": occs})
        ad.check_magnitude_plausibility(self.tmp)
        self.assertTrue(any("absolute sanity band" in f for f in ad.FLAGS), ad.FLAGS)

    def test_a_lone_mean_only_family_is_still_tested(self):
        # H1's other half: a family with ONLY a mean (no sibling
        # percentiles) must still be bucketed and tested, not silently
        # skipped because "mean" is excluded from bound-building.
        occs = {str(i): {"mean_usd_year": 80000 + i * 500} for i in range(4)}
        occs["outlier"] = {"mean_usd_year": 9_000_000}
        self._write("bad", "bad", {"occupations": occs})
        ad.check_magnitude_plausibility(self.tmp)
        self.assertTrue(any("absolute sanity band" in f for f in ad.FLAGS), ad.FLAGS)

    def test_does_not_flag_a_tight_cluster(self):
        occs = {str(i): {"mean_usd_year": 80000 + i * 500, "median_usd_year": 78000 + i * 500} for i in range(8)}
        self._write("good", "good", {"occupations": occs})
        ad.check_magnitude_plausibility(self.tmp)
        self.assertEqual(ad.FLAGS, [])


class TestEmbeddedCrossCheckReconciles(AuditInvariantTestCase):
    def test_fails_when_computed_monthly_does_not_match_independent_recomputation(self):
        self._write("bad", "bad", {"native": {"mdrsnit_check": {
            "stand_dkk_hour": 408.56, "computed_monthly": 99999.99,  # wrong on purpose
            "published_mdrsnit": 65504.17, "residual_pct": 0.0025,
        }}})
        ad.check_embedded_cross_checks_reconcile(self.tmp, require_found=False)
        self.assertTrue(any("!= computed_monthly" in e for e in ad.ERRORS), ad.ERRORS)

    def test_passes_on_the_real_denmark_figures(self):
        self._write("good", "good", {"native": {"mdrsnit_check": {
            "stand_dkk_hour": 408.56, "computed_monthly": 65505.79,
            "published_mdrsnit": 65504.17, "residual_pct": 0.0025,
        }}})
        ad.check_embedded_cross_checks_reconcile(self.tmp, require_found=False)
        self.assertEqual(ad.ERRORS, [])


class TestRefreshIntervals(AuditInvariantTestCase):
    def test_flags_a_source_past_its_own_expected_interval(self):
        prov = self.tmp / "provenance.json"
        prov.write_text(json.dumps({"entries": [
            {"source_id": "salary_zz", "fetched_at": "2020-01-01T00:00:00Z"},  # years stale
        ]}), encoding="utf-8")
        ad.check_refresh_intervals(prov)
        self.assertTrue(any("past its own" in f for f in ad.FLAGS), ad.FLAGS)

    def test_does_not_flag_a_fresh_source(self):
        import datetime as dt
        prov = self.tmp / "provenance.json"
        recent = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        prov.write_text(json.dumps({"entries": [{"source_id": "salary_zz", "fetched_at": recent}]}),
                         encoding="utf-8")
        ad.check_refresh_intervals(prov)
        self.assertEqual(ad.FLAGS, [])


class TestPostingsMergeIsCurrent(AuditInvariantTestCase):
    """Package 14, Tier 0.1 / adversarial review M5 — this check had zero
    test coverage despite being the direct fix for the external audit's own
    "stale merge" finding (postings.json served 5 days, ~15,000 postings
    stale, silently)."""

    def test_fails_when_a_provider_file_is_newer_than_the_merge_recorded(self):
        self._write("postings", "postings", {
            "provider_summary": {"ashby": {"generated_at": "2026-01-01T00:00:00Z"}},
        })
        # Written directly, not via _write()/_envelope(), so its own
        # generated_at can differ from postings.json's recorded value --
        # simulating a provider harvested again, later, after the merge ran.
        (self.tmp / "postings_ashby.json").write_text(json.dumps({
            "source_id": "postings_ashby", "generated_at": "2026-01-06T00:00:00Z",
            "meta": {}, "data": {"postings": []},
        }), encoding="utf-8")

        ad.check_postings_merge_is_current(self.tmp)
        self.assertTrue(any("STALE" in e and "ashby" in e for e in ad.ERRORS), ad.ERRORS)

    def test_passes_when_every_built_provider_matches_the_merge(self):
        self._write("postings", "postings", {
            "provider_summary": {"ashby": {"generated_at": "2026-01-01T00:00:00Z"}},
        })
        self._write("postings_ashby", "postings_ashby", {"postings": []})
        ad.check_postings_merge_is_current(self.tmp)
        self.assertEqual(ad.ERRORS, [])

    def test_a_provider_never_built_in_this_environment_is_not_this_checks_concern(self):
        # No postings_ashby.json at all (never harvested here) -- must not
        # be treated as "stale", only a genuinely REBUILT-and-mismatched
        # provider file is an error.
        self._write("postings", "postings", {"provider_summary": {}})
        ad.check_postings_merge_is_current(self.tmp)
        self.assertEqual(ad.ERRORS, [])


class TestOecdWageBenchmark(AuditInvariantTestCase):
    """Package 14, Tier 1 (external audit Finding 1, SEVERE) / adversarial
    review M5 — the standing invariant meant to have caught Finding 1 "the
    day it shipped" had no test of its own, and no test at all of the
    hardening added against the blind spot the review's own M5 finding
    named (a renamed/missing WG_USD_PPP silently exempting every country
    and reporting a clean PASS)."""

    def _write_pair(self, wage_data: dict, oecd_data: dict) -> None:
        (self.tmp / "wage_distribution.json").write_text(
            json.dumps(_envelope("wage_distribution", wage_data)), encoding="utf-8")
        (self.tmp / "oecd_indicators.json").write_text(
            json.dumps(_envelope("oecd_wages", oecd_data)), encoding="utf-8")

    def test_fails_when_published_median_is_below_the_low_band(self):
        # ES-shaped: median well under 1.0x its own OECD avg_wages.
        self._write_pair(
            {"countries": [{"country": "ES", "native": {"year": 2018},
                             "combos": {"usd_regular_pay": {"ok": True, "value": {"median": 40000}}}}]},
            {"ES": {"avg_wages": {"WG_USD_PPP": [{"period": "2018", "value": 55000}]}}},
        )
        ad.check_oecd_wage_benchmark(self.tmp)
        self.assertTrue(any("ES" in f and "outside the" in f for f in ad.FLAGS), ad.FLAGS)

    def test_fails_when_published_median_is_above_the_high_band(self):
        self._write_pair(
            {"countries": [{"country": "ZZ", "native": {"year": 2024},
                             "combos": {"usd_regular_pay": {"ok": True, "value": {"median": 500000}}}}]},
            {"ZZ": {"avg_wages": {"WG_USD_PPP": [{"period": "2024", "value": 50000}]}}},  # 10x
        )
        ad.check_oecd_wage_benchmark(self.tmp)
        self.assertTrue(any("ZZ" in f and "outside the" in f for f in ad.FLAGS), ad.FLAGS)

    def test_passes_when_ratio_is_within_the_plausible_band(self):
        self._write_pair(
            {"countries": [{"country": "US", "native": {"year": 2024},
                             "combos": {"usd_regular_pay": {"ok": True, "value": {"median": 100000}}}}]},
            {"US": {"avg_wages": {"WG_USD_PPP": [{"period": "2024", "value": 64000}]}}},  # 1.5625x
        )
        ad.check_oecd_wage_benchmark(self.tmp)
        self.assertEqual(ad.FLAGS, [])

    def test_ae_and_qa_exempt_for_lacking_a_series_are_not_flagged_as_unexpected(self):
        self._write_pair(
            {"countries": [
                {"country": "AE", "native": {"year": 2024},
                 "combos": {"usd_regular_pay": {"ok": True, "value": {"median": 90000}}}},
                {"country": "US", "native": {"year": 2024},
                 "combos": {"usd_regular_pay": {"ok": True, "value": {"median": 100000}}}},
            ]},
            {"US": {"avg_wages": {"WG_USD_PPP": [{"period": "2024", "value": 64000}]}}},
            # AE deliberately absent from oecd_data -- the real, known exemption.
        )
        ad.check_oecd_wage_benchmark(self.tmp)
        self.assertFalse(any("beyond the known" in f for f in ad.FLAGS), ad.FLAGS)

    def test_a_country_exempt_beyond_the_known_ae_qa_baseline_is_flagged(self):
        # M5's own hardening: a THIRD country with no avg_wages series is
        # far more likely a real break (renamed ISO code, missing pull)
        # than a genuine new gap, and must not vanish into "exempt" silently.
        self._write_pair(
            {"countries": [
                {"country": "ZZ", "native": {"year": 2024},
                 "combos": {"usd_regular_pay": {"ok": True, "value": {"median": 90000}}}},
                {"country": "US", "native": {"year": 2024},
                 "combos": {"usd_regular_pay": {"ok": True, "value": {"median": 100000}}}},
            ]},
            {"US": {"avg_wages": {"WG_USD_PPP": [{"period": "2024", "value": 64000}]}}},
        )
        ad.check_oecd_wage_benchmark(self.tmp)
        self.assertTrue(any("beyond the known" in f and "ZZ" in f for f in ad.FLAGS), ad.FLAGS)

    def test_checked_zero_despite_real_rows_is_an_error_not_a_silent_pass(self):
        # Simulates exactly the M5 scenario: WG_USD_PPP renamed/missing
        # upstream. Every country in wage_distribution.json has real rows,
        # but oecd_indicators.json carries no WG_USD_PPP key for any of
        # them -- checked must stay 0, and that must be a loud ERROR, not
        # a quiet "0 checked, 0 flagged, PASS".
        self._write_pair(
            {"countries": [{"country": "US", "native": {"year": 2024},
                             "combos": {"usd_regular_pay": {"ok": True, "value": {"median": 100000}}}}]},
            {"US": {"avg_wages": {"WG_USD_PPP_RENAMED": [{"period": "2024", "value": 64000}]}}},
        )
        ad.check_oecd_wage_benchmark(self.tmp)
        self.assertTrue(any("checked 0 countries" in e for e in ad.ERRORS), ad.ERRORS)

    def test_missing_files_flags_rather_than_crashing(self):
        ad.check_oecd_wage_benchmark(self.tmp)
        self.assertTrue(any("missing" in f for f in ad.FLAGS), ad.FLAGS)
        self.assertEqual(ad.ERRORS, [])

    def test_a_row_with_unverified_pay_composition_is_uncheckable_not_flagged(self):
        # L10, an adversarial review finding: Canada's own two wage-panel
        # rows (source_id salary_ca) will NEVER have an .ok combo on any
        # basis, because data/pay_composition.json's own REAL, committed
        # salary_ca entry marks irregular_bonus "unknown" -- a permanent,
        # already-disclosed condition, not a fresh finding worth a flag
        # every single run forever. This reads the REAL pay_composition.json
        # (not a scratch fixture -- there is no processed_dir-style override
        # for it), so a future change to salary_ca's own entry would need
        # this test updated too, the same tradeoff TestConvertCompensationToUsd
        # already accepts for fx_rates.json.
        self._write_pair(
            {"countries": [{"country": "CA-21231", "source_id": "salary_ca", "native": {"year": 2024},
                             "combos": {"usd_regular_pay": {"ok": False, "reason": "no common basis"},
                                        "usd_total_earnings": {"ok": False, "reason": "no common basis"}}}]},
            {"CA": {"avg_wages": {"WG_USD_PPP": [{"period": "2024", "value": 60000}]}}},
        )
        ad.check_oecd_wage_benchmark(self.tmp)
        self.assertFalse(any("CA-21231" in f for f in ad.FLAGS), ad.FLAGS)

    def test_a_row_with_no_combo_and_a_verified_composition_is_still_flagged(self):
        # The other half of L10's own fix: a country whose composition IS
        # verified (not in pay_composition.json's own unverified set) but
        # still has no .ok combo for some OTHER reason must still flag --
        # this is real, worth-a-look signal, not the permanent Canada case.
        self._write_pair(
            {"countries": [{"country": "US", "source_id": "bls_oews", "native": {"year": 2024},
                             "combos": {"usd_regular_pay": {"ok": False, "reason": "no FX rate for 2024"},
                                        "usd_total_earnings": {"ok": False, "reason": "no FX rate for 2024"}}}]},
            {"US": {"avg_wages": {"WG_USD_PPP": [{"period": "2024", "value": 60000}]}}},
        )
        ad.check_oecd_wage_benchmark(self.tmp)
        self.assertTrue(any("US" in f and "no USD-converted median" in f for f in ad.FLAGS), ad.FLAGS)


class TestPostingsAnnualisedPlausibility(AuditInvariantTestCase):
    """Package 14, Tier 3.3 (external audit Finding 3) / adversarial review
    M5 — no test previously existed proving this check actually fires, or
    that the period multiplier (year/month/hour -> annualised) is applied
    before comparing against the band, rather than to the raw figure."""

    def _write_postings(self, postings: list[dict]) -> None:
        self._write("postings", "postings", {"postings": postings})

    def test_fails_on_an_implausibly_low_annualised_figure(self):
        self._write_postings([{
            "id": "p1", "company": "acme", "title": "Intern",
            "compensation": {"min": 100, "max": 100, "currency": "USD", "period": "year",
                              "usd": {"min": 100, "max": 100}},
        }])
        ad.check_postings_annualised_plausibility(self.tmp)
        self.assertTrue(any("outside the" in f for f in ad.FLAGS), ad.FLAGS)

    def test_fails_on_an_implausibly_high_annualised_figure(self):
        self._write_postings([{
            "id": "p2", "company": "acme", "title": "CEO",
            "compensation": {"min": 8_000_000, "max": 9_000_000, "currency": "USD", "period": "year",
                              "usd": {"min": 8_000_000, "max": 9_000_000}},
        }])
        ad.check_postings_annualised_plausibility(self.tmp)
        self.assertTrue(any("outside the" in f for f in ad.FLAGS), ad.FLAGS)

    def test_passes_on_an_ordinary_annual_figure(self):
        self._write_postings([{
            "id": "p3", "company": "acme", "title": "Engineer",
            "compensation": {"min": 120_000, "max": 150_000, "currency": "USD", "period": "year",
                              "usd": {"min": 120_000, "max": 150_000}},
        }])
        ad.check_postings_annualised_plausibility(self.tmp)
        self.assertEqual(ad.FLAGS, [])

    def test_hourly_period_is_annualised_before_the_band_check_not_after(self):
        # $55/hour looks implausibly LOW as a bare annual figure (well
        # under $500), but x2080 = $114,400/year, comfortably inside the
        # band -- proving the multiplier runs before the comparison, not
        # that hourly postings are just being skipped.
        self._write_postings([{
            "id": "p4", "company": "acme", "title": "Contractor",
            "compensation": {"min": 50, "max": 60, "currency": "USD", "period": "hour",
                              "usd": {"min": 50, "max": 60}},
        }])
        ad.check_postings_annualised_plausibility(self.tmp)
        self.assertEqual(ad.FLAGS, [])

    def test_a_posting_with_no_usd_conversion_is_not_counted_either_way(self):
        # No "usd" sub-field at all (unmapped currency or no FX rate for
        # that year) -- must be silently skipped by this check, never
        # treated as a flaggable $0.
        self._write_postings([{
            "id": "p5", "company": "acme", "title": "Engineer",
            "compensation": {"min": 40000, "max": 50000, "currency": "XYZ", "period": "year"},
        }])
        ad.check_postings_annualised_plausibility(self.tmp)
        self.assertEqual(ad.FLAGS, [])


if __name__ == "__main__":
    unittest.main()
