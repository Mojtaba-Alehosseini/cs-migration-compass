"""Package 20 -- src_wipo_gii.py's CSV parsing, and proof that package 19's
format-agnostic self-checks fire the same way against a CSV-sourced
full_table as they did against the PDF-sourced one they were built for.
`check_full_table_self_consistency()` itself is not re-implemented or
re-tested here -- it is imported and run for real (as in
test_audit_invariants.py) -- these tests are about the CSV PATH feeding it
correctly-shaped data, including on the specific violations Tier 3's own
gate 4 named: missing rank, duplicated rank, inversion, out-of-range score,
duplicate name, and that ties still pass.

Run directly (`python scripts/tests/test_package20_wipo_csv.py`) or via
scripts/tests/run_all.py.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit_data as ad  # noqa: E402
import src_wipo_gii as wg  # noqa: E402

CSV_HEADER = "v1,iso3,economy_name,income,score,rank,giiyr\n"


def _csv_row(v1, iso3, name, score, rank, giiyr="2025", income="HI"):
    # Mirrors WIPO's own format exactly: the decimal score is comma-separated
    # and quoted, so a raw comma inside it is never read as a delimiter.
    score_field = '"' + str(score).replace(".", ",") + '"'
    return f"{v1},{iso3},{name},{income},{score_field},{rank},{giiyr}\n"


def _make_csv(rows: list[tuple]) -> str:
    return CSV_HEADER + "".join(_csv_row(*r) for r in rows)


def _fetch(csv_text: str):
    with mock.patch.object(wg, "fetch_text", return_value=csv_text):
        return wg.fetch_full_table()


class TestParseDecimalComma(unittest.TestCase):
    def test_converts_a_comma_decimal_to_a_float(self):
        self.assertAlmostEqual(wg._parse_decimal_comma("65,96195221"), 65.96195221)

    def test_the_same_string_breaks_a_bare_float_cast(self):
        # The exact failure mode _parse_decimal_comma exists to avoid --
        # WIPO's real Switzerland row carries this exact value.
        with self.assertRaises(ValueError):
            float("65,96195221")

    def test_a_whole_number_with_no_comma_still_works(self):
        self.assertEqual(wg._parse_decimal_comma("139"), 139.0)


class TestFetchFullTable(unittest.TestCase):
    def test_a_realistic_row_parses_with_the_comma_decimal_intact(self):
        rows = _fetch(_make_csv([(1, "CHE", "Switzerland", "65.96195221", 1)]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["iso3"], "CHE")
        self.assertAlmostEqual(rows[0]["score"], 65.96195221)
        self.assertEqual(rows[0]["rank"], 1)

    def test_rows_are_sorted_by_rank_regardless_of_csv_row_order(self):
        rows = _fetch(_make_csv([
            (2, "SWE", "Sweden", "62.5", 2),
            (1, "CHE", "Switzerland", "66.0", 1),
        ]))
        self.assertEqual([r["rank"] for r in rows], [1, 2])

    def test_a_missing_rank_fails_the_whole_fetch_rather_than_dropping_one_row(self):
        # A malformed row is a signal the CSV itself is not what this script
        # expects -- run()'s own except-block turns this into the same
        # honest "unavailable" status a network failure already gets,
        # matching package 19's "no silent bad data" handling of a
        # malformed PDF row (see src_ef_epi.py / REPORT-P19.md).
        bad_csv = CSV_HEADER + "1,CHE,Switzerland,HI,\"66,0\",,2025\n"  # rank field empty
        with self.assertRaises(ValueError):
            _fetch(bad_csv)


class TestSelfChecksFireAgainstCsvSourcedData(unittest.TestCase):
    """Gate 4: package 19's check_full_table_self_consistency() must fire
    the same way whether meta.full_table came from a PDF or, as here, from
    src_wipo_gii.py's CSV path. Each violation below is built from REAL
    fetch_full_table() output (mocking only the network), not hand-written
    dicts, so this proves the CSV extraction path itself, not just the
    already-tested audit function in isolation."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wipo-csv-test-"))
        ad.ERRORS.clear()
        ad.FLAGS.clear()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rows_from_csv: list[dict], *, published_total: int = None) -> None:
        full_table = [{"rank": r["rank"], "name": r["name"], "score": r["score"]} for r in rows_from_csv]
        doc = {
            "source_id": "test",
            "generated_at": "2026-01-01T00:00:00Z",
            "meta": {
                "full_table": full_table,
                "full_table_stats": {
                    "published_total": published_total if published_total is not None else len(full_table),
                    "range": [0.0, 100.0],
                    "higher_is_better": True,
                },
            },
            "data": {},
        }
        (self.tmp / "test.json").write_text(json.dumps(doc), encoding="utf-8")

    def test_a_clean_csv_derived_table_passes(self):
        rows = _fetch(_make_csv([
            (1, "CHE", "Switzerland", "66.0", 1),
            (2, "SWE", "Sweden", "62.5", 2),
            (3, "USA", "United States of America", "61.69", 3),
        ]))
        self._write(rows)
        ad.check_full_table_self_consistency(self.tmp)
        self.assertEqual(ad.ERRORS, [])

    def test_ties_still_pass_when_sourced_from_the_csv(self):
        rows = _fetch(_make_csv([
            (1, "CHE", "Switzerland", "66.0", 1),
            (2, "SWE", "Sweden", "62.5", 2),
            (2, "NOR", "Norway", "62.5", 2),  # a genuine tie, same rank same score
            (4, "USA", "United States of America", "61.0", 4),
        ]))
        self._write(rows)
        ad.check_full_table_self_consistency(self.tmp)
        self.assertEqual(ad.ERRORS, [])

    def test_a_duplicated_rank_with_different_scores_fires(self):
        rows = _fetch(_make_csv([
            (1, "CHE", "Switzerland", "66.0", 1),
            (2, "SWE", "Sweden", "62.5", 2),
            (2, "NOR", "Norway", "60.0", 2),  # same rank, DIFFERENT score -- not a tie
        ]))
        self._write(rows)
        ad.check_full_table_self_consistency(self.tmp)
        self.assertTrue(any("not a tie, a parse conflict" in e for e in ad.ERRORS), ad.ERRORS)

    def test_an_inversion_fires(self):
        rows = _fetch(_make_csv([
            (1, "CHE", "Switzerland", "50.0", 1),   # rank 1 scores LOWER than rank 2
            (2, "SWE", "Sweden", "62.5", 2),
        ]))
        self._write(rows)
        ad.check_full_table_self_consistency(self.tmp)
        self.assertTrue(any("not monotonic" in e for e in ad.ERRORS), ad.ERRORS)

    def test_an_out_of_range_score_fires(self):
        rows = _fetch(_make_csv([
            (1, "CHE", "Switzerland", "150.0", 1),  # above GII's 0-100 scale
        ]))
        self._write(rows)
        ad.check_full_table_self_consistency(self.tmp)
        self.assertTrue(any("outside the publisher's own range" in e for e in ad.ERRORS), ad.ERRORS)

    def test_a_duplicate_name_fires(self):
        rows = _fetch(_make_csv([
            (1, "CHE", "Switzerland", "66.0", 1),
            (2, "SWE", "Switzerland", "62.5", 2),  # same name as rank 1, different iso3/rank
        ]))
        self._write(rows)
        ad.check_full_table_self_consistency(self.tmp)
        self.assertTrue(any("more than one row" in e for e in ad.ERRORS), ad.ERRORS)

    def test_row_count_below_the_published_total_fires(self):
        rows = _fetch(_make_csv([(1, "CHE", "Switzerland", "66.0", 1)]))
        self._write(rows, published_total=139)  # only 1 row written, 139 claimed
        ad.check_full_table_self_consistency(self.tmp)
        self.assertTrue(any("publisher states 139" in e for e in ad.ERRORS), ad.ERRORS)


if __name__ == "__main__":
    unittest.main()
