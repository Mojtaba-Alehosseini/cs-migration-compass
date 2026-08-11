"""ONS ASHE Table 14 -> UK IT-occupation wage distribution (SOC 2020, 4-digit).

Table 14.7 ("Annual pay - Gross") is the annual, UK-wide, all-employee cut of
the Annual Survey of Hours and Earnings, broken out by 4-digit SOC 2020 unit
group. It ships as a zip of paired workbooks: an "a" file (median, mean, job
counts, percentiles 10-90) and a "b" file with the same row layout, holding
the coefficient of variation for every one of those figures — a published
quality measure, kept rather than discarded.

Verified against the live 2025-provisional file (not assumed): the download
path still says "soc2010" (ONS kept the old URL slug for continuity) but the
workbook titles and the "All" sheet both say "Occupation SOC20 (4)" and the
row for code 2134 reads 360 (thousand jobs) / GBP 55,587 median — matching
this package's brief exactly. This is genuinely SOC 2020, not a stale SOC2010
cut under a misleading path.

This vintage is PROVISIONAL. ONS's own notes flag a data-quality issue for
occupation 3312 (police officers) in this release, unrelated to the IT codes
here, but it is a reminder that "provisional" is a real, load-bearing status
and this pipeline records it rather than presenting the figures as final.
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_uk"
NAME = "ONS ASHE Table 14.7 — Annual pay (Gross), IT occupations, SOC 2020 4-digit"

ZIP_URL = (
    "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/"
    "earningsandworkinghours/datasets/occupation4digitsoc2010ashetable14/"
    "2025provisional/ashetable142025provisional.zip"
)
VALUES_ENTRY = "ashetable142025provisional/PROV - Occupation SOC20 (4) Table 14.7a   Annual pay - Gross 2025.xlsx"
CV_ENTRY = "ashetable142025provisional/PROV - Occupation SOC20 (4) Table 14.7b   Annual pay - Gross 2025 CV.xlsx"

# Column order verified against the live "All" sheet, header row 5 (1-indexed).
COLUMNS = [
    "description", "code", "jobs_thousand", "median", "median_pct_change",
    "mean", "mean_pct_change", "p10", "p20", "p25", "p30", "p40", "p60", "p70", "p75", "p80", "p90",
]
HEADER_ROW_IDX = 4  # 0-indexed
DATA_START_IDX = 5

# 2134 is the target (Programmers and software development professionals);
# 2133/2135/2136/2137 are its IT-professional siblings and 1137 the manager
# grade above them. Sourced from the work order, cross-checked row-for-row
# against the live file below.
TARGET_CODES = ["1137", "2133", "2134", "2135", "2136", "2137"]


def _num(v):
    """ONS marks suppressed cells 'x' (CV>20%, unreliable) and disclosive ones
    '..'. Both become null — never a guessed number, never a zero."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if s in ("x", "..", "", "-", "."):
        return None
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def _read_sheet(zf: zipfile.ZipFile, entry: str) -> dict[str, dict]:
    with zf.open(entry) as f:
        wb = openpyxl.load_workbook(f, data_only=True, read_only=True)
        ws = wb["All"]
        rows = list(ws.iter_rows(values_only=True))
    header = rows[HEADER_ROW_IDX]
    assert header[1] == "Code", f"unexpected header at row {HEADER_ROW_IDX}: {header[:4]}"
    out: dict[str, dict] = {}
    for row in rows[DATA_START_IDX:]:
        code = str(row[1]).strip() if row and row[1] is not None else ""
        if code not in TARGET_CODES:
            continue
        out[code] = {col: (row[i] if col in ("description",) else _num(row[i]))
                     for i, col in enumerate(COLUMNS)}
    return out


def run() -> None:
    banner(SOURCE_ID, NAME)

    zip_bytes = fetch(ZIP_URL, dest=RAW / SOURCE_ID / "ashetable142025provisional.zip")
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))

    values = _read_sheet(zf, VALUES_ENTRY)
    cvs = _read_sheet(zf, CV_ENTRY)

    missing = [c for c in TARGET_CODES if c not in values]
    if missing:
        log(f"    ! codes not found in the live file: {missing}")

    occupations = {}
    for code in TARGET_CODES:
        v = values.get(code)
        if not v:
            continue
        cv = cvs.get(code, {})
        # Every pay figure carries its own unit (GBP per year) in its field
        # name — see src_salary_se.py's comment on DISPERSION_CONTENTS for
        # why: a bare "median" that relies on a sibling meta string for its
        # unit is exactly the "hourly_mean_usd" mistake this package fixed.
        occupations[code] = {
            "title": v["description"].strip() if isinstance(v["description"], str) else v["description"],
            "jobs_thousand": v["jobs_thousand"],
            "mean_gbp_year": v["mean"], "median_gbp_year": v["median"],
            "p10_gbp_year": v["p10"], "p25_gbp_year": v["p25"], "p75_gbp_year": v["p75"], "p90_gbp_year": v["p90"],
            "p20_gbp_year": v["p20"], "p30_gbp_year": v["p30"], "p40_gbp_year": v["p40"],
            "p60_gbp_year": v["p60"], "p70_gbp_year": v["p70"], "p80_gbp_year": v["p80"],
            "mean_pct_change_yoy": v["mean_pct_change"], "median_pct_change_yoy": v["median_pct_change"],
            "coefficient_of_variation_pct": {
                "jobs_thousand": cv.get("jobs_thousand"), "mean": cv.get("mean"), "median": cv.get("median"),
                "p10": cv.get("p10"), "p25": cv.get("p25"), "p75": cv.get("p75"), "p90": cv.get("p90"),
            },
        }

    log(f"    {len(occupations)}/{len(TARGET_CODES)} target codes found")
    t = occupations.get("2134")
    if t:
        log(f"    2134 ({t['title']}): {t['jobs_thousand']}k jobs, median GBP {t['median_gbp_year']}, "
            f"CV {t['coefficient_of_variation_pct']['median']}%")

    write_processed(
        SOURCE_ID,
        {"occupations": occupations},
        meta={
            "occupation_family": "SOC 2020 minor group 213 (Information technology professionals) "
                "+ 1137 (IT directors)",
            "primary_code": "2134",
            "classification": "SOC 2020, 4-digit unit group",
            "unit": "GBP per year, gross, all employee jobs (full-time + part-time), UK-wide",
            "release": "ASHE 2025 PROVISIONAL (released 2025-10-23) — revised 2025 data follows "
                "Oct/Nov 2026. Provisional is a real status, not a formality: occupation 3312 "
                "(unrelated to these codes) was suppressed in this exact vintage for a data-quality "
                "issue, which is the kind of thing 'provisional' exists to catch.",
            "confidence": "official",
            "level": "country (UK-wide; ASHE Table 14 carries no sub-national breakdown — Table 15 "
                "does regional x occupation but was not in scope for this package)",
            "measures": "jobs count (thousand), mean/median/percentiles 10/20/25/30/40/60/70/75/80/90 "
                "(each field name carries its own _gbp_year unit), year-on-year percent change for "
                "mean and median, and the coefficient of variation for jobs/mean/median/p10/p25/p75/"
                "p90 from the paired CV workbook — a published precision measure, not derived here.",
            "why_it_matters": (
                "The UK is one of three countries (with Sweden and the US) reaching a genuine 4-digit "
                "occupation code with an official wage distribution, and its job-count column is the "
                "UK's only official headcount-by-IT-occupation figure on this site."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[ZIP_URL,
              "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/"
              "datasets/occupation4digitsoc2010ashetable14"],
        license_note="Open Government Licence v3.0. Cite: Office for National Statistics (ONS), "
                      "Annual Survey of Hours and Earnings (ASHE), Table 14.",
        redistribution="processed derivative only — the raw 11 MB ASHE zip is cached under "
                        "data/raw/salary_uk/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw download (OGL v3.0 would permit it; the repo simply "
                        "doesn't). Only the derived data/processed/salary_uk.json is committed.",
        transforms=[
            "Downloaded the 2025-provisional ASHE Table 14 zip and extracted the paired 14.7 "
            "(Annual pay - Gross) workbooks: 'a' (values) and 'b' (coefficients of variation).",
            "Read the 'All' sheet (both sexes, full-time + part-time combined) of each.",
            "Kept rows for SOC 2020 codes 1137, 2133-2137 verbatim: description, job count, mean, "
            "median, the full published percentile set, year-on-year % change, and CV.",
            "ONS's own suppression markers ('x' = CV>20% unreliable, '..' = disclosive) become null "
            "— never a guessed number.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(occupations),
        coverage=f"{len(occupations)}/{len(TARGET_CODES)} target SOC 2020 codes, UK-wide, 2025 provisional",
        status="ok" if occupations else "failed",
        notes="2025 data is PROVISIONAL; the revised vintage follows Oct/Nov 2026 and should replace this.",
    )


if __name__ == "__main__":
    main_guard(run)
