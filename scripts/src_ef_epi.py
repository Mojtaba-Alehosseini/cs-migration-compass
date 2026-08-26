"""EF English Proficiency Index -> country proficiency scores and ranks.

Split out of the former src_pdf_indices.py in package 20, which moved
wipo_gii to WIPO's own CSV endpoint (see src_wipo_gii.py) once one was
found. ef.com/wwen/epi/ was checked for the same trick (package 20, Tier 2)
and does not have one, so this stays a PDF parse. What was actually
checked, so a future package does not have to redo it from scratch: the
page is a Next.js/Storyblok app; its `__NEXT_DATA__` SSR payload was
inspected in full and carries only CMS layout config for the ranking
section (271 bytes -- titles, spacing, background colour, no scores);
clicking "Load more" reveals additional rows with ZERO new network
requests, meaning the full dataset is already resident client-side by the
time the page loads, not fetched from a discoverable public endpoint on
demand; every loaded JS chunk was searched for the ranking data directly
(using "Zimbabwe" as a marker distinctive enough not to appear in
boilerplate) and the one hit found was an unrelated generic
country-calling-code list, not ranking data. However the full table
actually reaches the client, it is not doing so via a plain,
fetchable-outside-a-browser data file the way WIPO's CSV does -- the PDF
stays the extraction path here, verified against 123/123 published rows
(REPORT-P19.md).

The extraction is made to check itself: EVERY country in the table is
extracted, not just the 15 this site needs, which turns the parse into a
structure that can be validated against the publication's own numbers --
a complete rank sequence, monotonic scores, a row count matching the
publisher's stated total, every score in range. See pdf_table.py and
audit_data.py's check_full_table_self_consistency().

Gotcha (verified): ef.com 403s the default Python user agent.
scripts/_common.py always sends a browser-like User-Agent.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, RAW, banner, fetch, log, main_guard,
    record_provenance, to_iso2, write_processed,
)
from pdf_table import find_columns, parse_table  # noqa: E402

SOURCE_ID = "ef_epi"
NAME = "EF English Proficiency Index 2025"
URL = ("https://www.ef.com/assetscdn/WIBIwq6RdJvcD9bc8RMd/cefcom-epi-site/reports/2025/"
       "ef-epi-2025-english.pdf")
FILENAME = "ef-epi-2025.pdf"
PAGE_INDEX = 4          # 0-indexed; verified by hand, see REPORT-P19.md Tier 1
FIELDS_PER_GROUP = 3    # (rank, name, score) column groups
PUBLISHED_TOTAL = 123   # EF's own stated "123 countries and regions"

# EF EPI has no publicly fixed theoretical bound; this is honestly a
# plausibility band, not a publisher scale -- generous headroom on both
# sides of the observed 2025 data (390.0-624.0) so it still catches a
# genuine parsing error (e.g. a rank number landing in the score field).
# Read into full_table_stats["range"] below and checked in audit_data.py's
# check_full_table_self_consistency(), never used to filter rows during
# extraction -- the full table is kept regardless of range.
RANGE = (300.0, 750.0)

DEFINITION = "EF EPI score (roughly 400-700); higher = stronger English proficiency among non-native speakers."
LICENSE_NOTE = "EF publishes the EPI report freely; cite EF Education First, EF English Proficiency Index 2025."
MISSING_NOTE = (
    "EF EPI only scores countries where English is NOT a native language, so Australia, the "
    "US, Canada, the UK and Ireland are absent BY DESIGN, not through a failed extraction. "
    "For those countries the site shows 'English is the native language' instead of a score."
)


def extract_full_table(blob: bytes) -> list[tuple[int, str, float, int]]:
    """Parse the PDF's column-group ranking table via word geometry.

    PAGE_INDEX and FIELDS_PER_GROUP are specific to this edition's PDF
    layout, verified by hand (see REPORT-P19.md's Tier 1 evidence: 123/123
    rows matched against EF's own web summary). A future edition can shift
    its table to a different page -- that shows up as a row-count/gap/
    monotonicity failure in audit_data.py's check_full_table_self_consistency(),
    not a silent wrong answer, because the full table (not just our 15
    countries) ships in meta.full_table for that check to see.
    """
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        page = pdf.pages[PAGE_INDEX]
        words = page.extract_words()
    groups = find_columns(words, fields_per_group=FIELDS_PER_GROUP)
    return parse_table(words, groups)


def run() -> None:
    banner(SOURCE_ID, NAME)
    try:
        blob = fetch(URL, dest=RAW / SOURCE_ID / FILENAME, retries=2)
    except Exception as exc:  # noqa: BLE001
        log(f"    unavailable: {type(exc).__name__}: {exc}")
        write_processed(SOURCE_ID, {}, meta={"status": "unavailable", "error": str(exc)})
        record_provenance(
            source_id=SOURCE_ID, name=NAME, urls=[URL], license_note=LICENSE_NOTE,
            transforms=["Download failed; nothing extracted, nothing estimated."],
            output=f"data/processed/{SOURCE_ID}.json", status="failed",
            coverage="0/15 countries",
            notes="PDF unreachable at build time — treated as missing data, not filled in.",
        )
        return

    full_rows = extract_full_table(blob)

    out: dict[str, dict] = {}
    conflicts: list[str] = []
    for rank, row_name, score, _gi in full_rows:
        iso2 = to_iso2(row_name)
        if iso2 is None or iso2 not in COUNTRY_IDS:
            continue
        if iso2 in out and out[iso2]["rank"] != rank:
            conflicts.append(f"{iso2}: rank {out[iso2]['rank']} then rank {rank} ({row_name!r})")
            continue
        out[iso2] = {
            "score": score,
            "rank": rank,
            "source_line": f"page {PAGE_INDEX + 1}, rank {rank}/{PUBLISHED_TOTAL}: {row_name} = {score}",
        }
    if conflicts:
        log(f"    !! {len(conflicts)} country matched two different rows: {'; '.join(conflicts)}")

    missing = [c for c in COUNTRY_IDS if c not in out]
    log(f"    extracted {len(full_rows)} total rows from page {PAGE_INDEX + 1}; "
        f"{len(out)}/15 of our countries resolved")
    if missing:
        log(f"    !! not found: {', '.join(missing)} (left missing, never guessed)")

    write_processed(
        SOURCE_ID, out,
        meta={
            "definition": DEFINITION,
            "confidence": "index",
            "level": "country",
            "extraction": "PDF word-geometry column parsing (pdf_table.py)",
            "countries_without_data": missing,
            "countries_without_data_note": MISSING_NOTE,
            "fragility_caveat": (
                "Extracted from a PDF's own layout, not a data file. The FULL published table is "
                "parsed (not just our 15 countries) and kept below in full_table/full_table_stats so "
                "it can be checked against the publisher's own row count, rank sequence and range -- "
                "see audit_data.py's check_full_table_self_consistency(). 'source_line' on each of our "
                "15 countries names the exact rank and page it came from for manual audit. (WIPO GII "
                "moved off this PDF-parsing pattern in package 20 once its own CSV was found -- see "
                "src_wipo_gii.py. EF EPI was checked for an equivalent data file the same package and "
                "does not have one -- see this file's own module docstring for what was checked.)"
            ),
            "full_table": [{"rank": r, "name": n, "score": s} for r, n, s, _gi in full_rows],
            "full_table_stats": {
                "row_count": len(full_rows),
                "published_total": PUBLISHED_TOTAL,
                "range": list(RANGE),
                "higher_is_better": True,
                "extraction": (
                    f"page {PAGE_INDEX + 1} (1-indexed), {FIELDS_PER_GROUP} fields per column group, "
                    "pdf_table.parse_table()"
                ),
            },
        },
    )
    record_provenance(
        source_id=SOURCE_ID, name=NAME, urls=[URL], license_note=LICENSE_NOTE,
        transforms=[
            "Downloaded the published PDF with a browser User-Agent (ef.com 403s otherwise).",
            f"Extracted word geometry from page {PAGE_INDEX + 1} with pdfplumber.extract_words().",
            "Reconstructed the table's column groups from repeated word x-positions, then parsed "
            "each column group independently so a neighbouring column's digits can never be read "
            "as this column's score (see pdf_table.py).",
            f"Extracted all {len(full_rows)} published rows, not just our 15 countries, so the table "
            "validates itself against the publisher's own row count, rank sequence and range.",
            "Matched each row's name to our 15 countries with the shared to_iso2() resolver.",
            "Countries not confidently matched are omitted rather than guessed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(out),
        coverage=f"{len(out)}/15 countries",
        status="ok" if out else "partial",
        notes=f"Full table: {len(full_rows)}/{PUBLISHED_TOTAL} rows extracted. "
              "PDF parsing is fragile by nature; every value carries its source line.",
        redistribution=(
            f"processed derivative only -- the raw PDF is cached under data/raw/{SOURCE_ID}/ but that "
            "directory is gitignored, so this repo does not redistribute it. Only the 15-country "
            f"slice and the full extracted table are committed, in data/processed/{SOURCE_ID}.json."
        ),
    )


if __name__ == "__main__":
    main_guard(run)
