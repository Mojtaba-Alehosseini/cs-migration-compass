"""Package 12, tier 1.3 — USAJOBS Historic JOA API. The one government
source in this package that is licence-clean AND carries real numeric
compensation on every record (verified live this session): no key, but a
browser-shaped User-Agent is required (a bare Python UA gets nothing useful
back — matches the work order's own instruction). `ResultsPerPage` is NOT a
valid parameter (returns 400 — found live, not assumed from documentation);
`PositionSeries` is, and correctly filters (`2210` = IT Management, `0854` =
Computer Engineering — the two OPM job-family series closest to this
project's own isco08:2512 scope).

LICENCE: 17 U.S.C. Section 105 — U.S. federal government works are not
subject to copyright in the US. Attribute as "USAJOBS / U.S. OPM" — the work
order is explicit this is NOT the same as CC0 (CC0 is a rights-HOLDER
choosing to waive rights they have; Section 105 means no US copyright ever
attached in the first place — different legal basis, same practical
redistribution freedom domestically, worth stating correctly rather than
reaching for the more familiar CC0 label).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import banner, fetch_json, log, main_guard, record_provenance, write_processed  # noqa: E402
from postings_common import country_from_location, reinterpret_implausible_year  # noqa: E402

SOURCE_ID = "postings_usajobs"
BASE = "https://data.usajobs.gov/api/historicjoa"
# 2210 IT Management, 0854 Computer Engineering — OPM's own job-family series
# closest to this project's isco08:2512 scope. Not 1550 (Computer Science) —
# checked live, 1550 skews heavily toward statistician/research roles at
# federal agencies, not software-developer-shaped work.
SERIES = ["2210", "0854"]
PAGES_PER_SERIES = 4  # 500 records/page (API's own default) x 4 x 2 series = up to 4,000 records scanned
HEADERS = {"User-Agent": "mortea@dtu.dk cs-migration-compass research (github.com/Mojtaba-Alehosseini/cs-migration-compass)"}


def _fetch_series(series: str) -> list[dict]:
    records: list[dict] = []
    token = None
    for page in range(PAGES_PER_SERIES):
        url = f"{BASE}?PositionSeries={series}"
        if token:
            url = f"{BASE}?continuationtoken={token}"
        doc = fetch_json(url, headers=HEADERS, cache=False, retries=3, backoff=2.0)
        page_records = doc.get("data", [])
        records.extend(page_records)
        token = doc.get("paging", {}).get("metadata", {}).get("continuationToken")
        nxt = doc.get("paging", {}).get("next")
        if not nxt or not page_records:
            break
    return records


def run() -> None:
    banner(SOURCE_ID, "USAJOBS Historic JOA — real numeric federal compensation")
    postings: list[dict] = []
    total_by_series: dict[str, int] = {}
    for series in SERIES:
        recs = _fetch_series(series)
        total_by_series[series] = len(recs)
        log(f"    series {series}: {len(recs)} announcements fetched")
        for r in recs:
            lo, hi = r.get("minimumSalary"), r.get("maximumSalary")
            comp = None
            salary_type = (r.get("salaryType") or "").lower()
            # "Per Year" and "Per Hour" cover 3,984 of 4,000 records live;
            # the other two real values seen ("Student Stipend Paid", "Per
            # Day") have no clean bucket in postings.ts's own Compensation
            # type — skipped rather than defaulted into "year" the way an
            # earlier version of this check did (startswith("per hour") ->
            # else "year" silently mapped BOTH of those into "year" too).
            if salary_type == "per year":
                period = "year"
            elif salary_type == "per hour":
                period = "hour"
            else:
                period = None
            if lo is not None and hi is not None and lo > 0 and period:
                raw_text = f"{lo:,.0f}-{hi:,.0f} USD ({r.get('salaryType', '')})"
                # Package 14, Tier 3.2 (external audit Finding 3) — a
                # handful of "Per Year" seasonal/entry announcements
                # (Internal Revenue Service seasonal Clerk roles, Forest
                # Service seasonal technicians) carry hourly-shaped values
                # ($12-26) under their own reported salaryType of "Per
                # Year" — OPM's own listing, not this pipeline's parsing;
                # reinterpret_implausible_year's own hourly-shaped rule
                # applies the same way it does for Ashby's own mistagged
                # interval, see that function's own docstring.
                if period == "year":
                    fix = reinterpret_implausible_year(lo, hi, raw_text)
                    if fix:
                        lo, hi, period = fix
                comp = {"min": lo, "max": hi, "currency": "USD", "period": period,
                        "raw_text": raw_text, "confidence": "structured"}
            locs = r.get("positionlocations") or [{}]
            loc = locs[0]
            loc_raw = ", ".join(x for x in (loc.get("positionLocationCity"), loc.get("positionLocationState")) if x)
            postings.append({
                "id": f"usajobs:{r.get('usajobsControlNumber')}",
                "provider": "usajobs", "company": r.get("hiringAgencyName") or r.get("hiringDepartmentName"),
                "company_slug": r.get("hiringDepartmentCode") or "usajobs",
                "title": r.get("positionTitle"), "location_raw": loc_raw,
                "country": country_from_location(loc_raw) or "US",
                "remote": None,
                "url": f"https://www.usajobs.gov/GetJob/ViewDetails/{r.get('usajobsControlNumber')}"
                       if r.get("usajobsControlNumber") else None,
                "posted_at": r.get("positionOpenDate"),
                "compensation": comp,
                "occupation": None,
                "_series": series,
            })

    with_comp = sum(1 for p in postings if p["compensation"])
    log(f"    {len(postings)} total postings, {with_comp} ({with_comp/len(postings)*100 if postings else 0:.0f}%) "
        f"with a real numeric compensation range")

    write_processed(SOURCE_ID, {"postings": postings}, meta={
        "series_covered": SERIES,
        "records_by_series": total_by_series,
        "postings_count": len(postings),
        "compensation_present_count": with_comp,
    })
    record_provenance(
        source_id=SOURCE_ID,
        name="USAJOBS Historic JOA — U.S. federal job announcements, real numeric pay",
        urls=[f"{BASE}?PositionSeries={s}" for s in SERIES],
        license_note='17 U.S.C. SS 105 (U.S. federal government work — no US copyright attaches). '
                      'Attribute as "USAJOBS / U.S. OPM" — NOT CC0 (a different legal basis: CC0 is a '
                      "rights-holder's own waiver of rights they hold; SS105 means no US copyright ever "
                      "existed here). Requires a descriptive, non-generic User-Agent header — a bare "
                      "default UA is effectively blocked (found live, not assumed).",
        redistribution="Every returned record's own fields are redistributed directly — this endpoint "
                        "already serves individual, already-public announcement records, not a bulk "
                        "file this pipeline narrows down.",
        transforms=[
            "Filtered live to PositionSeries 2210 (IT Management) and 0854 (Computer Engineering) — "
            "found ResultsPerPage is NOT a valid parameter (400 live), PositionSeries is.",
            "Paged via the API's own continuationToken, not a page-number parameter.",
            "Read minimumSalary/maximumSalary directly — real numbers, no parsing needed, unlike "
            "every ATS-provider source in this package.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(postings),
        coverage=f"{len(postings)} announcements across {len(SERIES)} OPM series",
        notes="Advertised pay — NEVER merged with survey-earnings data. Government job announcements, "
              "not private-sector, disclosed as such downstream (build_postings.py, the site's own UI).",
    )


if __name__ == "__main__":
    main_guard(run)
