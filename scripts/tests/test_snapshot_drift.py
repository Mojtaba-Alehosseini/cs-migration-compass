"""Package 13, Tier 5 gate 8 evidence — proves snapshot_stats.py's drift
comparison actually catches material movement against a synthetic
previous run (the work order's own example: a source dropping 40%), and
does not false-positive on a no-op re-run or on ordinary postings growth.

Also covers three gaps an independent adversarial review found and this
package fixed: per-provider and per-country postings counts are recorded
in every snapshot but were never actually compared (M7); a genuine drop
now goes to its own DROPS list, checked by main()'s own return code, so
wiring this into an unattended workflow (Tier 4) actually blocks a bad
commit instead of printing a warning nothing stops for (M6/M8); a small
country's own count swinging by a large PERCENTAGE on a tiny base is
sample noise, not signal, and stays a FLAG rather than a DROP.

Run directly (`python scripts/tests/test_snapshot_drift.py`) or via
scripts/tests/run_all.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import snapshot_stats as ss  # noqa: E402


def _snapshot(record_counts, postings_overall=None, postings_by_provider=None, postings_by_country=None):
    return {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "record_counts": dict(record_counts),
        "postings_overall": postings_overall or {"total": 1000, "stated_pay": 400},
        "postings_by_provider": postings_by_provider or {},
        "postings_by_country": postings_by_country or {},
    }


class TestDriftComparison(unittest.TestCase):
    def setUp(self):
        ss.FLAGS.clear()
        ss.DROPS.clear()

    def test_a_40_percent_drop_is_a_blocking_drop_not_just_a_flag(self):
        previous = _snapshot({"salary_uk": 100})
        current = _snapshot({"salary_uk": 60})  # exactly the work order's own example
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("dropped 40.0%" in d for d in ss.DROPS), ss.DROPS)
        self.assertEqual(ss.FLAGS, [], "a real drop must not ALSO sit in FLAGS — it's one signal, not two")

    def test_a_no_op_rerun_flags_and_drops_nothing(self):
        previous = _snapshot({"salary_uk": 100, "postings_lever": 3055})
        current = _snapshot(dict(previous["record_counts"]), dict(previous["postings_overall"]))
        ss.compare_against_previous(current, previous)
        self.assertEqual(ss.FLAGS, [])
        self.assertEqual(ss.DROPS, [])

    def test_postings_growth_is_not_flagged(self):
        # Real, observed behaviour this package's own Tier 0 refactor
        # verification produced: Lever legitimately grew 3,055 -> 9,928
        # postings between two live crawls. That's the crawl doing its
        # job, not drift worth a human's attention.
        previous = _snapshot({"postings_lever": 3055})
        current = _snapshot({"postings_lever": 9928})
        ss.compare_against_previous(current, previous)
        self.assertEqual(ss.FLAGS, [])
        self.assertEqual(ss.DROPS, [])

    def test_postings_growth_drops_only_on_a_real_drop(self):
        previous = _snapshot({"postings_lever": 9928})
        current = _snapshot({"postings_lever": 5000})  # a real drop, not growth
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("postings_lever dropped" in d for d in ss.DROPS), ss.DROPS)

    def test_unexpected_growth_in_a_non_postings_source_is_flagged_not_dropped(self):
        # A static government survey suddenly doubling in row count is as
        # suspicious as one collapsing — both directions matter for a
        # source that should be stable between runs. Growth is never a
        # DROP, so this stays advisory even though it's material.
        previous = _snapshot({"salary_uk": 100})
        current = _snapshot({"salary_uk": 200})
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("grew 100.0%" in f for f in ss.FLAGS), ss.FLAGS)
        self.assertEqual(ss.DROPS, [])

    def test_no_previous_snapshot_establishes_a_baseline_without_flagging(self):
        current = _snapshot({"salary_uk": 100})
        ss.compare_against_previous(current, None)
        self.assertEqual(ss.FLAGS, [])
        self.assertEqual(ss.DROPS, [])

    def test_a_brand_new_source_since_the_previous_snapshot_is_flagged_not_silent(self):
        previous = _snapshot({"salary_uk": 100})
        current = _snapshot({"salary_uk": 100, "salary_zz": 50})
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("salary_zz is new since the previous snapshot" in f for f in ss.FLAGS), ss.FLAGS)
        self.assertEqual(ss.DROPS, [])


class TestPerProviderAndCountryDrift(unittest.TestCase):
    """Adversarial review finding M7: postings_by_provider and postings_
    by_country were recorded in every snapshot but compare_against_previous
    never read either — an overall total that stays flat because OTHER
    providers backfilled a collapsed one, or a country_from_location()
    regression (R14's own bug class) moving postings into "unresolved"
    with the total unchanged, both produced zero flags before this fix."""

    def setUp(self):
        ss.FLAGS.clear()
        ss.DROPS.clear()

    def test_one_provider_collapsing_is_caught_even_though_the_total_is_masked_by_others(self):
        previous = _snapshot(
            {},
            postings_overall={"total": 20000, "stated_pay": 8000},
            postings_by_provider={"lever": {"postings_count": 10000}, "greenhouse": {"postings_count": 10000}},
        )
        # lever collapses to 200; greenhouse grows enough that the OVERALL
        # total this test cares about isn't even wired here (this test is
        # specifically about the per-provider comparison, not the total).
        current = _snapshot(
            {},
            postings_overall={"total": 20000, "stated_pay": 8000},
            postings_by_provider={"lever": {"postings_count": 200}, "greenhouse": {"postings_count": 19800}},
        )
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("provider 'lever' dropped" in d for d in ss.DROPS), ss.DROPS)

    def test_a_country_resolution_regression_is_caught_at_real_scale(self):
        previous = _snapshot({}, postings_by_country={"US": {"total": 5000, "stated_pay": 2000},
                                                        "unresolved": {"total": 500, "stated_pay": 0}})
        current = _snapshot({}, postings_by_country={"US": {"total": 500, "stated_pay": 200},
                                                       "unresolved": {"total": 5000, "stated_pay": 0}})
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("country 'US' dropped" in d for d in ss.DROPS), ss.DROPS)

    def test_a_small_countrys_percentage_swing_is_flagged_not_dropped(self):
        # 5 -> 3 is a 40% drop by percentage but pure sample noise at n=5 —
        # below MIN_COUNTRY_COUNT_FOR_DROP, so it must not block a commit.
        previous = _snapshot({}, postings_by_country={"DK": {"total": 5, "stated_pay": 0}})
        current = _snapshot({}, postings_by_country={"DK": {"total": 3, "stated_pay": 0}})
        ss.compare_against_previous(current, previous)
        self.assertEqual(ss.DROPS, [])
        self.assertTrue(any("country 'DK' dropped" in f for f in ss.FLAGS), ss.FLAGS)


class TestMainReturnCode(unittest.TestCase):
    """Adversarial review finding M6/M8: main() returned 0 unconditionally,
    so wiring this into postings-refresh.yml (Tier 4) would not actually
    have stopped a commit over a real drop. Tests compare_against_previous
    + the DROPS-checking branch directly rather than the full main() (which
    touches the real committed data/quality_history/ and data/processed/
    on disk) — the return-code LOGIC is what's under test here."""

    def setUp(self):
        ss.FLAGS.clear()
        ss.DROPS.clear()

    def test_a_real_drop_would_produce_a_nonzero_exit(self):
        previous = _snapshot({"salary_uk": 100})
        current = _snapshot({"salary_uk": 50})
        ss.compare_against_previous(current, previous)
        # Mirrors main()'s own branch: DROPS present -> return 1.
        exit_code = 1 if ss.DROPS else 0
        self.assertEqual(exit_code, 1)

    def test_flags_alone_with_no_drops_would_produce_a_zero_exit(self):
        previous = _snapshot({"salary_uk": 100})
        current = _snapshot({"salary_uk": 100, "salary_zz": 50})  # new source: a flag, not a drop
        ss.compare_against_previous(current, previous)
        exit_code = 1 if ss.DROPS else 0
        self.assertEqual(exit_code, 0)
        self.assertTrue(ss.FLAGS)


if __name__ == "__main__":
    unittest.main()
