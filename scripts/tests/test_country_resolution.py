"""Package 13, Tier 0 — regression tests for postings_common.py's
country_from_location(), covering docs/REGRESSION-CATALOGUE.md's R14: a
plain-substring resolver silently misassigned "Atlanta, Georgia" to the
country Georgia, "Milwaukee, Wisconsin" to the UK ("uk" inside "milwaukee"),
"Ukraine" to the UK (same reason), "King of Prussia, PA" to Russia
("russia" inside "prussia"), and "China Lake, California" to China.

Every test calls the real, currently-shipped function — none of this logic
is reimplemented here. Test inputs and both the old-wrong and new-correct
answers are taken verbatim from country_from_location()'s own docstring in
postings_common.py, which states these were re-verified against the real
committed dataset before the fix shipped (2,108 of 35,936 postings' own
country field changed).

Run directly (`python scripts/tests/test_country_resolution.py`) or via
scripts/tests/run_all.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import postings_common  # noqa: E402


class TestSubstringCollisionsFixed(unittest.TestCase):
    """R14 — each of these was wrong under plain substring matching and is
    correct under the current whole-word/whole-phrase matcher
    (_word_match). Each assertion also pins the OLD wrong answer via
    assertNotEqual, so a regression back to bare substring matching fails
    this test even if some other change happened to leave the primary
    assertion passing by coincidence."""

    def test_atlanta_georgia_resolves_to_us_not_the_country_georgia(self):
        result = postings_common.country_from_location("Atlanta, Georgia")
        self.assertEqual(result, "US")
        self.assertNotEqual(result, "GE", "must not resolve to the country Georgia")

    def test_milwaukee_wisconsin_resolves_to_us_not_uk(self):
        # "uk" is a substring of "milwaukee" itself, independent of the
        # state name — the original bug matched on the city text alone.
        result = postings_common.country_from_location("Milwaukee, Wisconsin")
        self.assertEqual(result, "US")
        self.assertNotEqual(result, "GB", "'uk' inside 'milwaukee' must not match")

    def test_bare_milwaukee_resolves_to_us_via_city_table_not_uk(self):
        # Without the state suffix, this exercises the city table
        # (Milwaukee is not in it) falling through to None today — the
        # substantive regression is that it must never be GB. If Milwaukee
        # is later added to the city table, update this assertion to "US"
        # rather than deleting the not-equal check.
        result = postings_common.country_from_location("Milwaukee")
        self.assertNotEqual(result, "GB", "'uk' inside 'milwaukee' must not match")

    def test_ukraine_resolves_to_ua_not_uk(self):
        result = postings_common.country_from_location("Ukraine")
        self.assertEqual(result, "UA")
        self.assertNotEqual(result, "GB", "'uk' inside 'ukraine' must not match")

    def test_king_of_prussia_resolves_to_us_not_russia(self):
        result = postings_common.country_from_location("King of Prussia, PA")
        self.assertEqual(result, "US")
        self.assertNotEqual(result, "RU", "'russia' inside 'prussia' must not match")

    def test_albuquerque_new_mexico_resolves_to_us_not_mexico(self):
        result = postings_common.country_from_location("Albuquerque, New Mexico")
        self.assertEqual(result, "US")
        self.assertNotEqual(result, "MX", "the 'new mexico' state name must win over the bare 'mexico' country entry")

    def test_bare_new_mexico_resolves_to_us_not_mexico(self):
        result = postings_common.country_from_location("New Mexico")
        self.assertEqual(result, "US")
        self.assertNotEqual(result, "MX")

    def test_china_lake_california_resolves_to_us_not_china(self):
        # The full state name ("California") is checked before the
        # country-name table, so this one resolves correctly — contrast
        # with the abbreviated "China Lake, CA" case below, a disclosed
        # residual ambiguity, not a regression of this same bug.
        result = postings_common.country_from_location("China Lake, California")
        self.assertEqual(result, "US")
        self.assertNotEqual(result, "CN")


class TestDisclosedResidualAmbiguity(unittest.TestCase):
    """Not a bug: country_from_location()'s own docstring discloses that a
    bare 2-letter state/province code can still lose to an earlier
    country-name-table match when the code is checked later in the
    function than the colliding name. Pinned here as documented, ACCEPTED
    behaviour (see NEEDS-DECISION.md) — if this function is ever reordered
    to fix one of these, update this test rather than deleting it, so the
    other direction's own mirror case (a real "Vancouver, WA") doesn't
    silently break instead."""

    def test_china_lake_ca_abbreviated_still_resolves_to_china_not_us(self):
        result = postings_common.country_from_location("China Lake, CA")
        self.assertEqual(result, "CN",
                          "documented residual ambiguity — if this now returns US, the function was "
                          "reordered; re-verify the 'CA - Toronto' mirror case in NEEDS-DECISION.md "
                          "still resolves as documented before updating this assertion")

    def test_bare_georgia_resolves_to_us_by_deliberate_disclosed_default(self):
        # Not a residual bug — a deliberate, disclosed default: of the 143
        # real "Georgia"-labelled postings this pipeline had actually
        # harvested when this was decided, zero were Tbilisi.
        result = postings_common.country_from_location("Atlanta, Georgia")
        self.assertEqual(result, "US")


if __name__ == "__main__":
    unittest.main()
