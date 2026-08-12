"""Tilastokeskus (Statistics Finland) PxWeb API -> Finnish ICT-occupation wages.

Table StatFin/pra/15au ("Earnings of full-time wage and salary earners per
month by sector, occupational group... and sex"). AL2010 occupation 2512 —
AL2010 (Classification of Occupations 2010) is Finland's national adaptation
of ISCO-08, and 2512 carries the same 4-digit numbering as ISCO's "Software
developers" (confirmed against the table's own live label, not assumed).

Unit: EUR per MONTH, full-time earners only — the table is scoped that way at
the source (its own title says "full-time wage and salary earners"), unlike
Sweden/Denmark/Norway/UK/Canada/US which are not restricted to full-time. That
scope difference is real and is recorded in meta rather than smoothed over.

SECTOR (package 9 fix): the table's sector dimension is not binary. Verified
live against the table's own dimension metadata: `S0` (this package's
previous choice, "Total") is the WHOLE economy, including all three
government tiers (`S13111` central, `S13131` local, `S13132` wellbeing
services county); `S11_S12_S15` is specifically "Non-financial corporations,
financial and insurance corporations and non-profit institutions serving
households" — the actual private sector. Switched to `S11_S12_S15` this
package for cross-country comparability with sources that are private-sector
by construction (or close to it), and because package 9's own work order
named this code explicitly, having checked it against the table's live
metadata rather than assuming a binary public/private split existed.

TWO EARNINGS BASES, both published by this same table (package 9 finding):
`koko_psaaja_kans_*` ("total earnings") and `koko_psaaja_sans_*` ("earnings
for regular working hours") are separate, parallel content codes — not a
derived difference this pipeline computes. `sans` excludes whatever `kans`
includes beyond regular-hours pay (overtime, at minimum); Statistics
Finland's own methodology page is the source for exactly what separates
them, not assumed here. Both are now fetched, under separate never-blended
field names, matching this package's regular_pay vs total_earnings design
(see scripts/normalise.py) — Finland is one of the few sources that
publishes this distinction natively rather than needing a component
subtracted out.

No age or tenure cross exists for Finland in this package: the "pra" table
family's occupation-bearing tables (15au/15ax/15ay/15az) do not cross with
age, and 15aw/15av (which do cross with age) do not carry an occupation
dimension — checked against the live table catalog, not assumed from the
phase-4 plan's summary, which does not list Finland among the age-cross
sources either.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, jsonstat_rows, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_fi"
NAME = "Tilastokeskus (Statistics Finland) — ICT occupation wages, full-time earners (AL2010)"
TABLE_URL = "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/pra/15au.px"

# AL2010 "251 Software and applications developers and analysts".
AL2010_CODES = ["2511", "2512", "2513", "2514", "2519"]

SECTOR = "S11_S12_S15"  # private sector — see docstring; was "S0" (whole economy) before package 9

CONTENTS = {
    "koko_psaaja_lkm": "n_employees",
    "koko_psaaja_kans_ka": "total_mean_eur_month",
    "koko_psaaja_kans_p10": "total_p10_eur_month",
    "koko_psaaja_kans_med": "total_median_eur_month",
    "koko_psaaja_kans_p90": "total_p90_eur_month",
    "koko_psaaja_sans_ka": "regular_mean_eur_month",
    "koko_psaaja_sans_p10": "regular_p10_eur_month",
    "koko_psaaja_sans_med": "regular_median_eur_month",
    "koko_psaaja_sans_p90": "regular_p90_eur_month",
}


def run() -> None:
    banner(SOURCE_ID, NAME)

    body = {
        "query": [
            {"code": "timeperiod_y", "selection": {"filter": "item", "values": ["2024"]}},
            {"code": "sektoriluokitus_7_20230101", "selection": {"filter": "item", "values": [SECTOR]}},
            {"code": "ammatti_19_20180101", "selection": {"filter": "item", "values": AL2010_CODES}},
            {"code": "sukupuoli_9_20180101", "selection": {"filter": "item", "values": ["SSS"]}},
            {"code": "contentscode", "selection": {"filter": "item", "values": list(CONTENTS)}},
        ],
        "response": {"format": "json-stat2"},
    }
    dest = RAW / SOURCE_ID / "15au.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log(f"    cached  {dest.relative_to(dest.parents[3])}")
        doc = json.loads(dest.read_text(encoding="utf-8"))
    else:
        raw = fetch(TABLE_URL, method="POST", json_body=body, headers={"Content-Type": "application/json"}, cache=False)
        dest.write_bytes(raw)
        doc = json.loads(raw)

    occ_titles = doc["dimension"]["ammatti_19_20180101"]["category"]["label"]
    year = doc["dimension"]["timeperiod_y"]["category"]["label"]["2024"]

    dispersion: dict[str, dict] = {c: {} for c in AL2010_CODES}
    rows = 0
    for row in jsonstat_rows(doc):
        code = row["ammatti_19_20180101"]
        field = CONTENTS[row["contentscode"]]
        dispersion.setdefault(code, {})[field] = row["_value"]
        rows += 1

    out = {
        "occupations": {
            code: {"title": occ_titles.get(code, code), "year": "2024", "dispersion": dispersion.get(code, {})}
            for code in AL2010_CODES
        },
    }

    log(f"    {rows} dispersion cells across {len(AL2010_CODES)} occupations, year {year}")
    log(f"    2512 ({occ_titles.get('2512')}): {dispersion.get('2512')}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "AL2010 group 251 — Software and applications developers and analysts",
            "occupation_codes": {c: occ_titles.get(c, c) for c in AL2010_CODES},
            "primary_code": "2512",
            "classification": "AL2010 / Classification of Occupations 2010 (Finland's national "
                "adaptation of ISCO-08)",
            "unit": "EUR per month, FULL-TIME wage and salary earners only, private sector "
                "(S11_S12_S15 — non-financial/financial/insurance corporations and NPISH), both sexes. "
                "Scoped to full-time at the source — the other Nordic sources in this package are not. "
                "Two parallel bases: total_* (total earnings) and regular_* (earnings for regular "
                "working hours) — see module docstring, not a subtraction this pipeline computed.",
            "confidence": "official",
            "level": "country (Finland, private sector)",
            "years": ["2024"],
            "history_caveat": "This table (StatFin/pra/15au) exposes a single reference year (2024) "
                "via the live API; earlier years live in the StatFin_Passiivi archive under separate, "
                "per-year table IDs and were not pulled into this harvester — a single current year is "
                "what the work order accepted as sufficient for this source.",
            "crosswalk_hazard": (
                "Checked against ISCO-08 4-digit definitions in data/occupations.json (Tier 4): all "
                "five AL2010 251x codes map to their matching isco08:251x at 'high' confidence, "
                "verified directly against this table's own live occupation labels (which include the "
                "numeric prefix, e.g. '2511 Systems analysts' — national_title in occupations.json "
                "must be copied verbatim including that prefix)."
            ),
            "why_it_matters": "One of nine countries with genuine occupation-level percentile-family "
                "wage data (N, mean, P10, median, P90), and — uniquely in this spine — one that "
                "publishes both a total-earnings and a regular-hours-earnings basis natively, needing "
                "no component subtracted to get a 'regular pay' figure.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[TABLE_URL],
        license_note="CC BY 4.0 (Statistics Finland open data licence). Cite: Statistics Finland "
                      "(Tilastokeskus), table StatFin/pra/15au.",
        redistribution="processed derivative only — the raw json-stat2 payload is cached under "
                        "data/raw/salary_fi/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw source. Only the derived data/processed/salary_fi.json "
                        "is committed.",
        transforms=[
            f"Queried AL2010 codes {', '.join(AL2010_CODES)} (group 251) x sector {SECTOR} (private "
            "sector — package 9 fix, was 'S0'/whole economy) x both sexes x 2024 (the table's sole "
            "exposed year) from StatFin/pra/15au via POST, format json-stat2.",
            "Kept N, and BOTH earnings bases the table publishes — total_* (koko_psaaja_kans_*) and "
            "regular_* (koko_psaaja_sans_*, 'earnings for regular working hours') — under separate, "
            "never-blended field names. Package 8 fetched total_* only; package 9 added regular_*.",
            "Occupation titles are the API's own labels, not hand-typed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=rows,
        coverage=f"{len(AL2010_CODES)} AL2010 occupations, single year (2024), Finland private sector "
                 "only, full-time earners only",
        notes="Full-time-only scope is the table's own restriction, not a filter this pipeline chose — "
              "see meta.unit. Sector switched from 'S0' (whole economy) to 'S11_S12_S15' (private "
              "sector) in package 9, per that package's work order, checked against the table's own "
              "live sector-dimension metadata.",
    )


if __name__ == "__main__":
    main_guard(run)
