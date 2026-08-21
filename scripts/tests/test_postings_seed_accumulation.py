"""Package 14, Tier 0 — regression tests for the destructive-refresh bug
the external audit's Finding 3 describes: verified companies fell 1,419 ->
606 (Ashby alone went 862 -> 304) because a postings harvester wrote its
own `verified_companies` fresh every run, with no memory of what the
previous, committed run had already confirmed, and no protection against a
single truncated or rate-limited probe.

These call the real merge functions in scripts/postings_common.py
directly, not a reimplementation of them — a regression here means the
actual pipeline behaviour changed, not that this test's own copy of the
logic drifted from it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from postings_common import (  # noqa: E402
    DEFAULT_MAX_CONSECUTIVE_FAILURES, build_probe_order, merge_verified_companies,
)


class TestBuildProbeOrder(unittest.TestCase):
    def test_cached_tokens_are_always_probed(self):
        order = build_probe_order(["a", "b"], already_cached={"a", "b"}, previously_verified=set(),
                                   max_new_per_run=0)
        self.assertEqual(set(order), {"a", "b"})

    def test_previously_verified_tokens_are_reclaimed_unconditionally_even_with_zero_new_budget(self):
        # This is THE fix. package 12's own committed Ashby seed list (862
        # companies) is far larger than a single run's own "new candidate"
        # cap (400) -- an empty CI cache (data/raw/ is gitignored, no
        # actions/cache step persists it between scheduled runs) means the
        # OLD code's "not already_cached" bucket, capped at 400, is what a
        # committed 862-company list collapsed through. Bucket 2 below must
        # never be capped, or this same collapse just repeats.
        candidates = [f"co{i}" for i in range(1000)]
        previously_verified = {f"co{i}" for i in range(900, 1000)}  # 100 known-good, not cached
        order = build_probe_order(candidates, already_cached=set(), previously_verified=previously_verified,
                                   max_new_per_run=0)
        self.assertEqual(set(order), previously_verified)

    def test_new_candidates_are_still_capped(self):
        candidates = [f"co{i}" for i in range(1000)]
        order = build_probe_order(candidates, already_cached=set(), previously_verified=set(), max_new_per_run=50)
        self.assertEqual(len(order), 50)

    def test_a_token_never_appears_twice_across_buckets(self):
        candidates = [f"co{i}" for i in range(20)]
        already_cached = {"co0", "co1"}
        previously_verified = {"co1", "co2"}  # co1 deliberately in both cached and previously-verified
        order = build_probe_order(candidates, already_cached, previously_verified, max_new_per_run=20)
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(len(order), 20)  # every one of the 20 candidates appears exactly once

    def test_a_previously_verified_token_that_fell_out_of_the_hint_file_is_still_reclaimed(self):
        # L5, an adversarial review finding: a company this pipeline once
        # independently verified must keep getting re-checked even after a
        # THIRD-PARTY aggregator's own hint list stops mentioning its token --
        # otherwise it stays "verified" in the committed file forever, never
        # probed again, never given the chance to earn a failure streak and
        # eventually drop. "orphan" here is deliberately NOT in candidates at
        # all, unlike every other bucket's own tokens.
        candidates = ["co1", "co2"]  # orphan's own token, "orphan", is absent
        previously_verified = {"co1", "orphan"}
        order = build_probe_order(candidates, already_cached=set(), previously_verified=previously_verified,
                                   max_new_per_run=0)
        self.assertIn("orphan", order)
        self.assertEqual(len(order), len(set(order)))  # still no duplicates once reclaimed


class TestMergeVerifiedCompanies(unittest.TestCase):
    def test_a_company_verified_this_run_is_written_fresh_with_streak_reset(self):
        previous = {"acme": {"company": "Acme", "provider": "ashby", "job_count": 3,
                              "consecutive_failures": 2, "last_seen_ok": "2026-08-01T00:00:00+00:00"}}
        this_run = {"acme": {"company": "Acme", "provider": "ashby", "job_count": 5}}
        merged, removed = merge_verified_companies(previous, probed_tokens={"acme"}, this_run_verified=this_run)
        self.assertEqual(merged["acme"]["job_count"], 5)
        self.assertEqual(merged["acme"]["consecutive_failures"], 0)
        self.assertEqual(removed, [])

    def test_the_destructive_bug_itself_a_provider_returning_nothing_no_longer_erases_the_seed_list(self):
        # Tier 5 gate 2's own scenario: one provider's run finds nothing at
        # all (every candidate 404s, times out, or the API is briefly
        # down) -- this is EXACTLY what a single scheduled run looked like
        # right before Finding 3's collapse.
        previous = {f"co{i}": {"company": f"Co {i}", "provider": "ashby", "job_count": 4,
                                "consecutive_failures": 0, "last_seen_ok": "2026-08-01T00:00:00+00:00"}
                    for i in range(300)}
        probed = set(previous.keys())
        merged, removed = merge_verified_companies(previous, probed_tokens=probed, this_run_verified={})
        self.assertEqual(len(merged), 300)  # the whole seed list survives intact
        self.assertEqual(removed, [])  # one bad run removes nobody
        self.assertTrue(all(c["consecutive_failures"] == 1 for c in merged.values()))

    def test_a_company_is_dropped_only_once_it_reaches_the_failure_threshold(self):
        previous = {"acme": {"company": "Acme", "provider": "lever", "job_count": 2,
                              "consecutive_failures": DEFAULT_MAX_CONSECUTIVE_FAILURES - 1,
                              "last_seen_ok": "2026-07-01T00:00:00+00:00"}}
        merged, removed = merge_verified_companies(previous, probed_tokens={"acme"}, this_run_verified={})
        self.assertNotIn("acme", merged)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["token"], "acme")
        self.assertEqual(removed[0]["consecutive_failures"], DEFAULT_MAX_CONSECUTIVE_FAILURES)

    def test_a_company_not_probed_this_run_is_untouched_not_penalised(self):
        previous = {"acme": {"company": "Acme", "provider": "greenhouse", "job_count": 7,
                              "consecutive_failures": 0, "last_seen_ok": "2026-08-01T00:00:00+00:00"}}
        merged, removed = merge_verified_companies(previous, probed_tokens=set(), this_run_verified={})
        self.assertEqual(merged["acme"], previous["acme"])  # byte-for-byte unchanged
        self.assertEqual(removed, [])

    def test_a_brand_new_company_is_added_with_a_zero_failure_streak(self):
        merged, removed = merge_verified_companies(
            {}, probed_tokens={"newco"}, this_run_verified={"newco": {"company": "NewCo", "provider": "ashby", "job_count": 1}})
        self.assertIn("newco", merged)
        self.assertEqual(merged["newco"]["consecutive_failures"], 0)
        self.assertIsNotNone(merged["newco"]["last_seen_ok"])

    def test_recovery_a_previously_lost_company_that_responds_again_is_restored_fresh(self):
        # Tier 0.3's own shape: a token absent from the CURRENTLY committed
        # file (already lost) that responds when re-probed is added back
        # exactly like a brand-new verification -- no special casing
        # needed, restoring is just "verified this run, not in previous".
        merged, removed = merge_verified_companies(
            {}, probed_tokens={"lost_co"}, this_run_verified={"lost_co": {"company": "Lost Co", "provider": "ashby", "job_count": 12}})
        self.assertEqual(merged["lost_co"]["job_count"], 12)
        self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()
