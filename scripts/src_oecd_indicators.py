"""OECD SDMX → house prices, average wages, hours worked, tax wedge.

Four dataflows, one script, because they share the same SDMX plumbing:

  house_prices  real & nominal house-price and rent indices  (Housing theme trends)
  avg_wages     average annual wages, USD PPP                 (the "All jobs" toggle:
                                                               "a mid-level dev earns
                                                               1.8x the national average")
  hours_worked  average annual hours actually worked          (Work-life)
  tax_wedge     labour tax wedge, single person at 100% AW    (cross-check on our
                                                               net_pct_single_mid_dev)

Dataflow IDs were resolved from the live OECD registry, not guessed — several
plausible-looking IDs do not exist. Gulf countries are not OECD members and are
absent throughout; that is recorded, never filled in.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, ISO2_TO_ISO3, ISO3_TO_ISO2, RAW, banner, fetch_text, log,
    main_guard, record_provenance, write_processed,
)

SOURCE_ID = "oecd_indicators"
NAME = "OECD Data Explorer (SDMX) — house prices, wages, hours, tax wedge"
BASE = "https://sdmx.oecd.org/public/rest/data"

OECD_ISO3 = "+".join(ISO2_TO_ISO3[c] for c in COUNTRY_IDS if c not in ("AE", "QA"))
NOT_OECD = ["AE", "QA"]

BLOCKS = {
    "house_prices": {
        "flow": "OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0",
        "key": f"{OECD_ISO3}.Q..",
        "start": "1970",
        "dims": ("MEASURE", "UNIT_MEASURE"),
        "time": "TIME_PERIOD",
    },
    "avg_wages": {
        "flow": "OECD.ELS.SAE,DSD_EARNINGS@AV_AN_WAGE,1.0",
        "key": "all",
        "start": "1990",
        "dims": ("MEASURE", "UNIT_MEASURE"),
        "time": "TIME_PERIOD",
        "keep": lambda r: r.get("UNIT_MEASURE") in ("USD_PPP", "XDC") and r.get("SEX", "_Z") == "_Z",
    },
    "hours_worked": {
        "flow": "OECD.ELS.SAE,DSD_HW@DF_AVG_ANN_HRS_WKD,1.0",
        "key": "all",
        "start": "1990",
        "dims": ("MEASURE", "UNIT_MEASURE"),
        "time": "TIME_PERIOD",
        "keep": lambda r: r.get("WORKER_STATUS", "_T") == "_T",
    },
    "tax_wedge": {
        "flow": "OECD.CTP.TPS,DSD_TAX_WAGES_COMP@DF_TW_COMP,2.1",
        "key": "all",
        "start": "2000",
        "dims": ("MEASURE", "UNIT_MEASURE"),
        "time": "TIME_PERIOD",
        # single person, no children, at 100% of the average wage — the household
        # shape our net-pay model describes.
        "keep": lambda r: (
            r.get("HOUSEHOLD_TYPE") == "S_C0"
            and r.get("INCOME_PRINCIPAL") == "AW100"
            and r.get("MEASURE") in ("AV_TW", "NIAT", "GEBT", "AV_ITR")
        ),
    },
}


def run() -> None:
    banner(SOURCE_ID, NAME)
    out: dict[str, dict] = {c: {} for c in COUNTRY_IDS}
    urls: list[str] = []
    grand_total = 0
    block_coverage: dict[str, list[str]] = {}

    for block, cfg in BLOCKS.items():
        url = f"{BASE}/{cfg['flow']}/{cfg['key']}?format=csv&startPeriod={cfg['start']}"
        urls.append(url)
        text = fetch_text(url, dest=RAW / SOURCE_ID / f"{block}.csv")
        keep = cfg.get("keep")
        n = 0
        seen: set[str] = set()

        for row in csv.DictReader(io.StringIO(text)):
            iso2 = ISO3_TO_ISO2.get((row.get("REF_AREA") or "").strip())
            if iso2 is None:
                continue
            if keep is not None and not keep(row):
                continue
            try:
                value = float(row["OBS_VALUE"])
            except (KeyError, TypeError, ValueError):
                continue
            series_key = "_".join(
                (row.get(d) or "").strip() for d in cfg["dims"] if (row.get(d) or "").strip()
            ) or "value"
            period = (row.get(cfg["time"]) or "").strip()
            out[iso2].setdefault(block, {}).setdefault(series_key, []).append(
                {"period": period, "value": value}
            )
            seen.add(iso2)
            n += 1

        for iso2 in seen:
            for series in out[iso2][block].values():
                series.sort(key=lambda r: r["period"])
        block_coverage[block] = sorted(seen)
        grand_total += n
        log(f"    {block:14s} {n:7,} obs · {len(seen)}/15 countries")

    out = {k: v for k, v in out.items() if v}
    missing_all = [c for c in COUNTRY_IDS if c not in out]
    log(f"    no OECD data at all: {', '.join(missing_all) or 'none'}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "blocks": {
                "house_prices": "Real/nominal house price and rent indices, quarterly (base year varies)",
                "avg_wages": "Average annual wages — USD_PPP and national currency, annual",
                "hours_worked": "Average annual hours actually worked per worker, annual",
                "tax_wedge": "Labour tax wedge, single person no children at 100% of average wage",
            },
            "series_key_format": "MEASURE_UNITMEASURE as published by OECD",
            "confidence": "official",
            "level": "country",
            "countries_without_data": NOT_OECD,
            "coverage_by_block": block_coverage,
            "membership_caveat": (
                "AE and QA are not OECD members and appear in none of these dataflows. "
                "The UI shows 'no data' for them rather than substituting a regional proxy."
            ),
            "avg_wages_use": (
                "avg_wages is what makes the Developers / All-jobs toggle honest: the dev salary is "
                "ours, the national average is OECD's, and the ratio is computed, not asserted."
            ),
            "tax_wedge_filter": "HOUSEHOLD_TYPE=S_C0 (single, no children), INCOME_PRINCIPAL=AW100",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=urls,
        license_note=(
            "OECD terms and conditions — free re-use with attribution for non-commercial use. "
            "Cite: OECD Data Explorer, dataflow IDs listed per block."
        ),
        transforms=[
            "Resolved all four dataflow IDs from the live OECD SDMX registry (several plausible IDs do not exist).",
            "Requested SDMX-CSV per dataflow; used the 'all' key where the flow requires more key positions than we filter on.",
            "Mapped REF_AREA ISO3 to our ISO2 set; every other country dropped.",
            "avg_wages: kept USD_PPP and national-currency series, both sexes combined (SEX=_Z).",
            "hours_worked: kept total worker status (_T).",
            "tax_wedge: filtered to single person without children at 100% of the average wage; "
            "kept average tax wedge, average income tax rate, gross earnings and net income.",
            "Grouped into MEASURE_UNITMEASURE series and sorted by period. No rebasing or smoothing.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=grand_total,
        coverage=f"{len(out)}/15 countries (AE, QA are not OECD members)",
        notes="Index bases differ by country and block — compare shape, not level.",
    )


if __name__ == "__main__":
    main_guard(run)
