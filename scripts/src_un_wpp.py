"""UN World Population Prospects 2024 → demographic projections to 2100.

Second institutional forecast source. Rendered like every institutional forecast:
solid line, attribution chip ("UN WPP 2024, medium variant"), never blended with
the site's own naive extrapolation.

Endpoint note (matters for reproducibility): the UN Data Portal API's /data/
endpoints now return HTTP 401 without a token — only the metadata endpoints stay
open. The official bulk CSV download is still free and keyless, so that is what
this script uses.
"""
from __future__ import annotations

import csv
import gzip
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, RAW, banner, fetch, log, main_guard, record_provenance,
    to_iso2, write_processed,
)

SOURCE_ID = "un_wpp"
NAME = "UN World Population Prospects 2024 — bulk CSV"
URL = ("https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/"
       "CSV_FILES/WPP2024_TotalPopulationBySex.csv.gz")

# WPP 2024 estimates run through 2023; 2024 onward is projection.
LAST_ESTIMATE_YEAR = 2023
KEEP_VARIANTS = {"Medium", "Estimates"}
START, END = 1990, 2100


def _f(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def run() -> None:
    banner(SOURCE_ID, NAME)
    blob = fetch(URL, dest=RAW / SOURCE_ID / "WPP2024_TotalPopulationBySex.csv.gz")
    text = gzip.decompress(blob).decode("utf-8-sig", errors="replace")

    out: dict[str, dict[str, list]] = {}
    total = 0
    variants_seen: set[str] = set()

    for row in csv.DictReader(io.StringIO(text)):
        variant = (row.get("Variant") or "").strip()
        variants_seen.add(variant)
        if variant not in KEEP_VARIANTS:
            continue
        iso2 = to_iso2((row.get("ISO2_code") or "").strip() or (row.get("ISO3_code") or "").strip())
        if iso2 not in COUNTRY_IDS:
            continue
        year = _f(row.get("Time"))
        if year is None or not (START <= year <= END):
            continue
        year = int(year)
        pop = _f(row.get("PopTotal"))
        dens = _f(row.get("PopDensity"))
        if pop is None:
            continue
        is_proj = year > LAST_ESTIMATE_YEAR
        block = out.setdefault(iso2, {})
        # WPP publishes population in thousands.
        block.setdefault("total_population", []).append(
            {"year": year, "value": pop * 1000, "is_projection": is_proj}
        )
        if dens is not None:
            block.setdefault("population_density", []).append(
                {"year": year, "value": dens, "is_projection": is_proj}
            )
        total += 1

    for country in out.values():
        for series in country.values():
            series.sort(key=lambda r: r["year"])
            seen: set[int] = set()
            series[:] = [p for p in series if not (p["year"] in seen or seen.add(p["year"]))]

    horizon = max(
        (p["year"] for c in out.values() for p in c.get("total_population", []) if p["is_projection"]),
        default=0,
    )
    log(f"    {len(out)}/15 countries, {total:,} rows kept, projections to {horizon}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "edition": "World Population Prospects 2024",
            "institution": "UN DESA Population Division",
            "attribution_chip": "UN WPP 2024, medium variant",
            "kind": "institutional_forecast",
            "variant": "medium (plus historical estimates)",
            "confidence": "official",
            "units": {"total_population": "persons", "population_density": "persons per km2"},
            "projection_rule": f"is_projection = year > {LAST_ESTIMATE_YEAR} (WPP 2024 estimates end there).",
            "render_rule": "Solid, attributed line. Never blended with the site's naive extrapolation.",
            "variants_available_but_not_used": sorted(variants_seen - KEEP_VARIANTS),
            "api_note": (
                "The UN Data Portal /data/ API returns 401 without a token; this script uses the "
                "free bulk CSV instead so `make pipeline` needs no credentials."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[URL],
        license_note=(
            "CC BY 3.0 IGO. Cite: United Nations, Department of Economic and Social Affairs, "
            "Population Division (2024). World Population Prospects 2024."
        ),
        transforms=[
            "Downloaded and gunzipped the 17 MB total-population bulk CSV (~720k rows).",
            "Kept only the 'Estimates' and medium 'Medium' variants; all other projection variants dropped.",
            "Filtered to our 15 countries by ISO2/ISO3 code and to years 1990-2100.",
            "Converted WPP's thousands to persons.",
            f"Marked years after {LAST_ESTIMATE_YEAR} as projections; de-duplicated by year.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=total,
        coverage=f"{len(out)}/15 countries, {START}-{END} (projections from {LAST_ESTIMATE_YEAR + 1})",
        notes="Medium variant only — high/low variants deliberately not shown, to avoid implying a range we did not model.",
    )


if __name__ == "__main__":
    main_guard(run)
