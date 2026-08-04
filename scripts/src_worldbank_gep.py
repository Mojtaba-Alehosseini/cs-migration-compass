"""World Bank Global Economic Prospects → third institutional forecast (cross-check).

GEP publishes GDP-growth forecasts a couple of years ahead. The prompt flags this
one as "verify at build" rather than pre-verified, so this script DISCOVERS the
current data file from the GEP landing page instead of hardcoding a URL that
rots every release.

If no machine-readable file is found, that is recorded as a miss. The forecast
layer does not depend on it: OECD Economic Outlook and UN WPP already supply
attributed institutional projections.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ISO3_TO_ISO2, RAW, banner, fetch, fetch_text, log, main_guard,
    record_provenance, to_iso2, write_processed,
)

SOURCE_ID = "worldbank_gep"
NAME = "World Bank Global Economic Prospects — growth forecasts"
LANDING = "https://www.worldbank.org/en/publication/global-economic-prospects"
EDITION_HINT = "World Bank GEP"


def discover() -> list[str]:
    """Find candidate xlsx/csv links on the GEP landing page."""
    try:
        html = fetch_text(LANDING, dest=RAW / SOURCE_ID / "gep_landing.html", retries=2)
    except Exception as exc:  # noqa: BLE001
        log(f"    landing page unreachable: {type(exc).__name__}")
        return []
    links = re.findall(r'href="([^"]+\.(?:xlsx|xls|csv))"', html, flags=re.I)
    out: list[str] = []
    for href in links:
        url = urljoin(LANDING, href)
        if url not in out:
            out.append(url)
    log(f"    discovered {len(out)} data link(s) on the GEP page")
    return out[:6]


def parse_any(blob: bytes, name: str) -> dict:
    """Best-effort parse of a GEP table into {ISO2: {year: growth_pct}}."""
    out: dict[str, dict] = {}
    if name.lower().endswith((".xlsx", ".xls")):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
        except Exception:  # noqa: BLE001
            return out
        for ws in wb.worksheets:
            header_years: dict[int, int] = {}
            for row in ws.iter_rows(max_row=400, max_col=30, values_only=True):
                if row is None:
                    continue
                # locate a header row carrying 4-digit years
                found = {i: int(str(c).strip()[:4]) for i, c in enumerate(row)
                         if c is not None and re.fullmatch(r"(19|20)\d{2}(\.0)?[fe]?", str(c).strip())}
                if len(found) >= 3:
                    header_years = found
                    continue
                if not header_years:
                    continue
                label = next((str(c).strip() for c in row[:3] if isinstance(c, str) and c.strip()), None)
                iso2 = to_iso2(label) if label else None
                if iso2 is None:
                    continue
                for i, year in header_years.items():
                    v = row[i] if i < len(row) else None
                    if isinstance(v, (int, float)):
                        out.setdefault(iso2, {})[str(year)] = float(v)
    return out


def run() -> None:
    banner(SOURCE_ID, NAME)
    urls = discover()
    parsed: dict = {}
    used: str | None = None

    for url in urls:
        try:
            blob = fetch(url, dest=RAW / SOURCE_ID / Path(url).name.split("?")[0], retries=1)
        except Exception as exc:  # noqa: BLE001
            log(f"    {Path(url).name}: {type(exc).__name__}")
            continue
        got = parse_any(blob, url)
        if len(got) >= 5:
            parsed, used = got, url
            break
        log(f"    {Path(url).name}: parsed {len(got)} countries — not enough, trying next")

    if parsed:
        log(f"    parsed {len(parsed)}/15 countries from {Path(used or '').name}")
        status, note = "ok", "Third institutional forecast, used as a cross-check overlay."
    else:
        log("    no machine-readable GEP forecast table found — recorded as a miss, nothing estimated.")
        status = "unavailable"
        note = ("No parseable GEP data file was discoverable at build time. The forecast layer does "
                "not depend on it — OECD EO and UN WPP supply attributed projections.")

    write_processed(
        SOURCE_ID,
        parsed,
        meta={
            "institution": "World Bank",
            "attribution_chip": EDITION_HINT,
            "kind": "institutional_forecast",
            "confidence": "official",
            "status": status,
            "source_file": used,
            "render_rule": "Solid, attributed line. Never blended with the naive extrapolation.",
            "note": note,
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[LANDING] + ([used] if used else []),
        license_note="CC BY 4.0 — World Bank. Cite: World Bank, Global Economic Prospects.",
        transforms=[
            "Discovered candidate data files by scanning the GEP landing page for xlsx/csv links "
            "(the per-release URL changes, so it is not hardcoded).",
            "Parsed the first table whose header row carries 4-digit years and whose rows resolve to countries.",
            "Kept growth values keyed by year; nothing inferred when no table parsed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=sum(len(v) for v in parsed.values()),
        coverage=f"{len(parsed)}/15 countries",
        status=status,
        notes=note,
    )


if __name__ == "__main__":
    main_guard(run)
