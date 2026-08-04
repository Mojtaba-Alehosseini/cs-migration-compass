"""Teranet–National Bank House Price Index → Canadian city house prices, 1990-06→.

Real city-level monthly history for all 6 of our Canadian cities. The endpoint is
undocumented (it backs the charts on housepriceindex.ca) but stable and public;
it is recorded as such in data-pipeline-sources.json.

TLS note: this host serves an intermediate certificate that certifi does not
carry. scripts/_common.py routes verification through the OS trust store via
`truststore` — we do not disable certificate verification.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CA_CITY_TERANET_KEY, RAW, banner, fetch_json, log, main_guard,
    record_provenance, write_processed,
)

SOURCE_ID = "teranet_national_bank_hpi"
NAME = "Teranet–National Bank House Price Index (Canada)"
URL = "https://housepriceindex.ca/_data/indx_data.json"


def _months(start: str, n: int) -> list[str]:
    """Month labels 'YYYY-MM' starting at `start` ('YYYY-MM-DD'), length n."""
    y, m = int(start[0:4]), int(start[5:7])
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def run() -> None:
    banner(SOURCE_ID, NAME)
    doc = fetch_json(URL, dest=RAW / SOURCE_ID / "indx_data.json")

    profiles = doc["profiles"]
    indx = doc["data"]["indx"]
    meta = doc["data"]["meta"]
    start = meta["start_date"]

    sample_len = max(len(v) for v in indx.values())
    axis = _months(start, sample_len)

    out: dict[str, dict] = {}
    total = 0
    for city, key in CA_CITY_TERANET_KEY.items():
        series_raw = indx.get(key)
        if series_raw is None:
            log(f"    !! Teranet series '{key}' missing for {city}")
            continue
        points = [
            {"date": axis[i], "index": v}
            for i, v in enumerate(series_raw)
            if v is not None and i < len(axis)
        ]
        if not points:
            log(f"    !! {city}: series present but entirely null")
            continue
        out[city] = {
            "series_key": key,
            "area_name": profiles.get(key, {}).get("name", key),
            "series": points,
            "first": points[0],
            "last": points[-1],
        }
        total += len(points)
        log(f"    {city:10s} {points[0]['date']} → {points[-1]['date']}  ({len(points)} months)")

    # National composite as a benchmark line, clearly labelled as such.
    composite = None
    if "c11" in indx:
        pts = [{"date": axis[i], "index": v} for i, v in enumerate(indx["c11"]) if v is not None]
        composite = {
            "series_key": "c11",
            "area_name": profiles.get("c11", {}).get("name", "Composite 11"),
            "series": pts,
        }

    write_processed(
        SOURCE_ID,
        {"cities": out, "composite_benchmark": composite},
        meta={
            "index_type": "Teranet–National Bank repeat-sales house price index (June 2005 = 100)",
            "frequency": "monthly",
            "range": f"{meta['start_date']} to {meta['end_date']}",
            "confidence": "index",
            "level": "Canadian metro",
            "index_caveat": (
                "An index of price change, not a price level. Per-city series start later than "
                "the array start; leading nulls are dropped rather than back-filled."
            ),
            "endpoint_note": (
                "Undocumented JSON endpoint backing housepriceindex.ca charts. Public and stable, "
                "but not a contracted API — if it moves, this script is the thing to fix."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[URL],
        license_note=(
            "Teranet & National Bank of Canada. Free public access for non-commercial use with "
            "attribution; index values are proprietary. We commit the derived per-city series."
        ),
        transforms=[
            "Fetched the JSON payload backing housepriceindex.ca (35 profiles, 7 data blocks).",
            "Rebuilt the monthly date axis from data.meta.start_date and the series length.",
            "Selected the 6 series matching our Canadian cities; dropped leading nulls "
            "(a city's index simply starts later) rather than back-filling.",
            "Kept the Composite 11 series separately as a labelled national benchmark.",
            "No rebasing, no smoothing.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=total,
        coverage=f"{len(out)}/6 Canadian cities, monthly {meta['start_date']}→{meta['end_date']}",
        notes="Real city-level history for Canada.",
        redistribution="derived per-city series committed; raw payload also committed (public endpoint)",
    )


if __name__ == "__main__":
    main_guard(run)
