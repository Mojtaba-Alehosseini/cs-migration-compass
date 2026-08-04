"""OECD Economic Outlook (EO) → institutional forecast overlay.

This is a REAL forecast from a named institution, and the site must render it as
such: a solid line with an attribution chip ("OECD Economic Outlook 119"), never
averaged with our own naive extrapolation.

Distinguishing actual from projection: the EO cube does not flag it, so we do it
with data rather than a guess — any EO year later than the last year for which
the World Bank publishes an actual GDP-per-capita figure for that same country is
marked is_projection = true. That rule is recorded in the output and in
docs/METHODOLOGY.md.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, ISO2_TO_ISO3, ISO3_TO_ISO2, PROCESSED, RAW, banner, fetch_text,
    log, main_guard, record_provenance, write_processed,
)

SOURCE_ID = "oecd_economic_outlook"
NAME = "OECD Economic Outlook 119 — projections"
FLOW = "OECD.ECO.MAD,DSD_EO@DF_EO,1.5"
BASE = "https://sdmx.oecd.org/public/rest/data"
EDITION = "OECD Economic Outlook 119"

# EO measure code -> our key. Verified present in the live cube.
MEASURES = {
    "GDPV_ANNPCT": "real_gdp_growth_pct",
    "GDP_ANNPCT": "nominal_gdp_growth_pct",
    "UNR": "unemployment_pct",
    "POP": "population",
    "NLGQ": "govt_net_lending_pct_gdp",
}

EO_COUNTRIES = [c for c in COUNTRY_IDS if c not in ("AE", "QA")]


def last_actual_year_by_country() -> dict[str, int]:
    """Last year the World Bank reports actual GDP/capita, per country."""
    path = PROCESSED / "world_bank.json"
    if not path.exists():
        log("    !! world_bank.json missing — run src_world_bank.py first; "
            "falling back to a fixed projection cutoff")
        return {}
    wb = json.loads(path.read_text(encoding="utf-8"))["data"]
    out: dict[str, int] = {}
    for iso2, block in wb.items():
        series = block.get("gdp_per_capita_usd") or []
        if series:
            out[iso2] = max(p["year"] for p in series)
    return out


def run() -> None:
    banner(SOURCE_ID, NAME)
    key = "+".join(ISO2_TO_ISO3[c] for c in EO_COUNTRIES) + "..A"
    url = f"{BASE}/{FLOW}/{key}?format=csv&startPeriod=2000"
    text = fetch_text(url, dest=RAW / SOURCE_ID / "eo_annual.csv")

    cutoffs = last_actual_year_by_country()
    fallback_cutoff = max(cutoffs.values()) if cutoffs else 2025

    out: dict[str, dict[str, list]] = {}
    n = 0
    for row in csv.DictReader(io.StringIO(text)):
        key_ = MEASURES.get((row.get("MEASURE") or "").strip())
        if key_ is None:
            continue
        iso2 = ISO3_TO_ISO2.get((row.get("REF_AREA") or "").strip())
        if iso2 is None:
            continue
        try:
            year = int((row.get("TIME_PERIOD") or "").strip())
            value = float(row["OBS_VALUE"])
        except (TypeError, ValueError, KeyError):
            continue
        cutoff = cutoffs.get(iso2, fallback_cutoff)
        out.setdefault(iso2, {}).setdefault(key_, []).append(
            {"year": year, "value": value, "is_projection": year > cutoff}
        )
        n += 1

    horizon = 0
    for country in out.values():
        for series in country.values():
            series.sort(key=lambda r: r["year"])
            proj = [p["year"] for p in series if p["is_projection"]]
            if proj:
                horizon = max(horizon, max(proj))

    log(f"    {len(out)}/{len(EO_COUNTRIES)} OECD countries, {n:,} observations")
    log(f"    projection horizon: {horizon} · actual/projection cutoff per country from World Bank actuals")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "edition": EDITION,
            "institution": "OECD",
            "attribution_chip": EDITION,
            "kind": "institutional_forecast",
            "measures": {v: k for k, v in MEASURES.items()},
            "confidence": "official",
            "countries_without_data": ["AE", "QA"],
            "projection_horizon": horizon,
            "projection_rule": (
                "is_projection = year > (last year the World Bank publishes an actual GDP/capita "
                "figure for that country). The EO cube carries no projection flag, so this is derived "
                "from data rather than assumed."
            ),
            "render_rule": (
                "Draw as a SOLID line with the attribution chip. Never average with, or blend into, "
                "the site's own naive extrapolation, which is drawn as a hatched band."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[url],
        license_note=(
            "OECD terms and conditions — free re-use with attribution for non-commercial use. "
            f"Cite: {EDITION}."
        ),
        transforms=[
            f"Requested annual EO series for {len(EO_COUNTRIES)} OECD countries from {FLOW}.",
            "Kept 5 measures: real and nominal GDP growth, unemployment, population, net lending.",
            "Derived is_projection per point by comparing the EO year against the last World Bank "
            "actual year for the same country — the EO cube has no projection flag.",
            "Sorted ascending by year. No blending with any other forecast or with our extrapolation.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=n,
        coverage=f"{len(out)}/15 countries (AE, QA are not OECD members), projections to {horizon}",
        notes="Institutional forecast — rendered solid and attributed, kept separate from naive extrapolation.",
    )


if __name__ == "__main__":
    main_guard(run)
