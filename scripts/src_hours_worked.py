"""Eurostat lfsa_ewhun2 + Statistics Canada WDS -> usual weekly hours worked.

Package 9's normalisation module (scripts/normalise.py) needs a sourced
hours-per-week figure to convert an hourly wage to annual (or vice versa)
WITHOUT assuming the US convention of 2080 hours/year (40h x 52 weeks) —
Denmark's own full-time employees work about 38 usual weekly hours, and the
2080 convention would overstate Denmark's annual-equivalent pay by roughly
7%. This file exists so DK/NL/IE (this spine's hourly-wage countries with a
real Eurostat cross) and CA (hourly-wage, no EU cross available) each get
their OWN sourced hours figure instead.

EUROSTAT lfsa_ewhun2 — "Average usual weekly hours worked in the main job,
by professional status, full-time/part-time and NACE Rev. 2 activity".
sex=T (total), wstatus=SAL (employees), worktime=FT (full-time),
age=Y_GE15 (15 years or over, the broadest available band — no upper
bound, matching this spine's other "no age restriction" defaults),
nace_r2=J (Information and communication) where populated, falling back to
TOTAL (all activities) where J is empty for a country — RECORDED which
basis was actually used per country, not silently blended. Covers DK, NL,
IE among this spine's hourly-wage countries.

Eurostat's own "status" flags (a SEPARATE sparse map in the JSON-stat
payload, keyed by the same linear index as "value" — _common.jsonstat_rows()
does not surface it, since most sources in this pipeline don't need it) are
carried through explicitly here: a "u" (low reliability, small sample) flag
on an hours figure means anything normalise.py derives from it inherits
that uncertainty, and package 9's work order requires this pipeline be able
to say so.

CANADA — StatCan Web Data Service, table 14-10-0043-01 ("Average usual and
actual hours worked in a reference week by type of work, annual"), vector
2529313 (Canada, Average usual hours, Main job, Full-time employment,
Total-Gender, 15 years and over) — verified live, 2020-2025, values
39.7-40.0. Job Bank's own wage figures are explicitly "usual hours ...
not counting any overtime", so this vector (usual, not actual, hours) is
the matching concept, not a mismatched one. No EU cross exists for Canada,
so this is StatCan's own labour force survey, a different source family
from the other three countries in this file, sourced separately.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    RAW, banner, fetch, fetch_json, jsonstat_rows, log, main_guard,
    record_provenance, write_processed,
)

SOURCE_ID = "hours_worked"
NAME = "Eurostat lfsa_ewhun2 (DK/NL/IE) + Statistics Canada WDS (CA) — usual weekly hours worked"

EUROSTAT_COUNTRIES = ["DK", "NL", "IE"]
EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/lfsa_ewhun2"

STATCAN_PID = 14100043
STATCAN_COORD = "1.2.1.2.1.1.0.0.0.0"  # Canada / Avg usual hours / Main job / FT / Total-Gender / 15+
STATCAN_VECTOR = 2529313
STATCAN_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromCubePidCoordAndLatestNPeriods"


def _fetch_eurostat(nace: str) -> dict:
    url = (f"{EUROSTAT_BASE}?format=JSON&sex=T&wstatus=SAL&worktime=FT&age=Y_GE15&nace_r2={nace}"
           + "".join(f"&geo={c}" for c in EUROSTAT_COUNTRIES))
    return fetch_json(url, dest=RAW / SOURCE_ID / f"lfsa_ewhun2_{nace}.json"), url


def run() -> None:
    banner(SOURCE_ID, NAME)

    doc, url_j = _fetch_eurostat("J")
    rows_j = list(jsonstat_rows(doc))

    # jsonstat_rows() doesn't surface doc["status"] (the reliability-flag
    # sparse map) — rebuild the same linear-index math it uses internally
    # so the 'u' flag can be attached to the right row, rather than
    # modifying the shared helper for this one file's need.
    dims = doc["id"]
    sizes = doc["size"]
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    cats = []
    for d in dims:
        index = doc["dimension"][d]["category"]["index"]
        keys = sorted(index, key=lambda k: index[k]) if isinstance(index, dict) else list(index)
        cats.append(keys)
    status_map = doc.get("status", {})

    def flag_for(row: dict) -> str | None:
        idx = 0
        for i, d in enumerate(dims):
            idx += cats[i].index(row[d]) * strides[i]
        return status_map.get(str(idx))

    by_country: dict[str, dict] = {}
    used_nace: dict[str, str] = {}
    for c in EUROSTAT_COUNTRIES:
        c_rows = [r for r in rows_j if r["geo"] == c]
        used_nace[c] = "J"
        if not c_rows:
            # NACE J empty for this country — fall back to TOTAL, fetched
            # only if actually needed (not pre-fetched for every country).
            doc_t, url_t = _fetch_eurostat("TOTAL")
            c_rows = [r for r in jsonstat_rows(doc_t) if r["geo"] == c]
            used_nace[c] = "TOTAL"
        by_year = {}
        for r in c_rows:
            by_year[r["time"]] = {"usual_weekly_hours": r["_value"], "reliability_flag": flag_for(r)}
        by_country[c] = {
            "by_year": by_year,
            "nace_r2_used": used_nace[c],
            "source": "eurostat_lfsa_ewhun2",
        }
        latest_year = max(by_year) if by_year else None
        log(f"    {c} (NACE {used_nace[c]}): {len(by_year)} years, latest {latest_year}: "
            f"{by_year.get(latest_year)}")

    # --- Canada: StatCan WDS, a different source family ---
    body = [{"productId": STATCAN_PID, "coordinate": STATCAN_COORD, "latestN": 10}]
    ca_dest = RAW / SOURCE_ID / "statcan_14100043.json"
    ca_dest.parent.mkdir(parents=True, exist_ok=True)
    if ca_dest.exists() and ca_dest.stat().st_size > 0:
        log(f"    cached  {ca_dest.relative_to(ca_dest.parents[3])}")
        import json
        ca_raw = json.loads(ca_dest.read_text(encoding="utf-8"))
    else:
        import json
        raw_bytes = fetch(STATCAN_URL, method="POST", json_body=body,
                           headers={"Content-Type": "application/json"}, cache=False)
        ca_dest.write_bytes(raw_bytes)
        ca_raw = json.loads(raw_bytes)

    ca_points = ca_raw[0]["object"]["vectorDataPoint"]
    ca_by_year = {}
    for p in ca_points:
        year = p["refPer"][:4]
        ca_by_year[year] = {"usual_weekly_hours": p["value"], "reliability_flag": None}
    by_country["CA"] = {
        "by_year": ca_by_year,
        "source": "statcan_wds_14100043",
        "vector_id": STATCAN_VECTOR,
        "concept_note": "Average usual hours, main job, full-time employment, both sexes, 15+ — "
                        "matches Job Bank's own 'usual hours, not counting overtime' basis.",
    }
    ca_latest = max(ca_by_year) if ca_by_year else None
    log(f"    CA (StatCan): {len(ca_by_year)} years, latest {ca_latest}: {ca_by_year.get(ca_latest)}")

    total_rows = sum(len(v["by_year"]) for v in by_country.values())

    write_processed(
        SOURCE_ID,
        {"countries": by_country},
        meta={
            "unit": "usual hours worked per week, full-time employees",
            "confidence": "official",
            "eurostat_countries": EUROSTAT_COUNTRIES,
            "eurostat_scope": "sex=T, wstatus=SAL (employees), worktime=FT, age=Y_GE15 (15+, no upper "
                "bound). nace_r2=J (Information and communication) where populated; TOTAL (all "
                "activities) where a country has no J-sector series — see each country's own "
                "nace_r2_used field, never silently blended.",
            "reliability_flag_note": "Eurostat's own 'u' (low reliability) or other status flags, "
                "carried through per year where present. null means the source published no flag for "
                "that cell, not that the flag was checked and found clean.",
            "canada_note": "No EU cross exists for Canada — sourced separately from Statistics "
                "Canada's own Labour Force Survey (table 14-10-0043-01), matched to Job Bank's own "
                "'usual hours, not counting overtime' wage concept.",
            "usage_rule": "Never use a flat 2080 hours/year (the US 40x52 convention) for any other "
                "country in this spine — Denmark's own usual hours (~38/week) would be overstated by "
                "roughly 7% under that assumption. See scripts/normalise.py.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[url_j, STATCAN_URL],
        license_note="Eurostat re-use policy — free re-use with attribution (Commission Decision "
                      "2011/833/EU), for DK/NL/IE. Statistics Canada Open Government Licence - Canada "
                      "2.0, for CA. Cite: Eurostat, lfsa_ewhun2; Statistics Canada, table 14-10-0043-01.",
        redistribution="processed derivative only — raw payloads cached under data/raw/hours_worked/ "
                        "but that directory is gitignored, so this repo does not redistribute them. "
                        "Only the derived data/processed/hours_worked.json is committed.",
        transforms=[
            "Fetched Eurostat lfsa_ewhun2 (JSON-stat 2.0) for DK/NL/IE, NACE J, falling back to TOTAL "
            "per-country where J returned no rows for that country.",
            "Independently rebuilt the JSON-stat linear-index math (matching _common.jsonstat_rows() "
            "internally) to look up each row's reliability flag from doc['status'] — that shared "
            "helper does not surface status flags, since most sources using it don't need them.",
            "Fetched StatCan WDS table 14-10-0043-01 at a specific, hand-identified coordinate "
            "(Canada / Average usual hours / Main job / Full-time / Total-Gender / 15+) via "
            "getDataFromCubePidCoordAndLatestNPeriods.",
            "No smoothing, no interpolation. Values kept exactly as published, per year, per country.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=total_rows,
        coverage="DK/NL/IE (Eurostat) + CA (StatCan) — 4 of this spine's hourly-wage countries",
        notes="Denmark, Ireland and Canada also have LONGRP/SES06/Job-Bank-employee-group filters of "
              "their own (see each salary_*.json's own meta) — this file's hours figures use the "
              "closest available full-time, all-industries-or-NACE-J cut, not a filter-matched "
              "population identical to each wage source's own. Documented, not silently assumed exact.",
    )


if __name__ == "__main__":
    main_guard(run)
