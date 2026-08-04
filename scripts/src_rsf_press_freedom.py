"""Reporters Without Borders World Press Freedom Index → Freedom theme.

Gives an overall score/rank plus the five RSF sub-indicators (political,
economic, legislative, social, safety), which is what makes this useful beyond a
single number — "safe to be a journalist" and "economically free press" move
independently.

CSV quirks handled: semicolon-delimited, comma decimal separator, ISO3 country
codes, and multilingual country-name columns.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, RAW, banner, fetch, log, main_guard, record_provenance,
    to_iso2, write_processed,
)

SOURCE_ID = "rsf_press_freedom"
NAME = "Reporters Without Borders — World Press Freedom Index"
YEARS = [2026, 2025, 2024, 2023, 2022]
URL_TMPL = "https://rsf.org/sites/default/files/import_classement/{year}.csv"

FIELDS = {
    "score": ["Score {year}", "Score", "score"],
    "rank": ["Rank", "rank"],
    "political": ["Political Context", "Political indicator"],
    "economic": ["Economic Context", "Economic indicator"],
    "legal": ["Legal Context", "Legislative Context", "Legislative indicator"],
    "social": ["Social Context", "Sociocultural Context", "Sociocultural indicator"],
    "safety": ["Safety", "Safety indicator"],
}


def _num(v: str | None) -> float | None:
    if v is None:
        return None
    v = v.strip().replace(",", ".")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _pick(row: dict, names: list[str], year: int) -> str | None:
    for n in names:
        key = n.format(year=year)
        if key in row:
            return row[key]
    return None


def run() -> None:
    banner(SOURCE_ID, NAME)
    out: dict[str, list[dict]] = {}
    urls: list[str] = []
    got_years: list[int] = []

    for year in YEARS:
        url = URL_TMPL.format(year=year)
        try:
            blob = fetch(url, dest=RAW / SOURCE_ID / f"{year}.csv", retries=2)
        except Exception as exc:  # noqa: BLE001 - older vintages may not exist
            log(f"    {year}: unavailable ({type(exc).__name__}) — skipped, not imputed")
            continue
        urls.append(url)
        # 2022-2024 vintages carry a UTF-8 BOM; without utf-8-sig the first column
        # header becomes "﻿ISO" and every row silently fails to resolve.
        text = blob.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        n = 0
        total_ranked = 0
        for row in reader:
            iso2 = to_iso2((row.get("ISO") or "").strip())
            rank = _num(_pick(row, FIELDS["rank"], year))
            if rank is not None:
                total_ranked = max(total_ranked, int(rank))
            if iso2 not in COUNTRY_IDS:
                continue
            rec = {"year": year}
            for key, names in FIELDS.items():
                rec[key] = _num(_pick(row, names, year))
            rec["ranked_of"] = None  # filled below
            out.setdefault(iso2, []).append(rec)
            n += 1
        for iso2 in out:
            for rec in out[iso2]:
                if rec["year"] == year:
                    rec["ranked_of"] = total_ranked
        got_years.append(year)
        log(f"    {year}: {n}/15 countries (of {total_ranked} ranked worldwide)")

    for series in out.values():
        series.sort(key=lambda r: r["year"])

    missing = [c for c in COUNTRY_IDS if c not in out]
    if missing:
        log(f"    !! never present: {', '.join(missing)}")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "score_definition": "RSF composite score 0-100, higher = freer press",
            "sub_indicators": "political, economic, legal, social, safety — each 0-100, higher = better",
            "confidence": "index",
            "years": sorted(got_years),
            "countries_without_data": missing,
            "methodology_break": (
                "RSF changed methodology in 2022; scores before and after are not strictly "
                "comparable. We only fetch 2022+ for that reason."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=urls,
        license_note="RSF publishes the index openly; cite Reporters Without Borders (RSF), World Press Freedom Index.",
        transforms=[
            f"Fetched the per-year CSV for {', '.join(map(str, sorted(got_years)))} (semicolon-delimited).",
            "Converted comma decimal separators to points.",
            "Resolved ISO3 codes to our 15 ISO2 countries; all other rows dropped.",
            "Captured overall score, rank and the five sub-indicators, plus the worldwide ranked count "
            "per year so a rank can be shown with its denominator.",
            "Restricted to 2022+ because RSF's methodology changed that year.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=sum(len(v) for v in out.values()),
        coverage=f"{len(out)}/15 countries, {min(got_years)}-{max(got_years)}",
        notes="Years that failed to download are omitted, never interpolated.",
    )


if __name__ == "__main__":
    main_guard(run)
