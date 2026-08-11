"""Canada Job Bank Wages open data -> NOC 2021 software-occupation wages, by
economic region.

The only one of the four sources with sub-national granularity: a national
figure plus 84 provincial/economic-region breakouts (85 geographies total),
which matters because this site is city-based, not just country-based. NOC
2021 reaches 5 digits, one more than the other three sources' 4-digit ceiling.

Verified against the live 2025 file, not assumed: wages here are published
PER HOUR (CAD), not per year — the file's own Annual_Wage_Flag is 0 for all
four target occupations, and it is 1 (with an explicit "presented at an
annual rate" comment) for occupations that genuinely are annualised, so this
is Job Bank's own distinction, not a guess. This pipeline keeps the hourly
figure as published and does not annualise it: multiplying by a standard
work-year is an assumption this source does not make, and turning it into
one here would be exactly the kind of invented precision this project's
integrity rules exist to prevent. A consumer that wants an annual figure
should do that conversion visibly, not inherit a silent one.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_ca"
NAME = "Job Bank Wages (Canada) — NOC 2021, software occupations, by economic region"

CSV_URL = (
    "https://open.canada.ca/data/dataset/adad580f-76b0-4502-bd05-20c125de9116/resource/"
    "9da94d63-b178-4a64-aeb3-b6a3bd721ad2/download/"
    "2a71-das-wage2025opendata-esdc-all-19nov2025-vf.csv"
)

# NOC 2021 v1.0, minor group 2123 (Computer, software and Web designers and
# developers), plus 21311 (Computer engineers) from a DIFFERENT minor group
# (2131, Electrical/electronics/computer engineers) — hardware/telecom
# engineering, not software. It is on this list because the work order named
# it as a Canadian sibling code, and its wage figure is genuinely useful, but
# it is not an ICT-professionals occupation and must not be blended into a
# "software developer" comparison with the other three — see
# data/occupations.json's crosswalk entry for 21311 and meta.crosswalk_hazard
# below. Verified against StatCan's own unit-group definitions before
# selection, not guessed from the code number alone:
#   21231 Software engineers and designers        (2123 — software/web)
#   21232 Software developers and programmers      (2123 — software/web)
#   21234 Web developers and programmers           (2123 — software/web)
#   21311 Computer engineers, except the above      (2131 — hardware/telecom engineering)
TARGET_NOCS = ["NOC_21231", "NOC_21232", "NOC_21234", "NOC_21311"]

# Every measure field name carries its own unit (CAD per HOUR — the one
# source of the four not in an annual or monthly period) — see
# src_salary_se.py's comment on DISPERSION_CONTENTS for why a bare "median"
# relying on a sibling meta string for its unit is the mistake to avoid.
WAGE_FIELDS = {
    "Low_Wage_Salaire_Minium": "p10_low_cad_hour",
    "Quartile1_Wage_Salaire_Quartile1": "p25_q1_cad_hour",
    "Median_Wage_Salaire_Median": "median_cad_hour",
    "Quartile3_Wage_Salaire_Quartile3": "p75_q3_cad_hour",
    "High_Wage_Salaire_Maximal": "p90_high_cad_hour",
    "Average_Wage_Salaire_Moyen": "average_cad_hour",
}


def _num(v: str | None) -> float | None:
    if v is None:
        return None
    s = v.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def run() -> None:
    banner(SOURCE_ID, NAME)

    raw = fetch(CSV_URL, dest=RAW / SOURCE_ID / "wages_2025.csv")
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    all_rows = list(reader)
    log(f"    {len(all_rows)} total rows in the file")

    occupations: dict[str, dict] = {}
    noc_title: dict[str, str] = {}
    annual_flag_seen: set[str] = set()

    for noc in TARGET_NOCS:
        rows = [r for r in all_rows if r.get("NOC_CNP") == noc]
        if not rows:
            continue
        noc_title[noc] = rows[0]["NOC_Title_eng"]
        geographies = []
        for r in rows:
            annual_flag_seen.add(r.get("Annual_Wage_Flag_Salaire_annuel", ""))
            geographies.append({
                "province": r.get("prov"),
                "economic_region_code": r.get("ER_Code_Code_RE"),
                "economic_region_name": r.get("ER_Name"),
                "is_national": r.get("ER_Name") == "Canada",
                **{label: _num(r.get(col)) for col, label in WAGE_FIELDS.items()},
                "employees_with_nonwage_benefit_pct": _num(r.get("EmployeesWithNonWageBenefit_Pct")),
                "data_source": r.get("Data_Source_E") or None,
                "reference_period": r.get("Reference_Period") or None,
                "annual_wage_flag": r.get("Annual_Wage_Flag_Salaire_annuel"),
                "suppressed_note": r.get("Wage_Comment_E") or None,
            })
        n_with_median = sum(1 for g in geographies if g["median_cad_hour"] is not None)
        occupations[noc.removeprefix("NOC_")] = {
            "noc_code": noc.removeprefix("NOC_"),
            "title": noc_title[noc],
            "geographies": geographies,
        }
        log(f"    {noc}: {len(geographies)} geographies, {n_with_median} with a published median")

    if annual_flag_seen - {"0"}:
        log(f"    ! unexpected Annual_Wage_Flag values on target NOCs: {annual_flag_seen} "
            "— these occupations were assumed hourly-only; verify before trusting the unit label")

    total_rows = sum(len(o["geographies"]) for o in occupations.values())

    write_processed(
        SOURCE_ID,
        {"occupations": occupations},
        meta={
            "occupation_family": "NOC 2021 v1.0 minor group 2123 (Computer, software and Web "
                "designers and developers: 21231/21232/21234) plus 21311, a DIFFERENT minor group "
                "(2131, Electrical/electronics/computer engineers) — see crosswalk_hazard below.",
            "primary_code": "21231",
            "classification": "NOC 2021 Version 1.0, 5-digit unit group",
            "unit": "CAD per HOUR, not annual — see module docstring. Not converted here.",
            "level": "85 sub-national geographies (provinces/territories + economic regions) "
                "plus 1 national ('Canada') row per occupation — genuinely city-adjacent, unlike "
                "the other three sources in this package.",
            "measures": "low/~P10, Q1/~P25, median, Q3/~P75, high/~P90, and average (each field name "
                "carries its own _cad_hour unit), plus the percent of employees with a non-wage "
                "benefit and which of Labour Force Survey / Small Area Estimation / Census / EI data "
                "underlies each geography's figure.",
            "confidence": "official",
            "coverage_note": "Many economic-region rows are published with null wage fields — Job "
                "Bank's own small-area suppression, kept as null with the original comment in "
                "'suppressed_note', never backfilled from the provincial figure.",
            "crosswalk_hazard": (
                "21311 ('Computer engineers, except software engineers and designers') is hardware/ "
                "telecommunications engineering, not an ICT-professionals occupation — StatCan's own "
                "definition covers 'computer and telecommunications hardware ... mainframe systems ... "
                "fibre-optic networks ... wireless communication networks'. It belongs to NOC minor "
                "group 2131, not 2123 (the software/web group the other three codes share). See "
                "data/occupations.json, which anchors it to isco08:21 (a different branch of the "
                "ISCO-08 tree from the other three codes' isco08:2512/2513) for exactly this reason. "
                "Do not fold its wage figure into a 'software developer' comparison."
            ),
            "why_it_matters": (
                "The only source of the four that is genuinely sub-national. Reaches NOC's 5-digit "
                "unit-group level, one digit finer than the other three sources' 4-digit ceiling."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[CSV_URL,
              "https://open.canada.ca/data/en/dataset/adad580f-76b0-4502-bd05-20c125de9116"],
        license_note="Open Government Licence - Canada 2.0. Cite: Employment and Social Development "
                      "Canada (ESDC) / Job Bank, Wages.",
        redistribution="processed derivative only — the raw 18 MB wages CSV is cached under "
                        "data/raw/salary_ca/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw download (OGL-Canada 2.0 would permit it; the repo "
                        "simply doesn't). Only the derived data/processed/salary_ca.json is committed.",
        transforms=[
            f"Downloaded the 2025 wages CSV ({len(all_rows):,} rows, all NOC 2021 occupations, "
            "all geographies) and filtered to 4 target NOC codes.",
            "Kept every geography row for each target NOC verbatim, including rows where the wage "
            "fields are null because Job Bank suppressed them for small-area reliability — the "
            "geography is kept, not dropped, with the null and Job Bank's own comment intact.",
            "Confirmed via the file's own Annual_Wage_Flag that all four target occupations are "
            "published hourly, not annual; no unit conversion performed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=total_rows,
        coverage=f"{len(occupations)}/{len(TARGET_NOCS)} target NOC codes x up to 86 geographies each",
        status="ok" if occupations else "failed",
    )


if __name__ == "__main__":
    main_guard(run)
