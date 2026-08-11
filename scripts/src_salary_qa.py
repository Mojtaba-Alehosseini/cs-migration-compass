"""Qatar Planning and Statistics Authority (via data.gov.qa) -> Gulf wage series.

This is the source package 7 corrected the site's copy for: Explore's Jobs
theme used to say "the Gulf has no series", which was wrong — Qatar
publishes one. This script is that correction's payoff: a real,
CC BY 4.0, ISCO major-group-2 ("Professionals") wage series, 2020-2023, by
sex, from data.gov.qa dataset
"workers-in-paid-employment-15-years-and-above-and-monthly-average-wage-q1".

Occupation depth is ISCO MAJOR GROUP ONLY (1-digit-equivalent) — "Professionals"
covers every professional occupation, not IT specifically, the same caveat
Ireland's SES06 carries. No finer occupation breakdown exists in this
dataset; the site must not present this as an IT-specific figure.

No sex-combined ("Total") row exists in the source — only Males and Females
separately. Both are kept, verbatim; no population-weighted average is
computed here, because that would be a real derived number the source does
not itself publish, and this pipeline's rule is that derivations happen
downstream, visibly, from committed inputs (see build_site_data.py's own
convention: ship the inputs, compute defaults, never bake in an uncited
blend).

Corroborated against ILOSTAT flow DF_EAR_EMTA_SEX_OCU_NB (verified live,
QAT filter, real CSV rows returned) — cited in provenance as a cross-check
source, not re-parsed into this file's own data, to keep one clear
provenance chain per number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_qa"
NAME = "Qatar Planning and Statistics Authority — wages by ISCO major group, via data.gov.qa"
DATASET_SLUG = "workers-in-paid-employment-15-years-and-above-and-monthly-average-wage-q1"
RECORDS_URL = (f"https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/{DATASET_SLUG}/records"
               "?limit=100")  # dataset has 72 rows total; OpenDataSoft defaults to 10 without this
ILOSTAT_CORROBORATION_URL = (
    "https://sdmx.ilo.org/rest/data/ILO,DF_EAR_EMTA_SEX_OCU_NB,1.0/QAT.......?startPeriod=2018"
)

TARGET_OCCUPATION = "Professionals"  # ISCO-08 major group 2


def run() -> None:
    banner(SOURCE_ID, NAME)

    dest = RAW / SOURCE_ID / "records.json"
    raw = fetch(RECORDS_URL, dest=dest, headers={"Accept": "application/json"})
    doc = json.loads(raw)
    records = doc.get("results", [])
    if doc.get("total_count") != len(records):
        log(f"    ! total_count={doc.get('total_count')} but got {len(records)} records — "
            "the API paginates past the default limit; re-check the ?limit= parameter")

    by_year_sex: dict[str, dict] = {}
    for rec in records:
        if rec.get("occupation") != TARGET_OCCUPATION:
            continue
        year, sex = rec["year"], rec["gender"]
        by_year_sex.setdefault(year, {})[sex] = {
            "paid_employment_workers": rec["paid_employment_workers"],
            "monthly_average_wage_qar": rec["monthly_average_wage_qr"],
        }

    years = sorted(by_year_sex)
    log(f"    {len(years)} years x up to 2 sexes for '{TARGET_OCCUPATION}': {years}")
    if years:
        log(f"    {years[-1]}: {by_year_sex[years[-1]]}")

    out = {
        "occupations": {
            "isco08_major:2": {
                "title": TARGET_OCCUPATION,
                "scope": "ISCO-08 major group 2 — NOT ICT-specific, see module docstring",
                "by_year": by_year_sex,
            },
        },
    }

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "ISCO-08 major groups only (1-digit-equivalent) — this dataset's "
                "finest occupation breakdown",
            "primary_code": "isco08_major:2",
            "primary_label": TARGET_OCCUPATION,
            "classification": "ISCO-08 major group (Qatar's PSA publishes 9 major groups; no finer "
                "occupation code is exposed by this dataset)",
            "unit": "QAR per month (monthly_average_wage_qar); paid_employment_workers is a headcount",
            "confidence": "official",
            "level": "country (Qatar)",
            "years": years,
            "sex_note": "Source publishes Males and Females separately; no combined figure exists and "
                "none is computed here — see module docstring.",
            "crosswalk_hazard": (
                "'Professionals' is ISCO major group 2 in full — every professional occupation, not "
                "IT specifically. This is the site's ONLY Gulf wage series (the UAE has none since "
                "2009 — see salary_ae), and the copy correction in package 7 depends on this file "
                "existing; but it must never be presented as a software-developer-specific figure."
            ),
            "why_it_matters": (
                "The wage series Explore's Jobs theme now correctly says exists for the Gulf (package "
                "7 fixed the copy that used to claim otherwise). This is that series, finally wired to "
                "real data rather than just a corrected sentence."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[RECORDS_URL, ILOSTAT_CORROBORATION_URL],
        license_note="CC BY 4.0 (data.gov.qa open data licence). Cite: Qatar Planning and Statistics "
                      "Authority (PSA), via data.gov.qa.",
        redistribution="processed derivative only — the raw OpenDataSoft JSON payload is cached under "
                        "data/raw/salary_qa/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw source (CC BY 4.0 would permit it; the repo simply "
                        "doesn't). Only the derived data/processed/salary_qa.json is committed.",
        transforms=[
            "Fetched all records from the data.gov.qa OpenDataSoft dataset and kept only the "
            "'Professionals' (ISCO major group 2) rows, both sexes, 2020-2023.",
            "Kept paid-employment headcount and monthly average wage (QAR) verbatim, per sex, per "
            "year — no total/blended figure computed.",
            "Corroborated against ILOSTAT flow DF_EAR_EMTA_SEX_OCU_NB (verified live, QAT filter "
            "returns real rows) — cited in provenance, not re-parsed into this file's data.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=sum(len(v) for v in by_year_sex.values()),
        coverage=f"1 ISCO major group x 2 sexes x {len(years)} years, Qatar only",
        status="ok" if years else "failed",
        notes="Major-group depth only — the finest occupation breakdown data.gov.qa publishes for "
              "this indicator. Not IT-specific.",
    )


if __name__ == "__main__":
    main_guard(run)
