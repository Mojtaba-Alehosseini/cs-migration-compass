"""ATO Taxation Statistics Table 15A -> Australian software-occupation income.

The deepest occupation granularity in this entire salary spine — 6-digit
ANZSCO — but the shallowest distribution: mean and median only, no
percentiles at all. Checked directly: ABS's Employee Earnings and Hours
(EEH, 6306.0) publishes 4-digit ANZSCO with means and 1-digit with
percentiles, and no EEH dataflow exists on data.api.abs.gov.au to combine
the two — so there is no way to get an AU percentile at this occupation
depth from any live source. This pipeline does not synthesise one from a
mean and a median; every AU occupation record below carries
`distribution: "central-tendency-only"` so downstream consumers (package 9's
estimator, specifically) degrade instead of guessing a spread that was
never measured.

Two measures exist per occupation, and they are NOT the same thing —
recorded separately, matching this project's existing rule that survey
earnings and advertised pay (and, here, taxable income and wage income)
never share a field:

  - "Average/median salary or wage income" — gross employment earnings,
    the directly comparable figure to what every other country in this
    spine measures.
  - "Average/median taxable income" — assessable income after allowable
    deductions, across ALL income sources (not just wages: investment
    income, etc., minus deductions). This package's work order quotes
    148,516/134,370 for 261313, which is the TAXABLE income pair, not the
    salary-or-wage pair (135,788/132,758) — both are kept, both labelled by
    their real ATO column name, and the wage-income figure is the one
    treated as primary for cross-country comparison.

data.gov.au migrated its dataset platform since this project's earlier
sources were catalogued; the old CKAN `/api/3/action/package_show` endpoint
now 404s. The working path is the human-facing `/data/dataset/<slug>` page,
scraped for its direct-download resource link — recorded here because a
future session hitting the same 404 should not assume the whole domain is
blocked (unlike bls.gov, which genuinely is).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_au"
NAME = "ATO Taxation Statistics 2023-24, Table 15A — income by 6-digit ANZSCO occupation"

DATASET_PAGE = "https://data.gov.au/data/dataset/taxation-statistics-2023-24"
XLSX_URL = ("https://data.gov.au/data/dataset/faea4485-f407-457d-97f8-3f0822ccd654/resource/"
            "3286e287-ee87-4be4-87b2-56c5c6602009/download/ts24individual15occupationsex.xlsx")

# ANZSCO unit group 2613 "Software and applications programmers" — the whole
# 6-digit family, confirmed against the live workbook, not guessed.
TARGET_CODES = ["261311", "261312", "261313", "261314", "261315", "261316", "261317"]
PRIMARY_CODE = "261313"  # Software engineer


def run() -> None:
    banner(SOURCE_ID, NAME)

    raw = fetch(XLSX_URL, dest=RAW / SOURCE_ID / "ts24individual15occupationsex.xlsx")
    wb = openpyxl.load_workbook(__import__("io").BytesIO(raw), data_only=True, read_only=True)
    ws = wb["Table 15A"]
    rows = list(ws.iter_rows(values_only=True))

    occupations: dict[str, dict] = {}
    for row in rows[2:]:
        if not row or not row[1] or row[2] != "Total":
            continue
        m = re.match(r"(\d{6})\s+(.*)", str(row[1]))
        if not m or m.group(1) not in TARGET_CODES:
            continue
        code, title = m.group(1), m.group(2)
        occupations[code] = {
            "title": title,
            "anzsco_unit_group": str(row[0]),
            "n_individuals": row[3],
            "distribution": "central-tendency-only",
            "taxable_income": {"mean_aud_year": row[4], "median_aud_year": row[5]},
            "salary_or_wage_income": {"mean_aud_year": row[6], "median_aud_year": row[7]},
            "total_income": {"mean_aud_year": row[8], "median_aud_year": row[9]},
        }

    log(f"    {len(occupations)}/{len(TARGET_CODES)} target ANZSCO codes found")
    t = occupations.get(PRIMARY_CODE)
    if t:
        log(f"    {PRIMARY_CODE} ({t['title']}): N={t['n_individuals']}, "
            f"wage mean/median={t['salary_or_wage_income']}, "
            f"taxable mean/median={t['taxable_income']}")

    write_processed(
        SOURCE_ID,
        {"occupations": occupations},
        meta={
            "occupation_family": "ANZSCO unit group 2613 — Software and applications programmers",
            "primary_code": PRIMARY_CODE,
            "classification": "ANZSCO 2021, 6-digit occupation — the deepest granularity in this "
                "salary spine",
            "unit": "AUD per year (annual income, 2023-24 income year)",
            "measures": "Three DIFFERENT income concepts per occupation, never to be blended: "
                "salary_or_wage_income (gross employment earnings — the primary, cross-country-"
                "comparable figure), taxable_income (assessable income after deductions, across all "
                "income sources, not wages alone — this is what the work order's own reference figures "
                "cite), and total_income (before deductions, all sources). Mean and median only for "
                "each; no percentiles exist at this occupation depth from any live AU source — see "
                "module docstring. distribution is explicitly 'central-tendency-only' on every record.",
            "confidence": "official",
            "level": "country (Australia)",
            "year": "2023-24 income year",
            "crosswalk_hazard": (
                "Not yet checked against ISCO-08 4-digit definitions the way SSYK 2514 was in package "
                "7 — ANZSCO's own divergence from ISCO-08, if any, is unverified here. ANZSCO reaches "
                "6 digits, one finer than ISCO-08's 4, so any mapping is necessarily many-to-one or "
                "requires picking a specific 6-digit code as 'the' ISCO-08 unit's representative."
            ),
            "why_it_matters": "The deepest occupation granularity of the fifteen countries (6-digit "
                "ANZSCO splits 'software developer' into engineer/programmer/tester/security/devops/"
                "pentester), but with no percentile spread at all — the clearest real example of why "
                "package 9's estimator needs a distribution-quality flag, not just a distribution.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[XLSX_URL, DATASET_PAGE],
        license_note="CC BY 2.5 AU. Cite: Australian Taxation Office (ATO), Taxation statistics 2023-24, "
                      "Table 15A, via data.gov.au.",
        redistribution="processed derivative only — the raw 700 KB ATO workbook is cached under "
                        "data/raw/salary_au/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw download (CC BY 2.5 AU would permit it; the repo simply "
                        "doesn't). Only the derived data/processed/salary_au.json is committed.",
        transforms=[
            "Downloaded Table 15A (Average and median taxable income, salary or wages, and total "
            "income by occupation and sex) from the 2023-24 Taxation Statistics workbook.",
            f"Parsed all {len(TARGET_CODES)} 6-digit ANZSCO codes under unit group 2613 (Software and "
            "applications programmers), Sex='Total' rows only.",
            "Kept N, and mean/median for all three of taxable income, salary-or-wage income and total "
            "income, verbatim, under separate never-blended keys. No percentiles exist in this table.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(occupations) * 7,
        coverage=f"{len(occupations)}/{len(TARGET_CODES)} 6-digit ANZSCO codes, Australia, 2023-24 "
                 "income year",
        status="ok" if occupations else "failed",
        notes="Mean/median only — no percentile data exists for AU at this occupation depth from any "
              "live source (checked: ABS EEH 6306.0 has means at 4-digit and percentiles only at "
              "1-digit, and no EEH dataflow exists on data.api.abs.gov.au to bridge them).",
    )


if __name__ == "__main__":
    main_guard(run)
