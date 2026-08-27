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
    DEFAULT_MAX_CONSECUTIVE_FAILURES, build_probe_order, merge_verified_companies, reclaim_cycle_key,
)
import datetime as _dt  # noqa: E402


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

    def test_reclaim_cap_none_is_the_default_and_stays_uncapped(self):
        # Every existing caller passes no reclaim_cap at all -- confirms the
        # new parameter cannot silently change anyone's behaviour who has
        # not opted in.
        candidates = [f"co{i}" for i in range(10)]
        previously_verified = {f"co{i}" for i in range(10)}
        order = build_probe_order(candidates, already_cached=set(), previously_verified=previously_verified,
                                   max_new_per_run=0)
        self.assertEqual(set(order), previously_verified)


class TestReclaimCap(unittest.TestCase):
    """NEEDS-DECISION #41, closed package 21 -- a ROTATING cap, not a flat
    first-N truncation. The property that matters is the one a flat cap
    would fail: every previously-verified company gets reclaimed somewhere
    across a full cycle of keys, not just the ones that happen to sort
    first forever."""

    def test_a_single_run_never_exceeds_the_cap(self):
        previously_verified = {f"co{i}" for i in range(50)}
        order = build_probe_order([], already_cached=set(), previously_verified=previously_verified,
                                   max_new_per_run=0, reclaim_cap=10, reclaim_cycle_key=3)
        self.assertEqual(len(order), 10)
        self.assertTrue(set(order) <= previously_verified)

    def test_a_bucket_at_or_under_the_cap_is_not_truncated(self):
        previously_verified = {f"co{i}" for i in range(8)}
        order = build_probe_order([], already_cached=set(), previously_verified=previously_verified,
                                   max_new_per_run=0, reclaim_cap=10, reclaim_cycle_key=0)
        self.assertEqual(set(order), previously_verified)

    def test_every_company_is_reclaimed_exactly_once_across_a_full_cycle(self):
        # THE property a flat cap cannot have: cycle through every key from
        # 0 to ceil(n/cap)-1 and confirm the union covers everyone, with no
        # company appearing in two different weeks' slices.
        previously_verified = {f"co{i}" for i in range(97)}  # deliberately not a multiple of the cap
        cap = 10
        seen: list[str] = []
        n_cycles = -(-len(previously_verified) // cap)  # ceil
        for key in range(n_cycles):
            order = build_probe_order([], already_cached=set(), previously_verified=previously_verified,
                                       max_new_per_run=0, reclaim_cap=cap, reclaim_cycle_key=key)
            self.assertLessEqual(len(order), cap)
            seen.extend(order)
        self.assertEqual(len(seen), len(set(seen)),
                          "a company was reclaimed in more than one week's slice")
        self.assertEqual(set(seen), previously_verified,
                          "a company was never reclaimed in any week's slice")

    def test_the_same_key_always_selects_the_same_slice(self):
        # Determinism matters here specifically because Python set iteration
        # order is not guaranteed stable across processes -- the cap sorts
        # before slicing for exactly this reason.
        previously_verified = {f"co{i}" for i in range(40)}
        a = build_probe_order([], already_cached=set(), previously_verified=previously_verified,
                               max_new_per_run=0, reclaim_cap=10, reclaim_cycle_key=2)
        b = build_probe_order([], already_cached=set(), previously_verified=set(previously_verified),
                               max_new_per_run=0, reclaim_cap=10, reclaim_cycle_key=2)
        self.assertEqual(a, b)

    def test_reclaim_cycle_key_increments_by_exactly_one_every_week(self):
        # Not the ISO week number (an earlier version) -- see
        # reclaim_cycle_key's own docstring for why that resets at each
        # year boundary in a way that breaks round-robin `% n_chunks`
        # coverage. A plain week counter must never skip or repeat across
        # ANY Monday-to-Monday step, including a real 52/53-week year
        # boundary.
        a = reclaim_cycle_key(_dt.date(2026, 12, 28))
        b = reclaim_cycle_key(_dt.date(2027, 1, 4))  # the following Monday
        self.assertEqual(b, a + 1)

    def test_the_iso_week_number_would_have_broken_rotation_at_this_boundary(self):
        # The regression the test above exists to catch, demonstrated
        # directly: ISO week 53 of 2026 falls on 2026-12-28, ISO week 1 of
        # 2027 the following Monday -- a real, not synthetic, year boundary
        # where the two are not consecutive integers, so `% n_chunks` after
        # the reset does not equal `% n_chunks` before it plus one for
        # several realistic chunk counts. This is exactly the discontinuity
        # the fixed reclaim_cycle_key() (above) no longer has.
        last_iso_week = _dt.date(2026, 12, 28).isocalendar()[1]
        first_iso_week = _dt.date(2027, 1, 4).isocalendar()[1]
        self.assertNotEqual(first_iso_week, last_iso_week + 1,
                             "the ISO week number turned out to be consecutive across this "
                             "boundary after all -- this fixture no longer demonstrates the bug "
                             "the fix (toordinal() // 7) guards against")


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
