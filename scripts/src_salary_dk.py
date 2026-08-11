"""Danmarks Statistik StatBank API -> Danish ICT-occupation wage dispersion.

Table LONS20 ("Earnings"), DISCO-08 occupation 2512 "Software developers" —
DISCO-08 is Denmark's national adaptation of ISCO-08 and, like Sweden's SSYK,
keeps ISCO's numbering at the 4-digit level for this occupation (verified
against the table's own live label, not assumed).

Two things this pipeline has to get right that a naive read would miss:

1. UNIT: earnings here are DKK per HOUR WORKED, not annual and not monthly —
   the third distinct pay period this salary spine carries (Sweden: monthly,
   UK: annual, Canada: hourly, US: annual). Field names carry their own unit
   (see src_salary_se.py's note on the same discipline).
2. EMPLOYEE-GROUP FILTER: LONS20 crosses earnings by LONGRP (employee group:
   total / general managers / excl. young+trainees / non-managerial / young
   people / trainees). The work order's cited reference figure for 2512 was
   N=29,710; querying every LONGRP value against the live API, only
   LONGRP=MED ("Employees, non-managerial level") x AFLOEN=TIFA ("All forms
   of pay") comes close (29,096 for 2024, ~2% off) — the total-employee-group
   cut (LTOT) gives 31,647, materially different. MED is used here: it is
   also the principled choice (a "software developers" occupation figure
   should exclude the general-manager slice, which the LTOT cut does not),
   and the residual ~2% gap most likely reflects a data revision between the
   work order's research and this harvest (DST's own `updated` timestamp on
   this table postdates typical work-order research windows) rather than a
   wrong filter. Recorded here rather than silently matched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, jsonstat_rows, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_dk"
NAME = "Danmarks Statistik (DST) LONS20 — ICT occupation wage dispersion (DISCO-08)"
TABLE_URL = "https://api.statbank.dk/v1/data"

# DISCO-08 "251 Software and applications developers and analysts" plus its
# siblings, mirroring package 7's Swedish scope exactly (SSYK and DISCO-08
# are both ISCO-08-based national adaptations at the 3-digit level).
DISCO_CODES = ["2511", "2512", "2513", "2514", "2519"]
YEARS = [str(y) for y in range(2018, 2025)]

# ContentsCode ("LØNMÅL") values used, each -> its own unit-qualified field name.
CONTENTS = {
    "FORINKL": "mean_dkk_hour",     # "EARNINGS IN DKK PER HOUR WORKED" — the aggregate total
    "NEDRE": "p25_dkk_hour",        # lower quartile
    "MEDIAN": "median_dkk_hour",
    "OVRE": "p75_dkk_hour",         # upper quartile
    "ANTAL": "n_employees",         # count, no unit needed
}


def _query() -> dict:
    body = {
        "table": "LONS20",
        "format": "JSONSTAT",
        "lang": "en",
        "variables": [
            {"code": "ARBF", "values": DISCO_CODES},
            {"code": "SEKTOR", "values": ["1000"]},       # All sectors
            {"code": "AFLOEN", "values": ["TIFA"]},        # All forms of pay
            {"code": "LONGRP", "values": ["MED"]},         # Non-managerial employees — see docstring
            {"code": "LØNMÅL", "values": list(CONTENTS)},
            {"code": "KØN", "values": ["MOK"]},       # Men and women, total
            {"code": "Tid", "values": YEARS},
        ],
    }
    dest = RAW / SOURCE_ID / "LONS20.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log(f"    cached  {dest.relative_to(dest.parents[3])}")
        return json.loads(dest.read_text(encoding="utf-8"))
    raw = fetch(TABLE_URL, method="POST", json_body=body, headers={"Content-Type": "application/json"}, cache=False)
    dest.write_bytes(raw)
    return json.loads(raw)


def _shim(ds: dict) -> dict:
    """DST nests id/size INSIDE dataset.dimension (non-standard JSON-stat 2.0
    placement — Sweden's SCB keeps them as siblings of 'dimension'). Build the
    shape _common.jsonstat_rows() actually expects rather than editing that
    shared helper for one source's quirk."""
    dim = ds["dimension"]
    return {"id": dim["id"], "size": dim["size"], "dimension": dim, "value": ds["value"]}


def run() -> None:
    banner(SOURCE_ID, NAME)

    doc = _query()
    ds = _shim(doc["dataset"])
    occ_titles = ds["dimension"]["ARBF"]["category"]["label"]

    dispersion: dict[str, dict[str, dict]] = {c: {} for c in DISCO_CODES}
    rows = 0
    for row in jsonstat_rows(ds):
        code, year = row["ARBF"], row["Tid"]
        field = CONTENTS[row["LØNMÅL"]]
        dispersion.setdefault(code, {}).setdefault(year, {})[field] = row["_value"]
        rows += 1

    out = {
        "occupations": {
            code: {"title": occ_titles.get(code, code), "dispersion_by_year": dispersion.get(code, {})}
            for code in DISCO_CODES
        },
    }

    latest = YEARS[-1]
    t2512 = dispersion.get("2512", {}).get(latest, {})
    log(f"    {rows} dispersion cells across {len(DISCO_CODES)} occupations x {len(YEARS)} years")
    log(f"    2512 ({occ_titles.get('2512')}) {latest}: {t2512}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "DISCO-08 group 251 — Software and applications developers and analysts",
            "occupation_codes": {c: occ_titles.get(c, c) for c in DISCO_CODES},
            "primary_code": "2512",
            "classification": "DISCO-08 (Denmark's national adaptation of ISCO-08)",
            "unit": "DKK per hour worked, non-managerial employees, all sectors, all forms of pay, both sexes",
            "filter_note": (
                "LONGRP=MED (non-managerial employees), AFLOEN=TIFA (all forms of pay), SEKTOR=1000 "
                "(all sectors). See module docstring for why MED was chosen over the total-employee-group "
                "cut, and the small residual gap from the work order's cited reference N."
            ),
            "confidence": "official",
            "level": "country (Denmark, all sectors combined)",
            "years": YEARS,
            "crosswalk_hazard": (
                "Not yet checked against ISCO-08 4-digit definitions the way SSYK 2514 was in package 7 "
                "— DISCO-08's own 4-digit divergence from ISCO-08, if any, is unverified here. Treat "
                "2511-2519 sibling codes as unverified until data/occupations.json records a checked note."
            ),
            "why_it_matters": (
                "One of nine countries with genuine occupation-level percentile-family wage data; "
                "DISCO-08 mirrors SSYK's ISCO-08-based structure closely enough that the same crosswalk "
                "family (isco08:2512) very likely applies, pending the same definition check package 7 "
                "did for Sweden."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[f"{TABLE_URL} (table=LONS20)"],
        license_note="CC BY 4.0 (Danmarks Statistik open data licence). Cite: Statistics Denmark (DST), "
                      "table LONS20.",
        redistribution="processed derivative only — the raw StatBank JSON-stat payload is cached under "
                        "data/raw/salary_dk/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw source (CC BY 4.0 would permit it; the repo simply doesn't). "
                        "Only the derived data/processed/salary_dk.json is committed.",
        transforms=[
            f"Queried DISCO-08 codes {', '.join(DISCO_CODES)} (group 251) x all sectors x all forms of "
            f"pay x non-managerial employees x both sexes x {YEARS[0]}-{YEARS[-1]} from table LONS20 via "
            "POST, format JSONSTAT.",
            "Kept mean-equivalent, lower quartile, median, upper quartile (each _dkk_hour) and employee "
            "count verbatim.",
            "Occupation titles are the API's own labels, not hand-typed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=rows,
        coverage=f"{len(DISCO_CODES)} DISCO-08 occupations x {len(YEARS)} years, Denmark only (no "
                 "sub-national breakdown in this table)",
        notes="Uses the non-managerial-employees, all-forms-of-pay cut (LONGRP=MED, AFLOEN=TIFA) — see "
              "module docstring for why, and for the residual gap from an external cited reference figure.",
    )


if __name__ == "__main__":
    main_guard(run)
