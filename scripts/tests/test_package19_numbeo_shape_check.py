"""Package 19, Tier 4 — src_numbeo_history.py's country_year() reports the
table's TOTAL row count alongside our 15 countries' records, so a page
redesign that still matches the `id=t2`/`class=stripe` table selector but
returns a shrunken or restructured table is visible even in a year where
every one of our countries still happens to resolve. Before this, a table
selector match with the wrong table (or an empty one) returned silently --
same failure shape as the PDF flattened-text bug this package was written
to fix, just on a different source.

These tests fake fetch_text() so no network call happens; they exercise the
real country_year() and the real BeautifulSoup parse, not a re-implementation
of either.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import src_numbeo_history as nh  # noqa: E402


def _table_html(n_filler_rows: int, real_countries: list[str]) -> str:
    headers = "<th>Rank</th><th>Country</th><th>Cost of Living Index</th><th>Rent Index</th>"
    body = ""
    for name in real_countries:
        body += f"<tr><td>1</td><td>{name}</td><td>75.3</td><td>30.1</td></tr>"
    for i in range(n_filler_rows):
        body += f"<tr><td>{i}</td><td>Placeholder {i}</td><td>50.0</td><td>20.0</td></tr>"
    return f'<html><body><table id="t2"><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table></body></html>'


class TestCountryYearShapeCheck(unittest.TestCase):
    def test_a_normally_sized_table_reports_the_true_total_row_count(self):
        html = _table_html(n_filler_rows=117, real_countries=["Australia", "Germany", "France"])
        with mock.patch.object(nh, "fetch_text", return_value=html):
            out, total_rows = nh.country_year(2026)
        self.assertEqual(total_rows, 120)  # 117 filler + 3 real, regardless of match
        self.assertGreaterEqual(total_rows, nh.MIN_PLAUSIBLE_ROWS)
        self.assertIn("AU", out)
        self.assertIn("DE", out)

    def test_a_drastically_shrunken_table_is_caught_by_the_row_floor(self):
        # Simulates a redesign that still matches the table id/class selector
        # (id="t2") but is a DIFFERENT, much smaller table -- e.g. a "top 5
        # cheapest countries" widget instead of the full rankings.
        html = _table_html(n_filler_rows=2, real_countries=["Australia"])
        with mock.patch.object(nh, "fetch_text", return_value=html):
            out, total_rows = nh.country_year(2026)
        self.assertEqual(total_rows, 3)
        self.assertLess(total_rows, nh.MIN_PLAUSIBLE_ROWS)
        # Our one matched country is still returned -- the self-check flags
        # the table's SHAPE, it does not withhold data that did parse.
        self.assertIn("AU", out)

    def test_a_selector_that_no_longer_matches_anything_returns_zero_not_a_crash(self):
        html = "<html><body><p>This page has no rankings table at all.</p></body></html>"
        with mock.patch.object(nh, "fetch_text", return_value=html):
            out, total_rows = nh.country_year(2026)
        self.assertEqual((out, total_rows), ({}, 0))

    def test_run_records_a_shape_warning_for_a_shrunken_year_but_not_a_normal_one(self):
        small_html = _table_html(n_filler_rows=2, real_countries=["Australia"])
        normal_html = _table_html(n_filler_rows=117, real_countries=["Australia", "Germany"])

        def fake_fetch_text(url, **kw):
            return small_html if "title=2015" in url else normal_html

        with mock.patch.object(nh, "fetch_text", side_effect=fake_fetch_text), \
             mock.patch.object(nh, "YEARS", [2015, 2016]), \
             mock.patch.object(nh, "time") as fake_time, \
             mock.patch.object(nh, "write_processed") as fake_write, \
             mock.patch.object(nh, "record_provenance"), \
             mock.patch.object(nh, "load_cities", return_value=[{"id": "berlin", "name": "Berlin"}]), \
             mock.patch.object(nh, "numbeo_slug", return_value="Berlin"):
            fake_time.sleep.return_value = None
            nh.run()

        meta = fake_write.call_args.kwargs["meta"]
        self.assertEqual(len(meta["table_shape_warnings"]), 1)
        self.assertIn("2015", meta["table_shape_warnings"][0])


if __name__ == "__main__":
    unittest.main()
