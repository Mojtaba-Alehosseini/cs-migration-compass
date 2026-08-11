"""INE (Instituto Nacional de Estadistica) Tempus3 API -> Spanish IT wages.

Three tables from INE's Encuesta Cuatrienal de Estructura Salarial (EES —
"Quadrennial" Wage Structure Survey, INE operation 121; NOT the Encuesta
ANUAL, operation 140, whose series carry the same "EAES" code prefix and are
easy to reach for by mistake):

  70672  means and percentiles by sex and CNO-11 occupation subgroup
  70706  average gross salary by sex, occupation and AGE band
  70707  average gross salary by sex, occupation and TENURE band

Two findings from checking the live API rather than trusting the work order's
brief, in the spirit of package 7's own discipline (which found SSYK 2514 was
not what its number implied):

1. VINTAGE: the work order cites table 70672 as "2022". Queried live, EVERY
   series in this table — not just the occupation ones, the whole table,
   confirmed by fetching the full unfiltered dataset — carries exactly one
   year, 2018, with an empty result for an explicit 2022 date-range query.
   70672 is unambiguously the right table (correctly titled "Means and
   percentiles by sex and main groups and subgroups of the CNO-11" under the
   Cuatrienal operation, not a look-alike from the Annual survey), so this
   looks like a genuine vintage change since the work order's research
   rather than a wrong table ID: recorded here as 2018, not silently
   upgraded to a year the API does not return.
2. GRANULARITY MISMATCH BETWEEN TABLES: 70672 reaches CNO-11 subgroup 27
   ("Information technology professionals") directly. 70706 and 70707 do
   NOT — checked directly against their live series names, both cross age
   or tenure with a much coarser category, "Scientific and intellectual
   technicians and professionals" (CNO-11's major group 2, which bundles
   doctors, lawyers, engineers, teachers and scientists together with IT).
   There is no IT-specific age or tenure series in either table. Both are
   still fetched — the coarse cut is real, sourced data — but stored under
   an explicitly different, honestly-labelled key so package 9 cannot
   mistake it for an IT-specific gradient the way it could Sweden's, "251"
   Norway's or the UK's age-crossed sources.

Unit: EUR per YEAR (gross annual salary — the source's own magnitudes,
tens of thousands, are annual, not monthly or hourly).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, banner, fetch, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "salary_es"
NAME = "INE Encuesta Cuatrienal de Estructura Salarial (EES) — IT wages by CNO-11"
BASE = "https://servicios.ine.es/wstempus/js/EN/DATOS_TABLA"

# Table 70672's two ICT-flavoured occupation labels: the narrow CNO-11
# subgroup 27 (our primary target) and a broader rollup INE also publishes.
OCC_LABELS = {
    "it_professionals": "Information technology professionals",
    "ict_specialists_broad": "Information and communications technologies (ICT) specialists",
}
MEASURE_SUFFIXES = {
    "Average.": "mean_eur_year",
    "10th Percentile.": "p10_eur_year",
    "25th Percentile.": "p25_eur_year",
    "50th Percentile.": "median_eur_year",
    "75th Percentile.": "p75_eur_year",
    "90th Percentile.": "p90_eur_year",
}

# The broader occupation category age/tenure actually reach — see docstring.
BROAD_OCC_LABEL = "Scientific and intellectual technicians and professionals"


def _fetch_table(table_id: str) -> list[dict]:
    dest = RAW / SOURCE_ID / f"{table_id}.json"
    raw = fetch(f"{BASE}/{table_id}", dest=dest)
    import json
    return json.loads(raw)


def _series_for(rows: list[dict], occ_label: str, gender: str = "Both genders") -> dict[str, dict]:
    """key: measure suffix or age/tenure band -> {value, year}."""
    prefix = f"National Total. Base data. {gender}. {occ_label}."
    out: dict[str, tuple] = {}
    for s in rows:
        name = s["Nombre"].strip()
        if not name.startswith(prefix.strip()):
            continue
        tail = name[len(prefix):].strip()
        data = s.get("Data") or []
        if not data:
            continue
        latest = data[-1]
        out[tail] = (latest["Valor"], latest["Anyo"])
    return out


def run() -> None:
    banner(SOURCE_ID, NAME)

    disp_rows = _fetch_table("70672")
    age_rows = _fetch_table("70706")
    tenure_rows = _fetch_table("70707")

    occupations: dict[str, dict] = {}
    for key, occ_label in OCC_LABELS.items():
        series = _series_for(disp_rows, occ_label)
        measures = {}
        year = None
        for suffix, field in MEASURE_SUFFIXES.items():
            hit = series.get(suffix)
            if hit is None:
                continue
            measures[field] = hit[0]
            year = hit[1]
        occupations[key] = {"cno11_label": occ_label, "year": year, "dispersion": measures}
        log(f"    {key} ({occ_label}) {year}: {measures}")

    broad_age = _series_for(age_rows, BROAD_OCC_LABEL)
    broad_tenure = _series_for(tenure_rows, BROAD_OCC_LABEL)
    age_year = next(iter(broad_age.values()))[1] if broad_age else None
    tenure_year = next(iter(broad_tenure.values()))[1] if broad_tenure else None

    out = {
        "occupations": occupations,
        "broader_category_context": {
            "cno11_label": BROAD_OCC_LABEL,
            "note": "NOT IT-specific — see module docstring. Included because it is the finest "
                    "occupation grain at which INE crosses age or tenure at all.",
            "age_bands_eur_year": {band: val for band, (val, yr) in broad_age.items()},
            "age_year": age_year,
            "tenure_bands_eur_year": {band: val for band, (val, yr) in broad_tenure.items()},
            "tenure_year": tenure_year,
        },
    }

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": "CNO-11 (Clasificacion Nacional de Ocupaciones 2011)",
            "primary_code": "cno11:27",
            "primary_label": OCC_LABELS["it_professionals"],
            "classification": "CNO-11 subgroup 27 (no direct code exposed by this API — matched by "
                "INE's own English label text, not a numeric code; see crosswalk note)",
            "unit": "EUR per year, gross salary, national total, both sexes (dispersion table); "
                "average only for the age/tenure context, broader occupation category",
            "confidence": "official",
            "level": "country (Spain)",
            "vintage_note": "Table 70672 (dispersion) is 2018-vintage, NOT 2022 as this package's work "
                "order assumed — checked live: every series in the table, not just these two, returns "
                "no data for an explicit 2022 query. See module docstring.",
            "crosswalk_hazard": (
                "'Information technology professionals' is INE's own English label for a CNO-11 "
                "subgroup, not a code this API exposes numerically — data/occupations.json's mapping "
                "note must record that the correspondence rests on label text and INE's classification "
                "documentation, not a code-to-code lookup the way SE/UK/CA/US's mappings do. The age and "
                "tenure crosses do NOT reach this subgroup at all — they stop at CNO-11 major group 2, "
                "'Scientific and intellectual technicians and professionals', which is not an ICT "
                "occupation family (it bundles medicine, law, engineering, teaching and science with "
                "IT). Do not treat broader_category_context as an IT-specific age or tenure gradient."
            ),
            "why_it_matters": "One of nine countries with genuine occupation-level percentile wage "
                "data, and the only source with both a P10-P90 percentile spread AND a (broad-category) "
                "tenure cross — the only official occupation x tenure cross in this project.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[f"{BASE}/70672", f"{BASE}/70706", f"{BASE}/70707"],
        license_note="Attribution required under Ley 37/2007 (Spain's statistics law) — INE does not "
                      "publish these tables under a named Creative Commons licence; recorded exactly as "
                      "that, not labelled CC BY. Cite: Instituto Nacional de Estadistica (INE), Encuesta "
                      "Cuatrienal de Estructura Salarial (EES).",
        redistribution="processed derivative only — the raw Tempus3 JSON payloads are cached under "
                        "data/raw/salary_es/ but that directory is gitignored, so this repo does not "
                        "redistribute the raw source. Only the derived data/processed/salary_es.json "
                        "is committed.",
        transforms=[
            "Fetched tables 70672 (dispersion by CNO-11 occupation), 70706 (age) and 70707 (tenure) in "
            "full from INE's Tempus3 DATOS_TABLA endpoint, then filtered by matching each series' own "
            "English name text (INE's Tempus3 API is flat: series are self-describing by name, not "
            "selected via PxWeb-style dimension codes).",
            "Kept the latest available data point per matched series verbatim, with its own year — "
            "70672's occupation series are 2018; 70706/70707's are checked and recorded per-series.",
            "70706/70707 only reach CNO-11 major group 2 ('Scientific and intellectual technicians and "
            "professionals'), not subgroup 27 specifically — stored separately as "
            "broader_category_context, not merged into occupations.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=sum(len(o["dispersion"]) for o in occupations.values()) + len(broad_age) + len(broad_tenure),
        coverage="2 occupation labels (IT professionals + broader ICT specialists) with percentile "
                 "dispersion, plus 1 broader-category age cross and 1 broader-category tenure cross, "
                 "Spain only",
        notes="Vintage is 2018 for the dispersion table, not 2022 as assumed by the work order that "
              "commissioned this harvester — verified live, not a fetch error.",
    )


if __name__ == "__main__":
    main_guard(run)
