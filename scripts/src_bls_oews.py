"""BLS OEWS API → US metro software-developer wages and employment counts.

Two things the rest of the pipeline cannot give us for US cities:
  * an OFFICIAL wage figure (median/mean) to sit beside crowd-sourced salary data
  * an employment COUNT — how many software developers actually work in this metro

Verified limitation, surfaced honestly rather than hidden: the public OEWS API
returns data for the CURRENT year only. Identical series IDs for 2015-2024 come
back "No Data Available", and pre-2018-SOC codes (15-1132/15-1133) return
"Series does not exist". So this is a SNAPSHOT, not a history — the site labels
it that way and never draws a BLS trend line it does not have.

Series ID = OE + U + area-type + 7-digit area + 6-digit industry + 6-digit SOC +
2-digit datatype. Datatypes: 01 employment, 04 hourly mean, 13 annual median.
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
DATATYPES = {"01": "employment", "04": "hourly_mean_usd", "13": "annual_median_usd"}
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
            "history_caveat": (
                "VERIFIED LIMITATION: the public OEWS API returns the current reference year only. "
                "Identical series IDs for earlier years return 'No Data Available', and pre-2018-SOC "
                "codes return 'Series does not exist'. This is therefore a SNAPSHOT, not a history. "
                "The site must not draw a BLS trend line. Older years exist only in archived OEWS "
                "releases, which are a documented manual drop-in."
            ),
            "why_it_matters": (
                "This is the official counterweight to crowd-sourced salary data, and the only source "
                "of a real 'how many dev jobs exist here' count for US metros."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=urls,
        license_note="US federal government work — public domain. Cite: U.S. Bureau of Labor Statistics, OEWS.",
        transforms=[
            "Constructed OEWS series IDs for 30 metros (+ San Jose, + national) x 3 datatypes.",
            f"Requested them from the v2 API in batches of {BATCH} (the keyless per-request limit).",
            "Kept employment counts, hourly mean and annual median wages where the API returned data.",
            "Series returning 'No Data Available' are counted and omitted — never back-filled or estimated.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=found,
        coverage=f"{len(covered)}/30 US cities, current reference year only",
        status="ok" if found else "failed",
        notes="Snapshot only — the API exposes no OEWS history. Stated on the page, not hidden.",
    )


if __name__ == "__main__":
    main_guard(run)
