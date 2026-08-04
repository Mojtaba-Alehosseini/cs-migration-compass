"""Wikipedia list of countries by English-speaking population → language reality.

Pairs with EF EPI: EF measures how WELL non-native speakers score, this measures
how MANY people speak English at all. Together they answer the real question —
"can I actually live and work here in English?"

Honest caveat baked into the output: the underlying figures come from mixed
national censuses and a ~2012 Eurobarometer, so this is a single rough snapshot,
not a time series, and is tagged confidence "crowd".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    COUNTRY_IDS, RAW, banner, fetch_text, log, main_guard, record_provenance,
    to_iso2, write_processed,
)

SOURCE_ID = "wikipedia_english_speakers"
NAME = "Wikipedia — List of countries by English-speaking population"
URL = "https://en.wikipedia.org/wiki/List_of_countries_by_English-speaking_population"


def _pct(text: str) -> float | None:
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text.replace(" ", " "))
    if m:
        v = float(m.group(1))
        return v if 0 <= v <= 100 else None
    return None


def _int(text: str) -> int | None:
    t = re.sub(r"\[.*?\]", "", text).replace(",", "").replace(" ", "").strip()
    m = re.match(r"^(\d{4,})", t)
    return int(m.group(1)) if m else None


def run() -> None:
    banner(SOURCE_ID, NAME)
    html = fetch_text(URL, dest=RAW / SOURCE_ID / "english_speakers.html")
    soup = BeautifulSoup(html, "lxml")

    out: dict[str, dict] = {}
    for table in soup.select("table.wikitable"):
        headers = [th.get_text(" ", strip=True).lower() for th in table.select("tr th")]
        header_blob = " ".join(headers)
        if "english" not in header_blob:
            continue
        for tr in table.select("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            label = cells[0].get_text(" ", strip=True)
            iso2 = to_iso2(re.sub(r"\[.*?\]", "", label).strip())
            if iso2 not in COUNTRY_IDS or iso2 in out:
                continue
            row_text = [c.get_text(" ", strip=True) for c in cells]
            pct = next((p for p in (_pct(t) for t in row_text[1:]) if p is not None), None)
            cnt = next((c for c in (_int(t) for t in row_text[1:]) if c is not None), None)
            if pct is None and cnt is None:
                continue
            out[iso2] = {
                "english_speakers_pct": pct,
                "english_speakers_count": cnt,
                "row_label": label,
            }

    missing = [c for c in COUNTRY_IDS if c not in out]
    log(f"    parsed {len(out)}/15 countries")
    if missing:
        log(f"    !! not found in table: {', '.join(missing)} (left as null, not estimated)")

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "definition": "Share/count of the population who speak English (any proficiency), as compiled by Wikipedia.",
            "confidence": "crowd",
            "level": "country",
            "snapshot_only": True,
            "countries_without_data": missing,
            "vintage_caveat": (
                "Underlying figures come from different national censuses and a ~2012 Eurobarometer "
                "wave, so years are inconsistent between countries. Treat as a rough snapshot, never "
                "as a trend, and always show it beside EF EPI proficiency."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[URL],
        license_note="Wikipedia text is CC BY-SA 4.0. Underlying figures belong to the cited national sources.",
        transforms=[
            "Fetched the article HTML and parsed every wikitable whose header mentions English.",
            "Resolved the first cell of each row to one of our 15 countries; all other rows dropped.",
            "Extracted the first percentage and the first large integer found in the row.",
            "Countries absent from the table are recorded as missing, never estimated.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(out),
        coverage=f"{len(out)}/15 countries, single snapshot",
        notes="Mixed vintages by country — a snapshot, not a series.",
    )


if __name__ == "__main__":
    main_guard(run)
