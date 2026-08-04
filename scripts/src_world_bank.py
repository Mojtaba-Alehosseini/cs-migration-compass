"""World Bank Indicators API → country economy history (1990→).

Powers: economy trend charts (GDP/capita, inflation, unemployment, net migration,
population). Free, open, no key. Verified live.

Output shape:
  data.<ISO2>.<indicator_key> = [{"year": 1990, "value": 1234.5}, ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, ISO2_TO_ISO3, ISO3_TO_ISO2, RAW, banner, fetch_json, log,
    main_guard, record_provenance, write_processed,
)

SOURCE_ID = "world_bank"
NAME = "World Bank Open Data — Indicators API"

# indicator code -> our key. Chosen to cover the Money and Jobs themes.
INDICATORS = {
    "NY.GDP.PCAP.CD": "gdp_per_capita_usd",
    "NY.GDP.PCAP.PP.CD": "gdp_per_capita_ppp_intl",
    "FP.CPI.TOTL.ZG": "inflation_pct",
    "SL.UEM.TOTL.ZS": "unemployment_pct",
    "SM.POP.NETM": "net_migration",
    "SP.POP.TOTL": "population",
}

START, END = 1990, 2026
BASE = "https://api.worldbank.org/v2"


def run() -> None:
    banner(SOURCE_ID, NAME)
    iso3 = ";".join(ISO2_TO_ISO3[c] for c in COUNTRY_IDS)
    out: dict[str, dict[str, list]] = {c: {} for c in COUNTRY_IDS}
    urls: list[str] = []
    total_rows = 0

    for code, key in INDICATORS.items():
        url = f"{BASE}/country/{iso3}/indicator/{code}?format=json&per_page=20000&date={START}:{END}"
        urls.append(url)
        payload = fetch_json(url, dest=RAW / SOURCE_ID / f"{code}.json")
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            log(f"    !! no data returned for {code}")
            continue

        per_country: dict[str, list] = {c: [] for c in COUNTRY_IDS}
        for row in payload[1]:
            iso2 = ISO3_TO_ISO2.get(row.get("countryiso3code", ""))
            if iso2 is None or row.get("value") is None:
                continue
            per_country[iso2].append({"year": int(row["date"]), "value": row["value"]})

        for c, series in per_country.items():
            series.sort(key=lambda r: r["year"])
            out[c][key] = series
            total_rows += len(series)
        log(f"    {key:26s} {sum(len(v) for v in per_country.values()):5d} points")

    meta = {
        "indicators": {v: k for k, v in INDICATORS.items()},
        "unit_notes": {
            "gdp_per_capita_usd": "current US$",
            "gdp_per_capita_ppp_intl": "current international $ (PPP)",
            "inflation_pct": "annual % change, consumer prices",
            "unemployment_pct": "% of total labour force (modelled ILO estimate)",
            "net_migration": "persons, 5-year totals as published",
            "population": "persons, total",
        },
        "confidence": "official",
        "range": f"{START}-{END}",
    }
    write_processed(SOURCE_ID, out, meta=meta)
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=urls,
        license_note="CC BY 4.0 — World Bank Open Data. Cite: World Bank, World Development Indicators.",
        transforms=[
            "Requested 6 indicators for the 15 covered countries in one call each (semicolon-joined ISO3).",
            "Dropped rows with null values (World Bank returns nulls for unreported years).",
            "Regrouped from flat rows to {ISO2: {indicator_key: [{year, value}]}} sorted ascending by year.",
            "No smoothing, no interpolation, no imputation.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=total_rows,
        coverage=f"15/15 countries, {START}-{END} (per-indicator coverage varies by country)",
        notes="Values are as published; gaps are left as gaps.",
    )


if __name__ == "__main__":
    main_guard(run)
