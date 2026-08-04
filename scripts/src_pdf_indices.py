"""EF EPI (English proficiency) + WIPO GII (innovation) → two PDF-only indices.

Both publish their country tables as PDFs only, so both are extracted by text
scraping. That is inherently more fragile than an API, so the extraction is
conservative: a country is recorded only when a score is found on the same line
as its name and lands in the expected range. Anything else is left missing.

Gotcha (verified): ef.com and tind.wipo.int both 403 default Python user agents.
scripts/_common.py always sends a browser-like User-Agent.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, COUNTRY_NAMES, RAW, banner, fetch, log, main_guard,
    record_provenance, write_processed,
)

EF_URL = ("https://www.ef.com/assetscdn/WIBIwq6RdJvcD9bc8RMd/cefcom-epi-site/reports/2025/"
          "ef-epi-2025-english.pdf")
GII_URL = ("https://tind.wipo.int/record/50062/files/"
           "wipo-pub-2000-2024-en-global-innovation-index-2024-17th-edition.pdf")

# EF EPI scores cluster 400-700; GII scores are 0-70.
EF_RANGE = (300.0, 750.0)
GII_RANGE = (5.0, 80.0)


def pdf_lines(blob: bytes, max_pages: int = 60) -> list[str]:
    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page in pdf.pages[:max_pages]:
            text = page.extract_text() or ""
            lines.extend(text.splitlines())
    return lines


def scrape(lines: list[str], lo: float, hi: float) -> dict[str, dict]:
    """Extract each country's score from a PDF ranking table.

    Both reports lay their tables out as `<rank> <Country> <score> ...`, often with
    SEVERAL countries packed into one physical line. Two traps follow from that,
    and both produced wrong numbers before this was tightened:

      * taking the first in-range number on the line yields the RANK, not the score
        ("9 Germany 58.1" -> 9);
      * matching the first line that merely mentions the country yields chart
        labels and axis artifacts ("Netherlands Germany 500 500").

    So we require the anchored pattern rank-name-score, take the number that
    immediately FOLLOWS the country name, and prefer a decimal score where the
    index publishes one. Only if no anchored match exists anywhere do we fall back
    to the first number after the name, and a country with no confident match is
    left out entirely.
    """
    out: dict[str, dict] = {}
    for iso2 in COUNTRY_IDS:
        variants = [COUNTRY_NAMES[iso2]]
        if iso2 == "GB":
            variants += ["United Kingdom"]
        if iso2 == "US":
            variants += ["United States"]
        if iso2 == "AE":
            variants += ["United Arab Emirates"]

        anchored: list[tuple[float, int | None, str]] = []
        loose: list[tuple[float, int | None, str]] = []

        for line in lines:
            if "(cid:" in line:      # embedded-font garbage, not a table row
                continue
            for v in variants:
                # rank, name, score — the real table shape
                for m in re.finditer(rf"(?:(\d{{1,3}})\s+)?{re.escape(v)}\s+(\d+(?:\.\d+)?)", line):
                    try:
                        score = float(m.group(2))
                    except (TypeError, ValueError):
                        continue
                    if not (lo <= score <= hi):
                        continue
                    rank = int(m.group(1)) if m.group(1) else None
                    entry = (score, rank, line.strip()[:170])
                    (anchored if rank is not None else loose).append(entry)

        pool = anchored or loose
        if not pool:
            continue
        # Where the index publishes decimal scores, a decimal is the real score.
        decimals = [p for p in pool if p[0] != int(p[0])]
        score, rank, line = (decimals or pool)[0]
        out[iso2] = {"score": score, "rank": rank, "source_line": line}
    return out


def one(source_id: str, name: str, url: str, filename: str, rng: tuple[float, float],
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

    lines = pdf_lines(blob)
    out = scrape(lines, *rng)
    missing = [c for c in COUNTRY_IDS if c not in out]
    log(f"    extracted {len(out)}/15 countries from {len(lines):,} PDF lines")
    if missing:
        log(f"    !! not found: {', '.join(missing)} (left missing, never guessed)")

    write_processed(
        source_id, out,
        meta={
            "definition": definition,
            "confidence": confidence,
            "level": "country",
            "extraction": "PDF text scraping",
            "countries_without_data": missing,
            "countries_without_data_note": missing_note,
            "fragility_caveat": (
                "Extracted from a PDF layout, not a data file. A country is recorded only when its "
                "name and a plausible score appear on the same line; everything else is left missing. "
                "'source_line' preserves the exact line each value came from so any figure can be audited."
            ),
        },
    )
    record_provenance(
        source_id=source_id, name=name, urls=[url], license_note=license_note,
        transforms=[
            "Downloaded the published PDF with a browser User-Agent (both hosts 403 otherwise).",
            "Extracted text from the first 60 pages with pdfplumber.",
            f"For each country, took the first line containing its name and a number in {rng}.",
            "Recorded the originating line with every value for auditability.",
            "Countries not confidently matched are omitted rather than guessed.",
        ],
        output=f"data/processed/{source_id}.json",
        rows=len(out),
        coverage=f"{len(out)}/15 countries",
        status="ok" if out else "partial",
        notes="PDF scraping is fragile by nature; every value carries its source line.",
    )


def run() -> None:
    one(
        "ef_epi", "EF English Proficiency Index 2025", EF_URL, "ef-epi-2025.pdf", EF_RANGE,
        "EF EPI score (roughly 400-700); higher = stronger English proficiency among non-native speakers.",
        "EF publishes the EPI report freely; cite EF Education First, EF English Proficiency Index 2025.",
        missing_note=(
            "EF EPI only scores countries where English is NOT a native language, so Australia, the "
            "US, Canada, the UK and Ireland are absent BY DESIGN, not through a failed extraction. "
            "For those countries the site shows 'English is the native language' instead of a score."
        ),
    )
    one(
        "wipo_gii", "WIPO Global Innovation Index 2024", GII_URL, "wipo-gii-2024.pdf", GII_RANGE,
        "GII overall innovation score (0-100) and rank; higher = stronger innovation ecosystem.",
        "WIPO publishes the GII under CC BY 4.0 (some content excepted); cite WIPO, Global Innovation Index 2024.",
        missing_note=(
            "Countries missing here failed the anchored rank-name-score match — typically because "
            "their table row uses embedded-font glyphs that extract as '(cid:NN)' garbage. They are "
            "left out rather than filled with a number scraped from the wrong column."
        ),
    )


if __name__ == "__main__":
    main_guard(run)
