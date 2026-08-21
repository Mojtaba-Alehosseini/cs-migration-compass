"""World Bank Indicators API -> year-matched FX rates for currency conversion.

Package 9's normalisation rule (scripts/normalise.py) requires converting
each wage figure at the exchange rate FROM ITS OWN YEAR — never one modern
rate applied across the whole spine (the anachronism package 5 already
ruled out for house prices: "London stays in pounds — one 2026 FX rate
across 1968-2026 would lie"). This harvester exists so that rule has real,
sourced, year-by-year rates to draw from rather than a single hardcoded
number.

Indicator: PA.NUS.FCRF — "Official exchange rate (LCU per US$, PERIOD
AVERAGE)". Period-average, not end-of-period or a spot rate, is the
correct series here: an annual wage figure is itself an average over the
year, so it must be met with a rate that is also an average over the same
year, not a single day's snapshot. Verified live (this session): every
currency this spine needs returns data, annual, from 1960,
`lastupdated 2026-07-13`, CC BY 4.0 — same licence and same API this repo
already talks to in scripts/src_world_bank.py; this file follows that
module's shape exactly rather than inventing a second pattern for the same
API.

Eurozone note: LCU for Ireland, the Netherlands, Spain and Finland (the
four eurozone countries with live salary data in this spine) is EUR from
1999 onward, and each country's own legacy currency (IEP, NLG, ESP, FIM)
before that — this is the World Bank's own series behaving correctly, not
a special case this script codes around. Germany and Italy (DEM, ITL) are
fetched too even though neither has a live salary source yet (see
NEEDS-DECISION.md #15 and src_salary_it.py) — FX history costs nothing
extra to keep and Germany's Tier 2 may unblock in a future session.

AED and QAR are effectively pegged to the US dollar (3.6725 and 3.64
respectively, unchanged for decades) — recorded here as fetched, not
special-cased, but worth noting as one of the few conversions in this
spine that is honestly near-exact rather than a genuine market rate.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, ISO2_TO_ISO3, ISO3_TO_ISO2, RAW, banner, fetch_json, log,
    main_guard, record_provenance, write_processed,
)

SOURCE_ID = "fx_rates"
NAME = "World Bank Open Data — Official exchange rate, period average (PA.NUS.FCRF)"
INDICATOR = "PA.NUS.FCRF"
START, END = 1960, 2026
BASE = "https://api.worldbank.org/v2"

# AED/QAR pegs, for the meta note only — not used to compute or override
# anything the API itself returns.
KNOWN_PEGS = {"AE": "3.6725 AED per USD", "QA": "3.64 QAR per USD"}

# Package 14, Tier 3.1 — the postings panel's own compensation spans nine
# currencies (USD, EUR, GBP, CAD, SGD, JPY, KHR, INR, AMD), five of whose
# countries were never part of the wage spine's own 15 and so had no FX
# series here at all: routing postings through normalise.to_usd() (this
# package's own fix, see build_postings.py) needs a real, year-matched rate
# for every one of them, not just the ones the wage spine happened to need.
# Fetched as a SEPARATE request from the wage spine's own 15 (not folded
# into COUNTRY_IDS, which several other checks in this pipeline treat as
# exactly "the 15 wage-spine countries") — same indicator, same source,
# same period-average convention, merged into the SAME fx_rates.json under
# their own ISO2 keys. Not exhaustive of every currency any postings
# provider might ever surface (Finding 3's own list is what's live TODAY);
# a currency this pipeline sees in the future without a matching entry
# here fails normalise.to_usd() honestly (rule 1: no fallback), the same
# way any other unmapped year or country already does.
POSTINGS_EXTRA_FX_COUNTRIES = {"SG": "SGP", "JP": "JPN", "KH": "KHM", "IN": "IND", "AM": "ARM"}


def run() -> None:
    banner(SOURCE_ID, NAME)
    all_iso2 = COUNTRY_IDS + list(POSTINGS_EXTRA_FX_COUNTRIES)
    all_iso3_map = {**{c: ISO2_TO_ISO3[c] for c in COUNTRY_IDS}, **POSTINGS_EXTRA_FX_COUNTRIES}
    iso3_to_iso2_full = {**ISO3_TO_ISO2, **{v: k for k, v in POSTINGS_EXTRA_FX_COUNTRIES.items()}}
    iso3 = ";".join(all_iso3_map[c] for c in all_iso2)
    url = f"{BASE}/country/{iso3}/indicator/{INDICATOR}?format=json&per_page=20000&date={START}:{END}"
    payload = fetch_json(url, dest=RAW / SOURCE_ID / f"{INDICATOR}.json")

    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        log("    !! no data returned")
        out: dict[str, list] = {c: [] for c in all_iso2}
        total_rows = 0
    else:
        out = {c: [] for c in all_iso2}
        for row in payload[1]:
            iso2 = iso3_to_iso2_full.get(row.get("countryiso3code", ""))
            if iso2 is None or row.get("value") is None:
                continue
            out[iso2].append({"year": int(row["date"]), "value": row["value"]})
        for c, series in out.items():
            series.sort(key=lambda r: r["year"])
        total_rows = sum(len(v) for v in out.values())
        for c in POSTINGS_EXTRA_FX_COUNTRIES:
            latest = out[c][-1] if out[c] else None
            log(f"    {c} (postings-only): {len(out[c])} years, latest {latest}")

    for c in ("DK", "SE", "AE", "QA"):
        series = out.get(c, [])
        latest = series[-1] if series else None
        log(f"    {c}: {len(series)} years, latest {latest}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "indicator": INDICATOR,
            "indicator_label": "Official exchange rate (LCU per US$, period average)",
            "unit": "local currency units per 1 US dollar, PERIOD AVERAGE (not end-of-period, not spot)",
            "confidence": "official",
            "range": f"{START}-{END}",
            "usage_rule": "Convert a wage figure using the rate from THAT FIGURE'S OWN YEAR — never a "
                "single modern rate applied across multiple years. See scripts/normalise.py.",
            "eurozone_note": "LCU is EUR from 1999 for eurozone countries (IE, NL, ES, FI in this "
                "spine's live sources; DE, IT fetched too though neither has live salary data yet) and "
                "each country's own legacy currency before 1999 — the World Bank's own series, not a "
                "transform this pipeline applies.",
            "known_pegs": KNOWN_PEGS,
            "postings_extra_countries": {
                "note": "Package 14, Tier 3.1 — SG/JP/KH/IN/AM are NOT part of the 15-country wage "
                        "spine; fetched here only so the postings panel's own SGD/JPY/KHR/INR/AMD "
                        "compensation can convert through normalise.to_usd() with a real, year-matched "
                        "rate rather than not converting those currencies at all.",
                "countries": sorted(POSTINGS_EXTRA_FX_COUNTRIES),
            },
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[url],
        license_note="CC BY 4.0 — World Bank Open Data. Cite: World Bank, World Development Indicators.",
        redistribution="processed derivative only — the raw API response is cached under "
                        "data/raw/fx_rates/ but that directory is gitignored, so this repo does not "
                        "redistribute it (CC BY 4.0 would permit it; the repo simply doesn't). Only "
                        "the derived data/processed/fx_rates.json is committed.",
        transforms=[
            f"Requested indicator {INDICATOR} for all 15 wage-spine countries PLUS 5 postings-only "
            f"countries (SG, JP, KH, IN, AM — package 14, Tier 3.1, needed to convert postings' own "
            f"SGD/JPY/KHR/INR/AMD compensation) in one call (semicolon-joined ISO3), {START}-{END}.",
            "Dropped rows with null values (World Bank returns nulls for unreported years).",
            "Regrouped from flat rows to {ISO2: [{year, value}]} sorted ascending by year — same "
            "shape convention as scripts/src_world_bank.py.",
            "No smoothing, no interpolation, no imputation, no override of AED/QAR's known peg values "
            "— fetched exactly as published.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=total_rows,
        coverage=f"15/15 wage-spine countries + 5/5 postings-only countries (SG, JP, KH, IN, AM), "
                 f"{START}-{END} (per-country coverage varies; pre-independence or pre-modern-currency "
                 "years are gaps, not zeros)",
        notes="Period-average, not end-of-period — the correct series for converting an annual wage "
              "figure, which is itself an average over the year.",
    )


if __name__ == "__main__":
    main_guard(run)
