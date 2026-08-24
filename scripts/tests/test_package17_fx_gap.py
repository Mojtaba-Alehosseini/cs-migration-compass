"""Package 17 — the FX year-matching rule, relaxed exactly where it was doing harm.

Package 9 established: a figure with no matching-year rate is not converted.
That is right for a historical series — pricing a 1968 London house at a 2026
rate would be a lie of fifty-eight years. Applied to a job posted this month it
threw away 88-92% of the annual-pay advertisements for GB, CA, DE and FR to
avoid an error of about two percent.

The rule now takes a MAXIMUM GAP, defaulting to zero. Every existing caller
keeps exact year-matching because none of them passes it; only the postings
conversion opts in. These tests pin both halves, because relaxing a rule is
exactly the kind of change that quietly relaxes it everywhere.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import normalise as nm  # noqa: E402
from postings_common import convert_compensation_to_usd  # noqa: E402

PROCESSED = SCRIPTS.parent / "data" / "processed"


class TestStrictByDefault(unittest.TestCase):
    """The historical series must not have moved an inch."""

    def test_to_usd_still_refuses_a_missing_year_when_not_asked_otherwise(self):
        for cc, year in (("GB", 2026), ("DE", 2026), ("GB", 1959), ("AM", 1988)):
            with self.subTest(country=cc, year=year):
                r = nm.to_usd(1000, cc, year)
                self.assertFalse(r["ok"])
                self.assertIn("never substituted from a different year", r["reason"])

    def test_the_default_is_zero_not_merely_small(self):
        """A default of 1 would silently estimate for every caller in the repo."""
        import inspect
        sig = inspect.signature(nm.to_usd)
        self.assertEqual(sig.parameters["max_gap_years"].default, 0)

    def test_fx_rate_itself_is_untouched(self):
        """The primitive still answers only for the exact year; the allowance
        lives in a separate function so nothing can acquire it by accident."""
        self.assertIsNone(nm.fx_rate("GB", 2026))
        self.assertIsNotNone(nm.fx_rate("GB", 2025))

    def test_the_wage_spine_never_passes_a_gap(self):
        """The spine converts survey figures whose year is the whole point of
        them, so it must still REFUSE a year it has no rate for.

        This asserts behaviour, not source text. An earlier version of this test
        was `assertNotIn("max_gap_years", src)`, which adversarial review broke
        in one line: build_wage_distribution.py calls `nm.to_usd(v, country,
        year)` positionally, so `nm.to_usd(v, country, year, 2)` routes the
        whole wage spine through the allowance without the string ever
        appearing, and all fifteen tests stayed green. A guard that a positional
        argument walks past is not a guard.

        GB 2026 is the case that matters: no 2026 rate is published, a 2025 rate
        is one year away and therefore reachable if anyone ever opts this path
        in. The spine must decline it anyway."""
        import build_wage_distribution as bwd

        value = {f: 50_000 for f in bwd._FIELDS}
        for cc, year in (("GB", 2026), ("DE", 2026), ("CA", 2026)):
            with self.subTest(country=cc, year=year):
                r = bwd._to_usd_all(value, cc, year, bwd._FIELDS[0])
                self.assertFalse(
                    r["ok"],
                    f"the wage spine converted {cc} {year} — it has no {year} rate, so this "
                    f"can only mean the spine now reaches for another year's")
                self.assertIn("never substituted from a different year", r["reason"])

        # Control: the same call for a year that DOES have a rate must succeed,
        # or the assertion above would pass for the wrong reason.
        ok = bwd._to_usd_all(value, "GB", 2025, bwd._FIELDS[0])
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["fx_year"], 2025)


class TestTheAllowance(unittest.TestCase):
    def test_a_one_year_gap_converts_and_says_it_estimated(self):
        r = nm.to_usd(100_000, "GB", 2026, max_gap_years=nm.MAX_FX_GAP_YEARS)
        self.assertTrue(r["ok"])
        self.assertTrue(r["estimated"])
        self.assertEqual(r["fx_year"], 2025)
        self.assertEqual(r["fx_gap_years"], 1)
        self.assertEqual(r["fx_year_requested"], 2026)
        self.assertIn("ESTIMATE", r["chain"][0]["detail"])

    def test_an_exact_year_is_never_marked_as_an_estimate(self):
        r = nm.to_usd(100_000, "GB", 2025, max_gap_years=nm.MAX_FX_GAP_YEARS)
        self.assertTrue(r["ok"])
        self.assertFalse(r["estimated"])
        self.assertEqual(r["fx_gap_years"], 0)
        self.assertNotIn("ESTIMATE", r["chain"][0]["detail"])

    def test_beyond_the_threshold_it_still_refuses(self):
        """The point of a ceiling is that it is reached."""
        for year in (2028, 2029, 2035):
            with self.subTest(year=year):
                r = nm.to_usd(1000, "GB", year, max_gap_years=nm.MAX_FX_GAP_YEARS)
                self.assertFalse(r["ok"])

    def test_a_substituted_rate_can_never_look_exact(self):
        """There is no path returning a substituted rate without the flag."""
        for gap in (0, 1, 2, 3):
            for year in range(2023, 2030):
                r = nm.to_usd(1000, "GB", year, max_gap_years=gap)
                if r["ok"]:
                    with self.subTest(gap=gap, year=year):
                        self.assertIn("estimated", r)
                        self.assertEqual(r["estimated"], r["fx_year"] != year)

    def test_the_nearest_year_wins(self):
        got = nm.fx_rate_within("GB", 2026, 2)
        self.assertEqual(got["year"], 2025)          # 1 back beats 2 back
        self.assertEqual(got["gap_years"], 1)

    def test_a_tie_prefers_the_published_past(self):
        """The documented tie-break, exercised against a series built to
        produce a tie.

        The previous version of this asserted fx_rate_within("GB", 2026, 2) ==
        2025, which is decided by GAP (1 beats 2) and never reaches the
        tie-break at all — inverting the comparison left all fifteen tests
        green. The corpus cannot exercise it either: across every (country,
        year) pair in fx_rates.json there is not one case where two candidate
        years sit at equal distance within the ceiling. A documented rule that
        neither the tests nor the data can reach is a rule nobody is keeping,
        so the series is supplied here."""
        series = [{"year": 2020, "value": 1.10}, {"year": 2022, "value": 9.90}]
        real = nm._fx_series
        nm._fx_series = lambda cc: series if cc == "ZZ" else real(cc)
        try:
            # 2021 is exactly one year from each. The past must win.
            got = nm.fx_rate_within("ZZ", 2021, 2)
            self.assertIsNotNone(got)
            self.assertEqual(got["year"], 2020, "a tie resolved to the future rate")
            self.assertEqual(got["rate"], 1.10)
            self.assertEqual(got["gap_years"], 1)
            self.assertTrue(got["estimated"])
        finally:
            nm._fx_series = real

    def test_the_ceiling_cannot_be_argued_past(self):
        """MAX_FX_GAP_YEARS is a ceiling, not a default. A caller asking for
        more gets the ceiling, not what it asked for — reachable before this
        as to_usd(1000, "GB", 2100, 100) -> gap_years 75, ok True."""
        self.assertIsNone(nm.fx_rate_within("GB", 2100, 100))
        r = nm.to_usd(1000, "GB", 2100, max_gap_years=100)
        self.assertFalse(r["ok"])
        # And a float year cannot produce a float gap to render.
        got = nm.fx_rate_within("GB", 2026.4, nm.MAX_FX_GAP_YEARS)
        self.assertIsInstance(got["gap_years"], int)

    def test_a_mid_series_hole_too_wide_to_bridge_is_still_refused(self):
        """Cambodia has no published rate for 1974-1989. A two-year allowance
        cannot cross a sixteen-year hole, and must not try."""
        r = nm.to_usd(1000, "KH", 1980, max_gap_years=nm.MAX_FX_GAP_YEARS)
        self.assertFalse(r["ok"])

    def test_the_threshold_is_two_and_its_reasoning_is_written_down(self):
        self.assertEqual(nm.MAX_FX_GAP_YEARS, 2)
        src = (SCRIPTS / "normalise.py").read_text(encoding="utf-8")
        self.assertIn("median", src.split("MAX_FX_GAP_YEARS")[0][-2000:],
                      "the constant must carry the measured error that justifies it")
        meth = (SCRIPTS.parent / "docs" / "METHODOLOGY.md").read_text(encoding="utf-8")
        self.assertIn("MAX_FX_GAP_YEARS", meth,
                      "the threshold must be stated in the methodology, not only in code")


class TestPostingsCarryTheFlag(unittest.TestCase):
    def test_a_posting_conversion_carries_the_estimate_flag(self):
        got = convert_compensation_to_usd({"currency": "GBP", "min": 50_000, "max": 60_000}, 2026)
        self.assertIsNotNone(got)
        self.assertTrue(got["estimated"])
        self.assertEqual(got["fx_year"], 2025)
        self.assertEqual(got["fx_gap_years"], 1)

    def test_an_exact_year_posting_is_not_flagged(self):
        got = convert_compensation_to_usd({"currency": "GBP", "min": 50_000, "max": 60_000}, 2025)
        self.assertFalse(got["estimated"])

    def test_every_converted_posting_in_the_corpus_declares_its_gap(self):
        """The property that matters on the wire: a consumer rendering a
        converted figure must be able to mark it without re-deriving why."""
        path = PROCESSED / "postings.json"
        if not path.exists():
            self.skipTest("postings.json not built")
        rows = json.loads(path.read_text(encoding="utf-8"))["data"]["postings"]
        missing = [r["id"] for r in rows
                   if (r.get("compensation") or {}).get("usd")
                   and "estimated" not in r["compensation"]["usd"]]
        self.assertEqual(missing[:5], [],
                         f"{len(missing)} converted postings carry no estimate flag")

    def test_no_posting_is_converted_past_the_threshold(self):
        path = PROCESSED / "postings.json"
        if not path.exists():
            self.skipTest("postings.json not built")
        rows = json.loads(path.read_text(encoding="utf-8"))["data"]["postings"]
        over = [(r["id"], r["compensation"]["usd"]["fx_gap_years"]) for r in rows
                if (r.get("compensation") or {}).get("usd")
                and (r["compensation"]["usd"].get("fx_gap_years") or 0) > nm.MAX_FX_GAP_YEARS]
        self.assertEqual(over[:5], [],
                         f"{len(over)} postings converted at a rate further than "
                         f"{nm.MAX_FX_GAP_YEARS} years away")


if __name__ == "__main__":
    unittest.main()
