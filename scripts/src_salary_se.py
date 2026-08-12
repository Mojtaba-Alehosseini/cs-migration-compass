"""SCB (Statistics Sweden) PxWeb API -> Swedish ICT-occupation wage dispersion.

The reference implementation of the four-source salary spine: CC0, 4-digit SSYK
2012, and the only one of the four with published confidence intervals. Two
tables, both under AM0110A (the National Mediation Office's wage-structure
statistics):

  LoneSpridSektYrk4AN  mean/median/P10/P25/P75/P90 + 95% CIs, by occupation
  LonYrkeAlder4AN      monthly salary + employee count, by occupation x age band

The age x occupation cross is one of only four official occupation x age
breakdowns across the fifteen countries this site covers, which is why it is
pulled here even though nothing in this package renders it yet.

Occupation scope is deliberately narrow: SSYK 2012's "251 Software and
applications developers and analysts" group (2511-2519), not all 432 SSYK
occupations SCB publishes. SSYK's own unit-group labels are pulled from the
API and stored verbatim, because SSYK's fourth digit does NOT reliably track
ISCO-08's fourth digit at the same code point -- see scripts/crosswalk.py and
data/occupations.json, where 2514 ("System testers and test managers", not
"Applications programmers") is the documented example.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    RAW, banner, fetch, jsonstat_rows, log, main_guard, record_provenance,
    write_processed,
)
import json

SOURCE_ID = "salary_se"
NAME = "SCB wage structure statistics — ICT occupations (SSYK 2012)"
BASE = "https://api.scb.se/OV0104/v1/doris/en/ssd/AM/AM0110/AM0110A"

# SSYK 2012 "251 Software and applications developers and analysts". Labels are
# not hardcoded here beyond this comment -- the API's own occupation labels are
# what gets stored, so a wrong guess here cannot silently mislabel the output.
SSYK_CODES = ["2511", "2512", "2513", "2514", "2515", "2516", "2519"]
YEARS = ["2023", "2024", "2025"]

# Every measure field name carries its own unit (SEK per month) — no field is
# named just "median" with the unit left to a sibling meta string. That
# detached-unit pattern is exactly the bug this package found and fixed in
# BLS OEWS's old "hourly_mean_usd" (which held an annual figure); repeating
# it here, in a package built specifically to be joined across three other
# currencies and periods, would be the same mistake with worse consequences.
# CI fields are named _margin because SCB returns a single scalar per measure
# (e.g. median 53,500 with median_ci95_margin_sek_month 880) — a +/- half
# width around the point estimate, not an interval's lower/upper bounds.
DISPERSION_TABLE = "LoneSpridSektYrk4AN"
DISPERSION_CONTENTS = {
    "000007CD": "mean_sek_month", "000007CE": "median_sek_month",
    "000007CF": "p10_sek_month", "000007CG": "p25_sek_month",
    "000007CH": "p75_sek_month", "000007CI": "p90_sek_month",
    "000007CJ": "mean_ci95_margin_sek_month", "000007CK": "median_ci95_margin_sek_month",
    "000007CL": "p10_ci95_margin_sek_month", "000007CM": "p25_ci95_margin_sek_month",
    "000007CN": "p75_ci95_margin_sek_month", "000007CO": "p90_ci95_margin_sek_month",
}

AGE_TABLE = "LonYrkeAlder4AN"
AGE_CONTENTS = {"000007BN": "monthly_salary_sek", "000007BK": "n_employees"}
AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65-66", "65-68", "tot"]


def _query(table: str, occupations: list[str], contents: dict[str, str], extra: list[dict] | None = None) -> dict:
    # Sektor="0" is "all sectors" (whole economy) — verified live against
    # this table's own dimension metadata (package 9 check): codes 1-3 are
    # public sector (1 central government, 2 primary municipalities, 3
    # county council), 4-5 are private sector (4 manual workers, 5
    # non-manual workers). This was already the intended scope — package 9's
    # work order confirmed table AM0110A is correct (it already was) and
    # clarified that "private sector" is this Sektor dimension, not a
    # different table; it did not instruct switching to the private-only
    # codes, unlike its explicit instruction for Finland (see
    # src_salary_fi.py) — kept as "0" here, deliberately, not silently.
    body = {
        "query": [
            {"code": "Sektor", "selection": {"filter": "item", "values": ["0"]}},
            {"code": "Yrke2012", "selection": {"filter": "item", "values": occupations}},
            {"code": "Kon", "selection": {"filter": "item", "values": ["1+2"]}},
            *(extra or []),
            {"code": "ContentsCode", "selection": {"filter": "item", "values": list(contents)}},
            {"code": "Tid", "selection": {"filter": "item", "values": YEARS}},
        ],
        "response": {"format": "json-stat2"},
    }
    raw = fetch(f"{BASE}/{table}", dest=RAW / SOURCE_ID / f"{table}.json", method="POST",
                json_body=body, headers={"Content-Type": "application/json"})
    return json.loads(raw)


def run() -> None:
    banner(SOURCE_ID, NAME)

    occ_titles: dict[str, str] = {}

    # --- dispersion: mean/median/percentiles + CIs, by occupation and year ---
    disp_doc = _query(DISPERSION_TABLE, SSYK_CODES, DISPERSION_CONTENTS)
    occ_titles.update(disp_doc["dimension"]["Yrke2012"]["category"]["label"])
    dispersion: dict[str, dict[str, dict]] = {c: {} for c in SSYK_CODES}
    disp_rows = 0
    for row in jsonstat_rows(disp_doc):
        code, year, field, val = row["Yrke2012"], row["Tid"], DISPERSION_CONTENTS[row["ContentsCode"]], row["_value"]
        dispersion.setdefault(code, {}).setdefault(year, {})[field] = val
        disp_rows += 1

    # --- age x occupation: monthly salary + N, by occupation, age band and year ---
    age_doc = _query(AGE_TABLE, SSYK_CODES, AGE_CONTENTS,
                      extra=[{"code": "Alder", "selection": {"filter": "item", "values": AGE_BANDS}}])
    age: dict[str, dict[str, dict[str, dict]]] = {c: {} for c in SSYK_CODES}
    age_rows = 0
    age_bands_seen: set[str] = set()
    for row in jsonstat_rows(age_doc):
        code, year, band = row["Yrke2012"], row["Tid"], row["Alder"]
        field, val = AGE_CONTENTS[row["ContentsCode"]], row["_value"]
        age.setdefault(code, {}).setdefault(year, {}).setdefault(band, {})[field] = val
        age_bands_seen.add(band)
        age_rows += 1

    out = {
        "occupations": {
            code: {
                "title": occ_titles.get(code, code),
                "dispersion_by_year": dispersion.get(code, {}),
                "age_by_year": age.get(code, {}),
            }
            for code in SSYK_CODES
        },
    }

    latest = YEARS[-1]
    n_2512 = ((age.get("2512", {}).get(latest, {}) or {}).get("tot", {}) or {}).get("n_employees")
    log(f"    {disp_rows} dispersion cells, {age_rows} age-cross cells, "
        f"{len(age_bands_seen)} age bands seen: {sorted(age_bands_seen)}")
    log(f"    2512 ({occ_titles.get('2512')}) {latest}: N={n_2512}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "SSYK 2012 group 251 — Software and applications developers and analysts",
            "occupation_codes": {c: occ_titles.get(c, c) for c in SSYK_CODES},
            "primary_code": "2512",
            "classification": "SSYK 2012 (Sweden's national adaptation of ISCO-08)",
            "unit": "SEK per month, gross, all sectors, both sexes",
            "measures": {
                "dispersion_by_year": "mean, median, P10/P25/P75/P90 (each _sek_month) and each "
                    "measure's own 95% CI HALF-WIDTH (each _ci95_margin_sek_month — add/subtract "
                    "from the point estimate, it is not an interval's bounds) — table "
                    "AM0110A/LoneSpridSektYrk4AN",
                "age_by_year": "monthly salary (SEK) and employee count (N) by 7 age bands plus "
                    "total — table AM0110A/LonYrkeAlder4AN. N is sometimes null for small cells "
                    "(e.g. the 18-24 band) — that is SCB's own suppression: jsonstat_rows() drops "
                    "cells the API returns as null rather than inventing a placeholder, so the key "
                    "is simply absent for that band/year, not present-and-null.",
            },
            "confidence": "official",
            "level": "country (Sweden, all sectors combined)",
            "years": YEARS,
            "crosswalk_hazard": (
                "SSYK 2012's fourth digit does not track ISCO-08's fourth digit at the same code "
                "point. 2514 here is 'System testers and test managers', not 'Applications "
                "programmers' (ISCO-08's 2514). Only 2512 has a checked, evidenced 4-digit mapping "
                "— see data/occupations.json."
            ),
            "why_it_matters": (
                "The only source of the four with confidence intervals, and one of only four "
                "official occupation x age crosses across all fifteen countries — the age gradient "
                "package 9 needs."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[f"{BASE}/{DISPERSION_TABLE}", f"{BASE}/{AGE_TABLE}"],
        license_note="CC0 1.0 Universal (SCB adopted CC0 for all open data 2021-07-01; no attribution "
                      "required). Cite: Statistics Sweden (SCB), wage and salary structures, private "
                      "and public sector.",
        redistribution="processed derivative only — the raw PxWeb JSON payloads are cached under "
                        "data/raw/salary_se/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw source (CC0 would permit it; the repo simply doesn't). "
                        "Only the derived data/processed/salary_se.json is committed.",
        transforms=[
            f"Queried SSYK 2012 codes {', '.join(SSYK_CODES)} (group 251, ICT professionals) x all "
            f"sectors x both sexes x {YEARS[0]}-{YEARS[-1]} from two PxWeb tables via POST, "
            "response format json-stat2.",
            "Dispersion table: kept mean, median, P10/P25/P75/P90 and each measure's 95% CI verbatim.",
            "Age table: kept monthly salary and employee count (N) for 7 age bands plus the total, "
            "verbatim, including SCB's own null suppression on small cells.",
            "Occupation titles are the API's own labels, not hand-typed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=disp_rows + age_rows,
        coverage=f"{len(SSYK_CODES)} SSYK occupations x {len(YEARS)} years, Sweden only (no sub-national breakdown in these tables)",
        notes="Reference implementation of the salary spine: CC0, 4-digit, with published confidence intervals.",
    )


if __name__ == "__main__":
    main_guard(run)
