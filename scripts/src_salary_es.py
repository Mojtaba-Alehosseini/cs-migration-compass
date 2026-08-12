"""INE (Instituto Nacional de Estadistica) Tempus3 API -> Spanish IT wages.

Four tables from INE, spanning two different surveys:

  70672  means and percentiles by sex and CNO-11 occupation subgroup (EES, operation 121)
  70706  average gross salary by sex, occupation and AGE band (EES, operation 121)
  70707  average gross salary by sex, occupation and TENURE band (EES, operation 121)
  28186  average gross ANNUAL salary by sex and major occupation group (EAES, operation 140)

70672/70706/70707 are the Encuesta Cuatrienal de Estructura Salarial (EES —
"Quadrennial" Wage Structure Survey); 28186 is the Encuesta ANUAL de
Estructura Salarial (EAES, operation 140) — a DIFFERENT, annual survey whose
series happen to share the same "EAES" code PREFIX as 70672's series
(EAES5770 etc.), which is exactly why it is easy to fetch the wrong table by
matching on the prefix alone rather than the actual table/operation ID.
28186 is added this package for currency: package 9's normalisation work
needs a currently-updated (2024, not 2018) Spain reference point even though
it cannot reach IT-specific occupation depth — see below.

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

# Table 28186 (EAES, operation 140 — a different, annual survey): the
# national "all occupations" headline series, added for currency. Verified
# live: series EAES2556 = "All occupations. Both genders. Average gross
# salary. National Total. Base data." — 2024 value 29,540.26, matching this
# package's own work order exactly. NOT IT-specific at any depth.
NATIONAL_REF_TABLE = "28186"
NATIONAL_REF_COD = "EAES2556"
NATIONAL_REF_LABEL = "All occupations. Both genders. Average gross salary. National Total. Base data."


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
    ref_rows = _fetch_table(NATIONAL_REF_TABLE)

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

    ref_series = next((s for s in ref_rows if s["COD"] == NATIONAL_REF_COD), None)
    ref_data = (ref_series or {}).get("Data") or []
    # NOT ref_data[-1]: this series' Data array is ordered NEWEST-first
    # (2024, 2023, ..., 2008) — the opposite order from 70672/70706/70707's
    # single-year series, where [-1] happened to work only because there was
    # nothing else in the array to get wrong. Caught by this script's own
    # first run: it logged "2008" as the reference year until fixed to pick
    # by max(Anyo) explicitly, order-independent.
    ref_latest = max(ref_data, key=lambda row: row["Anyo"]) if ref_data else None
    national_reference = {
        "label": NATIONAL_REF_LABEL,
        "scope": "ALL occupations, both sexes — NOT IT-specific at any depth. Added for currency: "
                 "the EES dispersion table above (70672) is 2018-vintage; this EAES annual series "
                 "reaches 2024. Use only as a general economy-wide reference point.",
        "mean_eur_year": ref_latest["Valor"] if ref_latest else None,
        "year": ref_latest["Anyo"] if ref_latest else None,
        "history_eur_year": {str(row["Anyo"]): row["Valor"] for row in ref_data},
    }
    log(f"    national reference (28186, {NATIONAL_REF_COD}) {national_reference['year']}: "
        f"{national_reference['mean_eur_year']}")

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
        "national_reference": national_reference,
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
                "no data for an explicit 2022 query. See module docstring. national_reference (table "
                "28186, a different survey) reaches 2024 — added in package 9 specifically to give a "
                "currently-updated Spain reference point alongside the stale IT-specific figures.",
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
        urls=[f"{BASE}/70672", f"{BASE}/70706", f"{BASE}/70707", f"{BASE}/{NATIONAL_REF_TABLE}"],
        license_note="Attribution required under Ley 37/2007 (Spain's statistics law) — INE does not "
                      "publish these tables under a named Creative Commons licence; recorded exactly as "
                      "that, not labelled CC BY. Cite: Instituto Nacional de Estadistica (INE), Encuesta "
                      "Cuatrienal de Estructura Salarial (EES) for 70672/70706/70707, Encuesta Anual de "
                      "Estructura Salarial (EAES) for 28186.",
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
            f"Fetched table {NATIONAL_REF_TABLE} (a different survey, EAES operation 140) and kept "
            f"series {NATIONAL_REF_COD} ('{NATIONAL_REF_LABEL}') in full, all 17 years (2008-2024) — "
            "added this package for a currently-updated national reference point. Package 8's own "
            "adversarial review lesson applied here too: this table's series share the same 'EAES' "
            "code prefix as 70672's, so it was matched by table ID (28186) and the series' own full "
            "name text, not by prefix alone.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=sum(len(o["dispersion"]) for o in occupations.values()) + len(broad_age) + len(broad_tenure)
             + len(ref_data),
        coverage="2 occupation labels (IT professionals + broader ICT specialists) with percentile "
                 "dispersion, plus 1 broader-category age cross and 1 broader-category tenure cross, "
                 "plus a 17-year all-occupations national reference series, Spain only",
        notes="Vintage is 2018 for the dispersion table, not 2022 as assumed by the work order that "
              "commissioned this harvester — verified live, not a fetch error.",
    )


if __name__ == "__main__":
    main_guard(run)
