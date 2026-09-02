"""Package 25, tier 1 — NEEDS-DECISION #58: a premium and the figure it
shifts must be measured on the SAME pay basis.

Finding F13 (package 11) suspected Norway's USD estimate was shifting a
basic-salary figure by a premium measured on total earnings, and it stayed
open for three packages because NOTHING IN THE DATA STATED EITHER BASIS.
`premium_basis` records mean-vs-median, which is the central statistic, a
different axis entirely.

Package 25 read the basis out of each office's own returned table metadata
and wrote it down (`pay_basis`, `pay_basis_source`). These tests pin the
facts that ruling rests on, so the pairing cannot silently drift:

  SE  SCB LonYrkeAlder4AN ContentsCode 000007BN "Monthly salary" — the same
      concept as its own dispersion table's 000007CD/000007CE (confirmed
      package 26: that table's own FULL ContentsCode list has a second,
      narrower concept, "Basic salary", which the dispersion table does not
      offer at all). manadslon excludes bonus per SCB's own current quality
      declaration (package 26, am0110_kd_2025.pdf, replacing package 25's
      carried pay_composition.json note). => regular_pay, and SE's own
      native figure is regular_pay. MATCHED.
  NO  SSB 11658 ContentsCodes GjMdTotal "Average monthly earnings (NOK)" and
      MedianMndLonn "Median monthly earnings (NOK)". SSB names the other
      concept differently and separately — 11418 carries AvtaltManedslonn
      "Basic monthly salary" — and neither fetched code says basic/Avtalt.
      => total_earnings, and NO's own native figure is total_earnings.
      MATCHED. Its usd_regular_pay combo is NOT, which is what F13 caught.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRADIENT = ROOT / "data" / "processed" / "experience_gradient.json"
WAGES = ROOT / "data" / "processed" / "wage_distribution.json"

VALID_BASES = {"regular_pay", "total_earnings"}


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))["data"]


class TestEveryGradientStatesItsPayBasis(unittest.TestCase):
    """The field whose ABSENCE was the defect."""

    def setUp(self) -> None:
        self.by_country = _load(GRADIENT)["by_country"]

    def test_every_curve_declares_a_valid_pay_basis(self) -> None:
        for cc, entry in self.by_country.items():
            with self.subTest(country=cc):
                basis = entry["meta"].get("pay_basis")
                self.assertIn(basis, VALID_BASES,
                              f"{cc}: pay_basis={basis!r} — a premium whose basis is unknown cannot be "
                              f"safely applied to any figure (NEEDS-DECISION #58)")

    def test_every_curve_cites_where_its_basis_came_from(self) -> None:
        for cc, entry in self.by_country.items():
            with self.subTest(country=cc):
                src = entry["meta"].get("pay_basis_source") or ""
                self.assertTrue(src.strip(),
                                f"{cc}: pay_basis is asserted with no pay_basis_source — the basis must be "
                                f"traceable to the publishing table, not claimed")

    def test_the_two_bases_are_the_ones_read_from_the_source_tables(self) -> None:
        """Pins the Tier 1 ruling itself. If a future refresh flips one of
        these, that is a real change in what the office publishes and must
        be re-read from the table, not silently accepted."""
        self.assertEqual(self.by_country["SE"]["meta"]["pay_basis"], "regular_pay")
        self.assertEqual(self.by_country["NO"]["meta"]["pay_basis"], "total_earnings")

    def test_swedens_own_citation_no_longer_leans_on_a_carried_note(self) -> None:
        """Package 25 closed #58 with an asymmetry stated rather than fixed:
        Norway's basis was settled by SSB's own returned labels directly;
        Sweden's leaned on pay_composition.json's own note, itself carrying
        "verified_live_this_session": false. Package 26 fetched SCB's own
        full ContentsCode metadata (not just the two codes this pipeline
        queries) and its own current quality declaration PDF, and rewrote
        the citation to point at both. This pins that the rewrite happened
        — not that the conclusion is unchanged (a separate test already
        covers that) — so a future edit cannot quietly regress the citation
        back to a carried note without this test naming it."""
        src = self.by_country["SE"]["meta"]["pay_basis_source"]
        self.assertIn("quality declaration", src.lower(),
                      "Sweden's own citation should point at SCB's quality declaration, the live "
                      "source package 26 fetched, not merely restate the old carried note")
        self.assertNotIn("pay_composition.json", src,
                         "the citation should no longer defer to pay_composition.json's own note "
                         "as its evidence for the basis — that note is what package 26 replaced")


class TestGradientBasisMatchesTheNativeFigureItShifts(unittest.TestCase):
    """computeEstimate() (the /work estimate) shifts row.native by this
    country's own premium. Checked in Python, where both files are loadable
    and the native block can be matched against the combos numerically —
    the browser has no basis field on `native` to compare against."""

    def setUp(self) -> None:
        self.by_country = _load(GRADIENT)["by_country"]
        self.rows = {c["country"]: c for c in _load(WAGES)["countries"]}

    def _native_basis(self, row: dict) -> str:
        """Which combo the generic `native` block was actually set from,
        determined numerically rather than assumed: the combos are the same
        figures annualised, so the one whose values are a constant multiple
        of native's is the basis native carries."""
        native = {k: v for k, v in row["native"]["value"].items() if v is not None}
        matches = []
        for basis in sorted(VALID_BASES):
            combo = row["combos"].get(f"native_{basis}")
            if not (combo and combo.get("ok")):
                continue
            cv = combo["value"]
            ratios = [cv[k] / native[k] for k in native if cv.get(k)]
            if ratios and max(ratios) - min(ratios) < 1e-6:
                matches.append(basis)
        self.assertEqual(len(matches), 1,
                         f"{row['country']}: native block matches {matches or 'no'} combo basis — "
                         f"expected exactly one")
        return matches[0]

    def test_each_personalising_country_shifts_a_figure_on_its_own_premium_basis(self) -> None:
        for cc, entry in self.by_country.items():
            with self.subTest(country=cc):
                row = self.rows[cc]
                self.assertEqual(
                    self._native_basis(row), entry["meta"]["pay_basis"],
                    f"{cc}: computeEstimate() shifts row.native, which is "
                    f"{self._native_basis(row)}, by a premium measured on "
                    f"{entry['meta']['pay_basis']} — the exact mismatch NEEDS-DECISION #58 exists for")

    def test_the_usd_path_really_selects_the_basis_matched_combo(self) -> None:
        """The BEHAVIOUR, not the data shape.

        The first version of this test asserted only that NO declares
        total_earnings and that both its USD combos exist — all of which stays
        true if computeEstimateUsdYear() is reverted to preferring
        regular_pay. It was a data-shape test wearing a behaviour test's name
        (package 25, adversarial review). This reads profile.ts itself and
        pins the selection rule: the combo key must be chosen FROM the
        gradient's own pay_basis, and the hardcoded regular-pay-first
        preference must be gone."""
        src = (ROOT / "site" / "src" / "data" / "profile.ts").read_text(encoding="utf-8")
        fn = src[src.index("export function computeEstimateUsdYear"):]
        fn = fn[:fn.index(chr(10) + "}" + chr(10))]
        self.assertIn("cg.meta.pay_basis", fn,
                      "the USD path must choose its combo from the gradient's own stated pay basis")
        self.assertIn("usd_total_earnings", fn)
        self.assertNotIn("const regular = row.combos['usd_regular_pay']", fn,
                         "the unconditional regular-pay-first preference is what NEEDS-DECISION #58 "
                         "ruled wrong for Norway; finding it here means the fix was reverted")

    def test_norways_two_usd_combos_both_exist_so_the_choice_is_real(self) -> None:
        """The selection above is only meaningful if both candidates are
        actually available for Norway — otherwise it would be picking the
        only option and would prove nothing."""
        no = self.rows["NO"]
        self.assertEqual(self.by_country["NO"]["meta"]["pay_basis"], "total_earnings")
        self.assertTrue(no["combos"]["usd_regular_pay"]["ok"])
        self.assertTrue(no["combos"]["usd_total_earnings"]["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
