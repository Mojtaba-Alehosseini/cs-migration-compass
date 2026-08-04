"""BIS Selected Property Prices (SDMX) → long-run national house-price history.

The deepest housing history available for our set — quarterly, some series from
1970. This is the country trend that city panels apply to a current city value
when no real city series exists, and it is labelled exactly that way in the UI
("city estimate = current value x country trend"), never passed off as city data.

Two value types are published and both are kept:
  R = real (inflation-adjusted), N = nominal
Two unit measures:
  628 = index, 771 = year-on-year % change

The Gulf (AE, QA) is not covered by BIS. That is recorded as a gap, not filled.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, RAW, banner, fetch_text, log, main_guard, record_provenance,
    write_processed,
)

SOURCE_ID = "bis_property_prices"
NAME = "BIS — Selected residential property prices (quarterly)"
BASE = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_SPP/1.0"

# BIS does not publish AE or QA in this dataflow (verified: HTTP 404).
BIS_COUNTRIES = [c for c in COUNTRY_IDS if c not in ("AE", "QA")]
NOT_COVERED = ["AE", "QA"]

VALUE_LABEL = {"R": "real", "N": "nominal"}
UNIT_LABEL = {"628": "index", "771": "yoy_pct"}


def run() -> None:
    banner(SOURCE_ID, NAME)
    key = "Q." + "+".join(BIS_COUNTRIES)
    url = f"{BASE}/{key}?format=csv"
    text = fetch_text(url, dest=RAW / SOURCE_ID / "spp_quarterly.csv")

    out: dict[str, dict[str, list]] = {}
    total = 0
    for row in csv.DictReader(io.StringIO(text)):
        iso2 = (row.get("REF_AREA") or "").strip()
        if iso2 not in BIS_COUNTRIES:
            continue
        val = VALUE_LABEL.get((row.get("VALUE") or "").strip())
        unit = UNIT_LABEL.get((row.get("UNIT_MEASURE") or "").strip())
        if val is None or unit is None:
            continue
        try:
            obs = float(row["OBS_VALUE"])
        except (KeyError, TypeError, ValueError):
            continue
        period = (row.get("TIME_PERIOD") or "").strip()  # e.g. 2026-Q1
        series_key = f"{val}_{unit}"
        out.setdefault(iso2, {}).setdefault(series_key, []).append(
            {"period": period, "value": obs}
        )
        total += 1

    for country in out.values():
        for series in country.values():
            series.sort(key=lambda r: r["period"])

    starts = {c: min(s[0]["period"] for s in v.values()) for c, v in out.items()}
    log(f"    {len(out)}/{len(BIS_COUNTRIES)} BIS countries, {total:,} observations")
    log(f"    earliest series: {min(starts.values())} · not covered by BIS: {', '.join(NOT_COVERED)}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "series_keys": {
                "real_index": "Real (CPI-deflated) residential property price index",
                "nominal_index": "Nominal residential property price index",
                "real_yoy_pct": "Real prices, year-on-year % change",
                "nominal_yoy_pct": "Nominal prices, year-on-year % change",
            },
            "frequency": "quarterly",
            "confidence": "official",
            "level": "country",
            "countries_covered": sorted(out),
            "countries_without_data": NOT_COVERED,
            "series_start": starts,
            "index_base_note": (
                "BIS index bases differ by country, so levels are NOT comparable across countries. "
                "Only the SHAPE of each series is meaningful — the UI must compare growth, never levels."
            ),
            "city_application_rule": (
                "Where a city has no real house-price series, the UI may apply this country trend to "
                "the city's current value and must label it 'city estimate = current value x country trend'."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[url],
        license_note=(
            "BIS statistics are free to use with attribution for non-commercial purposes. "
            "Cite: Bank for International Settlements, Selected residential property prices."
        ),
        transforms=[
            f"One SDMX-CSV request for all {len(BIS_COUNTRIES)} covered countries (key Q.<A>+<B>+...).",
            "Split into four series per country by VALUE (real/nominal) x UNIT_MEASURE (index / YoY %).",
            "Kept TIME_PERIOD verbatim as 'YYYY-Qn'; sorted ascending.",
            "Dropped non-numeric observations. No rebasing — BIS bases differ by country.",
            "AE and QA are not published in this dataflow and are recorded as uncovered.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=total,
        coverage=f"{len(out)}/15 countries (BIS excludes AE, QA), quarterly from {min(starts.values())}",
        notes="Index bases differ by country — comparable in shape, not in level.",
    )


if __name__ == "__main__":
    main_guard(run)
