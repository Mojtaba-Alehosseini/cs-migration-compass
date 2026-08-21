"""Package 14, Tier 1 — unit tests for crosswalk.resolve_set(), the set-wide
comparability rule the external audit's severe Finding 1 required. An
independent adversarial review flagged that this function shipped with NO
test coverage at all (unlike every other audit rule in this codebase) and,
separately, that an earlier revision had a real bug two of these tests exist
specifically to catch: M2 (a country deeper than the resolved depth was
marked "comparable, degraded" while its underlying VALUE stayed at its own
native, undegraded depth) and M3 (Canada's own two wage-panel rows, both
4-digit, double-counted as two countries toward the quorum instead of one).

Inputs below are shaped exactly like compare()'s own return value (see that
function's docstring) — synthetic depths and labels, not full occupation
mappings, since resolve_set() only ever reads {comparable, depth,
shared_key, reason} off each entry and never re-touches occupations.json
itself.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from crosswalk import resolve_set  # noqa: E402


def _comparable(depth: int, code: str) -> dict:
    return {"comparable": True, "depth": depth, "shared_key": f"isco08:{code[:depth]}", "degraded_by": None}


def _uncomparable(reason: str = "no ISCO-08 correspondence") -> dict:
    return {"comparable": False, "reason": reason}


class TestResolveSetQuorumAndDepth(unittest.TestCase):
    def test_deepest_depth_meeting_quorum_wins_over_shallowest_and_lone_outlier(self):
        # US and SE both reach 4-digit (quorum 2); IE only reaches 1-digit
        # alone. resolved_depth must be 4, not 1 (dragged down by IE) and
        # not skipped in favour of some deeper depth no pair shares.
        verdicts = {
            "US": _comparable(4, "2514"),
            "SE": _comparable(4, "2514"),
            "IE": _comparable(1, "2"),
        }
        result = resolve_set(verdicts)
        self.assertEqual(result["resolved_depth"], 4)
        self.assertEqual(result["shared_key"], "isco08:2514")

    def test_a_lone_deepest_country_does_not_resolve_the_set_to_its_own_depth(self):
        # Only DE reaches 4-digit; US and SE both reach 2-digit (quorum 2).
        # resolved_depth must be 2, not 4 -- "one country being 4-digit is
        # not 'a depth the SET shares'" (this function's own docstring).
        verdicts = {
            "DE": _comparable(4, "2514"),
            "US": _comparable(2, "25"),
            "SE": _comparable(2, "25"),
        }
        result = resolve_set(verdicts)
        self.assertEqual(result["resolved_depth"], 2)

    def test_no_depth_meets_quorum_resolves_to_none_and_every_row_excluded(self):
        verdicts = {
            "US": _comparable(4, "2514"),
            "SE": _comparable(2, "25"),
            "IE": _comparable(1, "2"),
        }
        result = resolve_set(verdicts)
        self.assertIsNone(result["resolved_depth"])
        self.assertIsNone(result["shared_key"])
        for label in verdicts:
            self.assertFalse(result["verdicts"][label]["comparable"])
            self.assertIn("reason", result["verdicts"][label])

    def test_already_uncomparable_rows_pass_through_with_their_own_reason(self):
        verdicts = {
            "US": _comparable(4, "2514"),
            "SE": _comparable(4, "2514"),
            "QA": _uncomparable("QA has no ISCO-08 correspondence at all for this occupation"),
        }
        result = resolve_set(verdicts)
        self.assertEqual(result["resolved_depth"], 4)
        self.assertEqual(result["verdicts"]["QA"],
                          {"comparable": False,
                           "reason": "QA has no ISCO-08 correspondence at all for this occupation"})

    def test_empty_input_resolves_to_none_without_crashing(self):
        result = resolve_set({})
        self.assertIsNone(result["resolved_depth"])
        self.assertEqual(result["verdicts"], {})

    def test_all_uncomparable_input_resolves_to_none_without_crashing(self):
        verdicts = {"QA": _uncomparable(), "AE": _uncomparable()}
        result = resolve_set(verdicts)
        self.assertIsNone(result["resolved_depth"])
        self.assertFalse(result["verdicts"]["QA"]["comparable"])
        self.assertFalse(result["verdicts"]["AE"]["comparable"])


class TestResolveSetExactMatchRegressionM2(unittest.TestCase):
    """M2 — a country DEEPER than resolved_depth must be excluded, not
    marked "comparable, degraded" while still carrying its own deeper,
    undegraded value underneath."""

    def test_a_country_deeper_than_resolved_depth_is_excluded_not_degraded(self):
        # US and SE both 2-digit (quorum 2, resolves to 2); DE reaches
        # 4-digit -- deeper than the resolved depth. DE must be EXCLUDED,
        # never "comparable" at 2-digit while build_wage_distribution.py's
        # own combos[key].value for DE is still scoped to its native
        # 4-digit occupation.
        verdicts = {
            "US": _comparable(2, "25"),
            "SE": _comparable(2, "25"),
            "DE": _comparable(4, "2514"),
        }
        result = resolve_set(verdicts)
        self.assertEqual(result["resolved_depth"], 2)
        de = result["verdicts"]["DE"]
        self.assertFalse(de["comparable"])
        self.assertNotIn("degraded", de)
        self.assertIn("deeper than", de["reason"])

    def test_a_comparable_row_never_carries_a_degraded_or_degraded_by_field(self):
        verdicts = {"US": _comparable(4, "2514"), "SE": _comparable(4, "2514")}
        result = resolve_set(verdicts)
        us = result["verdicts"]["US"]
        self.assertTrue(us["comparable"])
        self.assertEqual(us["depth"], us["own_depth"])
        self.assertNotIn("degraded", us)
        self.assertNotIn("degraded_by", us)

    def test_a_shallower_country_is_still_excluded_the_same_as_before(self):
        # Confirms the too-shallow branch (already correct pre-M2) still
        # works after the exact-match rewrite -- not just the new
        # too-deep branch.
        verdicts = {
            "US": _comparable(4, "2514"),
            "SE": _comparable(4, "2514"),
            "IE": _comparable(1, "2"),
        }
        result = resolve_set(verdicts)
        ie = result["verdicts"]["IE"]
        self.assertFalse(ie["comparable"])
        self.assertIn("cannot meet", ie["reason"])


class TestResolveSetQuorumCountsCountriesRegressionM3(unittest.TestCase):
    """M3 — Canada's two wage-panel rows (CA-21231, CA-21232, one per NOC
    code) must count as ONE country toward the quorum, not two."""

    def test_two_rows_from_the_same_country_do_not_alone_satisfy_quorum_two(self):
        # Both Canadian rows reach 4-digit, but that is still only ONE
        # country -- min_quorum=2 must NOT be satisfied by CA alone.
        verdicts = {
            "CA-21231": _comparable(4, "2514"),
            "CA-21232": _comparable(4, "2513"),
        }
        result = resolve_set(verdicts)
        self.assertIsNone(result["resolved_depth"])

    def test_canadas_two_rows_plus_one_more_real_country_do_satisfy_quorum_two(self):
        # Adding a genuinely different country at the same depth should
        # bring the distinct-country count to 2 and resolve.
        verdicts = {
            "CA-21231": _comparable(4, "2514"),
            "CA-21232": _comparable(4, "2513"),
            "US": _comparable(4, "2514"),
        }
        result = resolve_set(verdicts)
        self.assertEqual(result["resolved_depth"], 4)
        self.assertTrue(result["verdicts"]["CA-21231"]["comparable"])
        self.assertTrue(result["verdicts"]["CA-21232"]["comparable"])
        self.assertTrue(result["verdicts"]["US"]["comparable"])

    def test_forcing_country_names_in_the_disclosure_text_are_not_duplicated(self):
        # Canada's own two rows must appear as "CA" once in the "who
        # forced it" prose, not "CA, CA" -- forcing is deduplicated by
        # base_country even though forcing_labels (used for shared_key)
        # is not.
        verdicts = {
            "CA-21231": _comparable(4, "2514"),
            "CA-21232": _comparable(4, "2513"),
            "US": _comparable(4, "2514"),
            "IE": _comparable(1, "2"),
        }
        result = resolve_set(verdicts)
        reason = result["verdicts"]["IE"]["reason"]
        self.assertIn("CA", reason)
        self.assertNotIn("CA, CA", reason)


if __name__ == "__main__":
    unittest.main()
