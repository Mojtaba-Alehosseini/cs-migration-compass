"""UAE — an honest "no series" record, not a missing file.

Verified live, not assumed: ILOSTAT flow DF_EAR_EMTA_SEX_OCU_NB holds exactly
39 UAE rows, and every one of them is dated 2009 — no later year exists for
this country in this flow, at any occupation or sex breakdown. The UAE's own
statistics body (FCSC) has no occupation-level wage table newer than an
October 2008 release either. Seventeen years stale (2009 to this package's
2026 run) is the honest number to publish, and this file exists to publish
it precisely rather than let the country's absence from the salary spine
read as an oversight.

This script does not fetch anything at run time — the four figures below are
the last real values ILOSTAT holds for the UAE, pinned as data with their
real 2009 date, exactly the way a `no-series` record should look: present,
sourced, dated, and never updated to look more current than it is.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import banner, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_ae"
NAME = "UAE — no occupation-level wage series since 2009 (ILOSTAT last known figures)"
ILOSTAT_URL = "https://sdmx.ilo.org/rest/data/ILO,DF_EAR_EMTA_SEX_OCU_NB,1.0/ARE.......?startPeriod=1990"

# Verified live against the ILOSTAT SDMX CSV response on 2026-08-11: every one
# of the 39 UAE rows in this flow is year 2009. These four (ISCO-08 major
# groups, both sexes total) are the ones closest to software occupations;
# kept as a snapshot rather than re-fetched each run, because the source
# itself has published nothing newer to fetch.
LAST_KNOWN_2009 = {
    "isco08_major:2": {"title": "Professionals", "monthly_average_wage_aed": 13688.694},
    "isco08_major:1": {"title": "Managers", "monthly_average_wage_aed": 22038.627},
    "isco08_major:3": {"title": "Technicians and associate professionals",
                        "monthly_average_wage_aed": 10221.388},
    "isco08_major:0": {"title": "Armed forces occupations", "monthly_average_wage_aed": 20959.023},
}


def run() -> None:
    banner(SOURCE_ID, NAME)
    log("    NO LIVE FETCH — see module docstring. Recording the last known (2009) figures as a "
        "dated, sourced 'no current series' record.")

    out = {
        "occupations": LAST_KNOWN_2009,
        "status": "no-series",
        "last_known_year": 2009,
        "years_stale": "package build year minus 2009 — 17 years as of this run (2026)",
    }

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "ISCO-08 major groups (1-digit-equivalent) — the last depth the UAE "
                "published at all",
            "primary_code": "isco08_major:2",
            "primary_label": "Professionals",
            "classification": "ISCO-08 major group, 2009 vintage only",
            "unit": "AED per month",
            "confidence": "official",
            "status": "no-series",
            "level": "country (United Arab Emirates)",
            "years": [2009],
            "crosswalk_hazard": (
                "'Professionals' is ISCO major group 2 in full, not IT-specific — same caveat as "
                "Ireland's SES06 and Qatar's PSA series. On top of that, this figure is 17 years stale "
                "as of this package's run; it should be surfaced on the site as a dated historical "
                "reference, never as a current wage estimate."
            ),
            "why_it_matters": "Confirms the site's Explore Jobs copy ('the UAE's last occupation-level "
                "wage statistic is from 2009') with an exact figure and source, rather than the "
                "unsupported assertion the copy made before package 7's correction.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[ILOSTAT_URL],
        license_note="ILOSTAT open data terms (ILO). Cite: International Labour Organization (ILO), "
                      "ILOSTAT, flow DF_EAR_EMTA_SEX_OCU_NB. Underlying national source: UAE Federal "
                      "Competitiveness and Statistics Centre (FCSC), 2009 Labour Force Survey.",
        redistribution="the four cited 2009 figures are reproduced directly in "
                        "data/processed/salary_ae.json (there is no larger raw payload to separately "
                        "redistribute — see module docstring; this source does not fetch a raw file at "
                        "run time).",
        transforms=[
            "No transform — this is a dated snapshot of ILOSTAT's own published 2009 values for the "
            "UAE, verified live against the full 39-row flow before being pinned here (every row in "
            "the flow is 2009; nothing more recent exists to prefer over these).",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(LAST_KNOWN_2009),
        coverage="4 ISCO-08 major groups, single year (2009), UAE only",
        status="ok",  # real, non-empty, sourced data — the record's own status="no-series" field
                      # (see write_processed above) is what marks it stale, not provenance.status,
                      # which means "did the fetch produce data" and here it genuinely did
        notes="No occupation-level wage statistic exists for the UAE newer than 2009 in ILOSTAT or in "
              "the national statistics body's (FCSC) own releases — verified, not assumed. This file "
              "exists so that absence is a sourced, dated data record instead of a silent gap.",
    )


if __name__ == "__main__":
    main_guard(run)
