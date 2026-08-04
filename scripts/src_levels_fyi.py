"""levels.fyi enrichment → the "top employers" salary band.

The dataset already carries MARKET-WIDE salary bands (talent.com, PayScale, BLS).
This adds the other half of the documented two-tier reality: what large/known
employers actually pay in total compensation. The site shows BOTH bands and never
merges them — merging them is exactly what produced the impossible salary bands
that phase 3 had to repair.

Acquisition: levels.fyi is a JS app, but its
/t/software-engineer/locations/<slug> pages are server-rendered, so the values
were read from a real browser session and stored verbatim in
data/raw/levels_fyi/capture_<date>.json. This script does the deterministic part —
FX conversion, band construction and writing into cities.json — so the transform
is reviewable and re-runnable without a browser.

Figures are TOTAL COMPENSATION (base + stock + bonus) and are labelled as such;
the market bands are base-salary-like. Comparing them directly would overstate
the gap, and the UI says so.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA, RAW, banner, log, main_guard, record_provenance, write_processed,
)

SOURCE_ID = "levels_fyi"
NAME = "levels.fyi — Software Engineer total compensation by metro"
CAPTURE = RAW / "levels_fyi" / "capture_2026-08-04.json"
CITIES = DATA / "cities.json"
BASE_URL = "https://www.levels.fyi/t/software-engineer/locations/"


def run() -> None:
    banner(SOURCE_ID, NAME)
    if not CAPTURE.exists():
        raise FileNotFoundError(f"missing capture file {CAPTURE}")
    cap = json.loads(CAPTURE.read_text(encoding="utf-8"))
    fx = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))["meta"]["fx_rates_usd_base"]
    fx = {k: v for k, v in fx.items() if isinstance(v, (int, float))}

    def to_usd(value: float | None, currency: str) -> int | None:
        if value is None:
            return None
        if currency == "USD":
            return round(value)
        rate = fx.get(currency)
        if rate is None:
            return None
        return round(value / rate)

    cities_doc = json.loads(CITIES.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cities_doc["records"]}

    processed: dict[str, dict] = {}
    written = 0
    unknown: list[str] = []

    for city_id, rec in cap["records"].items():
        city = by_id.get(city_id)
        if city is None:
            unknown.append(city_id)
            continue
        cur = rec["currency"]
        entry = {
            "median_total_comp_usd": to_usd(rec.get("median"), cur),
            "p25_total_comp_usd": to_usd(rec.get("p25"), cur),
            "p75_total_comp_usd": to_usd(rec.get("p75"), cur),
            "currency_original": cur,
            "median_original": rec.get("median"),
            "p25_original": rec.get("p25"),
            "p75_original": rec.get("p75"),
            "as_of": rec.get("updated"),
            "role": "Software Engineer, all levels",
            "basis": "total compensation (base + stock + bonus)",
            "confidence": "crowd",
            "source": BASE_URL + rec["slug"],
        }
        # Written onto the city record as a SEPARATE field. The market bands in
        # salary_usd_year are untouched — this is a second band, not a correction.
        city["salary_levels_fyi"] = entry
        processed[city_id] = entry
        written += 1

    for city_id in cap.get("unverified", {}).get("cities", []):
        by_id[city_id]["salary_levels_fyi"] = {
            "median_total_comp_usd": None,
            "unavailable_reason": cap["unverified"]["why"],
            "source": BASE_URL,
            "confidence": "crowd",
        }
    for city_id in cap.get("unresolved", {}).get("cities", []):
        by_id[city_id]["salary_levels_fyi"] = {
            "median_total_comp_usd": None,
            "unavailable_reason": cap["unresolved"]["why"],
            "source": BASE_URL,
            "confidence": "crowd",
        }

    missing = cap["unresolved"]["cities"] + cap["unverified"]["cities"]
    log(f"    wrote salary_levels_fyi for {written}/73 cities")
    log(f"    explicitly marked unavailable: {len(missing)} — {', '.join(sorted(missing))}")
    if unknown:
        log(f"    !! capture ids not in cities.json: {', '.join(unknown)}")

    # Sanity: top-employer comp should generally sit at or above the market mid.
    # Where it does not, that is real (small metros, thin samples) but worth logging.
    below = []
    for city_id, entry in processed.items():
        med = entry["median_total_comp_usd"]
        mid = (by_id[city_id].get("salary_usd_year") or {}).get("mid")
        if med and mid and med < mid:
            below.append(f"{city_id} ({med:,} < {mid:,})")
    if below:
        log(f"    note: levels.fyi median below market mid in {len(below)} cities — "
            f"kept as-is, both bands shown: {', '.join(below[:6])}")

    cities_doc["levels_fyi_enriched_at"] = cap["captured_at"]
    CITIES.write_text(json.dumps(cities_doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"    updated {CITIES.relative_to(DATA.parent)}")

    write_processed(
        SOURCE_ID,
        processed,
        meta={
            "role": cap["role"],
            "basis": cap["figure"],
            "confidence": "crowd",
            "level": "city",
            "captured_at": cap["captured_at"],
            "fx": "pinned rates from data/metrics.json (see docs/METHODOLOGY.md)",
            "cities_unavailable": missing,
            "two_tier_rule": (
                "This is the 'top employers' band. cities.json keeps the market-wide band in "
                "salary_usd_year. The site shows both and never averages them — averaging the two "
                "families is what produced the impossible bands phase 3 had to repair."
            ),
            "comparability_caveat": (
                "levels.fyi reports TOTAL COMPENSATION including stock and bonus; the market bands are "
                "closer to base salary. The gap between the bands is therefore partly a definition "
                "difference, not purely an employer premium. The UI states this."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[BASE_URL + r["slug"] for r in list(cap["records"].values())[:8]] + [BASE_URL + "<city-slug>"],
        license_note=(
            "levels.fyi publishes these metro pages publicly and its robots.txt explicitly invites "
            "agent access. Data is crowd-sourced and remains theirs; we store derived per-city "
            "figures and cite levels.fyi on every one. No bulk redistribution."
        ),
        transforms=[
            "Read server-rendered /t/software-engineer/locations/<slug> pages in a browser session; "
            "captured median, 25th and 75th percentile total comp verbatim per metro.",
            "Converted local currency to USD using the FX rates pinned in data/metrics.json.",
            "Wrote a NEW salary_levels_fyi field on each city; salary_usd_year was left untouched.",
            "7 metros had no resolvable route and 3 returned an implausible value from a different "
            "page layout; all 10 are written with an explicit unavailable_reason instead of a number.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=written,
        coverage=f"{written}/73 cities (10 explicitly unavailable)",
        notes="Second salary band — top employers, total comp. Never merged with the market band.",
        redistribution="derived per-city figures committed; cited on every figure",
    )


if __name__ == "__main__":
    main_guard(run)
