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
extraction method below changed. But it also does not (and cannot, from
rank/name/score alone) tell whether a row's COUNTRY IDENTITY is right --
found by package 20's own adversarial review, which showed a rotated iso3
column (names, ranks and scores all left untouched) reproduces a table
that still satisfies every one of those checks perfectly, because none of
them ever see iso3 at all. Every row here is therefore matched twice --
once by iso3, once independently by economy_name -- and excluded from the
15-country slice, not guessed, if the two disagree. The same review also
found a zero-row parse could crash past run()'s own error handling and
leave a stale prior run in place under a fresh "ok" status; fetch_full_table()
now raises on that case itself, before any downstream code can skip it.

Gotcha (found by the same review, checking all 139 rows rather than only
the 15 this site tracks): WIPO's own CSV serves two economy names --
Turkiye and Cote d'Ivoire -- double-UTF-8-encoded, so a single correct
UTF-8 decode still yields mojibake ('TÃ¼rkiye'). The corruption is in
WIPO's own published bytes, not in how this script reads them; see
_fix_double_utf8()'s own docstring for the exact mechanism and why it only
touches strings that actually show the corruption's signature.

Edition currency is checked two ways, because a year-stamped URL can go
stale in a way nothing here would notice by default: the giiyr column
(every row's own stated edition, reported in full) catches WIPO silently
serving mismatched content under this URL; a lightweight HEAD probe against
next year's URL pattern catches the more likely failure -- this URL
quietly remaining valid and unchanged after a newer edition exists
elsewhere. An earlier draft of this module claimed the filename being
year-stamped meant a stale URL would "almost certainly" 404, reasoning by
analogy from the dead 2024 PDF URL; an adversarial review found that
claim was asserted, not established, for a static CSV asset, where the
opposite (an old file simply staying up) is the more likely publisher
behaviour. Not assumed here any more; probed for instead.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, DEFAULT_HEADERS, RAW, banner, fetch_text, log, main_guard,
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
    "A country is missing here either because the full 139-row table (see full_table below) "
    "contains no row whose iso3 resolves to it via _common.to_iso2(), or because that row's iso3 "
    "and economy_name columns resolved to two DIFFERENT countries (see cross_check_disagreements) "
    "and was excluded rather than guessed -- as of this edition all 15 of our countries resolve "
    "cleanly with no disagreement. (Package 19's PDF extraction lost the US and the Netherlands to "
    "flattened-text column interleaving and name-form mismatches; keying on the CSV's own iso3 "
    "field removes name matching from this source entirely, not just the specific mismatch that "
    "caused it.)"
)


def _parse_decimal_comma(s: str) -> float:
    """WIPO's CSV writes decimals as '65,96195221', quoted so the comma is
    not read as a field delimiter -- a plain float() raises ValueError on
    that string (comma is not a valid character in a Python float literal).
    Thousands-grouping is not a risk here: an adversarial review checked
    every field in every column of the real 139-row, 21-column file, not
    just the score column this function reads, and found not one comma-
    grouped number anywhere in it -- large values are written with no
    grouping at all ("95836,64063"), so a single comma-to-point
    substitution is the correct, sufficient fix, not merely a fix that
    happens to work for the narrower score-only case originally checked.
    An input this cannot handle correctly (a genuinely thousands-grouped
    number) either fails to appear in this publisher's own format or
    raises ValueError on the malformed result -- checked adversarially
    against ~30 constructed inputs (empty string, "NA", None, negative
    values, "nan"/"inf") and confirmed to raise rather than silently
    return a wrong-but-plausible number in every case but one, which
    cannot occur in this file: a genuinely double-grouped value like
    "1,234,56" would parse to 1.234 instead of raising -- moot here, since
    the format that would produce it does not exist in what this function
    actually reads."""
    return float(s.strip().replace(",", "."))


def _fix_double_utf8(s: str) -> str:
    """WIPO's own CSV serves some non-ASCII economy names double-UTF-8-
    encoded -- found by an adversarial review checking all 139 rows, not
    just our 15: 'Turkiye' and "Cote d'Ivoire" arrive as 'TÃ¼rkiye' and
    'CÃ´te d'Ivoire', a single (correct) UTF-8 decode still producing
    mojibake because the SOURCE BYTES already went through an extra
    encode/decode round-trip before WIPO served them (the original UTF-8
    bytes for 'u' with an umlaut were mistaken for Latin-1 and UTF-8-
    encoded a second time). fetch_text()'s own single UTF-8 decode is
    correct and faithful to what the file actually contains; the file
    itself is what's corrupted.

    U+00C3/U+00C2 are the textbook signature of this exact corruption --
    every 2-byte UTF-8 lead byte (0xC2-0xC3, which covers all of Latin-1
    Supplement, the block ordinary Western-European names live in) decodes
    to one of these two characters when wrongly read as Latin-1 -- so their
    presence in an economy name (which should never legitimately contain
    them) is the detection signal. The repair reverses exactly the
    corruption: re-encode as Latin-1 (recovering the original UTF-8 bytes
    the string was wrongly split into two characters), then decode as
    UTF-8 properly. Applied only when the signature is present AND the
    repair succeeds without raising -- an already-correctly-encoded name,
    or a future, differently-shaped encoding problem, is left as-is rather
    than risking a second, wrong transformation on text that was never
    broken."""
    if "Ã" not in s and "Â" not in s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def fetch_full_table() -> list[dict]:
    """Fetch and parse the CSV into (rank, iso3, name, score) rows, sorted
    by rank. Raises on a malformed row, or on a parse that produces no rows
    at all, rather than silently accepting either -- a CSV row missing
    rank/iso3/score, or an empty/header-only response, is exactly the kind
    of silent-wrong-answer risk this package exists to avoid, and the
    caller's own except block turns any of this into the same honest
    'unavailable' status a fetch failure already gets. (An empty result
    raising HERE, not several statements later inside run(), is deliberate:
    an adversarial review found the previous version let a zero-row parse
    reach an unguarded max() over an empty dict in run()'s own edition
    check, escaping the try/except entirely and leaving the PREVIOUS run's
    processed file and provenance entry in place, still marked status "ok"
    -- the exact silent-stale-data failure this whole package exists to
    rule out.)"""
    text = fetch_text(URL, dest=RAW / SOURCE_ID / FILENAME, retries=2)
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append({
            "iso3": row["iso3"].strip(),
            "name": _fix_double_utf8(row["economy_name"].strip()),
            "rank": int(row["rank"]),
            "score": _parse_decimal_comma(row["score"]),
            "giiyr": row["giiyr"].strip(),
        })
    if not rows:
        raise ValueError("CSV fetched successfully but parsed to zero data rows")
    rows.sort(key=lambda r: r["rank"])
    return rows


def run() -> None:
    banner(SOURCE_ID, NAME)
    try:
        full_rows = fetch_full_table()

        # Edition sanity, two checks, because they catch DIFFERENT failure
        # shapes and neither alone is sufficient (found by an adversarial
        # review, which showed the giiyr check alone is close to a
        # tautology: EDITION_YEAR both builds the URL and is what giiyr is
        # compared against, so it can only ever catch WIPO silently
        # rewriting a year-stamped file's own contents to a different
        # year's data -- not the much likelier failure, a URL that simply
        # keeps serving this same 2025 file forever after a 2026 edition
        # exists elsewhere. Unlike the dead 2024 PDF URL, nothing here
        # actually establishes that a stale CSV URL goes on to 404 -- that
        # was a PDF-delivery behaviour, asserted for this endpoint in an
        # earlier draft without evidence, and is not assumed here.
        #
        # 1. giiyr column: every row's own stated edition, reported in
        #    full (not just a pass/fail against the majority) so a
        #    genuinely partial degradation is visible even when it does not
        #    flip the plurality -- one economy (Venezuela, checked by hand)
        #    already carries giiyr="NA" in a genuinely current file, so a
        #    strict "every row must match" rule would be a check tuned to
        #    fail on real, correct data.
        edition_counts: dict[str, int] = {}
        for r in full_rows:
            edition_counts[r["giiyr"]] = edition_counts.get(r["giiyr"], 0) + 1
        majority_year, majority_count = max(edition_counts.items(), key=lambda kv: kv[1])
        edition_mismatch = None
        if majority_year != EDITION_YEAR:
            edition_mismatch = (
                f"CSV's own giiyr column majority ({majority_year}, {majority_count}/{len(full_rows)} "
                f"rows) does not match the edition this script requested ({EDITION_YEAR}) -- possible "
                "stale or wrong file served under the expected URL."
            )
            log(f"    !! {edition_mismatch}")

        # 2. Does a NEXT edition's URL already exist? This is the check
        # that actually answers "is 2025 still current" rather than "does
        # the 2025 URL still serve something calling itself 2025" -- a
        # lightweight HEAD probe, not a full fetch, and its own failure
        # (network error, WIPO renaming the pattern) is caught and
        # downgraded to a log line rather than failing this entire source
        # over a check that is a bonus signal, not the primary extraction.
        next_year = str(int(EDITION_YEAR) + 1)
        next_year_url = f"https://www.wipo.int/gii-ranking/data/bc_results_gii_{next_year}.csv"
        newer_edition_available = None
        try:
            probe = requests.head(next_year_url, headers=DEFAULT_HEADERS, timeout=20, allow_redirects=True)
            if probe.status_code == 200:
                newer_edition_available = (
                    f"{next_year_url} returned HTTP 200 -- a {next_year} edition may already be "
                    f"published. This script is still pinned to {EDITION_YEAR}; EDITION_YEAR needs a "
                    "human decision to update, matching how every prior edition bump in this pipeline "
                    "has been made (see REPORT-P19.md's own GII 2024->2025 update)."
                )
                log(f"    !! {newer_edition_available}")
        except Exception as exc:  # noqa: BLE001
            log(f"    (next-edition probe failed, not fatal: {type(exc).__name__}: {exc})")

        # Every row is matched TWICE, independently, by two different CSV
        # columns -- iso3 (an exact code lookup) and economy_name (the same
        # free-text resolver the old PDF path used). They are required to
        # agree. This is not the same check twice: iso3 and economy_name
        # are independently published columns, so a corruption that shifts
        # or misaligns one (a column offset, a re-export bug) will not
        # generally shift the other the same way, and the two resolvers
        # take different code paths through to_iso2() (an ISO3 dict lookup
        # vs name-string matching). Found necessary by an adversarial
        # review: rotating the iso3 column by one row while leaving
        # name/rank/score untouched produced a full_table that still passed
        # every one of audit_data.py's checks, because full_table never
        # carried iso3 at all -- rank/name/score alone cannot detect which
        # COUNTRY a row belongs to, only whether the table's shape is
        # internally consistent. A disagreement excludes that one row from
        # `out` (join the existing "not confidently matched" philosophy)
        # rather than failing the whole source over what could be a single
        # unresolvable territory name.
        out: dict[str, dict] = {}
        conflicts: list[str] = []
        cross_check_disagreements: list[str] = []
        for r in full_rows:
            iso2_by_code = to_iso2(r["iso3"])
            iso2_by_name = to_iso2(r["name"])
            if iso2_by_code is not None and iso2_by_name is not None and iso2_by_code != iso2_by_name:
                cross_check_disagreements.append(
                    f"iso3={r['iso3']!r} resolves to {iso2_by_code}, but name={r['name']!r} "
                    f"resolves to {iso2_by_name} (rank {r['rank']})"
                )
                continue
            iso2 = iso2_by_code
            if iso2 is None or iso2 not in COUNTRY_IDS:
                continue
            if iso2 in out:
                # Any repeat is suspicious -- WIPO's table has one row per
                # economy, so a second row resolving to a country already
                # in `out` is never legitimate, whether or not its rank
                # happens to match the first (the earlier version of this
                # guard only fired on a rank MISMATCH, which meant two rows
                # at the identical rank silently overwrote each other with
                # no log line at all -- found by the same review).
                conflicts.append(
                    f"{iso2}: rank {out[iso2]['rank']}/score {out[iso2]['score']} then "
                    f"rank {r['rank']}/score {r['score']} ({r['iso3']!r})"
                )
                continue
            out[iso2] = {
                "score": r["score"],
                "rank": r["rank"],
                "iso3": r["iso3"],
                "source_line": f"iso3={r['iso3']}, rank {r['rank']}/{PUBLISHED_TOTAL}: {r['name']} = {r['score']}",
            }
        if conflicts:
            log(f"    !! {len(conflicts)} country matched two different rows: {'; '.join(conflicts)}")
        if cross_check_disagreements:
            log(f"    !! {len(cross_check_disagreements)} row(s) failed the iso3-vs-name cross-check "
                f"(excluded, not guessed): {'; '.join(cross_check_disagreements)}")

        missing = [c for c in COUNTRY_IDS if c not in out]
        log(f"    extracted {len(full_rows)} total rows from the CSV; "
            f"{len(out)}/15 of our countries resolved")
        if missing:
            log(f"    !! not found: {', '.join(missing)} (left missing, never guessed)")
    except Exception as exc:  # noqa: BLE001
        log(f"    unavailable: {type(exc).__name__}: {exc}")
        write_processed(SOURCE_ID, {}, meta={"status": "unavailable", "error": str(exc)})
        record_provenance(
            source_id=SOURCE_ID, name=NAME, urls=[URL], license_note=LICENSE_NOTE,
            transforms=["Download or parse failed; nothing extracted, nothing estimated."],
            output=f"data/processed/{SOURCE_ID}.json", status="failed",
            coverage="0/15 countries",
            notes="CSV unreachable, empty, or malformed at build time — treated as missing data, "
                  "not filled in, and never left as a stale prior run.",
        )
        return

    write_processed(
        SOURCE_ID, out,
        meta={
            "definition": DEFINITION,
            "confidence": "index",
            "level": "country",
            "extraction": "CSV, keyed on iso3 (csv.DictReader + decimal-comma fixup)",
            "countries_without_data": missing,
            "countries_without_data_note": MISSING_NOTE,
            "edition_counts": edition_counts,
            "edition_mismatch": edition_mismatch,
            "newer_edition_available": newer_edition_available,
            "cross_check_disagreements": cross_check_disagreements,
            "fragility_caveat": (
                "Extracted from a data file this time, not a PDF layout -- but still checked the same "
                "way, on purpose: the FULL published table is parsed (not just our 15 countries) and "
                "kept below in full_table/full_table_stats so it validates against the publisher's own "
                "row count, rank sequence and range -- see audit_data.py's "
                "check_full_table_self_consistency(). 'source_line' on each of our 15 countries names "
                "the exact iso3 key and rank it came from for manual audit. Every row is also matched "
                "twice, once by iso3 and once by name, and excluded from the 15-country slice (not "
                "guessed) if the two disagree -- see cross_check_disagreements above."
            ),
            "full_table": [{"rank": r["rank"], "name": r["name"], "score": r["score"], "iso3": r["iso3"]}
                            for r in full_rows],
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
            "free-text name matching that previously lost the Netherlands to a name-form mismatch. "
            "Every row is matched a second, independent time by economy_name and the two are "
            "required to agree; a disagreement excludes that row rather than trusting either column.",
            "Decimal fields use a comma separator and are quoted (e.g. \"65,96195221\"); converted "
            "explicitly rather than relying on a bare float() cast, which raises on that string.",
            "A CSV that fetches successfully but parses to zero rows is treated as a failure, not an "
            "empty-but-valid result -- it raises before reaching any downstream check, so a prior "
            "run's processed file is never silently left in place under a fresh 'ok' status.",
            f"Extracted all {len(full_rows)} published rows, not just our 15 countries, so the table "
            "validates itself against the publisher's own row count, rank sequence and range.",
            "Countries not confidently matched, or matched inconsistently across iso3 and name, are "
            "omitted rather than guessed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(out),
        coverage=f"{len(out)}/15 countries",
        status="ok" if out else "partial",
        notes=(
            f"Full table: {len(full_rows)}/{PUBLISHED_TOTAL} rows extracted, edition {EDITION_YEAR}, "
            f"fetched from WIPO's own Nuxt data endpoint. "
            + (edition_mismatch or "Edition check: giiyr column matches the requested edition.")
            + (f" {newer_edition_available}" if newer_edition_available else "")
        ),
        redistribution=(
            f"processed derivative only -- the raw CSV is cached under data/raw/{SOURCE_ID}/ but that "
            "directory is gitignored, so this repo does not redistribute it (CC BY 4.0 would permit "
            "it; the repo simply doesn't). Only the 15-country slice and the full extracted table are "
            f"committed, in data/processed/{SOURCE_ID}.json."
        ),
    )


if __name__ == "__main__":
    main_guard(run)
