"""CBS (Statistics Netherlands) OData API -> Dutch software-occupation wages.

Table 85517NED, occupation code A000275 = BRC 2014 "0811 Software- en
applicatieontwikkelaars" (software and application developers).

This is package 8's hardest crosswalk case, by design of the source, not by
any choice made here: **BRC 2014 (Beroepenclassificatie, the Dutch
occupational classification) does not map to ISCO-08 at all.** Unlike SSYK,
DISCO-08, STYRK-08 and AL2010 — all of which are explicit national
adaptations of ISCO-08 that keep its numbering at some digit depth — BRC 2014
is an independently structured classification. Code "0811" carries no
numeric or structural relationship to ISCO-08's "2512"; the two just happen
to both describe software development. There is no defensible way to assign
this a 4-digit ISCO-08 key. data/occupations.json records this as the
"no ISCO correspondence" case package 8 adds to the crosswalk's confidence
vocabulary, not merely "2-digit-only" — see Tier 4.

Unit: EUR per HOUR (CBS's own "Bruto uurloon" / gross hourly wage topic
group) — the same pay period as Denmark's and Canada's figures (hourly),
just a different currency, not a new period this spine hasn't seen before.
See src_salary_se.py's note on why every field name carries its own unit
rather than relying on a sibling meta string (an earlier draft of this
docstring called this "a fifth distinct pay period" — miscounted, the same
error an adversarial review caught in src_salary_dk.py and
src_salary_no.py's docstrings; corrected here too).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_nl"
NAME = "CBS (Statistics Netherlands) — software/application developer wages (BRC 2014)"
BASE = "https://opendata.cbs.nl/ODataApi/OData/85517NED"
BEROEP_CODE = "A000275"   # BRC 2014 "0811 Software- en applicatieontwikkelaars"

FIELDS = {
    "Werknemer_1": "n_employees_thousands",
    "k_25ePercentiel_2": "p25_eur_hour",
    "k_50ePercentielMediaan_3": "median_eur_hour",
    "k_75ePercentiel_4": "p75_eur_hour",
}


def run() -> None:
    banner(SOURCE_ID, NAME)

    dest = RAW / SOURCE_ID / "typed_dataset.json"
    raw = fetch(f"{BASE}/TypedDataSet?$filter=Beroep eq '{BEROEP_CODE}'", dest=dest)
    doc = json.loads(raw)
    rows = doc.get("value", [])

    by_year: dict[str, dict] = {}
    for row in rows:
        period = row["Perioden"]  # e.g. "2024JJ00" — annual code
        if not period.endswith("JJ00"):
            continue
        year = period[:4]
        by_year[year] = {out_field: row[src_field] for src_field, out_field in FIELDS.items()
                          if row.get(src_field) is not None}

    out = {
        "occupations": {
            "0811": {
                "title": "Software- en applicatieontwikkelaars (software and application developers)",
                "brc_code": "0811",
                "dispersion_by_year": by_year,
            },
        },
    }

    years = sorted(by_year)
    latest = years[-1] if years else None
    log(f"    {len(by_year)} years of data, {years[0] if years else '?'}-{latest}")
    log(f"    0811 {latest}: {by_year.get(latest)}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "BRC 2014 (Beroepenclassificatie) — no ISCO-08 correspondence",
            "primary_code": "0811",
            "classification": "BRC 2014 — Statistics Netherlands' own occupational classification, "
                "independently structured from ISCO-08 (not a national adaptation of it, unlike SSYK/"
                "DISCO-08/STYRK-08/AL2010). See module docstring.",
            "unit": "EUR per hour, gross (n_employees_thousands is a headcount in THOUSANDS, CBS's own "
                "unit — 316 means 316,000 — kept as published rather than multiplied out, the same "
                "convention this project already uses for the UK's jobs_thousand field).",
            "confidence": "official",
            "level": "country (Netherlands)",
            "years": years,
            "crosswalk_hazard": (
                "BRC 2014 code 0811 does NOT map to ISCO-08 at any digit depth — this is not a "
                "4-digit-vs-2-digit granularity question the way Sweden's SSYK 2514 was, it is a "
                "genuinely different, non-corresponding classification system. data/occupations.json "
                "must not force a 2-digit isco08:25 fallback here as if BRC merely lacked precision; "
                "Tier 4 adds a distinct 'no ISCO correspondence' confidence level for exactly this case."
            ),
            "why_it_matters": "One of nine countries with genuine occupation-level dispersion data "
                "(median + quartiles + employee count), and the clearest real-world example of why the "
                "crosswalk needs a confidence level below '2-digit-only'.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[f"{BASE}/TypedDataSet?$filter=Beroep eq '{BEROEP_CODE}'", f"{BASE}/DataProperties",
              f"{BASE}/Beroep"],
        license_note="CC BY 4.0 (CBS StatLine open data licence). Cite: Statistics Netherlands (CBS), "
                      "table 85517NED.",
        redistribution="processed derivative only — the raw OData JSON payload is cached under "
                        "data/raw/salary_nl/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw source. Only the derived data/processed/salary_nl.json "
                        "is committed.",
        transforms=[
            f"Queried BRC 2014 code {BEROEP_CODE} (0811, software and application developers) from "
            "table 85517NED's TypedDataSet, filtered server-side via OData $filter.",
            "Kept employee count (thousands), P25, median and P75 gross hourly wage for every annual "
            "period (JJ00) verbatim; non-annual (quarterly) periods, if any, are excluded.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(by_year) * len(FIELDS),
        coverage=f"1 BRC occupation code x {len(years)} years, Netherlands only",
        notes="BRC 2014 has no ISCO-08 correspondence — see meta.crosswalk_hazard.",
    )


if __name__ == "__main__":
    main_guard(run)
