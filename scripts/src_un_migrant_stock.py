"""UN DESA International Migrant Stock 2024 → the nationality-mix explorer.

Table 1 is a full origin x destination matrix. For each of our 15 destinations we
keep:
  * total foreign-born stock per reference year (1990 → 2024)
  * the full origin breakdown for the latest year (powers "find people from ...")
  * the Iranian-born series specifically, because that is the diaspora question
    this project exists to answer

Gotcha (verified): un.org returns HTTP 403 to default Python user agents.
scripts/_common.py always sends a browser-like User-Agent.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, IRAN_M49, ISO2_TO_M49, RAW, banner, fetch, log, main_guard,
    record_provenance, write_processed,
)

SOURCE_ID = "un_migrant_stock"
NAME = "UN DESA — International Migrant Stock 2024 (by destination and origin)"
URL = ("https://www.un.org/development/desa/pd/sites/www.un.org.development.desa.pd/files/"
       "undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx")

SHEET = "Table 1"
HEADER_ROW = 11
# Aggregate rows (World, regions, income groups) share the 900-series / 1800-series
# location codes. Real countries have codes below 900.
MAX_COUNTRY_CODE = 900


def run() -> None:
    banner(SOURCE_ID, NAME)
    blob = fetch(URL, dest=RAW / SOURCE_ID / "migrant_stock_2024.xlsx")
    wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    ws = wb[SHEET]

    rows = ws.iter_rows(values_only=True)
    header = None
    for i, r in enumerate(rows, start=1):
        if i == HEADER_ROW:
            header = list(r)
            break
    if header is None:
        raise RuntimeError("could not locate the header row in Table 1")

    # Year columns repeat THREE times across the sheet: both sexes, then male,
    # then female (merged headers on row 10). Taking every 4-digit header would
    # silently interleave all three blocks into one series, so we keep only the
    # first occurrence of each year — the both-sexes block.
    year_cols: list[tuple[int, int]] = []
    seen_years: set[int] = set()
    for idx, cell in enumerate(header):
        try:
            y = int(str(cell).strip())
        except (TypeError, ValueError):
            continue
        if 1980 <= y <= 2035 and y not in seen_years:
            seen_years.add(y)
            year_cols.append((idx, y))
    i_dest = 4   # "Location code of destination"
    i_orig = 6   # "Location code of origin"
    i_dest_name, i_orig_name = 1, 5
    log(f"    reference years: {', '.join(str(y) for _, y in year_cols)}")

    m49_to_iso2 = {m: c for c, m in ISO2_TO_M49.items()}
    dest_codes = set(ISO2_TO_M49.values())

    totals: dict[str, list] = {}
    origins: dict[str, list] = {}
    iranian: dict[str, list] = {}
    latest_year = year_cols[-1][1]
    scanned = 0

    for r in rows:
        if r is None or len(r) <= i_orig:
            continue
        try:
            dest = int(r[i_dest])
            orig = int(r[i_orig])
        except (TypeError, ValueError):
            continue
        if dest not in dest_codes:
            continue
        iso2 = m49_to_iso2[dest]
        scanned += 1

        def series() -> list[dict]:
            out = []
            for idx, y in year_cols:
                v = r[idx] if idx < len(r) else None
                if isinstance(v, (int, float)):
                    out.append({"year": y, "value": int(v)})
            return out

        if orig == 900:  # origin = World → the total foreign-born stock
            totals[iso2] = series()
        elif orig == IRAN_M49:
            iranian[iso2] = series()

        if orig < MAX_COUNTRY_CODE and orig != 900:
            latest = next((p["value"] for p in reversed(series()) if p["year"] == latest_year), None)
            if latest:
                origins.setdefault(iso2, []).append(
                    {"origin_m49": orig, "origin": str(r[i_orig_name]).strip(), "value": latest}
                )

    for iso2, lst in origins.items():
        lst.sort(key=lambda x: -x["value"])

    log(f"    scanned {scanned:,} destination rows for our 15 countries")
    log(f"    totals: {len(totals)}/15 · origin breakdowns: {len(origins)}/15 · Iranian-born: {len(iranian)}/15")
    for iso2 in COUNTRY_IDS:
        ir = iranian.get(iso2, [])
        if ir:
            log(f"      {iso2}: Iranian-born {ir[-1]['value']:>9,} ({ir[-1]['year']})")

    write_processed(
        SOURCE_ID,
        {
            "total_foreign_born": totals,
            "origins_latest": origins,
            "iranian_born": iranian,
            "latest_year": latest_year,
        },
        meta={
            "definition": "Migrant stock = people living in a country who were born in another country.",
            "reference_years": [y for _, y in year_cols],
            "confidence": "official",
            "level": "country",
            "counts_not_shares": (
                "These are absolute head counts. Share of population is computed in the site from "
                "World Bank population, and the computation is shown."
            ),
            "origin_filter": "Origin rows with location codes >= 900 are regional aggregates and are excluded from the breakdown.",
            "iran_note": (
                "Iranian-born stock is extracted explicitly (M49 364) because diaspora size is a "
                "primary question for this project's audience."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[URL],
        license_note=(
            "UN public data, free to use with attribution. Cite: United Nations Department of "
            "Economic and Social Affairs, Population Division (2024). International Migrant Stock 2024."
        ),
        transforms=[
            "Downloaded the 6 MB origin-by-destination workbook with a browser User-Agent (un.org 403s otherwise).",
            "Read 'Table 1', locating the header at row 11 and detecting year columns by 4-digit headers.",
            "Kept rows whose destination M49 code is one of our 15 countries.",
            "Split into: total foreign-born (origin = World/900), per-origin breakdown for the latest "
            "reference year (country origins only, codes < 900), and the Iranian-born series (M49 364).",
            "Sorted origin breakdowns by descending stock. No estimation of missing corridors.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=scanned,
        coverage=f"{len(totals)}/15 destinations, reference years {year_cols[0][1]}-{latest_year}",
        notes="Absolute counts; shares are computed in-site against World Bank population and shown as a formula.",
    )


if __name__ == "__main__":
    main_guard(run)
