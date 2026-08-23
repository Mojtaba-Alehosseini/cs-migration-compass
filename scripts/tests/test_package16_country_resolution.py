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

    def test_two_live_misassignments_are_corrected(self):
        """Both were found by simulating the widening, not by looking for them."""
        # "porto" mapped to Portugal and matched the first word of a Brazilian city
        self.assertEqual(country_from_location("Porto Alegre, Rio Grande do Sul, Brasil"), "BR")
        self.assertEqual(country_from_location("Porto União, Santa Catarina, Brasil"), "BR")
        # the California San Jose won on the city table
        self.assertEqual(country_from_location("San Jose, Costa Rica"), "CR")

    def test_the_three_names_left_out_stay_left_out(self):
        """panama, lebanon and jordan each collide with a US place whose only US
        signal is the 2-letter state code, checked AFTER the country table. If
        someone adds them without reordering that check, these break. See
        NEEDS-DECISION.md #46."""
        self.assertEqual(country_from_location("Panama City Beach, FL"), "US")
        self.assertEqual(country_from_location("Lebanon, OH"), "US")
        self.assertEqual(country_from_location("West Jordan, UT"), "US")
        self.assertEqual(country_from_location("South Jordan, UT"), "US")

    def test_puerto_rico_maps_to_us_not_to_its_own_code(self):
        """A territorial-status question this pipeline does not answer. See #47."""
        self.assertEqual(country_from_location("San Juan, Puerto Rico"), "US")

    def test_the_widening_never_reassigns_a_committed_country(self):
        """THE safety property, checked against the real corpus rather than a
        handful of strings. Every row the parser can resolve must agree with the
        country the pipeline committed — except where the pipeline itself is the
        source (a provider stamps the country and the location text does not name
        it), which is why disagreement is only allowed in that direction."""
        path = PROCESSED / "postings.json"
        if not path.exists():
            self.skipTest("postings.json not built")
        rows = json.loads(path.read_text(encoding="utf-8"))["data"]["postings"]
        mismatched = []
        for r in rows:
            got = country_from_location(r.get("location_raw"))
            if got and r.get("country") and got != r["country"]:
                mismatched.append((r.get("location_raw"), r["country"], got))
        self.assertEqual(
            mismatched, [],
            f"{len(mismatched)} postings carry a country the parser now disagrees with. "
            f"Widening this parser may only fill blanks. First few: {mismatched[:5]}")

    def test_the_earlier_substring_disasters_stay_fixed(self):
        """Regression pins from the incident this function's docstring records."""
        self.assertEqual(country_from_location("Milwaukee, Wisconsin"), "US")
        self.assertEqual(country_from_location("King of Prussia, PA"), "US")
        self.assertEqual(country_from_location("Atlanta, Georgia"), "US")
        self.assertEqual(country_from_location("China Lake, California"), "US")


if __name__ == "__main__":
    unittest.main()
