"""CSO (Central Statistics Office Ireland) PxStat API -> Irish earnings, 1-digit SOC only.

Table SES06. Confirmed directly against the live table's own dimension
labels, not assumed from the work order's summary: the occupation dimension
(C03288V03961) has EXACTLY EIGHT values — "All occupational groups" plus the
eight 1-digit SOC major groups (Managers, Professional, Associate
professional and technical, Administrative and secretarial, Skilled trades,
Caring/leisure/other services, Sales and customer service, and — per the
category list — a further two not printed in the harvest log). There is no
finer occupation breakdown anywhere in this table. "Professional" (code "2")
is the closest available group to software development, and it is not an
ICT-specific figure: it covers every professional occupation Ireland's SOC
recognises — medicine, law, engineering, teaching, science and IT together.

This is the coarsest occupation source in the entire salary spine, coarser
even than Spain's broader age/tenure context or the Gulf's major-group
series. It earns its place anyway: it is Ireland's actual best available
official earnings-by-occupation figure, and the honest answer here is
"1-digit, not IT-specific", not "no data".

Unit: EUR per hour (mean and median), plus mean/median paid weekly hours —
CSO's own four SES06 measures, kept as published.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, jsonstat_rows, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_ie"
NAME = "CSO Ireland — SES06 earnings, 'Professional' 1-digit SOC major group"
TABLE_URL = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/SES06/JSON-stat/2.0/en"

STATISTIC_FIELDS = {
    "SES06C01": "mean_eur_hour",
    "SES06C03": "median_eur_hour",
    "SES06C02": "mean_paid_weekly_hours",
    "SES06C04": "median_paid_weekly_hours",
}
PROFESSIONAL_CODE = "2"  # 1-digit SOC major group "Professional"


def run() -> None:
    banner(SOURCE_ID, NAME)

    dest = RAW / SOURCE_ID / "SES06.json"
    raw = fetch(TABLE_URL, dest=dest)
    doc = json.loads(raw)

    occ_label = doc["dimension"]["C03288V03961"]["category"]["label"][PROFESSIONAL_CODE]
    year_labels = doc["dimension"]["TLIST(A1)"]["category"]["label"]

    by_year: dict[str, dict] = {}
    rows = 0
    for row in jsonstat_rows(doc):
        if row["C03288V03961"] != PROFESSIONAL_CODE:
            continue
        year = row["TLIST(A1)"]
        field = STATISTIC_FIELDS[row["STATISTIC"]]
        by_year.setdefault(year, {})[field] = row["_value"]
        rows += 1

    out = {
        "occupations": {
            "soc1:2": {
                "title": occ_label,
                "scope": "1-digit SOC major group — NOT ICT-specific, see module docstring",
                "by_year": by_year,
            },
        },
    }

    years = sorted(by_year)
    log(f"    {rows} cells across {len(years)} years: {years}")
    log(f"    '{occ_label}' {years[-1] if years else '?'}: {by_year.get(years[-1]) if years else None}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "SOC, 1-digit major groups only — the coarsest occupation depth in "
                "this salary spine",
            "primary_code": "soc1:2",
            "primary_label": occ_label,
            "classification": "UK-derived Standard Occupational Classification, 1-digit major group "
                "(Ireland's SES06 does not publish any finer occupation breakdown)",
            "unit": "EUR per hour (mean, median) and paid weekly hours (mean, median)",
            "confidence": "official",
            "level": "country (Ireland)",
            "years": years,
            "crosswalk_hazard": (
                "'Professional' (SOC major group 2) is not an ICT occupation — it is every "
                "professional occupation Ireland's SOC recognises, medicine/law/engineering/teaching/"
                "science bundled with IT. This cannot honestly reach even the 2-digit isco08:25 "
                "fallback the way most other 2-digit-only entries in this crosswalk can; it needs its "
                "own coarser confidence tier or an explicit 1-digit anchor — see Tier 4."
            ),
            "why_it_matters": "Ireland's actual best available official occupation-level earnings "
                "figure. The honest answer for this country is '1-digit, not IT-specific', which is "
                "what this file records rather than omitting the country entirely.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[TABLE_URL],
        license_note="CC BY 4.0 (CSO Ireland open data licence, PxStat). Cite: Central Statistics "
                      "Office (CSO) Ireland, table SES06.",
        redistribution="processed derivative only — the raw JSON-stat2 payload is cached under "
                        "data/raw/salary_ie/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw source. Only the derived data/processed/salary_ie.json "
                        "is committed.",
        transforms=[
            "Fetched table SES06 in full (JSON-stat 2.0) and kept only the 'Professional' (SOC major "
            "group 2) rows — the closest, but not ICT-specific, occupation cut this table publishes.",
            "Kept mean/median hourly earnings and mean/median paid weekly hours for every year the "
            "table carries (2018, 2022) verbatim.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=rows,
        coverage=f"1 SOC major group x {len(years)} years, Ireland only",
        notes="1-digit SOC only — confirmed against the table's own live dimension, not assumed. No "
              "ICT-specific series exists in Irish official statistics at any finer depth via this table.",
    )


if __name__ == "__main__":
    main_guard(run)
