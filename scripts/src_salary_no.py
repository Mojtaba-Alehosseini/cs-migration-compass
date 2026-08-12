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

PACKAGE 10 (tier 0.3, NEEDS-DECISION #18) ADDITION: table 11418's
ContentsCode carries seven values, not the one (Manedslonn) fetched through
package 9 — verified live against the table's own metadata (GET, no query):
Manedslonn (total monthly earnings), AvtaltManedslonn (basic salary — pay
BEFORE bonus/overtime/irregular allowances), Uregtil (irregular allowances),
Bonus, Overtid (overtime), plus AlderLA/AvtArbTid (age/contractual hours,
unrelated to composition). pay_composition.json's salary_no note previously
said this pipeline fetched only mean/median/p25/p75/n and had "nothing
subtractable... not because none exists at SSB" — checked properly this
package: a bonus/allowance breakdown DOES exist, and better than that,
AvtaltManedslonn is published at the SAME measuring-method granularity as
the total (median, average, P25, P75 — verified live, 2023-2025), not
merely as a mean. That makes it a strictly better fit than a Denmark-style
subtraction: rather than removing one flat mean-derived scalar from every
percentile of the total (distorting the spread — see NEEDS-DECISION #17's
Denmark discussion of exactly that problem), Norway's regular_pay basis
uses AvtaltManedslonn AS PUBLISHED, at every percentile SSB itself reports
it at. Bonus/Uregtil/Overtid themselves are published ONLY as a mean
(median and P25 are 0 in every year checked — most employees receive
neither in a given period, so SSB evidently doesn't publish their own
percentile spread) and are NOT fetched or used: this pipeline does not need
them, since it is not deriving regular_pay by subtraction here at all.

Manedslonn (still fetched, still "native"/total_earnings) and
AvtaltManedslonn do not sum-and-subtract to each other exactly against
Bonus+Uregtil+Overtid's own means (a ~530 NOK/~0.7%-of-salary residual in
2025, smaller in other years) — expected, not a bug: independent SSB
series, not one computed from the other, the same relationship FORINKL/
PENS/UREGEL/BASIS have to each other in Denmark's LONS20 (see
src_salary_dk.py). Not used as a subtraction input either way."""
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
# ContentsCode values queried alongside Manedslonn (the default/implicit content
# above) — package 10, tier 0.3. AvtaltManedslonn is Norway's own regular_pay-
# basis figure (bonus/overtime/irregular allowances OUT), published at the same
# measuring-method granularity as Manedslonn — see module docstring.
CONTENTS_CODES = ["Manedslonn", "AvtaltManedslonn"]

# 11658 is quarterly; take the most recent quarter available at run time.
# "999D" (All ages) added package 10, tier 1 — a same-quarter, same-table total
# to divide the age bands by, rather than the annual 11418 table's own total
# (a different table, a different period — the quarterly 11658 has its own).
AGE_BANDS = ["0-39", "40-54", "55+", "999D"]
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

    # --- 11418: dispersion by occupation and year, both ContentsCode values ---
    body = {
        "query": [
            {"code": "MaaleMetode", "selection": {"filter": "item", "values": list(CONTENTS_11418)}},
            {"code": "Yrke", "selection": {"filter": "item", "values": STYRK_CODES}},
            {"code": "Sektor", "selection": {"filter": "item", "values": ["ALLE"]}},
            {"code": "Kjonn", "selection": {"filter": "item", "values": ["0"]}},
            {"code": "AvtaltVanlig", "selection": {"filter": "item", "values": ["0"]}},
            {"code": "ContentsCode", "selection": {"filter": "item", "values": CONTENTS_CODES}},
            {"code": "Tid", "selection": {"filter": "item", "values": YEARS_11418}},
        ],
        "response": {"format": "json-stat2"},
    }
    doc = _query("11418", body)
    occ_titles = doc["dimension"]["Yrke"]["category"]["label"]
    # Manedslonn (total) keeps the existing bare field names (mean_nok_month etc.)
    # for backward compatibility with every already-committed consumer.
    # AvtaltManedslonn (regular_pay basis — package 10, tier 0.3) gets an
    # "avtalt_" prefix on the same field names.
    dispersion: dict[str, dict[str, dict]] = {c: {} for c in STYRK_CODES}
    disp_rows = 0
    for row in jsonstat_rows(doc):
        code, year, field = row["Yrke"], row["Tid"], CONTENTS_11418[row["MaaleMetode"]]
        prefix = "" if row["ContentsCode"] == "Manedslonn" else "avtalt_"
        dispersion.setdefault(code, {}).setdefault(year, {})[f"{prefix}{field}"] = row["_value"]
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
                "dispersion_by_year": "mean, median, P25/P75 and employee count (N), both Manedslonn "
                    "(total monthly earnings — bare field names) and AvtaltManedslonn (basic salary "
                    "before bonus/overtime/irregular allowances — avtalt_-prefixed field names, "
                    "package 10 tier 0.3) — table 11418. Both published at the same measuring-method "
                    "granularity; AvtaltManedslonn is Norway's own regular_pay-basis figure, not a "
                    "subtraction this pipeline performs — see module docstring.",
                "age_at_quarter": f"median and mean monthly salary by 3 age bands (0-39/40-54/55+) "
                    f"plus '999D' (all ages, same table/quarter — package 10 tier 1, a same-period "
                    f"total to compute age-band premiums against, rather than borrowing the annual "
                    f"11418 table's own total from a different period), latest available quarter "
                    f"({latest_q}) — table 11658. Coarser than Sweden's 7 bands, and quarterly rather "
                    "than annual, but a genuine occupation x age cross.",
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
            "Package 10 (tier 0.3): also queried ContentsCode=AvtaltManedslonn (basic salary, same "
            "measuring methods as Manedslonn) after checking table 11418's own metadata found it, "
            "Bonus, Uregtil and Overtid all published as separate components — resolving NEEDS-"
            "DECISION #18. Bonus/Uregtil/Overtid checked but not fetched: published as a mean only "
            "(median and P25 are 0 in every year checked), not needed since regular_pay uses "
            "AvtaltManedslonn directly rather than by subtraction.",
            "Occupation titles are the API's own labels, not hand-typed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=disp_rows + age_rows,
        coverage=f"{len(STYRK_CODES)} STYRK-08 occupations x {len(YEARS_11418)} years + age cross, "
                 "Norway only",
    )


if __name__ == "__main__":
    main_guard(run)
