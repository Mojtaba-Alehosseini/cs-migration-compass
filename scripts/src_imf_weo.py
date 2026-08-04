"""IMF World Economic Outlook → primary institutional forecast overlay.

WEO is the headline forecast source for the economy charts: by-country projections
of GDP growth, GDP per capita, inflation and unemployment out to ~2031.

NETWORK REALITY (measured, 2026-08): every imf.org host tested from this build
environment returns HTTP 403 at the Akamai edge — the WEO database page, the
DataMapper API (api/v1) and data.imf.org alike, with full browser headers and via
a real browser. sdmxcentral.imf.org responds but carries no WEO dataflow. This is
an edge/geo block on the environment, not a User-Agent problem, so no amount of
header tuning fixes it and we do not attempt to evade it.

Consequences, handled honestly:
  1. This script is written to work wherever imf.org IS reachable (a normal
     laptop, most CI runners). `make pipeline` will pick the data up there.
  2. When blocked, it records status="blocked" in provenance and writes an empty
     dataset — it never fabricates or approximates IMF numbers.
  3. A manual drop-in is supported at data/manual/imf_weo.json for exactly the
     shape below, so the overlay can be populated by hand from the free download.
     docs/SOURCES.md documents that procedure.

The site therefore still ships a working institutional-forecast layer via OECD
Economic Outlook and UN WPP, and simply shows no IMF line until IMF data exists.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA, ISO3_TO_ISO2, RAW, banner, fetch, log, main_guard, record_provenance,
    write_processed,
)

SOURCE_ID = "imf_weo"
NAME = "IMF World Economic Outlook — country projections"
EDITION = "IMF WEO, Apr 2026"
MANUAL = DATA / "manual" / "imf_weo.json"

# The bulk WEO file is a tab-delimited, latin-1 encoded .xls-named text file.
CANDIDATES = [
    "https://www.imf.org/-/media/Files/Publications/WEO/WEO-Database/2026/April/WEOApr2026all.ashx",
    "https://www.imf.org/-/media/Files/Publications/WEO/WEO-Database/2026/october/WEOOct2026all.ashx",
    "https://www.imf.org/external/pubs/ft/weo/2026/01/weodata/WEOApr2026all.xls",
]

# WEO subject codes we care about.
SUBJECTS = {
    "NGDP_RPCH": "real_gdp_growth_pct",
    "NGDPDPC": "gdp_per_capita_usd",
    "PCPIPCH": "inflation_pct",
    "LUR": "unemployment_pct",
}


def parse_weo(text: str) -> tuple[dict, int]:
    """Parse the tab-delimited WEO bulk export into {ISO2: {key: [{year, value, is_projection}]}}."""
    out: dict[str, dict[str, list]] = {}
    n = 0
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for row in reader:
        key = SUBJECTS.get((row.get("WEO Subject Code") or "").strip())
        if key is None:
            continue
        iso2 = ISO3_TO_ISO2.get((row.get("ISO") or "").strip())
        if iso2 is None:
            continue
        try:
            last_actual = int(str(row.get("Estimates Start After", "")).strip())
        except (TypeError, ValueError):
            last_actual = 0
        for col, raw in row.items():
            if not col or not col.strip().isdigit():
                continue
            year = int(col.strip())
            v = (raw or "").strip().replace(",", "")
            if v in ("", "n/a", "--"):
                continue
            try:
                value = float(v)
            except ValueError:
                continue
            out.setdefault(iso2, {}).setdefault(key, []).append(
                {"year": year, "value": value, "is_projection": bool(last_actual) and year > last_actual}
            )
            n += 1
    for c in out.values():
        for s in c.values():
            s.sort(key=lambda r: r["year"])
    return out, n


def run() -> None:
    banner(SOURCE_ID, NAME)

    # 1. manual drop-in wins if present — this is the documented unblock path
    if MANUAL.exists():
        payload = json.loads(MANUAL.read_text(encoding="utf-8"))
        data = payload.get("data", payload)
        log(f"    using manual drop-in {MANUAL.relative_to(DATA.parent)} ({len(data)} countries)")
        write_processed(SOURCE_ID, data, meta={
            "edition": payload.get("edition", EDITION), "institution": "IMF",
            "attribution_chip": payload.get("edition", EDITION), "kind": "institutional_forecast",
            "confidence": "official", "acquisition": "manual drop-in (see docs/SOURCES.md)",
            "render_rule": "Solid, attributed line. Never blended with the naive extrapolation.",
        })
        record_provenance(
            source_id=SOURCE_ID, name=NAME, urls=payload.get("urls", []),
            license_note="IMF WEO database is free to download and use with attribution. Cite: IMF, World Economic Outlook database.",
            transforms=["Loaded a hand-placed WEO extract from data/manual/imf_weo.json.",
                        "No transformation beyond schema validation."],
            output=f"data/processed/{SOURCE_ID}.json", rows=sum(len(s) for c in data.values() for s in c.values()),
            coverage=f"{len(data)}/15 countries (manual)", status="ok",
            notes="Populated by hand because imf.org is edge-blocked from the build environment.",
            redistribution="derived extract committed",
        )
        return

    # 2. try the live download
    errors: list[str] = []
    for url in CANDIDATES:
        try:
            blob = fetch(url, dest=RAW / SOURCE_ID / Path(url).name.replace(".ashx", ".tsv"), retries=2)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url} -> {type(exc).__name__}: {str(exc)[:120]}")
            continue
        text = blob.decode("utf-8-sig", errors="replace")
        if "\t" not in text.splitlines()[0]:
            text = blob.decode("latin-1", errors="replace")
        data, n = parse_weo(text)
        if not data:
            errors.append(f"{url} -> downloaded but parsed 0 rows")
            continue
        log(f"    {len(data)}/15 countries, {n:,} observations")
        write_processed(SOURCE_ID, data, meta={
            "edition": EDITION, "institution": "IMF", "attribution_chip": EDITION,
            "kind": "institutional_forecast", "confidence": "official",
            "subjects": {v: k for k, v in SUBJECTS.items()},
            "projection_rule": "is_projection from WEO's own 'Estimates Start After' column.",
            "render_rule": "Solid, attributed line. Never blended with the naive extrapolation.",
        })
        record_provenance(
            source_id=SOURCE_ID, name=NAME, urls=[url],
            license_note="IMF WEO database is free to download and use with attribution. Cite: IMF, World Economic Outlook database.",
            transforms=[
                "Downloaded the WEO bulk tab-delimited export.",
                "Kept 4 subject codes: real GDP growth, GDP per capita, inflation, unemployment.",
                "Used WEO's own 'Estimates Start After' column to flag projections — no inference needed.",
                "Mapped ISO3 to our ISO2 set; all other economies dropped.",
            ],
            output=f"data/processed/{SOURCE_ID}.json", rows=n,
            coverage=f"{len(data)}/15 countries", status="ok",
            notes="Primary institutional forecast overlay.",
        )
        return

    # 3. blocked — record it plainly, invent nothing
    log("    BLOCKED: every imf.org endpoint returned an edge error from this environment.")
    for e in errors:
        log(f"      {e}")
    log(f"    -> drop a WEO extract at {MANUAL.relative_to(DATA.parent)} to populate the IMF overlay.")
    write_processed(SOURCE_ID, {}, meta={
        "edition": EDITION, "institution": "IMF", "kind": "institutional_forecast",
        "status": "blocked",
        "why": ("All imf.org hosts return HTTP 403 at the Akamai edge from this build environment "
                "(website, DataMapper API and data.imf.org), including via a real browser. Not a "
                "User-Agent issue and not evaded."),
        "unblock": "Run this script from a network where imf.org is reachable, or place data/manual/imf_weo.json.",
        "site_behaviour": "No IMF line is drawn. OECD EO and UN WPP still provide institutional forecasts.",
        "render_rule": "Solid, attributed line when data exists. Never blended with the naive extrapolation.",
    })
    record_provenance(
        source_id=SOURCE_ID, name=NAME, urls=CANDIDATES,
        license_note="IMF WEO database is free to download and use with attribution.",
        transforms=["Attempted the WEO bulk download; every endpoint was edge-blocked. Nothing estimated."],
        output=f"data/processed/{SOURCE_ID}.json", rows=0, coverage="0/15 countries",
        status="blocked",
        notes=("imf.org is unreachable from this environment (HTTP 403 at the Akamai edge). The parser "
               "is complete and runs wherever IMF is reachable; a manual drop-in path is documented."),
    )


if __name__ == "__main__":
    main_guard(run)
