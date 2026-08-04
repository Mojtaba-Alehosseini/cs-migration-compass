"""Eurostat isoc_sks_itspt → ICT specialists employed, country level, 2004-2025.

This is the CS-specific jobs count: how many ICT specialists a country employs,
in thousands, and as a share of total employment. Powers the Jobs & Tech-scene
theme (count + share + 20-year trend).

Coverage is EU/EFTA only. Non-European countries in our set (US, CA, AU, AE, QA)
are ABSENT here by design — the site must show "no data" for them on this metric
rather than substituting something else.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, ISO2_TO_EUROSTAT, RAW, banner, fetch_json, jsonstat_rows, log,
    main_guard, record_provenance, write_processed,
)

SOURCE_ID = "eurostat_ict_specialists"
NAME = "Eurostat — Employed ICT specialists (isoc_sks_itspt)"
URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
       "isoc_sks_itspt?format=JSON&lang=en")

UNIT_KEY = {"THS_PER": "ict_specialists_thousands", "PC_EMP": "ict_share_of_employment_pct"}


def run() -> None:
    banner(SOURCE_ID, NAME)
    doc = fetch_json(URL, dest=RAW / SOURCE_ID / "isoc_sks_itspt.json")

    # Eurostat geo code -> our ISO2 (GB is published as "UK")
    geo_to_iso2 = {ISO2_TO_EUROSTAT[c]: c for c in COUNTRY_IDS}

    out: dict[str, dict[str, list]] = {}
    eu_benchmark: dict[str, list] = {}
    rows = 0

    for row in jsonstat_rows(doc):
        key = UNIT_KEY.get(row["unit"])
        if key is None:
            continue
        year, value = int(row["time"]), row["_value"]

        if row["geo"] == "EU27_2020":
            eu_benchmark.setdefault(key, []).append({"year": year, "value": value})
            continue

        iso2 = geo_to_iso2.get(row["geo"])
        if iso2 is None:
            continue
        out.setdefault(iso2, {}).setdefault(key, []).append({"year": year, "value": value})
        rows += 1

    for country in out.values():
        for series in country.values():
            series.sort(key=lambda r: r["year"])
    for series in eu_benchmark.values():
        series.sort(key=lambda r: r["year"])

    covered = sorted(out)
    missing = [c for c in COUNTRY_IDS if c not in out]
    log(f"    covered {len(covered)}/15: {', '.join(covered)}")
    log(f"    no data (non-EU/EFTA): {', '.join(missing)}")

    write_processed(
        SOURCE_ID,
        {"countries": out, "eu27_benchmark": eu_benchmark},
        meta={
            "units": {
                "ict_specialists_thousands": "thousand persons employed as ICT specialists",
                "ict_share_of_employment_pct": "% of total employment",
            },
            "confidence": "official",
            "range": "2004-2025",
            "countries_covered": covered,
            "countries_without_data": missing,
            "coverage_caveat": (
                "Eurostat covers EU/EFTA only. US, CA, AU, AE and QA have no series here; "
                "the site shows 'no data' for them rather than substituting another source."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[URL],
        license_note=(
            "Eurostat re-use policy — free re-use with attribution "
            "(Commission Decision 2011/833/EU). Cite: Eurostat, isoc_sks_itspt."
        ),
        transforms=[
            "Fetched full JSON-stat 2.0 cube (freq x unit x geo x time).",
            "Decoded the sparse row-major value map to explicit (unit, geo, year) rows.",
            "Kept the 15 covered countries plus the EU27_2020 aggregate as a benchmark line.",
            "Mapped Eurostat geo 'UK' to our ISO2 'GB'; dropped all other geographies.",
            "Split the two units into separate series: absolute count and share of employment.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=rows,
        coverage=f"{len(covered)}/15 countries (EU/EFTA only), 2004-2025 annual",
        notes="Non-EU countries genuinely have no series here; recorded as missing, not imputed.",
    )


if __name__ == "__main__":
    main_guard(run)
