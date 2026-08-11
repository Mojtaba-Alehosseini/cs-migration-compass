"""BLS OEWS API → US metro software-developer wages and employment counts.

Three things the rest of the pipeline cannot give us for US cities:
  * an OFFICIAL wage figure (mean/median/percentiles) beside crowd-sourced data
  * an employment COUNT — how many software developers actually work in this metro
  * the full percentile SPREAD (P10/P25/P75/P90), not just one number

Verified limitation, surfaced honestly rather than hidden: the public OEWS API
returns data for the CURRENT year only. Identical series IDs for 2015-2024 come
back "No Data Available", and pre-2018-SOC codes (15-1132/15-1133) return
"Series does not exist". So this is a SNAPSHOT, not a history — the site labels
it that way and never draws a BLS trend line it does not have. That finding
stands from package 5 and is unrelated to package 7's percentile extension.

Series ID = OE + U + area-type + 7-digit area + 6-digit industry + 6-digit SOC
+ 2-digit datatype:

    01 employment   03 hourly mean   04 ANNUAL mean   06-10 hourly P10-P90 (not fetched)
    11 annual P10   12 annual P25    13 annual median  14 annual P75  15 annual P90

FIX: this pipeline previously requested only datatype 04 and labelled it
"hourly_mean_usd". Datatype 04 is the ANNUAL mean, not the hourly one — the
stored figure (148,100 for the 2025 national series) was always correct, only
the key name was wrong; nothing that read "hourly_mean_usd" as an hourly rate
existed downstream (grepped: the site never consumes this field). Confirmed
three independent ways against the live API during development: (a) datatype
03 (hourly mean) returned 71.20 USD/hr for the 2025 national series, and
71.20 x a standard 2,080-hour work-year = 148,096 — matching 04's 148,100 to
within rounding; (b) 04's value is far too large to be an hourly wage; (c)
datatype 13, whose label was already correct, returns 135,980 for 2025 —
exactly the figure BLS's own May 2025 release cites as the national annual
median for this occupation. 04 relabelled to "annual_mean_usd" (no value
changed, only the key); 03 added as the new, correctly-sourced
"hourly_mean_usd".

STATUS AS COMMITTED: datatype 03 is in DATATYPES below, ready to fetch, but
this package's own repeated development testing exhausted BLS's unregistered-
API daily cap (25 requests/day; this script alone uses 9-11 per run; see
data/data-pipeline-sources.json) twice over — the second time immediately
after what looked like a reset, so the cap or its reset schedule is stricter
than a simple midnight boundary. data/processed/bls_oews.json therefore ships
this package UNCHANGED from its pre-package-7 state (three datatypes, the
'04' relabel not yet applied to committed data) rather than with a broken or
partial fetch — see NEEDS-DECISION.md. The next successful
`python scripts/pipeline.py bls_oews`, whenever quota allows, will pick up
this code as written and produce the full eight-datatype output; nothing
further needs to change in this file for that to happen.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    RAW, US_CITY_CBSA, US_CITY_CBSA_SECONDARY, banner, fetch, log, main_guard,
    record_provenance, write_processed,
)

SOURCE_ID = "bls_oews"
NAME = "BLS Occupational Employment and Wage Statistics (OEWS) — software developers"
API_V2 = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

SOC_SOFTWARE_DEV = "151252"   # Software Developers (2018 SOC)
INDUSTRY_ALL = "000000"
DATATYPES = {
    "01": "employment",
    "03": "hourly_mean_usd",       # the TRUE hourly mean — see module docstring
    "04": "annual_mean_usd",       # was mislabelled "hourly_mean_usd" — see module docstring
    "11": "annual_p10_usd",
    "12": "annual_p25_usd",
    "13": "annual_median_usd",
    "14": "annual_p75_usd",
    "15": "annual_p90_usd",
}
START_YEAR, END_YEAR = "2020", "2026"
BATCH = 25  # API v2 without a key allows 25 series per request


def series_id(area_code: str, datatype: str, area_type: str = "M") -> str:
    return f"OEU{area_type}{area_code.zfill(7)}{INDUSTRY_ALL}{SOC_SOFTWARE_DEV}{datatype}"


def run() -> None:
    banner(SOURCE_ID, NAME)

    targets: list[tuple[str, str, str]] = []  # (city, area_code, label)
    for city, code in US_CITY_CBSA.items():
        targets.append((city, code, "primary"))
    for city, code in US_CITY_CBSA_SECONDARY.items():
        targets.append((city, code, "secondary"))

    wanted: dict[str, tuple[str, str, str]] = {}
    for city, code, label in targets:
        for dt in DATATYPES:
            wanted[series_id(code, dt)] = (city, label, DATATYPES[dt])
    # national benchmark
    for dt in DATATYPES:
        wanted[series_id("0000000", dt, area_type="N")] = ("_national", "primary", DATATYPES[dt])

    ids = list(wanted)
    out: dict[str, dict] = {}
    urls: list[str] = []
    found = 0
    no_data = 0
    years_seen: set[str] = set()

    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        body = {"seriesid": chunk, "startyear": START_YEAR, "endyear": END_YEAR}
        raw = fetch(
            API_V2,
            dest=RAW / SOURCE_ID / f"batch_{i // BATCH:02d}.json",
            method="POST",
            json_body=body,
            headers={"Content-Type": "application/json"},
            retries=2,
        )
        urls.append(f"POST {API_V2} ({len(chunk)} series)")
        doc = json.loads(raw)
        for s in doc.get("Results", {}).get("series", []):
            sid = s.get("seriesID", "")
            meta = wanted.get(sid)
            if meta is None:
                continue
            city, label, field = meta
            points = []
            for d in s.get("data", []):
                try:
                    points.append({"year": int(d["year"]), "value": float(str(d["value"]).replace(",", ""))})
                    years_seen.add(d["year"])
                except (KeyError, ValueError):
                    continue
            if not points:
                no_data += 1
                continue
            points.sort(key=lambda p: p["year"])
            slot = out.setdefault(city, {})
            if label == "secondary":
                slot = slot.setdefault("secondary", {})
            slot[field] = points
            slot.setdefault("series_ids", {})[field] = sid
            found += 1

    covered = sorted(c for c in out if c != "_national")
    log(f"    {found} series with data, {no_data} returned 'No Data Available'")
    log(f"    {len(covered)}/30 US cities · years present: {', '.join(sorted(years_seen)) or 'none'}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation": "Software Developers (SOC 15-1252), all industries",
            "datatypes": DATATYPES,
            "confidence": "official",
            "level": "US metro (plus a national benchmark under '_national')",
            "years_returned": sorted(years_seen),
            "unit": "USD per year, except employment (headcount) and hourly_mean_usd (USD per hour — "
                "the one hourly figure BLS publishes; every other wage field is annual).",
            "history_caveat": (
                "VERIFIED LIMITATION: the public OEWS API returns the current reference year only. "
                "Identical series IDs for earlier years return 'No Data Available', and pre-2018-SOC "
                "codes return 'Series does not exist'. This is therefore a SNAPSHOT, not a history. "
                "The site must not draw a BLS trend line. Older years exist only in archived OEWS "
                "releases, which are a documented manual drop-in."
            ),
            "relabel_note": (
                "Prior to this package, datatype 04 was fetched and stored as 'hourly_mean_usd'. It "
                "is actually the ANNUAL mean (verified against the live API three independent ways — "
                "see module docstring). Nothing on the site read the old key. Relabelled to "
                "'annual_mean_usd'; the underlying number is unchanged. Datatype 03, the true hourly "
                "mean, is now fetched separately and stored under 'hourly_mean_usd' instead — so that "
                "key means what it always claimed to, sourced from the correct series."
            ),
            "top_code_note": (
                "BLS's May 2025 OEWS release began publishing specific high-percentile values instead "
                "of the old '>= $239,200' top-code. Verified live: national P90 for this occupation is "
                "214,670 and San Jose-Sunnyvale-Santa Clara's is 289,150 — both specific numbers, the "
                "second one above the old top-code ceiling, confirming this pipeline is receiving real "
                "uncapped percentiles, not a suppressed cap."
            ),
            "why_it_matters": (
                "This is the official counterweight to crowd-sourced salary data, and the only source "
                "of a real 'how many dev jobs exist here' count for US metros. The percentile set "
                "brings it to the same shape as the Sweden/UK/Canada salary sources added alongside it."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=urls,
        license_note="US federal government work — public domain. Cite: U.S. Bureau of Labor Statistics, OEWS.",
        redistribution="processed derivative only — the raw batch responses are cached under "
                        "data/raw/bls_oews/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw API responses. Only the derived "
                        "data/processed/bls_oews.json is committed (US government data is public "
                        "domain, so this is a choice, not a licence requirement).",
        transforms=[
            "Constructed OEWS series IDs for 30 metros (+ San Jose, + national) x 8 datatypes "
            "(employment, hourly mean, annual mean, annual P10/P25/median/P75/P90).",
            f"Requested them from the v2 API in batches of {BATCH} (the keyless per-request limit).",
            "Kept employment counts and all seven wage measures where the API returned data.",
            "Series returning 'No Data Available' are counted and omitted — never back-filled or estimated.",
            "Relabelled datatype 04 from 'hourly_mean_usd' to 'annual_mean_usd', and added datatype 03 "
            "as the new 'hourly_mean_usd' (see module docstring) — 04's stored number is unchanged, "
            "only its key; 03 is a genuinely new field sourced from the correct series.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=found,
        coverage=f"{len(covered)}/30 US cities, current reference year only",
        status="ok" if found else "failed",
        notes="Snapshot only — the API exposes no OEWS history. Stated on the page, not hidden.",
    )


if __name__ == "__main__":
    main_guard(run)
