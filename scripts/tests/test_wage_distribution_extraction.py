"""Package 13, Tier 0/5 — regression test for docs/REGRESSION-CATALOGUE.md's
R18: build_wage_distribution.py's own _pick() used k.endswith(suffix), which
matches Norway's real avtalt_mean_nok_month when asked for mean_nok_month
(the LONGER key ends with the shorter one) — genuinely ambiguous between two
different real pay bases (bonus-included Manedslonn vs. bonus-excluded
AvtaltManedslonn), resolved only by accidental dict iteration order. Found by
adversarial review, not anticipated; _extract_no()/_extract_fi() already
worked around it for their own fields by not calling _base_obs() at all, but
the shared helper itself stayed unfixed — this tests the helper directly, so
a future extractor built the ordinary way (calling _base_obs(), the way
_extract_se/_extract_dk/others already do) can't inherit the same ambiguity.

Run directly (`python scripts/tests/test_wage_distribution_extraction.py`)
or via scripts/tests/run_all.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_wage_distribution as bwd  # noqa: E402


class TestPickIsExactNotSuffixMatched(unittest.TestCase):
    def test_the_original_ambiguity_reproduced(self):
        # Norway's own real shape: the SAME row publishes both bases.
        row = {"avtalt_mean_nok_month": 71000, "mean_nok_month": 77420}
        self.assertEqual(bwd._pick(row, "mean_nok_month"), 77420,
                          "must return the row's own exact key, not a longer key that happens to end with it")

    def test_key_order_does_not_change_the_result(self):
        # The old bug's own failure mode was iteration-order-dependent —
        # reversing insertion order must not change which value comes back.
        row = {"mean_nok_month": 77420, "avtalt_mean_nok_month": 71000}
        self.assertEqual(bwd._pick(row, "mean_nok_month"), 77420)

    def test_a_genuinely_missing_key_still_returns_none(self):
        row = {"avtalt_mean_nok_month": 71000}
        self.assertIsNone(bwd._pick(row, "mean_nok_month"))

    def test_base_obs_extracts_the_right_basis_for_a_norway_shaped_row(self):
        row = {"mean_nok_month": 77420, "avtalt_mean_nok_month": 71000,
               "median_nok_month": 75000, "avtalt_median_nok_month": 69500}
        obs = bwd._base_obs("month", "NOK", 2025, row, "nok_month")
        self.assertEqual(obs["mean"], 77420)
        self.assertEqual(obs["median"], 75000)


class TestNativeBasisMatchesWhatEachExtractorsOwnDocstringClaims(unittest.TestCase):
    """Package 27, Tier 3 (NEEDS-DECISION #59, defect B). WagePanel.tsx's own
    "published: X" line used to render unconditionally beside a chain that
    might be computed on a DIFFERENT basis — traced live for Norway under the
    regular_pay toggle: "published: 77,420" (Norway's total_earnings figure)
    sitting directly above "75,500 x 12 = 906,000" (Norway's regular_pay
    figure), a citation that no longer matched its own arithmetic.
    `_native_basis()` is what WagePanel.tsx now gates that line on. Pinned
    per source_id against what each extractor's own docstring already
    claims in English (_extract_no: Manedslonn/total; _extract_fi,
    _extract_de: the regular_ prefix) — so a future edit that changes what
    `native` is built from without updating this function is caught here,
    not live."""

    def test_the_three_dual_native_basis_sources_are_not_all_the_same(self) -> None:
        # If this function returned one constant regardless of source_id, it
        # would pass a test that only checked one source at a time — proven
        # here by checking all three disagree with each other, which a
        # constant-returning stub could not do.
        no = bwd._native_basis("salary_no")
        fi = bwd._native_basis("salary_fi")
        de = bwd._native_basis("salary_de")
        self.assertEqual(no, "total_earnings")
        self.assertEqual(fi, "regular_pay")
        self.assertEqual(de, "regular_pay")
        self.assertNotEqual(no, fi, "Norway and Finland's own native figures are on different bases")

    def test_denmark_matches_neither_basis_its_own_native_is_a_third_concept(self) -> None:
        # STAND is DST's own pre-subtraction figure; both regular_pay and
        # total_earnings are reached FROM it by subtracting something, so it
        # is never equal to either — WagePanel.tsx must never show a
        # "published: X" line for Denmark on any toggle.
        self.assertIsNone(bwd._native_basis("salary_dk"))

    def test_unverified_composition_countries_also_return_none(self) -> None:
        # Canada and Qatar/UAE never show any combo in WagePanel regardless
        # (unverified pay_composition.json entries) — native_basis being
        # None for them is harmless, not a separate bug to chase.
        for source_id in ("salary_ca", "salary_qa", "salary_ae"):
            with self.subTest(source_id=source_id):
                self.assertIsNone(bwd._native_basis(source_id))

    def test_single_basis_sources_match_wagepanels_own_documented_summary(self) -> None:
        # WagePanel.tsx's own docstring names six of these seven explicitly:
        # GB/AU/ES publish bonus-included (total_earnings); SE/US/IE publish
        # bonus-excluded (regular_pay). Pinned here so the two files cannot
        # silently drift apart. The Netherlands is NOT one of the six the
        # docstring enumerates — salary_nl's "regular_pay" is grounded
        # independently, straight from pay_composition.json's own raw entry
        # (irregular_bonus: false, employer_social_contributions: false —
        # the same shape WagePanel.tsx's docstring defines as regular_pay's
        # canonical meaning, just not a country this file's prose happens to
        # name), not by extension of the docstring's own group listing.
        expected = {
            "salary_uk": "total_earnings", "salary_au": "total_earnings", "salary_es": "total_earnings",
            "salary_se": "regular_pay", "bls_oews": "regular_pay", "salary_ie": "regular_pay",
            "salary_nl": "regular_pay",
        }
        for source_id, basis in expected.items():
            with self.subTest(source_id=source_id):
                self.assertEqual(bwd._native_basis(source_id), basis)

    def test_resolve_country_writes_native_basis_onto_the_native_block(self) -> None:
        # Not just that the helper function returns the right value in
        # isolation — that resolve_country() actually threads it onto the
        # field WagePanel.tsx reads (`native.native_basis`), proven by
        # calling resolve_country() itself rather than assuming the wiring.
        obs = {
            "year": 2025, "period": "month", "currency": "NOK",
            "mean": 81050, "median": 77420, "p10": None, "p25": 63330, "p75": 93820, "p90": None,
            "n_employees": 8281,
            "basis_total_earnings": {"mean": 81050, "median": 77420, "p10": None, "p25": 63330, "p75": 93820, "p90": None},
            "basis_regular_pay": {"mean": 78230, "median": 75500, "p10": None, "p25": 62500, "p75": 90170, "p90": None},
        }
        resolved = bwd.resolve_country("NO", "salary_no", "2512", obs, None)
        self.assertEqual(resolved["native"]["native_basis"], "total_earnings")


if __name__ == "__main__":
    unittest.main()
