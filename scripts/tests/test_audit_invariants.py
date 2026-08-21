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
        self.assertTrue(any("cannot be recovered" in e for e in ad.ERRORS), ad.ERRORS)

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
    """check_magnitude_plausibility() deliberately excludes 'mean' from its
    own buckets (each distribution's spread is counted once via its
    percentiles, not mean too) and _find_families() needs >=2 matching
    fields to recognise a family at all -- so every fixture here carries
    both mean_usd_year AND median_usd_year, and the outlier is on median,
    the field that's actually bucketed."""

    def test_flags_an_order_of_magnitude_outlier(self):
        occs = {str(i): {"mean_usd_year": 80000 + i * 500, "median_usd_year": 78000 + i * 500} for i in range(8)}
        occs["outlier"] = {"mean_usd_year": 8_000_000, "median_usd_year": 8_000_000}  # 100x the rest
        self._write("bad", "bad", {"occupations": occs})
        ad.check_magnitude_plausibility(self.tmp)
        self.assertTrue(any("plausible range" in f for f in ad.FLAGS), ad.FLAGS)

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


if __name__ == "__main__":
    unittest.main()
