"""WIPO Global Innovation Index -> country innovation scores and ranks.

Package 19 parsed this from WIPO's own PDF via word-geometry reconstruction,
which worked (139/139 rows verified) but could not be fetched unattended:
every WIPO PDF-delivery URL sits behind an AWS WAF JS challenge (see
REPORT-P19.md, NEEDS-DECISION #55). Package 20 found the actual data source
instead: wipo.int/gii-ranking/en/ is a Nuxt app, and it loads its own
ranking table client-side from a plain CSV endpoint --

    https://www.wipo.int/gii-ranking/data/bc_results_gii_<year>.csv

-- found by reading what the page's own front end requests, not guessed.
Verified live: HTTP 200, no WAF, no cookie, no JS challenge, plain
urllib/requests with a browser User-Agent. It carries `iso3` directly, so
country matching is an exact ISO3 lookup, not the name-string matching that
lost the Netherlands ("Netherlands (Kingdom of the)") when this was PDF
text. No layout parsing, no pdf_table.py -- csv.DictReader plus one decimal
fixup.

Gotcha (verified): the CSV formats decimals with a COMMA, not a point, and
quotes any field containing one so the comma is not read as a delimiter --
`"65,96195221"` for Switzerland's score. `float()` on that string raises
ValueError; every numeric field this script reads goes through
_parse_decimal_comma() instead of a bare float()/int() cast.

Kept: the same full-table self-checking pattern package 19 built --
EVERY economy is extracted, not just the 15 this site needs, so the parse
validates itself against the publisher's own row count, rank sequence and
range in audit_data.py's check_full_table_self_consistency(). That check
does not care whether the table came from a PDF or a CSV; only the
extraction method below changed.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, RAW, banner, fetch_text, log, main_guard,
    record_provenance, to_iso2, write_processed,
)

SOURCE_ID = "wipo_gii"
NAME = "WIPO Global Innovation Index 2025"
EDITION_YEAR = "2025"
URL = f"https://www.wipo.int/gii-ranking/data/bc_results_gii_{EDITION_YEAR}.csv"
FILENAME = f"gii-{EDITION_YEAR}.csv"
PUBLISHED_TOTAL = 139  # WIPO's own stated "139 economies featured in GII 2025"

# GII's composite score is WIPO's own defined 0-100 scale (their methodology
# combines many 0-100 sub-indicators into one 0-100 index) -- a genuine
# publisher-stated bound, not fitted to what this repo happens to observe.
RANGE = (0.0, 100.0)

DEFINITION = "GII overall innovation score (0-100) and rank; higher = stronger innovation ecosystem."
LICENSE_NOTE = ("WIPO publishes the GII under CC BY 4.0 (some content excepted); "
                 "cite WIPO, Global Innovation Index 2025.")
MISSING_NOTE = (
    "A country is missing here only if the full 139-row table (see full_table below) contains "
    "no row whose iso3 resolves to it via _common.to_iso2() -- as of this edition all 15 of our "
    "countries resolve. (Package 19's PDF extraction lost the US and the Netherlands to flattened-"
    "text column interleaving and name-form mismatches; keying on the CSV's own iso3 field removes "
    "name matching from this source entirely, not just the specific mismatch that caused it.)"
)


def _parse_decimal_comma(s: str) -> float:
    """WIPO's CSV writes decimals as '65,96195221', quoted so the comma is
    not read as a field delimiter -- a plain float() raises ValueError on
    that string (comma is not a valid character in a Python float literal).
    Thousands-grouping is not a risk for the fields this script reads (GII
    scores run 0-100, never three digits before the point), so a single
    comma-to-point substitution is the correct, sufficient fix here."""
    return float(s.strip().replace(",", "."))


def fetch_full_table() -> list[dict]:
    """Fetch and parse the CSV into (rank, iso3, name, score) rows, sorted
    by rank. Raises on a malformed row rather than silently dropping it --
    a CSV row missing rank/iso3/score is exactly the kind of silent-wrong-
    answer risk this package exists to avoid, and the caller's own except
    block turns that into the same honest 'unavailable' status a fetch
    failure already gets."""
    text = fetch_text(URL, dest=RAW / SOURCE_ID / FILENAME, retries=2)
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append({
            "iso3": row["iso3"].strip(),
            "name": row["economy_name"].strip(),
            "rank": int(row["rank"]),
            "score": _parse_decimal_comma(row["score"]),
            "giiyr": row["giiyr"].strip(),
        })
    rows.sort(key=lambda r: r["rank"])
    return rows


def run() -> None:
    banner(SOURCE_ID, NAME)
    try:
        full_rows = fetch_full_table()
    except Exception as exc:  # noqa: BLE001
        log(f"    unavailable: {type(exc).__name__}: {exc}")
        write_processed(SOURCE_ID, {}, meta={"status": "unavailable", "error": str(exc)})
        record_provenance(
            source_id=SOURCE_ID, name=NAME, urls=[URL], license_note=LICENSE_NOTE,
            transforms=["Download failed; nothing extracted, nothing estimated."],
            output=f"data/processed/{SOURCE_ID}.json", status="failed",
            coverage="0/15 countries",
            notes="CSV unreachable or malformed at build time — treated as missing data, not filled in.",
        )
        return

    # Edition sanity: the filename is year-stamped, so a genuinely new
    # edition almost certainly means a new URL (as the 2024 PDF's own death
    # demonstrated) -- but the CSV's own giiyr column is a second, cheap
    # signal that this specific fetch actually served the edition its URL
    # claims to. Not hard-failed: one economy (Venezuela, checked by hand)
    # already carries giiyr="NA" in a genuinely current file, so a strict
    # "every row must match" rule would be a check tuned to fail on real,
    # correct data -- flagged loudly instead, majority-based.
    edition_counts: dict[str, int] = {}
    for r in full_rows:
        edition_counts[r["giiyr"]] = edition_counts.get(r["giiyr"], 0) + 1
    majority_year, majority_count = max(edition_counts.items(), key=lambda kv: kv[1])
    edition_mismatch = None
    if majority_year != EDITION_YEAR:
        edition_mismatch = (
            f"CSV's own giiyr column majority ({majority_year}, {majority_count}/{len(full_rows)} rows) "
            f"does not match the edition this script requested ({EDITION_YEAR}) -- possible stale or "
            "wrong file served under the expected URL."
        )
        log(f"    !! {edition_mismatch}")

    out: dict[str, dict] = {}
    conflicts: list[str] = []
    for r in full_rows:
        iso2 = to_iso2(r["iso3"])
        if iso2 is None or iso2 not in COUNTRY_IDS:
            continue
        if iso2 in out and out[iso2]["rank"] != r["rank"]:
            conflicts.append(f"{iso2}: rank {out[iso2]['rank']} then rank {r['rank']} ({r['iso3']!r})")
            continue
        out[iso2] = {
            "score": r["score"],
            "rank": r["rank"],
            "iso3": r["iso3"],
            "source_line": f"iso3={r['iso3']}, rank {r['rank']}/{PUBLISHED_TOTAL}: {r['name']} = {r['score']}",
        }
    if conflicts:
        log(f"    !! {len(conflicts)} country matched two different rows: {'; '.join(conflicts)}")

    missing = [c for c in COUNTRY_IDS if c not in out]
    log(f"    extracted {len(full_rows)} total rows from the CSV; "
        f"{len(out)}/15 of our countries resolved")
    if missing:
        log(f"    !! not found: {', '.join(missing)} (left missing, never guessed)")

    write_processed(
        SOURCE_ID, out,
        meta={
            "definition": DEFINITION,
            "confidence": "index",
            "level": "country",
            "extraction": "CSV, keyed on iso3 (csv.DictReader + decimal-comma fixup)",
            "countries_without_data": missing,
            "countries_without_data_note": MISSING_NOTE,
            "edition_mismatch": edition_mismatch,
            "fragility_caveat": (
                "Extracted from a data file this time, not a PDF layout -- but still checked the same "
                "way, on purpose: the FULL published table is parsed (not just our 15 countries) and "
                "kept below in full_table/full_table_stats so it validates against the publisher's own "
                "row count, rank sequence and range -- see audit_data.py's "
                "check_full_table_self_consistency(). 'source_line' on each of our 15 countries names "
                "the exact iso3 key and rank it came from for manual audit."
            ),
            "full_table": [{"rank": r["rank"], "name": r["name"], "score": r["score"]} for r in full_rows],
            "full_table_stats": {
                "row_count": len(full_rows),
                "published_total": PUBLISHED_TOTAL,
                "range": list(RANGE),
                "higher_is_better": True,
                "extraction": "csv.DictReader over the WIPO GII ranking-data CSV, keyed on iso3",
            },
        },
    )
    record_provenance(
        source_id=SOURCE_ID, name=NAME, urls=[URL], license_note=LICENSE_NOTE,
        transforms=[
            "URL found by inspecting what wipo.int/gii-ranking/en/ (a Nuxt app) itself requests to "
            "render its own ranking table -- a direct CSV data endpoint, not the rendered page.",
            "Fetched the CSV with a browser User-Agent (unattended: plain HTTP, no WAF challenge, "
            "no cookie, no browser session -- unlike the PDF path it replaces).",
            "Parsed with csv.DictReader, keyed on the iso3 column -- exact ISO3 matching, not the "
            "free-text name matching that previously lost the Netherlands to a name-form mismatch.",
            "Decimal fields use a comma separator and are quoted (e.g. \"65,96195221\"); converted "
            "explicitly rather than relying on a bare float() cast, which raises on that string.",
            f"Extracted all {len(full_rows)} published rows, not just our 15 countries, so the table "
            "validates itself against the publisher's own row count, rank sequence and range.",
            "Countries not confidently matched are omitted rather than guessed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(out),
        coverage=f"{len(out)}/15 countries",
        status="ok" if out else "partial",
        notes=(
            f"Full table: {len(full_rows)}/{PUBLISHED_TOTAL} rows extracted, edition {EDITION_YEAR}, "
            f"fetched from WIPO's own Nuxt data endpoint. "
            + (edition_mismatch or "Edition check: giiyr column matches the requested edition.")
        ),
    )


if __name__ == "__main__":
    main_guard(run)
