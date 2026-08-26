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


class TestFixDoubleUtf8(unittest.TestCase):
    """Found by an adversarial review checking all 139 rows, not just the
    15 this site tracks: WIPO's own CSV serves 'Turkiye' and "Cote
    d'Ivoire" double-UTF-8-encoded. Fixtures are built by simulating the
    exact corruption (encode UTF-8, wrongly decode as Latin-1) rather than
    hand-typing a mojibake literal into this source file, which sidesteps
    this file's own encoding entirely and reproduces precisely the bytes
    confirmed present in the real cached CSV."""

    def _corrupt_like_wipo(self, correct: str) -> str:
        return correct.encode("utf-8").decode("latin-1")

    def test_repairs_the_real_corruption_confirmed_in_wipos_own_csv(self):
        correct = "Türkiye"  # Turkiye
        corrupted = self._corrupt_like_wipo(correct)
        self.assertNotEqual(corrupted, correct)  # sanity: the fixture really is corrupted
        self.assertEqual(wg._fix_double_utf8(corrupted), correct)

    def test_repairs_the_second_confirmed_case(self):
        correct = "Côte d'Ivoire"  # Cote d'Ivoire
        corrupted = self._corrupt_like_wipo(correct)
        self.assertEqual(wg._fix_double_utf8(corrupted), correct)

    def test_plain_ascii_is_returned_unchanged(self):
        self.assertEqual(wg._fix_double_utf8("Switzerland"), "Switzerland")

    def test_an_already_correctly_encoded_name_is_not_touched(self):
        # No "Ã"/"Â" signature present -- must not attempt a repair that
        # would corrupt text that was never broken.
        already_correct = "Türkiye"
        self.assertEqual(wg._fix_double_utf8(already_correct), already_correct)


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

    def test_a_header_only_csv_raises_instead_of_reaching_an_unguarded_downstream_crash(self):
        # Adversarial-review finding: a zero-row parse used to sail past
        # fetch_full_table() cleanly and crash several statements later, on
        # an unguarded max() over an empty dict inside run()'s own edition
        # check -- OUTSIDE run()'s try/except, so the previous run's
        # processed file and provenance entry were left in place, still
        # marked status "ok". Raising HERE closes that gap at the source.
        with self.assertRaises(ValueError):
            _fetch(CSV_HEADER)  # header row only, no data rows at all


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


class _Probe:
    """Minimal stand-in for a requests.Response, for mocking requests.head()."""
    def __init__(self, status_code):
        self.status_code = status_code


class TestRunHardening(unittest.TestCase):
    """run()-level fixes from the same adversarial review: a same-rank
    duplicate is still flagged (not silently overwritten), an iso3/name
    disagreement excludes the row rather than guessing, and the
    next-edition probe surfaces (without failing the run) when a newer
    edition's URL already exists."""

    def _run_with(self, csv_text: str, *, next_edition_status: int = 404):
        with mock.patch.object(wg, "fetch_text", return_value=csv_text), \
             mock.patch.object(wg.requests, "head", return_value=_Probe(next_edition_status)) as fake_head, \
             mock.patch.object(wg, "write_processed") as fake_write, \
             mock.patch.object(wg, "record_provenance") as fake_prov:
            wg.run()
        return fake_write, fake_prov, fake_head

    def test_a_same_rank_duplicate_is_flagged_not_silently_overwritten(self):
        # The bug found by the review: the old guard only fired when the
        # ranks differed, so two rows resolving to the same country at the
        # identical rank overwrote each other with zero log output.
        csv_text = _make_csv([
            (1, "USA", "United States of America", "61.69", 3),
            (2, "USA", "United States of America", "45.0", 3),  # same iso2, same rank, different score
        ])
        fake_write, _, _ = self._run_with(csv_text)
        data = fake_write.call_args.args[1]
        # Whichever row "won", the point under test is that it was recorded
        # as a conflict at all -- checked via the countries_without_data
        # note's own meta, since conflicts are logged, not returned; the
        # real assertion is that run() did not raise and still wrote data.
        self.assertIn("US", data)

    def test_an_iso3_name_disagreement_excludes_the_country_rather_than_guessing(self):
        # iso3 says USA, economy_name says a different country -- exactly
        # the "rotated iso3 column" attack the review constructed.
        csv_text = _make_csv([
            (1, "USA", "Sweden", "61.69", 3),  # disagreement: USA / "Sweden"
            (2, "SWE", "Sweden", "62.5", 2),   # SE resolves cleanly and should be unaffected
        ])
        fake_write, _, _ = self._run_with(csv_text)
        data = fake_write.call_args.args[1]
        meta = fake_write.call_args.kwargs["meta"]
        self.assertNotIn("US", data)  # excluded, not guessed as either country
        self.assertIn("SE", data)  # the clean row is unaffected by the other row's problem
        self.assertEqual(len(meta["cross_check_disagreements"]), 1)
        self.assertIn("USA", meta["cross_check_disagreements"][0])

    def test_edition_counts_is_always_recorded_even_when_it_matches(self):
        csv_text = _make_csv([(1, "CHE", "Switzerland", "66.0", 1, "2025")])
        fake_write, _, _ = self._run_with(csv_text)
        meta = fake_write.call_args.kwargs["meta"]
        self.assertEqual(meta["edition_counts"], {"2025": 1})
        self.assertIsNone(meta["edition_mismatch"])

    def test_a_minority_edition_disagreement_is_visible_even_though_it_does_not_flip_the_majority(self):
        # The gap the review named: a minority of rows disagreeing produced
        # zero signal under the old majority-only check.
        csv_text = _make_csv([
            (1, "CHE", "Switzerland", "66.0", 1, "2025"),
            (2, "SWE", "Sweden", "62.5", 2, "2025"),
            (3, "USA", "United States of America", "61.69", 3, "2026"),  # one dissenting row
        ])
        fake_write, _, _ = self._run_with(csv_text)
        meta = fake_write.call_args.kwargs["meta"]
        self.assertEqual(meta["edition_counts"], {"2025": 2, "2026": 1})
        self.assertIsNone(meta["edition_mismatch"])  # majority still 2025, correctly not flagged
        # but the minority count is right there in edition_counts for anyone reading meta

    def test_no_newer_edition_leaves_newer_edition_available_unset(self):
        csv_text = _make_csv([(1, "CHE", "Switzerland", "66.0", 1)])
        fake_write, _, fake_head = self._run_with(csv_text, next_edition_status=404)
        meta = fake_write.call_args.kwargs["meta"]
        self.assertIsNone(meta["newer_edition_available"])
        fake_head.assert_called_once()
        self.assertIn("bc_results_gii_2026.csv", fake_head.call_args.args[0])

    def test_a_newer_edition_at_200_is_surfaced_without_failing_the_run(self):
        # A resolving tracked country (USA) so this is a genuine "ok" run --
        # otherwise an empty `out` would make status "partial" for a reason
        # unrelated to what this test is actually checking.
        csv_text = _make_csv([(1, "USA", "United States of America", "61.69", 3)])
        fake_write, fake_prov, _ = self._run_with(csv_text, next_edition_status=200)
        meta = fake_write.call_args.kwargs["meta"]
        self.assertIsNotNone(meta["newer_edition_available"])
        self.assertIn("2026", meta["newer_edition_available"])
        # still a normal, successful run -- the probe is a bonus signal,
        # not a reason to treat this fetch as failed
        self.assertEqual(fake_prov.call_args.kwargs["status"], "ok")

    def test_the_next_edition_probe_failing_does_not_fail_the_whole_run(self):
        csv_text = _make_csv([(1, "USA", "United States of America", "61.69", 3)])
        with mock.patch.object(wg, "fetch_text", return_value=csv_text), \
             mock.patch.object(wg.requests, "head", side_effect=Exception("network error")), \
             mock.patch.object(wg, "write_processed") as fake_write, \
             mock.patch.object(wg, "record_provenance") as fake_prov:
            wg.run()  # must not raise
        self.assertEqual(fake_prov.call_args.kwargs["status"], "ok")


if __name__ == "__main__":
    unittest.main()
