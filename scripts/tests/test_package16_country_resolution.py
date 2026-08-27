"""Package 16 — the location parser's safety property, and the cases that shaped it.

`country_from_location()` has shipped a matching bug once already: a plain
substring test assigned "Milwaukee, Wisconsin" to the UK, "King of Prussia, PA"
to Russia and "Atlanta, Georgia" to Georgia the country. Package 16 widened the
same function again — 31 country names and a noise-stripping retry — so the
property that made that widening safe is pinned here rather than left to a
one-off script nobody runs twice.

THE PROPERTY: widening may only turn "unresolved" into a country. It may never
change one country into another. Every candidate name was simulated against the
whole committed corpus under that rule, and the three that violated it are still
absent from the table.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
from postings_common import country_from_location  # noqa: E402

PROCESSED = SCRIPTS.parent / "data" / "processed"


class TestCountryResolution(unittest.TestCase):
    def test_remote_prefixes_resolve_to_their_country(self):
        """The single largest fixable group: a country token behind work-
        arrangement boilerplate. 763 postings turned on this alone."""
        for s in ["Remote - US", "Remote US", "US Remote", "US, Remote", "Remote, US",
                  "Remote (US)", "US - Remote", "US-Remote", "Remote (US based)"]:
            with self.subTest(location=s):
                self.assertEqual(country_from_location(s), "US")
        self.assertEqual(country_from_location("Remote CAN"), "CA")

    def test_a_posting_with_no_country_stays_unresolved(self):
        """These are not parse failures. A posting that says "Anywhere" genuinely
        names no country, and inventing one would invent a denominator."""
        for s in ["Remote", "remote", "Anywhere", "Fully Remote", "Global Remote",
                  "Remote (Global)", "World Wide - Remote", "Remoto", "550", ""]:
            with self.subTest(location=s):
                self.assertIsNone(country_from_location(s))

    def test_supra_national_regions_are_not_coerced_into_a_member_state(self):
        for s in ["Asia", "Europe", "LATAM", "North America", "EMEA", "APAC",
                  "Remote - North America"]:
            with self.subTest(location=s):
                self.assertIsNone(country_from_location(s))

    def test_country_names_added_in_package_16(self):
        for s, want in [("Morocco", "MA"), ("Casablanca, Maroc", "MA"), ("Uruguay", "UY"),
                        ("Cochabamba, Bolivia", "BO"), ("Masaya, Nicaragua", "NI"),
                        ("San Salvador, El Salvador", "SV"), ("Kingston, Jamaica", "JM")]:
            with self.subTest(location=s):
                self.assertEqual(country_from_location(s), want)

    def test_four_live_misassignment_groups_are_corrected(self):
        """All FOUR were found by simulating the widening, not by looking for them.
        An earlier report said two; the fixture-based test above enumerates the
        real set, which is how the undercount was caught."""
        # "porto" mapped to Portugal and matched the first word of a Brazilian city
        self.assertEqual(country_from_location("Porto Alegre, Rio Grande do Sul, Brasil"), "BR")
        self.assertEqual(country_from_location("Porto União, Santa Catarina, Brasil"), "BR")
        # the California San Jose won on the city table
        self.assertEqual(country_from_location("San Jose, Costa Rica"), "CR")
        # ...and two more the first write-up omitted: US-government postings
        # physically located abroad, where the location text names the country.
        self.assertEqual(country_from_location("Bahrain Island"), "BH")
        self.assertEqual(country_from_location("Kuwait"), "KW")

    def test_the_three_names_left_out_stay_left_out(self):
        """panama, lebanon and jordan each collide with a US place whose only US
        signal is the 2-letter state code, checked AFTER the country table. If
        someone adds them without reordering that check, these break. See
        NEEDS-DECISION.md #46."""
        self.assertEqual(country_from_location("Panama City Beach, FL"), "US")
        self.assertEqual(country_from_location("Lebanon, OH"), "US")
        self.assertEqual(country_from_location("West Jordan, UT"), "US")
        self.assertEqual(country_from_location("South Jordan, UT"), "US")

    def test_puerto_rico_maps_to_its_own_code_not_us(self):
        """NEEDS-DECISION #47, closed package 21: PR gets its own code. Was US
        through package 20 (deliberately, to avoid taking a position on
        territorial status unasked); the owner has now been asked."""
        self.assertEqual(country_from_location("San Juan, Puerto Rico"), "PR")

    # The four correction groups package 16 made deliberately, and the ONLY
    # disagreements with the pre-package-16 answer that are allowed to exist.
    # Keyed on a location PREFIX because one of them is a 400-character list of
    # thirteen Brazilian municipalities, and a test nobody can read is a test
    # nobody maintains.
    EXPECTED_CORRECTIONS = [
        # "porto" mapped to Portugal and matched the first word of a Brazilian city
        ("Porto Alegre, Rio Grande do Sul, Brasil", "PT", "BR"),
        ("Porto União, Santa Catarina, Brasil", "PT", "BR"),
        ("Araputanga, Mato Grosso, Brasil;", "PT", "BR"),
        # the California San Jose won on the city table
        ("San Jose, Costa Rica", "US", "CR"),
        # US-government postings physically located abroad; the text names the country
        ("Bahrain Island", "US", "BH"),
        ("Kuwait", "US", "KW"),
        # NEEDS-DECISION #47, closed package 21: Puerto Rico gets its own code.
        # Listed individually, not by a shared prefix -- unlike the Brasil group
        # above these seven don't share one (they start with seven different
        # city names), and a test nobody can read is a test nobody maintains
        # applies here too.
        ("Arecibo, Puerto Rico", "US", "PR"),
        ("CBP Puerto Rico/Virgin Islands", "US", "PR"),
        ("Carolina, Puerto Rico", "US", "PR"),
        ("Guaynabo, Puerto Rico", "US", "PR"),
        ("Juana Diaz, Puerto Rico", "US", "PR"),
        ("Puerta De Tierra, Puerto Rico", "US", "PR"),
        ("San Juan, Puerto Rico", "US", "PR"),
    ]

    def test_the_widening_never_reassigns_a_committed_country(self):
        """THE safety property — checked against ground truth the parser did not
        produce.

        An earlier version of this test compared the parser against
        postings.json's own `country` field. That field is SET from this very
        function by apply_postings_annotations.reresolve_countries(), so
        re-running the ordinary pipeline made any parser change self-consistent
        and turned the test green again — while silently reassigning countries.
        A reviewer demonstrated it: adding `panama` produced 12 mismatches, and
        one pipeline run restored a passing test with 34 US postings relabelled
        Panama. Deriving a check's ground truth from the function under test is
        the exact anti-pattern this repo has been bitten by before.

        The fixture is a snapshot of the country assignments as they stood
        BEFORE package 16 touched the parser, taken from git and keyed by
        location TEXT. Re-running the pipeline cannot change it."""
        fix = (Path(__file__).parent / "fixtures"
               / "country_assignments_before_package16.json")
        if not fix.exists():
            self.fail("the ground-truth fixture is missing; this test cannot be satisfied by "
                      "regenerating the pipeline, which is the point of it")
        before = json.loads(fix.read_text(encoding="utf-8"))["assignments"]
        contradictions = set()
        for loc, was in before.items():
            now = country_from_location(loc)
            if now and now != was:
                contradictions.add((loc, was, now))
        def is_expected(loc, was, now):
            return any(loc.startswith(p) and was == w and now == g
                       for p, w, g in self.EXPECTED_CORRECTIONS)

        unexpected = sorted((loc, was, now) for loc, was, now in contradictions
                            if not is_expected(loc, was, now))
        matched = {p for p, w, g in self.EXPECTED_CORRECTIONS
                   if any(loc.startswith(p) and was == w and now == g
                          for loc, was, now in contradictions)}
        missing = sorted({p for p, _, _ in self.EXPECTED_CORRECTIONS} - matched)
        self.assertEqual(
            unexpected, [],
            f"the parser now disagrees with {len(unexpected)} pre-package-16 assignment(s) that "
            f"nobody decided to change. Widening this parser may fill blanks; it may not "
            f"reassign a country without that reassignment being argued for and listed here. "
            f"First few: {[(l[:60], w, g) for l, w, g in unexpected[:5]]}")
        self.assertEqual(
            missing, [],
            f"{len(missing)} documented correction(s) no longer happen — the fix that made them "
            f"has been lost: {missing}")

    def test_the_fixture_is_large_enough_to_be_worth_something(self):
        """A fixture that shrank to a handful of rows would make the test above
        pass trivially, so its size is asserted too."""
        fix = (Path(__file__).parent / "fixtures"
               / "country_assignments_before_package16.json")
        before = json.loads(fix.read_text(encoding="utf-8"))["assignments"]
        self.assertGreater(len(before), 4000,
                           f"only {len(before)} location texts in the ground-truth fixture")

    def test_the_earlier_substring_disasters_stay_fixed(self):
        """Regression pins from the incident this function's docstring records."""
        self.assertEqual(country_from_location("Milwaukee, Wisconsin"), "US")
        self.assertEqual(country_from_location("King of Prussia, PA"), "US")
        self.assertEqual(country_from_location("Atlanta, Georgia"), "US")
        self.assertEqual(country_from_location("China Lake, California"), "US")


if __name__ == "__main__":
    unittest.main()
