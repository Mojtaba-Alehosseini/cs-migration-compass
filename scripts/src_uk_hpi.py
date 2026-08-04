"""UK HPI full file → UK city house prices (average price + index), monthly.

Real city-level history for London, Manchester and Edinburgh, published by
HM Land Registry. Unlike FHFA/Teranet this file carries an actual AVERAGE PRICE
in GBP as well as an index, so UK city pages can show a price level.

The filename carries the release month and the newest release is typically 2-3
months behind today, so we discover the latest available file rather than
hardcoding one.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DEFAULT_HEADERS, RAW, UK_CITY_HPI_REGION, banner, fetch_text, log,
    main_guard, record_provenance, write_processed,
)

SOURCE_ID = "uk_hpi"
NAME = "UK House Price Index — full file (HM Land Registry)"
BASE = "https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data"


def latest_release(max_back: int = 12) -> str:
    """Walk back month by month until a full file exists."""
    today = dt.date.today().replace(day=1)
    for i in range(max_back):
        y, m = today.year, today.month - i
        while m < 1:
            m += 12
            y -= 1
        url = f"{BASE}/UK-HPI-full-file-{y}-{m:02d}.csv"
        r = requests.head(url, headers=DEFAULT_HEADERS, timeout=60, allow_redirects=True)
        if r.status_code == 200:
            log(f"    latest release: {y}-{m:02d} ({int(r.headers.get('content-length', 0)):,} bytes)")
            return url
    raise RuntimeError("no UK HPI full file found in the last 12 months")


def _f(v: str) -> float | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def run() -> None:
    banner(SOURCE_ID, NAME)
    url = latest_release()
    text = fetch_text(url, dest=RAW / SOURCE_ID / Path(url).name)

    wanted = {region: city for city, region in UK_CITY_HPI_REGION.items()}
    out: dict[str, dict] = {}
    total = 0

    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        city = wanted.get((row.get("RegionName") or "").strip())
        if city is None:
            continue
        avg = _f(row.get("AveragePrice", ""))
        idx = _f(row.get("Index", ""))
        if avg is None and idx is None:
            continue
        # Date is dd/mm/yyyy in this file.
        d = (row.get("Date") or "").strip()
        try:
            day, mon, yr = d.split("/")
            month = f"{int(yr):04d}-{int(mon):02d}"
        except ValueError:
            continue
        rec = out.setdefault(
            city,
            {"region_name": row["RegionName"].strip(), "area_code": row.get("AreaCode", ""), "series": []},
        )
        rec["series"].append(
            {
                "month": month,
                "avg_price_gbp": avg,
                "index": idx,
                "detached_gbp": _f(row.get("DetachedPrice", "")),
                "flat_gbp": _f(row.get("FlatPrice", "")),
            }
        )
        total += 1

    for city, rec in out.items():
        rec["series"].sort(key=lambda r: r["month"])
        rec["first"], rec["last"] = rec["series"][0], rec["series"][-1]
        log(f"    {city:10s} {rec['first']['month']} → {rec['last']['month']}  ({len(rec['series'])} months)")

    missing = [c for c in UK_CITY_HPI_REGION if c not in out]
    if missing:
        log(f"    !! no rows for: {', '.join(missing)}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "fields": {
                "avg_price_gbp": "average sale price, GBP, not FX-converted here",
                "index": "UK HPI index (Jan 2015 = 100)",
                "flat_gbp": "average flat/maisonette price, GBP — the closest match to our apartment metric",
            },
            "frequency": "monthly",
            "confidence": "official",
            "level": "UK local authority / city",
            "release": Path(url).name,
            "currency_caveat": (
                "Prices are GBP as published. Converting a 1970s-2020s price series with a single "
                "pinned 2026 FX rate would be misleading, so conversion is left to the UI, which "
                "labels it, and the historical chart is shown in GBP."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[url],
        license_note=(
            "Contains HM Land Registry data © Crown copyright and database right. "
            "Open Government Licence v3.0."
        ),
        transforms=[
            "Discovered the latest monthly full-file release by HEAD-probing back from the current month.",
            "Streamed the ~35 MB CSV and kept only rows whose RegionName matches our 3 UK cities.",
            "Parsed dd/mm/yyyy dates to YYYY-MM; dropped rows with neither an average price nor an index.",
            "Kept average price, index, detached and flat prices; sorted ascending by month.",
            "Left values in GBP — no FX conversion of a multi-decade series.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=total,
        coverage=f"{len(out)}/3 UK cities, monthly (values sparse before the mid-1990s)",
        notes="Real city-level history including an actual price level, not just an index.",
    )


if __name__ == "__main__":
    main_guard(run)
