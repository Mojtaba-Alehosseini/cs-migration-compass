"""Package 13, Tier 5 gate 8 evidence — proves snapshot_stats.py's drift
comparison actually catches material movement against a synthetic
previous run (the work order's own example: a source dropping 40%), and
does not false-positive on a no-op re-run or on ordinary postings growth.

Run directly (`python scripts/tests/test_snapshot_drift.py`) or via
scripts/tests/run_all.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import snapshot_stats as ss  # noqa: E402


def _snapshot(record_counts, postings_overall=None):
    return {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "record_counts": dict(record_counts),
        "postings_overall": postings_overall or {"total": 1000, "stated_pay": 400},
    }


class TestDriftComparison(unittest.TestCase):
    def setUp(self):
        ss.FLAGS.clear()

    def test_a_40_percent_drop_is_flagged(self):
        previous = _snapshot({"salary_uk": 100})
        current = _snapshot({"salary_uk": 60})  # exactly the work order's own example
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("dropped 40.0%" in f for f in ss.FLAGS), ss.FLAGS)

    def test_a_no_op_rerun_flags_nothing(self):
        previous = _snapshot({"salary_uk": 100, "postings_lever": 3055})
        current = _snapshot(dict(previous["record_counts"]), dict(previous["postings_overall"]))
        ss.compare_against_previous(current, previous)
        self.assertEqual(ss.FLAGS, [])

    def test_postings_growth_is_not_flagged(self):
        # Real, observed behaviour this package's own Tier 0 refactor
        # verification produced: Lever legitimately grew 3,055 -> 9,928
        # postings between two live crawls. That's the crawl doing its
        # job, not drift worth a human's attention.
        previous = _snapshot({"postings_lever": 3055})
        current = _snapshot({"postings_lever": 9928})
        ss.compare_against_previous(current, previous)
        self.assertEqual(ss.FLAGS, [])

    def test_postings_growth_flags_only_on_a_drop(self):
        previous = _snapshot({"postings_lever": 9928})
        current = _snapshot({"postings_lever": 5000})  # a real drop, not growth
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("postings_lever dropped" in f for f in ss.FLAGS), ss.FLAGS)

    def test_unexpected_growth_in_a_non_postings_source_is_flagged(self):
        # A static government survey suddenly doubling in row count is as
        # suspicious as one collapsing — both directions matter for a
        # source that should be stable between runs.
        previous = _snapshot({"salary_uk": 100})
        current = _snapshot({"salary_uk": 200})
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("grew 100.0%" in f for f in ss.FLAGS), ss.FLAGS)

    def test_no_previous_snapshot_establishes_a_baseline_without_flagging(self):
        current = _snapshot({"salary_uk": 100})
        ss.compare_against_previous(current, None)
        self.assertEqual(ss.FLAGS, [])

    def test_a_brand_new_source_since_the_previous_snapshot_is_flagged_not_silent(self):
        previous = _snapshot({"salary_uk": 100})
        current = _snapshot({"salary_uk": 100, "salary_zz": 50})
        ss.compare_against_previous(current, previous)
        self.assertTrue(any("salary_zz is new since the previous snapshot" in f for f in ss.FLAGS), ss.FLAGS)


if __name__ == "__main__":
    unittest.main()
