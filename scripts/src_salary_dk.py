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
in the same LØNMÅL variable. Package 9 flagged a ~24% gap between MDRSNIT and
FORINKL-derived dispersion annualised at Eurostat's measured hours, and
shipped it as a disclosed limitation without resolving it (NEEDS-DECISION
#17). Package 10 (tier 0.2) reconciled it exactly, and the fix changes which
LØNMÅL family this pipeline treats as primary. The two-line answer: FORINKL
measures pay per hour ACTUALLY WORKED; MDRSNIT is built from STAND, DST's
"STANDARDIZED HOURLY EARNINGS" — pay per hour on DK's own standardised
full-time week, which nets out paid-but-not-worked time (holiday, sick leave)
the way FORINKL's denominator does not. The two concepts were never expected
to agree, and comparing FORINKL against MDRSNIT was comparing two different
LØNMÅL families, not a real disagreement between two DST statistics.

PROOF (verified live this session, every LØNMÅL code queried directly, not
inferred from a summary page): STAND x 160.33 h/month (= 1,924 h/yr / 12 =
DK's own 37-hour standardised full-time week x 52, the well-established
Danish overenskomst convention) reproduces MDRSNIT to within 0.002% —
checked across all 7 years (2018-2024) and all 5 DISCO-08 251x occupations
this table carries, 35 data points, worst residual 0.001%:

  2024, occ 2512: STAND=408.56, STANDx160.33=65,504.42, MDRSNIT=65,504.17
                  (+0.0004%)
  2018, occ 2512: STAND=348.88, STANDx160.33=55,935.93, MDRSNIT=55,935.77
                  (+0.0003%)
  (full table: 5 occupations x 7 years, .status/evidence/p10-gates.txt)

By contrast FORINKL x 38.4h/week (Eurostat's measured DK hours) x 52/12
overstates MDRSNIT by 23-25% in every single year — the exact ~24% package 9
flagged, now understood as two compounded mismatches: the wrong earnings
concept (FORINKL's worked-hour denominator vs STAND's standardised-hour
denominator) and the wrong hours figure (Eurostat's measured usual hours vs
DST's own standardisation constant, which are not the same 37-vs-38.4h
distinction wearing two different hats — they are literally required by two
different formulas). DST's own methodology page
(dst.dk/documentationofstatistics/39350029-...) is a JS-rendered shell this
session's fetch could not parse for prose confirmation (the same limitation
package 9 hit on GENESIS's PDF-only docs) — this pipeline is not relying on
that page's text, only on the live numeric identity above, which is stronger
evidence than a paraphrased methodology note would be.

CONSEQUENCE FOR THIS PIPELINE: mean_dkk_hour/p25_dkk_hour/median_dkk_hour/
p75_dkk_hour (the FORINKL family) remain fetched and committed — real DST
data, kept for context — but are no longer what feeds the wage-distribution
panel's native/regular_pay/total_earnings figures. The STAND family
(STAND/NEDREST/MEDIANST/OVREST, plus PENSST/UREGELST for the same
subtraction scripts/build_wage_distribution.py already performs) is fetched
as of package 10 and is what's actually used — see that file's _extract_dk()
and its explicit_hours_by_field, which now overrides the generic
hours_worked.json lookup with DK's own 37h/week standardisation constant
rather than Eurostat's measured hours, matching the concept STAND is
expressed in.

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
# Two parallel families — see module docstring. "_dkk_hour" = per hour ACTUALLY
# WORKED (FORINKL and siblings); "_std_dkk_hour" = per STANDARDISED hour, DK's
# own full-time-week convention (STAND and siblings) — the family that
# reconciles with MDRSNIT and is what build_wage_distribution.py now uses.
CONTENTS = {
    "FORINKL": "mean_dkk_hour",     # DST labels this "EARNINGS IN DKK PER HOUR WORKED" — not
                                     # itself "mean"/"average"; used as the mean here because it
                                     # sits opposite NEDRE/MEDIAN/OVRE in the same cell — see
                                     # module docstring point 2 for the full reasoning. Kept for
                                     # context; no longer this pipeline's primary DK figure.
    "NEDRE": "p25_dkk_hour",        # "Lower quartile, earnings in DKK per hour worked"
    "MEDIAN": "median_dkk_hour",    # "Median, earnings in DKK per hour worked"
    "OVRE": "p75_dkk_hour",         # "upper quartile, earnings in DKK per hour worked"
    "ANTAL": "n_employees",         # "Number of fulltime employees in the earnings statistics"
    "PENS": "employer_pension_dkk_hour",   # "Pension including ATP in DKK per hour worked" — package 9
    "UREGEL": "irregular_dkk_hour",        # "Irregular payments in DKK per hour worked" — package 9
    "STAND": "mean_std_dkk_hour",           # "STANDARDIZED HOURLY EARNINGS" — package 10, primary as of tier 0.2
    "NEDREST": "p25_std_dkk_hour",          # "Lower quartile, standardized earnings"
    "MEDIANST": "median_std_dkk_hour",      # "Median, standardized hourly earnings"
    "OVREST": "p75_std_dkk_hour",           # "Upper quartile, standardized hourly earnings"
    "PENSST": "employer_pension_std_dkk_hour",   # "Pension including ATP in DKK per standard hour"
    "UREGELST": "irregular_std_dkk_hour",         # "Irregular payment in DKK per standard hour"
}

# Fetched in the same query as CONTENTS but NOT hourly and NOT part of
# dispersion_by_year — see module docstring's MDRSNIT section.
MONTHLY_CODE = "MDRSNIT"

# DK's own standardised full-time week — 37h, the near-universal Danish
# overenskomst convention since the early-1990s working-time reductions.
# Not asserted from prose (DST's own methodology page is a JS shell this
# pipeline's fetch cannot parse — see module docstring); established
# empirically instead, by the STANDARDIZED_HOURS_PER_MONTH x STAND =
# MDRSNIT identity holding to <0.002% across every year and occupation this
# table publishes (module docstring; full check: .status/evidence/p10-gates.txt).
STANDARDISED_HOURS_PER_WEEK = 37.0
STANDARDISED_HOURS_PER_MONTH = STANDARDISED_HOURS_PER_WEEK * 52 / 12  # 160.33...


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


MDRSNIT_RECONCILIATION_TOLERANCE_PCT = 0.5  # DST's own STAND-to-MDRSNIT identity measures <0.002%
                                             # in every year/occupation checked; 0.5% is a generous
                                             # margin against a future data revision, not the expected
                                             # residual — see module docstring for the measured range.


def _verify_mdrsnit_reconciliation(dispersion: dict, monthly: dict) -> dict:
    """Package 10, tier 0.2: prove — every time this harvester runs, not just
    once in an investigation — that STAND x STANDARDISED_HOURS_PER_MONTH
    reproduces DST's own MDRSNIT to a small residual, for every year and
    occupation this table publishes both. Raises if any residual exceeds
    MDRSNIT_RECONCILIATION_TOLERANCE_PCT: a reconciliation this pipeline
    relies on to pick STAND over FORINKL as the primary DK figure must stay
    proven, not just have been proven once. See module docstring for the
    full reasoning and the measured 23-25% gap this replaced."""
    checked, worst_pct, worst_ref = [], 0.0, None
    for code, years in monthly.items():
        for year, mdrsnit in years.items():
            stand = dispersion.get(code, {}).get(year, {}).get("mean_std_dkk_hour")
            if stand is None or mdrsnit is None:
                continue
            computed = stand * STANDARDISED_HOURS_PER_MONTH
            residual_pct = (computed / mdrsnit - 1) * 100
            checked.append({"occupation": code, "year": year, "stand_dkk_hour": stand,
                             "computed_monthly": round(computed, 2), "published_mdrsnit": mdrsnit,
                             "residual_pct": round(residual_pct, 4)})
            if abs(residual_pct) > abs(worst_pct):
                worst_pct, worst_ref = residual_pct, f"{code}/{year}"
    if not checked:
        raise RuntimeError("_verify_mdrsnit_reconciliation: no (STAND, MDRSNIT) pair found to check — "
                            "the STAND or MDRSNIT fetch broke silently")
    if abs(worst_pct) > MDRSNIT_RECONCILIATION_TOLERANCE_PCT:
        raise RuntimeError(f"_verify_mdrsnit_reconciliation: {worst_ref} residual {worst_pct:+.3f}% "
                            f"exceeds {MDRSNIT_RECONCILIATION_TOLERANCE_PCT}% — the STAND<->MDRSNIT "
                            "identity this pipeline relies on to prefer STAND over FORINKL no longer "
                            "holds; do not silently keep using STAND as primary, investigate first")
    log(f"    MDRSNIT reconciliation: {len(checked)} (occupation, year) pairs checked, "
        f"worst residual {worst_pct:+.4f}% ({worst_ref})")
    return {"formula": "STAND (DKK/standardised hour) x 160.33 (= 37h/week x 52 / 12) = "
                        "MDRSNIT (DKK/month)",
            "tolerance_pct": MDRSNIT_RECONCILIATION_TOLERANCE_PCT,
            "worst_residual_pct": round(worst_pct, 4), "worst_residual_at": worst_ref,
            "pairs_checked": checked}


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

    mdrsnit_check = _verify_mdrsnit_reconciliation(dispersion, monthly)
    checks_by_code: dict[str, list[dict]] = {}
    for pair in mdrsnit_check["pairs_checked"]:
        checks_by_code.setdefault(pair["occupation"], []).append(pair)

    out = {
        "occupations": {
            code: {
                "title": occ_titles.get(code, code),
                "dispersion_by_year": dispersion.get(code, {}),
                "standardized_monthly_dkk_by_year": monthly.get(code, {}),
                # Nested per-occupation (not just the top-level summary below) because
                # build_wage_distribution.py's _extract_dk() only ever sees one
                # occupation's own slice of this document, not the whole file.
                "mdrsnit_reconciliation_by_year": {c["year"]: c for c in checks_by_code.get(code, [])},
            }
            for code in DISCO_CODES
        },
        # Whole-table summary, independent of which occupation a reader is looking at.
        "mdrsnit_reconciliation": {k: v for k, v in mdrsnit_check.items() if k != "pairs_checked"},
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
            "unit": "Two parallel families, full-time non-managerial employees (ANTAL's own label — "
                "'Number of fulltime employees'), all sectors, all forms of pay, both sexes — see "
                "module docstring. mean_dkk_hour/p25_dkk_hour/median_dkk_hour/p75_dkk_hour: DKK per "
                "hour ACTUALLY WORKED (FORINKL family); mean_dkk_hour is this pipeline's inference "
                "from FORINKL, not DST's own stated 'mean' — see module docstring point 2. Kept for "
                "context; no longer this pipeline's primary DK figure as of package 10. "
                "mean_std_dkk_hour/p25_std_dkk_hour/median_std_dkk_hour/p75_std_dkk_hour: DKK per "
                "STANDARDISED hour (STAND family) — package 10's primary DK figure, chosen because it "
                "reconciles with MDRSNIT (see mdrsnit_reconciliation below and the module docstring); "
                "annualises via STANDARDISED_HOURS_PER_WEEK (37h), not the generic cross-country "
                "hours_worked.json. employer_pension_dkk_hour/irregular_dkk_hour (package 9) and their "
                "_std_ counterparts (package 10) are real published components of the same cell, "
                "sourced for scripts/normalise.py's subtraction — not inferred or estimated. "
                "standardized_monthly_dkk_by_year is DST's own MDRSNIT headline monthly figure — as of "
                "package 10, its relationship to STAND is proven (mdrsnit_reconciliation), not merely "
                "carried as an unconfirmed reference point.",
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
            "dispersion data.",
            "Package 10 (tier 0.2): also kept STAND/NEDREST/MEDIANST/OVREST/PENSST/UREGELST — the "
            "standardised-hour counterparts to FORINKL/NEDRE/MEDIAN/OVRE/PENS/UREGEL — after proving "
            "STAND x 160.33h/month reproduces MDRSNIT to <0.002% across every year/occupation this "
            "table publishes (mdrsnit_reconciliation, recomputed and re-verified on every run — see "
            "module docstring). This resolved NEEDS-DECISION #17's ~24% disagreement: it was FORINKL "
            "(worked-hour) vs MDRSNIT (standardised-hour) being compared as though they were the same "
            "concept, not a real gap between two DST statistics.",
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
