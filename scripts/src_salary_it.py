"""Italy — an honest "no occupation-level wage series" record.

Not a missing file: a first-class, documented finding. ISTAT publishes no
occupation-level earnings flow. Its `CONTRACTUAL_OCCUPATION` dimension
(present in several ISTAT SDMX flows) classifies by CONTRACT GRADE —
operaio/impiegato/quadro/dirigente (blue-collar/white-collar/middle
management/executive) — not by CP2011 (Italy's occupation classification,
its own ISCO-08 adaptation). The only flow that does carry a genuine CP2011
occupation code alongside earnings is a school-leaver cohort outcomes survey
(earnings a fixed period after graduation, not a general wage structure by
occupation), which is a different measurement entirely and not comparable to
the other fourteen countries' occupation-wage tables in this spine.

This finding is inherited from the work order that commissioned this
package, which reports having scanned ISTAT's full SDMX dataflow catalogue
(4,896 flows) — not independently re-verified by re-scanning the catalogue
this run. An earlier draft of this docstring claimed the scan as "this
package's own research"; corrected after an adversarial review asked
whether that scan actually happened this session (it did not — this file
records the work order's claim, honestly attributed, the same caution this
package's own harvesters apply to every other work-order-cited figure).
Re-scanning nearly five thousand dataflows on every pipeline run would be
expensive regardless of provenance; if a future session has reason to
believe ISTAT has since published a CP2011 earnings flow, that is worth a
fresh targeted check.

The NACE J (information and communication) sector route exists as an
alternative and is named here as exactly that — a SECTOR figure, not an
occupation one, and not fetched by this script or any other harvester in
this pipeline (grepped: no `scripts/src_*.py` file touches either Eurostat
flow named below). Two different Eurostat NACE-J earnings flows are named
in `phase-4-salary-and-cv-plan.md`, and an earlier draft of this docstring
conflated them — corrected after an adversarial review caught the error:
`earn_ses22_49` (Professionals x NACE J) is the flow the plan doc says is
"empty for DK, SE, FI, IT"; `earn_ses_pub2n` (median hourly, NACE J) is the
flow the plan doc says is "populated for all nine EU countries" — i.e. NOT
described as empty for Italy. Neither flow is implemented here, so this
file makes no claim about either one's actual Italy coverage — only that
neither is fetched, and NACE J would be a sector figure either way, not an
occupation one.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import banner, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_it"
NAME = "Italy — no occupation-level wage earnings flow exists (ISTAT)"


def run() -> None:
    banner(SOURCE_ID, NAME)
    log("    NO LIVE FETCH — there is nothing to fetch. See module docstring: ISTAT publishes no "
        "occupation-level (CP2011) earnings flow, per the work order's own reported scan of its full "
        "SDMX dataflow catalogue — not independently re-verified this run.")

    out = {
        "occupations": {},
        "status": "no-occupation-series",
        "alternative": {
            "route": "NACE J (information and communication) sector earnings",
            "scope": "SECTOR, not occupation — includes every job in the ICT sector (support staff, "
                     "sales, management), not software developers specifically",
            "note": "Not fetched by this script or any other harvester in this pipeline. Two Eurostat "
                    "NACE-J flows are named in phase-4-salary-and-cv-plan.md (earn_ses22_49, said there "
                    "to be empty for DK/SE/FI/IT; earn_ses_pub2n, said there to be populated for all "
                    "nine EU countries) — neither is implemented here, and this file makes no claim "
                    "about either one's Italy coverage specifically. See module docstring.",
        },
    }

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": None,
            "primary_code": None,
            "classification": "CP2011 (Italy's ISCO-08 adaptation) exists as a classification, but no "
                "ISTAT flow crosses it with earnings — see module docstring for what was checked.",
            "confidence": "official",
            "status": "no-occupation-series",
            "level": "country (Italy)",
            "years": [],
            "why_it_matters": "The honest answer for Italy is absence, documented with what was "
                "checked and why, not silence and not a substituted sector figure presented as an "
                "occupation one.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=["https://esploradati.istat.it/SDMXWS/rest/dataflow/IT1/ALL/latest"],
        license_note="N/A — no data fetched. If a future session locates a genuine CP2011 earnings "
                      "flow, record its actual licence then.",
        redistribution="N/A — no raw data fetched or cached.",
        transforms=[
            "No transform — this file records the absence of a source, per the work order's own "
            "reported scan of ISTAT's full SDMX dataflow catalogue (4,896 flows), not independently "
            "re-verified or re-scanned here.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=0,
        coverage="no occupation-level coverage exists for Italy in this pipeline",
        status="ok",  # the record itself (documented absence + alternative + what-was-checked) is
                      # real, non-empty content — see src_salary_ae.py's identical reasoning
        notes="ISTAT publishes no occupation-level (CP2011) earnings flow. Its CONTRACTUAL_OCCUPATION "
              "dimension is contract grade (operaio/impiegato/quadro/dirigente), not occupation. The "
              "only CP2011-crossed earnings flow is a school-leaver cohort survey, not a general wage "
              "structure and not comparable to this spine's other sources. NACE J sector earnings are "
              "the named alternative, not substituted here because a sector figure is not an "
              "occupation figure.",
    )


if __name__ == "__main__":
    main_guard(run)
