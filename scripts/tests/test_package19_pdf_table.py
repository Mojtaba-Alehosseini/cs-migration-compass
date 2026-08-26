"""Package 19 — scripts/pdf_table.py reconstructs column tables from PDF word
geometry instead of flattening pages to text, because flattening interleaves
side-by-side columns onto one line ("23 Australia 48.1 22 6 90 Cabo Verde
22.3 13 4") and silently drops or misreads whichever country's score is not
the first number after its name -- WIPO GII lost the US and the Netherlands
this way, and EF EPI's rank column collapsed into the name ("04Germany")
with no space to split on.

Every test here reproduces, on a small synthetic fixture, one of the bugs
that was actually caught (and fixed) while building this against the real
EF EPI and WIPO GII PDFs -- see pdf_table.py's own docstrings for the fuller
account of each. A fixture that only exercises the happy path would not have
caught any of them the first time; these are written so that reverting the
fix they name makes the test fail, not so that they merely pass today.

Run directly (`python scripts/tests/test_package19_pdf_table.py`) or via
scripts/tests/run_all.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pdf_table as pt  # noqa: E402


def w(text: str, x0: float, top: float) -> dict:
    return {"text": text, "x0": x0, "top": top}


class TestSubLines(unittest.TestCase):
    def test_sub_pixel_baseline_jitter_stays_one_line(self):
        words = [w("Rank", 40, 100.0), w("Name", 80, 100.3), w("Score", 160, 99.8)]
        lines = pt.sub_lines(words)
        self.assertEqual(len(lines), 1)
        self.assertEqual({ww["text"] for ww in lines[0][1]}, {"Rank", "Name", "Score"})

    def test_a_real_row_gap_splits_into_two_lines(self):
        words = [w("Row1", 40, 100.0), w("Row2", 40, 114.0)]
        lines = pt.sub_lines(words)
        self.assertEqual(len(lines), 2)


class TestFindColumns(unittest.TestCase):
    def _clean_table(self, n_rows: int = 12):
        words = []
        for i in range(n_rows):
            top = 100.0 + 14.0 * i
            words += [w(str(i + 1), 40.0, top), w(f"Country{i}", 80.0, top), w(str(10.0 + i), 160.0, top)]
        return words

    def test_detects_one_clean_group_of_three(self):
        groups = pt.find_columns(self._clean_table(), fields_per_group=3)
        self.assertEqual(groups, [(40.0, 80.0, 160.0)])

    def test_scattered_noise_below_min_count_forms_no_group(self):
        words = self._clean_table() + [w("Fig.", 500.0, 50.0), w("3:", 520.0, 50.0), w("caption", 540.0, 50.0)]
        groups = pt.find_columns(words, fields_per_group=3)
        self.assertEqual(groups, [(40.0, 80.0, 160.0)])

    def test_smeared_second_word_positions_do_not_chain_into_a_phantom_column(self):
        # Reproduces the bug: a two-word country name's SECOND word lands at
        # a slightly different x0 on every row ("United States", "New
        # Zealand", "Hong Kong" ...). Each step is only 2px from its
        # neighbour, so a clustering rule that chains off the LAST point
        # added merges all 12 into one wide, meaningless "column". Clustering
        # that caps from the cluster's FIRST point instead breaks this into
        # small clusters that never reach min_count, exactly as a real
        # single, tight column (rank/name/score below) does.
        words = self._clean_table()
        for i in range(12):
            words.append(w("Smear", 118.0 + 2.0 * i, 100.0 + 14.0 * i))
        groups = pt.find_columns(words, fields_per_group=3)
        self.assertEqual(groups, [(40.0, 80.0, 160.0)])

    def test_a_stray_anchor_that_clears_min_count_refuses_rather_than_misaligns(self):
        # Found by an adversarial review: a caption/legend block that happens
        # to clear min_count adds ONE extra anchor. Silently chunking
        # fields_per_group at a time then builds every group from the wrong
        # words from that point on -- on the real WIPO page, five extra
        # words at one existing sub-threshold cluster position took a
        # 139/139 parse to 0 *wrong* rows. Refusing (empty groups) is the
        # safe failure: the caller's row-count self-check reports an empty
        # table loudly instead of accepting a misaligned one silently.
        words = self._clean_table()  # -> exactly 3 clean anchors, 40/80/160
        words += [w(f"note{i}", 5.0, 700.0 + 9.0 * i) for i in range(10)]  # a 4th anchor
        groups = pt.find_columns(words, fields_per_group=3)
        self.assertEqual(groups, [])


class TestParseTable(unittest.TestCase):
    GROUPS = [(40.0, 80.0, 160.0)]

    def test_clean_rows_parse_exactly(self):
        words = [
            w("1", 40, 100), w("Alpha", 80, 100), w("10.5", 160, 100),
            w("2", 40, 114), w("Beta", 80, 114), w("9.0", 160, 114),
            w("3", 40, 128), w("Gamma", 80, 128), w("8.25", 160, 128),
        ]
        results = pt.parse_table(words, self.GROUPS)
        self.assertEqual(results, [(1, "Alpha", 10.5, 0), (2, "Beta", 9.0, 0), (3, "Gamma", 8.25, 0)])

    def test_glued_rank_and_name_split_correctly(self):
        # "04Germany" -- rank and name rendered with zero inter-character
        # gap, so extract_words() returns it as ONE token. Nothing but the
        # leading-digit-run regex separates the rank from the name.
        words = [w("04Germany", 40, 100), w("615", 160, 100)]
        results = pt.parse_table(words, self.GROUPS)
        self.assertEqual(results, [(4, "Germany", 615.0, 0)])

    def test_name_wrapped_across_three_physical_lines_is_fully_recovered(self):
        words = [
            w("1", 40, 100), w("Democratic", 80, 100), w("45.0", 160, 100),
            w("Republic", 80, 114), w("of", 105, 114), w("the", 120, 114),
            w("Congo", 80, 128),
        ]
        results = pt.parse_table(words, self.GROUPS)
        self.assertEqual(results, [(1, "Democratic Republic of the Congo", 45.0, 0)])

    def test_ties_pass_through_as_two_distinct_rows_not_collapsed(self):
        # Two countries genuinely publish at the same rank. parse_table has
        # no opinion on this -- it is not its job to decide whether a
        # repeated rank is a legitimate tie or a parse conflict (that is
        # audit_data.py's job, tested separately) -- it must simply not
        # lose or merge either row.
        words = [
            w("13", 40, 100), w("South", 80, 100), w("Africa", 108, 100), w("602.0", 160, 100),
            w("13", 40, 114), w("Zimbabwe", 80, 114), w("602.0", 160, 114),
        ]
        results = pt.parse_table(words, self.GROUPS)
        self.assertEqual(results, [(13, "South Africa", 602.0, 0), (13, "Zimbabwe", 602.0, 0)])


class TestParseTableIndependentGroups(unittest.TestCase):
    # Two column groups sharing physical lines -- WIPO GII's actual layout,
    # "1 Switzerland 66.0 1 1 71 Colombia 28.5 18 5" packs two countries
    # into one subline. The whole point of per-group x-zone parsing is that
    # group 1's rank can never be read as group 0's score.
    GROUPS = [(40.0, 80.0, 160.0), (250.0, 290.0, 370.0)]

    def test_neighbouring_group_never_leaks_into_this_groups_score(self):
        words = [
            w("5", 40, 100), w("Foo", 80, 100), w("12.3", 160, 100),
            w("6", 250, 100), w("Bar", 290, 100), w("45.6", 370, 100),
        ]
        results = pt.parse_table(words, self.GROUPS)
        self.assertEqual(results, [(5, "Foo", 12.3, 0), (6, "Bar", 45.6, 1)])

    def test_packed_row_with_real_scores_in_both_zones_is_kept(self):
        words = [
            w("1", 40, 100), w("Switzerland", 80, 100), w("66.0", 160, 100),
            w("1", 250, 100), w("Colombia", 290, 100), w("28.5", 370, 100),
        ]
        results = pt.parse_table(words, self.GROUPS)
        self.assertEqual(len(results), 2)

    def test_footer_spanning_both_name_zones_with_no_score_anywhere_is_dropped(self):
        # "Low-income Sub-Saharan Africa Latin America and the Caribbean" --
        # a caption sitting far below the last real row, touching both
        # groups' NAME zones but carrying no number in either SCORE zone.
        good = [
            w("1", 40, 100), w("Switzerland", 80, 100), w("66.0", 160, 100),
            w("1", 250, 100), w("Colombia", 290, 100), w("28.5", 370, 100),
        ]
        footer = [w("Sub-Saharan", 80, 200), w("Latin", 290, 200)]
        results = pt.parse_table(good + footer, self.GROUPS)
        self.assertEqual(len(results), 2)
        self.assertNotIn("Sub-Saharan", " ".join(r[1] for r in results))

    def test_a_word_geometrically_in_the_score_zone_must_still_parse_as_a_number(self):
        # "Caribbean" (tail of the footer above) can land inside a score
        # x-range by coincidence. Landing there is not enough -- it must
        # actually parse as a float, or the footer-exclusion filter is
        # defeated by the very column it is supposed to protect.
        footer_only = [w("Sub-Saharan", 80, 200), w("Caribbean", 370, 200)]
        results = pt.parse_table(footer_only, self.GROUPS)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
