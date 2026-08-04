"""FHFA metro house-price index → real US city house-price history, 1975Q1→.

This is genuine CITY-level history (not a country trend applied to a city), so
US city profiles get a real "since 1975" housing chart.

Honest caveat carried into the output: for 13 of our 30 metros FHFA publishes
only the METROPOLITAN DIVISION (MSAD) — the inner part of the metro — not the
whole MSA. We store the published area name so the UI can label exactly which
geography the line describes.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    RAW, US_CITY_FHFA, US_CITY_FHFA_SECONDARY, banner, fetch_text, log,
    main_guard, record_provenance, write_processed,
)

SOURCE_ID = "fhfa_hpi_metro"
NAME = "FHFA House Price Index — All-Transactions, Metropolitan Areas (quarterly)"
URL = "https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_metro.csv"

# The file has no header row. Verified column order against the live download.
COLS = ["metro_name", "cbsa", "year", "quarter", "index_nsa", "stderr"]


def _num(s: str) -> float | None:
    s = (s or "").strip().strip("()").strip()
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def run() -> None:
    banner(SOURCE_ID, NAME)
    text = fetch_text(URL, dest=RAW / SOURCE_ID / "hpi_at_metro.csv")

    wanted: dict[str, list[str]] = {}
    for city, code in US_CITY_FHFA.items():
        wanted.setdefault(code, []).append(city)
    secondary = {code: city for city, code in US_CITY_FHFA_SECONDARY.items()}

    by_code: dict[str, dict] = {}
    total = 0
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 5:
            continue
        code = row[1].strip()
        if code not in wanted and code not in secondary:
            continue
        idx = _num(row[4])
        if idx is None:
            continue  # FHFA writes "-" for years before a metro's series starts
        rec = by_code.setdefault(code, {"area_name": row[0].strip(), "series": []})
        rec["series"].append({"year": int(row[2]), "quarter": int(row[3]), "index": idx})
        total += 1

    out: dict[str, dict] = {}
    for code, cities in wanted.items():
        rec = by_code.get(code)
        if rec is None:
            log(f"    !! no rows for CBSA {code} ({', '.join(cities)})")
            continue
        rec["series"].sort(key=lambda r: (r["year"], r["quarter"]))
        for city in cities:
            entry = {
                "cbsa": code,
                "area_name": rec["area_name"],
                "is_metro_division": "(MSAD)" in rec["area_name"],
                "series": rec["series"],
                "first": rec["series"][0],
                "last": rec["series"][-1],
            }
            sec_code = US_CITY_FHFA_SECONDARY.get(city)
            if sec_code and sec_code in by_code:
                s = by_code[sec_code]
                s["series"].sort(key=lambda r: (r["year"], r["quarter"]))
                entry["secondary"] = {
                    "cbsa": sec_code,
                    "area_name": s["area_name"],
                    "series": s["series"],
                    "why": "Our sf_bay_area record spans SF + San Jose; both are shown, never averaged.",
                }
            out[city] = entry

    divisions = sorted(c for c, e in out.items() if e["is_metro_division"])
    log(f"    {len(out)}/30 US cities matched, {total:,} quarterly observations")
    log(f"    metro-division (not full MSA) geographies: {len(divisions)} — {', '.join(divisions)}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "index_type": "All-Transactions House Price Index, not seasonally adjusted (index, 1995Q1=100)",
            "frequency": "quarterly",
            "range": "1975Q1 onwards (per-metro start varies)",
            "confidence": "official",
            "level": "US metro",
            "geography_caveat": (
                "For 13 metros FHFA publishes only the metropolitan division (MSAD), a subset of "
                "the full metro area. 'area_name' records exactly which geography each line is, and "
                "'is_metro_division' flags it so the UI can say so."
            ),
            "index_caveat": (
                "This is an INDEX of price change, not a price level. It answers 'how much have "
                "prices moved', never 'what does a flat cost' — that stays with the Numbeo $/m2 figure."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[URL],
        license_note="US federal government work — public domain. Cite: FHFA House Price Index.",
        transforms=[
            "Downloaded the headerless all-transactions metro CSV (410 metros, 84k rows).",
            "Selected the 30 metros matching our US cities, plus San Jose as the Bay Area's second series.",
            "Dropped rows where the index is '-' (period before a metro's series begins).",
            "Sorted each series by (year, quarter); recorded the published area name and an "
            "is_metro_division flag rather than silently treating a division as the whole metro.",
            "No rebasing, no smoothing, no interpolation.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=total,
        coverage=f"{len(out)}/30 US cities, 1975Q1-latest quarterly",
        notes="Real city-level history — not a country trend applied to a city.",
    )


if __name__ == "__main__":
    main_guard(run)
