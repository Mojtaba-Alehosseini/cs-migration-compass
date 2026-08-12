"""SSB (Statistics Norway) API -> Norwegian ICT-occupation wage dispersion.

Two tables, mirroring package 7's Swedish pair exactly:

  11418  mean/median/quartiles/N by STYRK-08 occupation (annual)
  11658  median/mean monthly salary by occupation x 3 age bands (quarterly)

STYRK-08 is Norway's national adaptation of ISCO-08; occupation 2512
"Software developers" is confirmed against the table's own live label.

Unit: NOK per MONTH — table 11418's ContentsCode is literally "Monthly
earnings (NOK)" ("Manedslonn"), the same PAY PERIOD as Sweden's figures
(monthly), just a different currency — not a new period this spine hasn't
seen before. Every field name here carries its own unit for exactly the
reason src_salary_se.py documents.

11658's age bands are coarse (0-39 / 40-54 / 55+, plus an "unspecified"
code) compared to Sweden's seven bands, and its time dimension is quarterly,
not annual — the latest quarter is used. It is still a genuine occupation x
age cross, one of the few in this project.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch_json, jsonstat_rows, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_no"
NAME = "SSB (Statistics Norway) — ICT occupation wage dispersion (STYRK-08)"
BASE = "https://data.ssb.no/api/v0/en/table"

# STYRK-08 "251 Software and applications developers and analysts".
STYRK_CODES = ["2511", "2512", "2513", "2514", "2519"]
YEARS_11418 = ["2021", "2022", "2023", "2024", "2025"]

CONTENTS_11418 = {
    "02": "mean_nok_month", "01": "median_nok_month",
    "051": "p25_nok_month", "061": "p75_nok_month", "10": "n_employees",
}

# 11658 is quarterly; take the most recent quarter available at run time.
AGE_BANDS = ["0-39", "40-54", "55+"]
CONTENTS_11658 = {"MedianMndLonn": "median_nok_month", "GjMdTotal": "mean_nok_month"}


def _query(table: str, body: dict) -> dict:
    dest = RAW / SOURCE_ID / f"{table}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log(f"    cached  {dest.relative_to(dest.parents[3])}")
        import json
        return json.loads(dest.read_text(encoding="utf-8"))
    doc = fetch_json(f"{BASE}/{table}", dest=dest, method="POST", json_body=body,
                      headers={"Content-Type": "application/json"})
    return doc


def _latest_quarter() -> str:
    meta = fetch_json(f"{BASE}/11658", cache=False)
    tid = next(v for v in meta["variables"] if v["code"] == "Tid")
    return tid["values"][-1]


def run() -> None:
    banner(SOURCE_ID, NAME)

    # --- 11418: dispersion by occupation and year ---
    body = {
        "query": [
            {"code": "MaaleMetode", "selection": {"filter": "item", "values": list(CONTENTS_11418)}},
            {"code": "Yrke", "selection": {"filter": "item", "values": STYRK_CODES}},
            {"code": "Sektor", "selection": {"filter": "item", "values": ["ALLE"]}},
            {"code": "Kjonn", "selection": {"filter": "item", "values": ["0"]}},
            {"code": "AvtaltVanlig", "selection": {"filter": "item", "values": ["0"]}},
            {"code": "ContentsCode", "selection": {"filter": "item", "values": ["Manedslonn"]}},
            {"code": "Tid", "selection": {"filter": "item", "values": YEARS_11418}},
        ],
        "response": {"format": "json-stat2"},
    }
    doc = _query("11418", body)
    occ_titles = doc["dimension"]["Yrke"]["category"]["label"]
    dispersion: dict[str, dict[str, dict]] = {c: {} for c in STYRK_CODES}
    disp_rows = 0
    for row in jsonstat_rows(doc):
        code, year, field = row["Yrke"], row["Tid"], CONTENTS_11418[row["MaaleMetode"]]
        dispersion.setdefault(code, {}).setdefault(year, {})[field] = row["_value"]
        disp_rows += 1

    # --- 11658: median/mean monthly salary by occupation x age band, latest quarter ---
    latest_q = _latest_quarter()
    body2 = {
        "query": [
            {"code": "Kjonn", "selection": {"filter": "item", "values": ["0"]}},
            {"code": "Alder", "selection": {"filter": "item", "values": AGE_BANDS}},
            {"code": "Yrke", "selection": {"filter": "item", "values": STYRK_CODES}},
            {"code": "ContentsCode", "selection": {"filter": "item", "values": list(CONTENTS_11658)}},
            {"code": "Tid", "selection": {"filter": "item", "values": [latest_q]}},
        ],
        "response": {"format": "json-stat2"},
    }
    doc2 = _query("11658", body2)
    age: dict[str, dict[str, dict]] = {c: {} for c in STYRK_CODES}
    age_rows = 0
    for row in jsonstat_rows(doc2):
        code, band, field = row["Yrke"], row["Alder"], CONTENTS_11658[row["ContentsCode"]]
        age.setdefault(code, {}).setdefault(band, {})[field] = row["_value"]
        age_rows += 1

    out = {
        "occupations": {
            code: {
                "title": occ_titles.get(code, code),
                "dispersion_by_year": dispersion.get(code, {}),
                "age_at_quarter": {"quarter": latest_q, "bands": age.get(code, {})},
            }
            for code in STYRK_CODES
        },
    }

    latest_y = YEARS_11418[-1]
    log(f"    {disp_rows} dispersion cells, {age_rows} age-cross cells (quarter {latest_q})")
    log(f"    2512 ({occ_titles.get('2512')}) {latest_y}: {dispersion.get('2512', {}).get(latest_y)}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "STYRK-08 group 251 — Software and applications developers and analysts",
            "occupation_codes": {c: occ_titles.get(c, c) for c in STYRK_CODES},
            "primary_code": "2512",
            "classification": "STYRK-08 (Norway's national adaptation of ISCO-08)",
            "unit": "NOK per month, all sectors, all employees, both sexes",
            "measures": {
                "dispersion_by_year": "mean, median, P25/P75 and employee count (N) — table 11418",
                "age_at_quarter": f"median and mean monthly salary by 3 age bands (0-39/40-54/55+), "
                    f"latest available quarter ({latest_q}) — table 11658. Coarser than Sweden's 7 "
                    "bands, and quarterly rather than annual, but a genuine occupation x age cross.",
            },
            "confidence": "official",
            "level": "country (Norway, all sectors combined)",
            "years": YEARS_11418,
            "crosswalk_hazard": (
                "Checked against ISCO-08 4-digit definitions in data/occupations.json (Tier 4): all "
                "five STYRK-08 251x codes map to their matching isco08:251x at 'high' confidence, "
                "verified directly against this table's own live occupation labels."
            ),
            "why_it_matters": (
                "One of the few countries with a genuine occupation x age cross (with Sweden) — Spain's "
                "age/tenure cross exists too, but only at the broader CNO-11 major-group depth, not "
                "occupation-specific (see src_salary_es.py); Norway's, like Sweden's, is IT-specific. "
                "package 9's experience gradient needs occupation-specific crosses like this one."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[f"{BASE}/11418", f"{BASE}/11658"],
        license_note="CC BY 4.0 (Statistics Norway open data licence, data.norge.no / SSB API terms). "
                      "Cite: Statistics Norway (SSB), tables 11418 and 11658.",
        redistribution="processed derivative only — the raw JSON-stat2 payloads are cached under "
                        "data/raw/salary_no/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw source. Only the derived data/processed/salary_no.json "
                        "is committed.",
        transforms=[
            f"Queried STYRK-08 codes {', '.join(STYRK_CODES)} (group 251) x all sectors x both sexes x "
            f"all employees x {YEARS_11418[0]}-{YEARS_11418[-1]} from table 11418.",
            f"Queried the same codes x 3 age bands x the latest available quarter ({latest_q}) from "
            "table 11658.",
            "Kept mean, median, quartiles, N (11418) and age-banded median/mean (11658) verbatim.",
            "Occupation titles are the API's own labels, not hand-typed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=disp_rows + age_rows,
        coverage=f"{len(STYRK_CODES)} STYRK-08 occupations x {len(YEARS_11418)} years + age cross, "
                 "Norway only",
    )


if __name__ == "__main__":
    main_guard(run)
