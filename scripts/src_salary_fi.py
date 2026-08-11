"""Tilastokeskus (Statistics Finland) PxWeb API -> Finnish ICT-occupation wages.

Table StatFin/pra/15au ("Earnings of full-time wage and salary earners per
month by sector, occupational group... and sex"). AL2010 occupation 2512 —
AL2010 (Classification of Occupations 2010) is Finland's national adaptation
of ISCO-08, and 2512 carries the same 4-digit numbering as ISCO's "Software
developers" (confirmed against the table's own live label, not assumed).

Unit: EUR per MONTH, full-time earners only — the table is scoped that way at
the source (its own title says "full-time wage and salary earners"), unlike
Sweden/Denmark/Norway/UK/Canada/US which are not restricted to full-time. That
scope difference is real and is recorded in meta rather than smoothed over.

No age or tenure cross exists for Finland in this package: the "pra" table
family's occupation-bearing tables (15au/15ax/15ay/15az) do not cross with
age, and 15aw/15av (which do cross with age) do not carry an occupation
dimension — checked against the live table catalog, not assumed from the
phase-4 plan's summary, which does not list Finland among the age-cross
sources either.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, jsonstat_rows, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_fi"
NAME = "Tilastokeskus (Statistics Finland) — ICT occupation wages, full-time earners (AL2010)"
TABLE_URL = "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/pra/15au.px"

# AL2010 "251 Software and applications developers and analysts".
AL2010_CODES = ["2511", "2512", "2513", "2514", "2519"]

CONTENTS = {
    "koko_psaaja_lkm": "n_employees",
    "koko_psaaja_kans_ka": "mean_eur_month",
    "koko_psaaja_kans_p10": "p10_eur_month",
    "koko_psaaja_kans_med": "median_eur_month",
    "koko_psaaja_kans_p90": "p90_eur_month",
}


def run() -> None:
    banner(SOURCE_ID, NAME)

    body = {
        "query": [
            {"code": "timeperiod_y", "selection": {"filter": "item", "values": ["2024"]}},
            {"code": "sektoriluokitus_7_20230101", "selection": {"filter": "item", "values": ["S0"]}},
            {"code": "ammatti_19_20180101", "selection": {"filter": "item", "values": AL2010_CODES}},
            {"code": "sukupuoli_9_20180101", "selection": {"filter": "item", "values": ["SSS"]}},
            {"code": "contentscode", "selection": {"filter": "item", "values": list(CONTENTS)}},
        ],
        "response": {"format": "json-stat2"},
    }
    dest = RAW / SOURCE_ID / "15au.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log(f"    cached  {dest.relative_to(dest.parents[3])}")
        doc = json.loads(dest.read_text(encoding="utf-8"))
    else:
        raw = fetch(TABLE_URL, method="POST", json_body=body, headers={"Content-Type": "application/json"}, cache=False)
        dest.write_bytes(raw)
        doc = json.loads(raw)

    occ_titles = doc["dimension"]["ammatti_19_20180101"]["category"]["label"]
    year = doc["dimension"]["timeperiod_y"]["category"]["label"]["2024"]

    dispersion: dict[str, dict] = {c: {} for c in AL2010_CODES}
    rows = 0
    for row in jsonstat_rows(doc):
        code = row["ammatti_19_20180101"]
        field = CONTENTS[row["contentscode"]]
        dispersion.setdefault(code, {})[field] = row["_value"]
        rows += 1

    out = {
        "occupations": {
            code: {"title": occ_titles.get(code, code), "year": "2024", "dispersion": dispersion.get(code, {})}
            for code in AL2010_CODES
        },
    }

    log(f"    {rows} dispersion cells across {len(AL2010_CODES)} occupations, year {year}")
    log(f"    2512 ({occ_titles.get('2512')}): {dispersion.get('2512')}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "AL2010 group 251 — Software and applications developers and analysts",
            "occupation_codes": {c: occ_titles.get(c, c) for c in AL2010_CODES},
            "primary_code": "2512",
            "classification": "AL2010 / Classification of Occupations 2010 (Finland's national "
                "adaptation of ISCO-08)",
            "unit": "EUR per month, FULL-TIME wage and salary earners only, all sectors, both sexes. "
                "Scoped to full-time at the source — the other Nordic sources in this package are not.",
            "confidence": "official",
            "level": "country (Finland, all sectors combined)",
            "years": ["2024"],
            "history_caveat": "This table (StatFin/pra/15au) exposes a single reference year (2024) "
                "via the live API; earlier years live in the StatFin_Passiivi archive under separate, "
                "per-year table IDs and were not pulled into this harvester — a single current year is "
                "what the work order accepted as sufficient for this source.",
            "crosswalk_hazard": (
                "Not yet checked against ISCO-08 4-digit definitions the way SSYK 2514 was in package 7 "
                "— AL2010's own divergence from ISCO-08, if any, is unverified here."
            ),
            "why_it_matters": "One of nine countries with genuine occupation-level percentile-family "
                "wage data (N, mean, P10, median, P90).",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[TABLE_URL],
        license_note="CC BY 4.0 (Statistics Finland open data licence). Cite: Statistics Finland "
                      "(Tilastokeskus), table StatFin/pra/15au.",
        redistribution="processed derivative only — the raw json-stat2 payload is cached under "
                        "data/raw/salary_fi/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw source. Only the derived data/processed/salary_fi.json "
                        "is committed.",
        transforms=[
            f"Queried AL2010 codes {', '.join(AL2010_CODES)} (group 251) x all sectors x both sexes x "
            "2024 (the table's sole exposed year) from StatFin/pra/15au via POST, format json-stat2.",
            "Kept N, mean, P10, median, P90 (each for TOTAL earnings, not the narrower 'regular hours' "
            "variant the table also publishes) verbatim.",
            "Occupation titles are the API's own labels, not hand-typed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=rows,
        coverage=f"{len(AL2010_CODES)} AL2010 occupations, single year (2024), Finland only, "
                 "full-time earners only",
        notes="Full-time-only scope is the table's own restriction, not a filter this pipeline chose — "
              "see meta.unit.",
    )


if __name__ == "__main__":
    main_guard(run)
