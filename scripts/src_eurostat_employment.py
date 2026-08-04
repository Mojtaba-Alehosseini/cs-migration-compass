"""Eurostat nama_10_pe → total employment headcount, country level, 1975-2025.

The denominator for the Jobs theme: total jobs in the economy, so "IT jobs" can
be shown both as an absolute count and as a share of a real total.

Same EU/EFTA coverage limit as the ICT series — non-European countries are absent
by design and rendered as "no data".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, ISO2_TO_EUROSTAT, RAW, banner, fetch_json, jsonstat_rows, log,
    main_guard, record_provenance, write_processed,
)

SOURCE_ID = "eurostat_total_employment"
NAME = "Eurostat — Population and employment, national accounts (nama_10_pe)"
URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
       "nama_10_pe?format=JSON&lang=en")

# na_item -> our key. National concept = residents, the right denominator for
# "how many people here have a job".
ITEMS = {
    "EMP_NC": "total_employment_thousands",
    "SAL_NC": "employees_thousands",
    "SELF_NC": "self_employed_thousands",
    "POP_NC": "population_thousands",
}
UNIT = "THS_PER"


def run() -> None:
    banner(SOURCE_ID, NAME)
    doc = fetch_json(URL, dest=RAW / SOURCE_ID / "nama_10_pe.json")

    geo_to_iso2 = {ISO2_TO_EUROSTAT[c]: c for c in COUNTRY_IDS}
    out: dict[str, dict[str, list]] = {}
    rows = 0

    for row in jsonstat_rows(doc):
        if row["unit"] != UNIT:
            continue
        key = ITEMS.get(row["na_item"])
        if key is None:
            continue
        iso2 = geo_to_iso2.get(row["geo"])
        if iso2 is None:
            continue
        out.setdefault(iso2, {}).setdefault(key, []).append(
            {"year": int(row["time"]), "value": row["_value"]}
        )
        rows += 1

    for country in out.values():
        for series in country.values():
            series.sort(key=lambda r: r["year"])

    covered = sorted(out)
    missing = [c for c in COUNTRY_IDS if c not in out]
    log(f"    covered {len(covered)}/15: {', '.join(covered)}")
    log(f"    no data: {', '.join(missing)}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "units": {k: "thousand persons" for k in ITEMS.values()},
            "concept": "national concept (residents)",
            "confidence": "official",
            "range": "1975-2025",
            "countries_covered": covered,
            "countries_without_data": missing,
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[URL],
        license_note=(
            "Eurostat re-use policy — free re-use with attribution "
            "(Commission Decision 2011/833/EU). Cite: Eurostat, nama_10_pe."
        ),
        transforms=[
            "Fetched full JSON-stat 2.0 cube (freq x unit x na_item x geo x time).",
            "Kept unit THS_PER only; dropped the percentage-change unit.",
            "Kept 4 na_items: total employment, employees, self-employed, population (national concept).",
            "Mapped Eurostat geo 'UK' to ISO2 'GB'; dropped aggregates (EU27, EA*) and other geographies.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=rows,
        coverage=f"{len(covered)}/15 countries (EU/EFTA only), 1975-2025 annual",
        notes="Pairs with eurostat_ict_specialists to give IT jobs as a share of a real total.",
    )


if __name__ == "__main__":
    main_guard(run)
