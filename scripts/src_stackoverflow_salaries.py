"""Stack Overflow Developer Survey → CS-specific salary history by country.

The only source in this pipeline that gives DEVELOPER pay by country, role and
experience from the developers themselves — which is exactly the slice this
project is about. Everything else is either all-occupations (OECD) or a single
snapshot (levels.fyi, Numbeo).

Each annual CSV is ~150 MB, so we stream and aggregate rather than loading frames,
and we do not commit the raw files (see .gitignore). Which waves to fetch is
configurable:  SO_YEARS=2019,2021,2023,2024,2025 python scripts/src_stackoverflow_salaries.py

Aggregation is median-based and every bucket carries its sample size, so the UI
can hide or flag thin cells instead of drawing confident lines through n=3.
"""
from __future__ import annotations

import csv
import io
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, RAW, banner, fetch_text, log, main_guard, record_provenance,
    to_iso2, write_processed,
)

SOURCE_ID = "stackoverflow_survey"
NAME = "Stack Overflow Annual Developer Survey — salaries by country"
URL_TMPL = ("https://github.com/StackExchange/Survey/raw/refs/heads/main/packages/"
            "archive/{year}/results.csv")

DEFAULT_YEARS = ["2022", "2023", "2024", "2025"]
MIN_SAMPLE = 5            # buckets thinner than this are kept but flagged
COMP_FLOOR, COMP_CEIL = 5_000, 1_000_000   # drop obvious junk entries

COMP_COLS = ["ConvertedCompYearly", "ConvertedComp", "ConvertedSalary", "Salary"]
COUNTRY_COLS = ["Country"]
EXP_COLS = ["YearsCodePro", "YearsCodedJobPro", "YearsCodedJob"]
ROLE_COLS = ["DevType"]


def _first(row: dict, names: list[str]) -> str | None:
    for n in names:
        if n in row and row[n] not in (None, "", "NA"):
            return row[n]
    return None


def _exp_band(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip().lower()
    if s.startswith("less than"):
        years = 0.5
    elif s.startswith("more than"):
        years = 51.0
    else:
        try:
            years = float(s)
        except ValueError:
            return None
    if years < 3:
        return "new_grad"
    if years < 6:
        return "mid"
    return "senior"


def run() -> None:
    banner(SOURCE_ID, NAME)
    years = [y.strip() for y in os.environ.get("SO_YEARS", ",".join(DEFAULT_YEARS)).split(",") if y.strip()]
    log(f"    waves requested: {', '.join(years)}  (override with SO_YEARS=...)")

    by_country: dict[str, dict[str, dict]] = defaultdict(dict)
    by_role: dict[str, dict[str, dict]] = defaultdict(dict)
    urls: list[str] = []
    failures: list[str] = []
    grand = 0

    for year in years:
        url = URL_TMPL.format(year=year)
        try:
            text = fetch_text(url, dest=RAW / SOURCE_ID / f"{year}_results.csv", retries=2)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{year}: {type(exc).__name__}")
            log(f"    {year}: unavailable ({type(exc).__name__}) — skipped, not imputed")
            continue
        urls.append(url)

        buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
        role_buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
        rows = 0
        for row in csv.DictReader(io.StringIO(text)):
            rows += 1
            iso2 = to_iso2(_first(row, COUNTRY_COLS))
            if iso2 not in COUNTRY_IDS:
                continue
            raw_comp = _first(row, COMP_COLS)
            if raw_comp is None:
                continue
            try:
                comp = float(raw_comp)
            except ValueError:
                continue
            if not (COMP_FLOOR <= comp <= COMP_CEIL):
                continue
            band = _exp_band(_first(row, EXP_COLS))
            buckets[(iso2, band or "all")].append(comp)
            buckets[(iso2, "all")].append(comp)
            devtype = _first(row, ROLE_COLS) or ""
            for role in (r.strip() for r in devtype.split(";")):
                if role:
                    role_buckets[(iso2, role)].append(comp)

        for (iso2, band), vals in buckets.items():
            by_country[iso2].setdefault(year, {})[band] = {
                "median_usd": round(statistics.median(vals)),
                "p25_usd": round(statistics.quantiles(vals, n=4)[0]) if len(vals) >= 4 else None,
                "p75_usd": round(statistics.quantiles(vals, n=4)[2]) if len(vals) >= 4 else None,
                "n": len(vals),
                "thin_sample": len(vals) < MIN_SAMPLE,
            }
        for (iso2, role), vals in role_buckets.items():
            if len(vals) < 3:
                continue
            by_role[iso2].setdefault(year, {})[role] = {
                "median_usd": round(statistics.median(vals)),
                "n": len(vals),
                "thin_sample": len(vals) < MIN_SAMPLE,
            }
        grand += rows
        kept = sum(v["n"] for c in by_country.values() for y, b in c.items() if y == year
                   for k, v in b.items() if k == "all")
        log(f"    {year}: {rows:,} responses → {kept:,} usable in our 15 countries")

    status = "ok" if by_country and not failures else ("partial" if by_country else "failed")
    write_processed(
        SOURCE_ID,
        {"by_country_experience": by_country, "by_country_role": by_role},
        meta={
            "compensation_field": "ConvertedCompYearly (USD, converted by Stack Overflow)",
            "experience_bands": {"new_grad": "<3 years professional", "mid": "3-6", "senior": "6+"},
            "confidence": "crowd",
            "level": "country",
            "waves": years,
            "min_sample_flag": MIN_SAMPLE,
            "outlier_filter": f"responses outside ${COMP_FLOOR:,}-${COMP_CEIL:,} dropped as data-entry noise",
            "self_selection_caveat": (
                "Respondents self-select and skew toward English-speaking, Stack-Overflow-using "
                "developers. Useful for SHAPE and cross-country comparison, weaker as an absolute "
                "level. Every bucket carries n and a thin_sample flag so the UI can say so."
            ),
            "failures": failures,
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=urls,
        license_note=(
            "Stack Overflow releases survey results under the Open Database License (ODbL). "
            "Cite: Stack Overflow Annual Developer Survey."
        ),
        transforms=[
            f"Streamed the annual results CSV for waves: {', '.join(years)} (~150 MB each).",
            "Resolved the free-text Country column to our 15 ISO2 codes; all other responses dropped.",
            f"Dropped compensation outside ${COMP_FLOOR:,}-${COMP_CEIL:,}.",
            "Bucketed by experience (<3 / 3-6 / 6+ professional years) and separately by DevType role.",
            "Computed median plus p25/p75 per bucket, always retaining n and a thin_sample flag.",
            "Raw CSVs are cached locally but excluded from the repo for size (see .gitignore).",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=grand,
        coverage=f"{len(by_country)}/15 countries across {len(urls)} wave(s)",
        status=status,
        notes="Self-selected sample — comparative signal, not an authoritative wage level.",
        redistribution="aggregates committed; raw survey CSVs not committed (size)",
    )


if __name__ == "__main__":
    main_guard(run)
