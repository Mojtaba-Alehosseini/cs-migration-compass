"""EF EPI (English proficiency) + WIPO GII (innovation) -> two PDF-only indices.

Both publish their country tables as PDFs only, so both are extracted by
parsing the PDF's own layout. That is inherently more fragile than an API,
so the extraction is made to check itself: EVERY country in the table is
extracted, not just the 15 this site needs, which turns the parse into a
structure that can be validated against the publication's own numbers --
a complete rank sequence, monotonic scores, a row count matching the
publisher's stated total, every score in the publisher's own range. See
pdf_table.py and audit_data.py's check_full_table_self_consistency().

Gotcha (verified): ef.com and tind.wipo.int both 403 default Python user
agents. scripts/_common.py always sends a browser-like User-Agent.

Gotcha (verified, unresolved -- see NEEDS-DECISION.md): WIPO's PDF delivery
now sits behind an AWS WAF JS challenge on EVERY URL shape tried, including
the tind.wipo.int/record path that the 2024-edition file used successfully
with nothing but a browser User-Agent. A plain unattended `requests` fetch
gets HTTP 202 with an empty body (`x-amzn-waf-action: challenge`), not the
PDF. fetch()'s own dest-file cache means this only bites on a checkout that
has never successfully fetched this URL before -- see NEEDS-DECISION.md for
what that means for the scheduled refresh and the options considered.
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

EF_URL = ("https://www.ef.com/assetscdn/WIBIwq6RdJvcD9bc8RMd/cefcom-epi-site/reports/2025/"
          "ef-epi-2025-english.pdf")
# 2024 edition (17th, tind.wipo.int/record/50062) went dead sometime after
# it was first wired up -- an empty response body, not a 404. This is the
# 2025 edition (18th), found via the 2024 PDF's own DOI (10.34667/tind.58864)
# resolved at https://doi.org/10.34667/tind.58864 -> tind.wipo.int/record/58864.
GII_URL = ("https://tind.wipo.int/record/58864/files/"
           "wipo-pub-2000-2025-en-global-innovation-index-2025-innovation-at-a-crossroads.pdf")

# GII's composite score is WIPO's own defined 0-100 scale (their methodology
# combines many 0-100 sub-indicators into one 0-100 index) -- a genuine
# publisher-stated bound, not fitted to what this repo happens to observe.
# EF EPI has no equivalent publicly fixed theoretical bound; EF_RANGE is
# honestly a plausibility band, not a publisher scale -- generous headroom
# on both sides of the observed 2025 data (390.0-624.0) so it still catches
# a genuine parsing error (e.g. a rank number landing in the score field)
# without pretending to be authoritative the way GII_RANGE is. Both are
# read into full_table_stats["range"] below and checked in
# audit_data.py's check_full_table_self_consistency(), never used to filter
# rows during extraction -- the full table is kept regardless of range.
EF_RANGE = (300.0, 750.0)
GII_RANGE = (0.0, 100.0)


def extract_full_table(blob: bytes, *, page_index: int, fields_per_group: int
                        ) -> list[tuple[int, str, float, int]]:
    """Parse ONE PDF page's column-group ranking table via word geometry.

    `page_index` and `fields_per_group` are specific to one edition's PDF
    layout, verified by hand against the file this package shipped with
    (see REPORT-P19.md's Tier 1 evidence: 123/123 EF EPI rows, 139/139 WIPO
    GII rows, matched against each publisher's own web summary). A future
    edition can shift its table to a different page -- that shows up as a
    row-count/gap/monotonicity failure in audit_data.py's
    check_full_table_self_consistency(), not a silent wrong answer, because
    the full table (not just our 15 countries) ships in `meta.full_table`
    for that check to see.
    """
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        page = pdf.pages[page_index]
        words = page.extract_words()
    groups = find_columns(words, fields_per_group=fields_per_group)
    return parse_table(words, groups)


def one(source_id: str, name: str, url: str, filename: str, rng: tuple[float, float],
        *, page_index: int, fields_per_group: int, published_total: int,
        definition: str, license_note: str, confidence: str = "index",
        missing_note: str | None = None) -> None:
    banner(source_id, name)
    try:
        blob = fetch(url, dest=RAW / source_id / filename, retries=2)
    except Exception as exc:  # noqa: BLE001
        log(f"    unavailable: {type(exc).__name__}: {exc}")
        write_processed(source_id, {}, meta={"status": "unavailable", "error": str(exc)})
        record_provenance(
            source_id=source_id, name=name, urls=[url], license_note=license_note,
            transforms=["Download failed; nothing extracted, nothing estimated."],
            output=f"data/processed/{source_id}.json", status="failed",
            coverage="0/15 countries",
            notes="PDF unreachable at build time — treated as missing data, not filled in.",
        )
        return

    full_rows = extract_full_table(blob, page_index=page_index, fields_per_group=fields_per_group)

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
            "source_line": f"page {page_index + 1}, rank {rank}/{published_total}: {row_name} = {score}",
        }
    if conflicts:
        log(f"    !! {len(conflicts)} country matched two different rows: {'; '.join(conflicts)}")

    missing = [c for c in COUNTRY_IDS if c not in out]
    log(f"    extracted {len(full_rows)} total rows from page {page_index + 1}; "
        f"{len(out)}/15 of our countries resolved")
    if missing:
        log(f"    !! not found: {', '.join(missing)} (left missing, never guessed)")

    write_processed(
        source_id, out,
        meta={
            "definition": definition,
            "confidence": confidence,
            "level": "country",
            "extraction": "PDF word-geometry column parsing (pdf_table.py)",
            "countries_without_data": missing,
            "countries_without_data_note": missing_note,
            "fragility_caveat": (
                "Extracted from a PDF's own layout, not a data file. The FULL published table is "
                "parsed (not just our 15 countries) and kept below in full_table/full_table_stats so "
                "it can be checked against the publisher's own row count, rank sequence and range -- "
                "see audit_data.py's check_full_table_self_consistency(). 'source_line' on each of our "
                "15 countries names the exact rank and page it came from for manual audit."
            ),
            "full_table": [{"rank": r, "name": n, "score": s} for r, n, s, _gi in full_rows],
            "full_table_stats": {
                "row_count": len(full_rows),
                "published_total": published_total,
                "range": list(rng),
                "higher_is_better": True,  # both sources: rank 1 = highest score
                "extraction": (
                    f"page {page_index + 1} (1-indexed), {fields_per_group} fields per column group, "
                    "pdf_table.parse_table()"
                ),
            },
        },
    )
    record_provenance(
        source_id=source_id, name=name, urls=[url], license_note=license_note,
        transforms=[
            "Downloaded the published PDF with a browser User-Agent (both hosts 403 otherwise).",
            f"Extracted word geometry from page {page_index + 1} with pdfplumber.extract_words().",
            "Reconstructed the table's column groups from repeated word x-positions, then parsed "
            "each column group independently so a neighbouring column's digits can never be read "
            "as this column's score (see pdf_table.py).",
            f"Extracted all {len(full_rows)} published rows, not just our 15 countries, so the table "
            "validates itself against the publisher's own row count, rank sequence and range.",
            "Matched each row's name to our 15 countries with the shared to_iso2() resolver.",
            "Countries not confidently matched are omitted rather than guessed.",
        ],
        output=f"data/processed/{source_id}.json",
        rows=len(out),
        coverage=f"{len(out)}/15 countries",
        status="ok" if out else "partial",
        notes=f"Full table: {len(full_rows)}/{published_total} rows extracted. "
              "PDF parsing is fragile by nature; every value carries its source line.",
    )


def run() -> None:
    one(
        "ef_epi", "EF English Proficiency Index 2025", EF_URL, "ef-epi-2025.pdf", EF_RANGE,
        page_index=4, fields_per_group=3, published_total=123,
        definition="EF EPI score (roughly 400-700); higher = stronger English proficiency among non-native speakers.",
        license_note="EF publishes the EPI report freely; cite EF Education First, EF English Proficiency Index 2025.",
        missing_note=(
            "EF EPI only scores countries where English is NOT a native language, so Australia, the "
            "US, Canada, the UK and Ireland are absent BY DESIGN, not through a failed extraction. "
            "For those countries the site shows 'English is the native language' instead of a score."
        ),
    )
    one(
        "wipo_gii", "WIPO Global Innovation Index 2025", GII_URL, "wipo-gii-2025.pdf", GII_RANGE,
        page_index=17, fields_per_group=5, published_total=139,
        definition="GII overall innovation score (0-100) and rank; higher = stronger innovation ecosystem.",
        license_note="WIPO publishes the GII under CC BY 4.0 (some content excepted); cite WIPO, Global Innovation Index 2025.",
        missing_note=(
            "A country is missing here only if the full 139-row table (see full_table below) contains "
            "no row whose name resolves to it via _common.to_iso2() -- as of this edition all 15 of "
            "our countries resolve. (An earlier version of this extraction flattened the PDF's two "
            "side-by-side columns into one text stream, which interleaved unrelated countries' rows "
            "onto the same line and lost the US and the Netherlands outright; that is fixed by parsing "
            "column geometry instead of flattened text -- see pdf_table.py.)"
        ),
    )


if __name__ == "__main__":
    main_guard(run)
