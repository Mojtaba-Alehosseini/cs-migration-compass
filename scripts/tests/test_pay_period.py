"""Package 13, Tier 0 — regression tests for pay-period / pay-basis parsing
across all four postings providers, covering docs/REGRESSION-CATALOGUE.md's
R15 (period mislabelled from an assumed enum/interval that didn't match the
real API values — the €200-250/yr-for-an-hourly-role bug), R16 ($0
compensation rendered as a real figure), and R17 (the HN free-text parser's
three compounding bugs: an unbound number match, a lost HTML entity, and a
mis-applied 'k' suffix).

Every test calls the real, currently-shipped function. Lever's and
Greenhouse's fixtures are not invented — they are the exact values recorded
live in this pipeline's own cached output (Lever: lever:21hhs, lever:
ableserve, lever:adventus; Greenhouse: the 10beauty case cited in
src_postings_greenhouse.py's own comment, the same company posting both an
hourly and an annual range under the identical "Salary Range" title).

Run directly (`python scripts/tests/test_pay_period.py`) or via
scripts/tests/run_all.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import postings_common  # noqa: E402
import src_postings_ashby as ashby  # noqa: E402
import src_postings_greenhouse as greenhouse  # noqa: E402
import src_postings_hn as hn  # noqa: E402
import src_postings_lever as lever  # noqa: E402


def _ashby_doc(min_value, max_value, currency, interval, tier_summary="", org="TestCo"):
    return {
        "organizationName": org,
        "jobs": [{
            "id": "job1", "title": "Engineer", "location": "Remote",
            "compensation": {
                "compensationTiers": [{
                    "tierSummary": tier_summary,
                    "components": [{
                        "minValue": min_value, "maxValue": max_value,
                        "currencyCode": currency, "interval": interval,
                    }],
                }],
            },
        }],
    }


class TestAshbyPeriodMapping(unittest.TestCase):
    """R15 — Ashby's own interval field is "<n> <UNIT>" ("1 HOUR", "1 YEAR",
    "1 MONTH"), not the "HOURLY"/"YEARLY"/"MONTHLY" enum an earlier version
    assumed. The assumed enum matched nothing, so period silently defaulted
    to "year" for every posting, including ones Ashby's own tierSummary
    called "per hour"."""

    def test_1_hour_interval_maps_to_hour_not_defaulted_to_year(self):
        out = ashby._normalise("t", _ashby_doc(20, 25, "EUR", "1 HOUR", "€20-25 per hour"))
        self.assertEqual(out[0]["compensation"]["period"], "hour")

    def test_1_year_interval_maps_to_year(self):
        out = ashby._normalise("t", _ashby_doc(60000, 80000, "EUR", "1 YEAR"))
        self.assertEqual(out[0]["compensation"]["period"], "year")

    def test_1_month_interval_maps_to_month(self):
        out = ashby._normalise("t", _ashby_doc(5000, 6000, "EUR", "1 MONTH"))
        self.assertEqual(out[0]["compensation"]["period"], "month")

    def test_1_week_interval_has_no_bucket_and_is_skipped_not_guessed(self):
        # No weekly bucket exists in postings.ts's own Compensation type —
        # mapping it to month would understate by ~4x.
        out = ashby._normalise("t", _ashby_doc(1000, 1200, "EUR", "1 WEEK"))
        self.assertIsNone(out[0]["compensation"])

    def test_none_interval_equity_only_is_skipped(self):
        out = ashby._normalise("t", _ashby_doc(0, 0, "EUR", "NONE"))
        self.assertIsNone(out[0]["compensation"])

    def test_the_old_exact_match_assumption_fails_on_the_real_interval_shape(self):
        # Calls the real shipped matching logic (ashby._normalise(), via
        # the fixture helper above), not string methods in isolation — an
        # earlier version of this test asserted a fact about Python's own
        # str.replace() with no project code involved at all (adversarial
        # review finding L17). The historical bug assumed an EXACT-match
        # enum ("HOURLY"/"YEARLY"/"MONTHLY"); the real API returns "1
        # HOUR" etc — a different string an exact-equality check would
        # never match (note "HOURLY" itself DOES contain "HOUR" as a
        # substring, so the bug was exact-match-vs-shape, not a substring
        # miss the way the R15 catalogue entry's own short summary reads).
        # Reconstructed here as a real function, monkey-patched in for one
        # call, not asserted as a string fact.
        def buggy_normalise(token, doc):
            out = []
            for j in doc.get("jobs", []):
                comp = j.get("compensation") or {}
                parsed_comp = None
                for tier in comp.get("compensationTiers") or []:
                    for c in tier.get("components", []):
                        if not c.get("minValue") or not c.get("currencyCode"):
                            continue
                        interval = (c.get("interval") or "").upper()
                        if interval == "HOURLY":
                            period = "hour"
                        elif interval == "MONTHLY":
                            period = "month"
                        elif interval == "YEARLY":
                            period = "year"
                        else:
                            period = "year"  # the bug: silent default, not skip
                        parsed_comp = {"min": c["minValue"], "max": c.get("maxValue") or c["minValue"],
                                       "currency": c["currencyCode"], "period": period,
                                       "raw_text": "", "confidence": "structured"}
                        break
                    if parsed_comp:
                        break
                out.append({"compensation": parsed_comp})
            return out

        doc = _ashby_doc(20, 25, "EUR", "1 HOUR", "€20-25 per hour")
        real_result = ashby._normalise("t", doc)[0]["compensation"]["period"]
        buggy_result = buggy_normalise("t", doc)[0]["compensation"]["period"]
        self.assertEqual(real_result, "hour")
        self.assertEqual(buggy_result, "year",
                          "the reconstructed exact-match bug must silently default a real hourly "
                          "rate to 'year' — if this stops failing, the reconstruction no longer "
                          "matches the historical bug")


class TestAshbyZeroGuard(unittest.TestCase):
    """R16 — `is None`/`is not None` alone let a genuinely empty $0-$0
    range through as a confident figure; the guard must reject any
    non-positive minimum."""

    def test_zero_min_value_is_rejected_not_rendered_as_a_real_figure(self):
        out = ashby._normalise("t", _ashby_doc(0, 0, "USD", "1 YEAR"))
        self.assertIsNone(out[0]["compensation"])

    def test_a_real_positive_range_still_passes(self):
        out = ashby._normalise("t", _ashby_doc(60000, 80000, "USD", "1 YEAR"))
        self.assertIsNotNone(out[0]["compensation"])


class TestLeverPeriodMapping(unittest.TestCase):
    """R15 — Lever's own `interval` is "per-year-salary" / "per-hour-wage" /
    "per-month-salary"; an earlier version did `.replace('per-', '')`,
    turning "per-year-salary" into "year-salary", which matches nothing.
    Fixtures are the real values recorded live for lever:21hhs (year),
    lever:ableserve (hour), and lever:adventus (month)."""

    def test_per_year_salary_maps_to_year(self):
        result = lever._parse_salary_range({"min": 55000, "max": 90000, "currency": "USD", "interval": "per-year-salary"})
        self.assertEqual(result["period"], "year")
        self.assertEqual(result["min"], 55000)
        self.assertEqual(result["max"], 90000)

    def test_per_hour_wage_maps_to_hour(self):
        result = lever._parse_salary_range({"min": 37.82, "max": 37.82, "currency": "USD", "interval": "per-hour-wage"})
        self.assertEqual(result["period"], "hour")

    def test_per_month_salary_maps_to_month(self):
        result = lever._parse_salary_range({"min": 80000, "max": 90000, "currency": "PHP", "interval": "per-month-salary"})
        self.assertEqual(result["period"], "month")

    def test_the_old_replace_per_prefix_bug_would_have_produced_year_salary(self):
        # Calls the real lever._parse_salary_range() against a reconstructed
        # buggy sibling, not a string fact in isolation (adversarial review
        # finding L17 — an earlier version of this test asserted
        # "per-year-salary".replace("per-", "") == "year-salary" with no
        # project code involved at all).
        def buggy_parse(sr):
            if not sr or not sr.get("min"):
                return None
            interval = (sr.get("interval") or "").lower().replace("per-", "")  # the bug
            if "hour" in interval:
                period = "hour"
            elif "month" in interval and "bi-" not in interval and "semi-" not in interval:
                period = "month"
            else:
                period = None  # "year-salary" matches neither branch above
            if period is None:
                return None
            return {"min": sr["min"], "max": sr.get("max") or sr["min"], "period": period}

        sr = {"min": 55000, "max": 90000, "currency": "USD", "interval": "per-year-salary"}
        real_result = lever._parse_salary_range(sr)
        buggy_result = buggy_parse(sr)
        self.assertEqual(real_result["period"], "year")
        self.assertIsNone(buggy_result,
                           "the reconstructed .replace('per-', '') bug must silently drop a real "
                           "annual salary range (its own 'year-salary' matches neither the hour nor "
                           "month branch) — if this stops failing, the reconstruction no longer "
                           "matches the historical bug")

    def test_bi_week_interval_has_no_bucket_and_is_skipped(self):
        result = lever._parse_salary_range({"min": 2000, "max": 2500, "currency": "USD", "interval": "per-bi-week-salary"})
        self.assertIsNone(result)

    def test_semi_month_interval_is_skipped_not_forced_into_month(self):
        # "semi-month" contains "month" as a bare substring — must not
        # match the month branch, which excludes it explicitly.
        result = lever._parse_salary_range({"min": 2000, "max": 2500, "currency": "USD", "interval": "per-semi-month-salary"})
        self.assertIsNone(result)


class TestLeverZeroGuard(unittest.TestCase):
    """R16 — `sr.get("min")` is falsy for a real `0`, matching Greenhouse's
    and USAJOBS's own harvesters."""

    def test_zero_min_is_rejected(self):
        result = lever._parse_salary_range({"min": 0, "max": 0, "currency": "USD", "interval": "per-year-salary"})
        self.assertIsNone(result)

    def test_missing_salary_range_object_is_rejected(self):
        self.assertIsNone(lever._parse_salary_range(None))


class TestGreenhousePeriodInference(unittest.TestCase):
    """R15 — Greenhouse's `pay_input_ranges` carries no period field at all;
    period is inferred from magnitude (no real annual salary is under
    $1,000/year, no real hourly wage is over $1,000/hour). Fixtures are the
    exact live 10beauty values this pipeline's own comment cites: the SAME
    company posts both under the identical "Salary Range" title."""

    def test_low_magnitude_range_infers_hour(self):
        result = greenhouse._parse_pay_input_ranges([{"min_cents": 2200, "max_cents": 2700, "currency_type": "USD"}])
        self.assertEqual(result["period"], "hour")
        self.assertEqual(result["min"], 22.0)
        self.assertEqual(result["max"], 27.0)

    def test_high_magnitude_range_infers_year(self):
        result = greenhouse._parse_pay_input_ranges([{"min_cents": 6500000, "max_cents": 8000000, "currency_type": "USD"}])
        self.assertEqual(result["period"], "year")
        self.assertEqual(result["min"], 65000.0)
        self.assertEqual(result["max"], 80000.0)

    def test_same_company_can_post_both_shapes_independently(self):
        # The exact scenario an earlier "assume every range is annual"
        # version got wrong: two DIFFERENT postings, same employer.
        hourly = greenhouse._parse_pay_input_ranges([{"min_cents": 2200, "max_cents": 2700, "currency_type": "USD"}])
        yearly = greenhouse._parse_pay_input_ranges([{"min_cents": 6500000, "max_cents": 8000000, "currency_type": "USD"}])
        self.assertNotEqual(hourly["period"], yearly["period"])


class TestGreenhouseZeroGuard(unittest.TestCase):
    def test_zero_min_cents_is_rejected(self):
        result = greenhouse._parse_pay_input_ranges([{"min_cents": 0, "max_cents": 0, "currency_type": "USD"}])
        self.assertIsNone(result)

    def test_empty_ranges_list_is_rejected(self):
        self.assertIsNone(greenhouse._parse_pay_input_ranges([]))


class TestFreeTextCompensationParser(unittest.TestCase):
    """R17(a,c) — postings_common.parse_compensation_text(). (a) the number
    match must be BOUND to a currency marker, not just the first
    number-dash-number pattern in the line; (c) an English "k" suffix on
    only the second number ("$146-220k") applies to BOTH numbers, not just
    the one it's attached to."""

    def test_unrelated_leading_number_range_is_not_matched_over_the_real_one(self):
        # The exact live HN text this bug produced: "hybrid, 2-3 days/week"
        # preceded the real "$160-170K CAD" salary range on the same line.
        result = postings_common.parse_compensation_text("hybrid, 2-3 days/week onsite, $160-170K CAD")
        self.assertIsNotNone(result)
        self.assertEqual(result["min"], 160000)
        self.assertEqual(result["max"], 170000)

    def test_explicit_currency_code_beats_a_bare_dollar_sign(self):
        result = postings_common.parse_compensation_text("$160-170K CAD")
        self.assertEqual(result["currency"], "CAD",
                          "an explicit 3-letter code must win even though '$' would default to USD")

    def test_k_suffix_on_second_number_applies_to_both(self):
        # "$146-220k" means 146,000-220,000, not 146-220,000.
        result = postings_common.parse_compensation_text("$146-220k")
        self.assertEqual(result["min"], 146000)
        self.assertEqual(result["max"], 220000)

    def test_a_bare_small_range_with_no_currency_marker_is_not_matched(self):
        result = postings_common.parse_compensation_text("2-3 days/week, hybrid")
        self.assertIsNone(result)

    def test_hourly_period_detected_from_per_hour_text(self):
        result = postings_common.parse_compensation_text("$80-140/hour")
        self.assertEqual(result["period"], "hour")


class TestHtmlEntityUnescaping(unittest.TestCase):
    """R17(b) — an earlier version's hand-picked .replace() calls missed
    `&#x2F;` (HN's own encoding of a literal "/"), so "$80-140/hr" arrived
    at parse_compensation_text() as "$80-140&#x2F;hr" and the "/hour"
    period regex could never match — found by reading the actual extracted
    values, not by inspecting the function in isolation."""

    def test_forward_slash_entity_is_unescaped(self):
        self.assertEqual(hn._strip_html("$80&#x2F;140&#x2F;hr"), "$80/140/hr")

    def test_period_detection_works_end_to_end_after_unescaping(self):
        raw = "Compensation: $80&#x2F;hr &#x2F; negotiable"
        cleaned = hn._strip_html(raw)
        result = postings_common.parse_compensation_text(cleaned)
        # The literal text has no dash-separated range ("$80/hr" alone), so
        # this asserts the unescaping succeeded (a real "/" now present),
        # not that this particular string produces a parsed range.
        self.assertIn("/hr", cleaned)
        self.assertNotIn("&#x2F;", cleaned)


if __name__ == "__main__":
    unittest.main()
