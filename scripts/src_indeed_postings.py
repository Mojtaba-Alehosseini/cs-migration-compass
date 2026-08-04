"""Indeed Hiring Lab job-postings tracker → US metro postings index, 2020-02→.

Gives city profiles a real hiring-demand trend line: how job postings in this
metro moved since February 2020 (index, 2020-02-01 = 100).

The daily file is ~61 MB. We aggregate to monthly means per metro — daily noise
carries no signal at this zoom level and shipping 2,300 daily points per city to
a static site is indefensible. The aggregation is recorded in provenance.
"""
from __future__ import annotations

import csv
import io
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    RAW, US_CITY_CBSA, US_CITY_CBSA_SECONDARY, banner, fetch_text, log,
    main_guard, record_provenance, write_processed,
)

SOURCE_ID = "indeed_hiring_lab_job_postings"
NAME = "Indeed Hiring Lab — Job Postings Index (US metros)"
URL = ("https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/US/"
       "metro_job_postings_us.csv")


def run() -> None:
    banner(SOURCE_ID, NAME)
    text = fetch_text(URL, dest=RAW / SOURCE_ID / "metro_job_postings_us.csv")

    code_to_cities: dict[str, list[str]] = defaultdict(list)
    for city, code in US_CITY_CBSA.items():
        code_to_cities[code].append(city)
    for city, code in US_CITY_CBSA_SECONDARY.items():
        code_to_cities[code].append(f"{city}::secondary")

    monthly: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    names: dict[str, str] = {}
    kept = 0

    for row in csv.DictReader(io.StringIO(text)):
        code = (row.get("cbsa_code") or "").strip()
        if code not in code_to_cities:
            continue
        try:
            value = float(row["indeed_job_postings_index"])
        except (KeyError, TypeError, ValueError):
            continue
        date = (row.get("date") or "").strip()
        if len(date) < 7:
            continue
        monthly[code][date[:7]].append(value)
        names.setdefault(code, (row.get("metro") or "").strip())
        kept += 1

    out: dict[str, dict] = {}
    for code, months in monthly.items():
        series = [
            {"month": m, "index": round(statistics.fmean(v), 2), "days": len(v)}
            for m, v in sorted(months.items())
        ]
        for target in code_to_cities[code]:
            if target.endswith("::secondary"):
                city = target.split("::")[0]
                out.setdefault(city, {})["secondary"] = {
                    "cbsa": code, "metro": names.get(code), "series": series,
                }
            else:
                entry = out.setdefault(target, {})
                entry.update({"cbsa": code, "metro": names.get(code), "series": series,
                              "first": series[0], "last": series[-1]})

    log(f"    {len(out)}/30 US cities, {kept:,} daily rows → "
        f"{sum(len(v.get('series', [])) for v in out.values()):,} monthly points")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "index_base": "2020-02-01 = 100, seasonally adjusted by Indeed Hiring Lab",
            "frequency": "monthly (aggregated here from daily)",
            "confidence": "index",
            "level": "US metro",
            "scope_caveat": (
                "This is the ALL-postings index for the metro, not software-only. Indeed publishes a "
                "Software Development sector index at national level; a metro-by-sector cut is not "
                "published, so the city line is all-jobs demand and is labelled as such."
            ),
            "aggregation_note": "Monthly mean of daily values; 'days' records how many daily observations each month carries.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[URL],
        license_note=(
            "Indeed Hiring Lab publishes this tracker publicly on GitHub for free use with "
            "attribution. Cite: Indeed Hiring Lab Job Postings Index."
        ),
        transforms=[
            "Downloaded the ~61 MB daily US-metro postings CSV.",
            "Kept only rows whose cbsa_code matches our 30 US metros (plus San Jose for the Bay Area).",
            "Aggregated daily values to monthly arithmetic means, retaining the observation count per month.",
            "No smoothing beyond that mean; no gap filling.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=kept,
        coverage=f"{len(out)}/30 US cities, monthly 2020-02 → latest",
        notes="All-postings index, not software-specific — labelled as such in the UI.",
        redistribution="monthly aggregate committed; the 61 MB daily raw file is cached locally but not committed",
    )


if __name__ == "__main__":
    main_guard(run)
