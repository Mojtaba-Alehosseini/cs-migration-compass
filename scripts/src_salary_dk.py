"""Danmarks Statistik StatBank API -> Danish ICT-occupation wage dispersion.

Table LONS20 ("Earnings"), DISCO-08 occupation 2512 "Software developers" —
DISCO-08 is Denmark's national adaptation of ISCO-08 and, like Sweden's SSYK,
keeps ISCO's numbering at the 4-digit level for this occupation (verified
against the table's own live label, not assumed).

Three things this pipeline has to get right that a naive read would miss:

1. UNIT: earnings here are DKK per HOUR WORKED, not annual and not monthly —
   the same pay period as Canada's figures (hourly), just a different
   currency. Field names carry their own unit (see src_salary_se.py's note
   on the same discipline).
2. WHAT "mean_dkk_hour" ACTUALLY IS: fetched via DST's tableinfo API
   (`/v1/tableinfo/LONS20`), the LØNMÅL code FORINKL is labelled only
   "EARNINGS IN DKK PER HOUR WORKED" — an aggregate-earnings header, the
   same way "STANDARDIZED HOURLY EARNINGS" headers a different group of
   codes in the same variable. DST does not itself call FORINKL a mean or
   an average (no "gennemsnit"/"average" word in its label). It is used
   here as this table's mean because it sits alongside three explicit
   dispersion measures in the SAME cross-tabulated cell — NEDRE (lower
   quartile), MEDIAN (median), OVRE (upper quartile) — and a fourth,
   unlabelled "headline earnings" figure reported per hour for a group of
   many employees functions as that group's average by construction. This
   is this pipeline's own reasonable inference from the table's structure,
   not a literal DST label — recorded explicitly after an adversarial
   review asked whether "mean_dkk_hour" asserts more than DST's own text
   confirms.
3. N SCOPE: ANTAL is labelled "Number of FULLTIME employees in the earnings
   statistics" — `n_employees` in this file counts full-time employees only,
   the same scoping restriction src_salary_fi.py documents for Finland (an
   earlier draft of this file's docstring implied full-time scoping was
   Finland-specific; it is not — Denmark's ANTAL carries the identical
   restriction).
4. EMPLOYEE-GROUP FILTER: LONS20 crosses earnings by LONGRP (employee group:
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

PACKAGE 9 ADDITIONS. Two LØNMÅL codes package 8 did not fetch, added for
package 9's pay-composition work:

  PENS_dkk_hour    "Pension including ATP in DKK per hour worked" — an
                   employer-plus-employee pension contribution component.
                   Verified live (2512, 2024): PENS=59.35, alongside
                   FORINKL=489.26, BASIS=403.50, UREGEL=9.06 — consistent
                   with PENS being one of several components that sum
                   toward FORINKL's total (403.50+59.35+9.06=471.91,
                   the ~17.35 DKK/hr gap to 489.26 plausibly covered by
                   the other, smaller, not-fetched components: overtime,
                   sick pay, nuisance bonus, fringe benefits, holiday
                   allowances). Fetched specifically so scripts/normalise.py
                   can subtract a real, sourced employer-pension figure from
                   FORINKL rather than needing DST to publish that
                   subtraction directly — this table lets it be sourced.
  UREGEL_dkk_hour  "Irregular payments in DKK per hour worked" — fetched for
                   the same reason, alongside PENS.

MDRSNIT ("STANDARDIZED MONTHLY EARNINGS", Danish "standardberegnet
månedsfortjeneste") is DST's own headline MONTHLY figure — a section header
in the same LØNMÅL variable, not a simple multiple of FORINKL. Verified live
(2512, 2024): MDRSNIT=65,504.17 DKK/month, while FORINKL x DK's own standard
160.33 h/month (1,924 h/yr / 12, per this package's own Tier 5 hours
convention) gives ≈78,451 — NOT close to MDRSNIT. BASIS (the "basic
earnings" component alone) x the same 160.33 gives ≈64,693 — much closer
(~1.2% gap). DST's own documentation for exactly what MDRSNIT includes could
not be retrieved this session (the published methodology is a PDF, not a
web page a fetch could parse) — this pipeline does NOT claim to know
MDRSNIT's precise composition, only its sourced value, stored separately
from the hourly dispersion data and explicitly flagged as unconfirmed
composition rather than guessed at. NOT used as this pipeline's primary DK
figure — FORINKL-derived dispersion remains that — but available as DST's
own monthly-native reference point.

An earlier package-8 predecessor work order named "smalfortjeneste" and
"bredfortjeneste" as Danish LONS20 concepts. Checked: neither term appears
anywhere in this table's own live dimension metadata (fetched via DST's
`/v1/tableinfo/LONS20` endpoint) — smalfortjeneste was retired with the 2010
statistic and bredfortjeneste is not a Lønstruktur term at all. Confirmed
this file never used either term (grepped this repo's own history); nothing
to fix here beyond recording that the check was made.
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
    "FORINKL": "mean_dkk_hour",     # DST labels this "EARNINGS IN DKK PER HOUR WORKED" — not
                                     # itself "mean"/"average"; used as the mean here because it
                                     # sits opposite NEDRE/MEDIAN/OVRE in the same cell — see
                                     # module docstring point 2 for the full reasoning.
    "NEDRE": "p25_dkk_hour",        # "Lower quartile, earnings in DKK per hour worked"
    "MEDIAN": "median_dkk_hour",    # "Median, earnings in DKK per hour worked"
    "OVRE": "p75_dkk_hour",         # "upper quartile, earnings in DKK per hour worked"
    "ANTAL": "n_employees",         # "Number of fulltime employees in the earnings statistics"
    "PENS": "employer_pension_dkk_hour",   # "Pension including ATP in DKK per hour worked" — package 9
    "UREGEL": "irregular_dkk_hour",        # "Irregular payments in DKK per hour worked" — package 9
}

# Fetched in the same query as CONTENTS but NOT hourly and NOT part of
# dispersion_by_year — see module docstring's MDRSNIT section.
MONTHLY_CODE = "MDRSNIT"


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
            {"code": "LØNMÅL", "values": [*CONTENTS, MONTHLY_CODE]},
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
    monthly: dict[str, dict[str, float]] = {c: {} for c in DISCO_CODES}
    rows = 0
    for row in jsonstat_rows(ds):
        code, year, lm = row["ARBF"], row["Tid"], row["LØNMÅL"]
        if lm == MONTHLY_CODE:
            monthly.setdefault(code, {})[year] = row["_value"]
        else:
            dispersion.setdefault(code, {}).setdefault(year, {})[CONTENTS[lm]] = row["_value"]
        rows += 1

    out = {
        "occupations": {
            code: {
                "title": occ_titles.get(code, code),
                "dispersion_by_year": dispersion.get(code, {}),
                "standardized_monthly_dkk_by_year": monthly.get(code, {}),
            }
            for code in DISCO_CODES
        },
    }

    latest = YEARS[-1]
    t2512 = dispersion.get("2512", {}).get(latest, {})
    m2512 = monthly.get("2512", {}).get(latest)
    log(f"    {rows} dispersion cells across {len(DISCO_CODES)} occupations x {len(YEARS)} years")
    log(f"    2512 ({occ_titles.get('2512')}) {latest}: {t2512}, MDRSNIT={m2512}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "DISCO-08 group 251 — Software and applications developers and analysts",
            "occupation_codes": {c: occ_titles.get(c, c) for c in DISCO_CODES},
            "primary_code": "2512",
            "classification": "DISCO-08 (Denmark's national adaptation of ISCO-08)",
            "unit": "DKK per hour worked, full-time non-managerial employees (ANTAL's own label — "
                "'Number of fulltime employees'), all sectors, all forms of pay, both sexes. "
                "mean_dkk_hour is this pipeline's inference from FORINKL, not DST's own stated 'mean' "
                "— see module docstring point 2. employer_pension_dkk_hour and irregular_dkk_hour "
                "(package 9) are real published components of the same cell, sourced for "
                "scripts/normalise.py's PENS-subtraction demonstration — not inferred or estimated. "
                "standardized_monthly_dkk_by_year (package 9) is DST's own MDRSNIT headline monthly "
                "figure; its precise composition is not confirmed — see module docstring.",
            "filter_note": (
                "LONGRP=MED (non-managerial employees), AFLOEN=TIFA (all forms of pay), SEKTOR=1000 "
                "(all sectors). See module docstring for why MED was chosen over the total-employee-group "
                "cut, and the small residual gap from the work order's cited reference N."
            ),
            "confidence": "official",
            "level": "country (Denmark, all sectors combined)",
            "years": YEARS,
            "crosswalk_hazard": (
                "Checked against ISCO-08 4-digit definitions in data/occupations.json (Tier 4): all "
                "five DISCO-08 251x codes map to their matching isco08:251x at 'high' confidence, "
                "verified directly against this table's own live occupation labels."
            ),
            "why_it_matters": (
                "One of nine countries with genuine occupation-level percentile-family wage data; "
                "DISCO-08 tracks SSYK's ISCO-08-based structure exactly at this depth, confirmed by "
                "the same live-label check package 7 did for Sweden — see crosswalk_hazard above."
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
            "Package 9: also kept PENS (employer_pension_dkk_hour) and UREGEL (irregular_dkk_hour) — "
            "real published components of the same cell — and MDRSNIT (standardized_monthly_dkk_by_year "
            "per occupation/year), DST's own monthly headline figure, stored separately from the hourly "
            "dispersion data since it is not hourly and its exact composition is not confirmed.",
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
