"""Numbeo yearly country snapshots + per-city history → cost-of-living over time.

Two things, both crowd-sourced and both labelled that way:
  * country cost-of-living / rent / property indices by year (?title=YYYY)
  * per-city historical cost-of-living pages, where they exist

This is the only freely available source of city-level cost history, and it is
thin — Numbeo itself warns that small cities carry few contributors. Every value
carries confidence "crowd" and the city pages that yield nothing are recorded as
misses rather than back-filled from the country trend without saying so.

We rate-limit deliberately: this is someone else's public website, not an API.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    RAW, banner, fetch_text, load_cities, log, main_guard, numbeo_slug,
    record_provenance, to_iso2, write_processed,
)

SOURCE_ID = "numbeo_history"
NAME = "Numbeo — yearly country indices and per-city cost-of-living history"
COUNTRY_URL = "https://www.numbeo.com/cost-of-living/rankings_by_country.jsp?title={year}"
CITY_URL = "https://www.numbeo.com/cost-of-living/city-history/in/{slug}"
YEARS = list(range(2015, 2027))
DELAY = 1.5  # seconds between requests — be a good citizen


def _f(t: str) -> float | None:
    t = (t or "").strip().replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def country_year(year: int) -> dict[str, dict]:
    html = fetch_text(COUNTRY_URL.format(year=year), dest=RAW / SOURCE_ID / f"country_{year}.html", retries=2)
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id=re.compile("t2|rankings")) or soup.find("table", class_="stripe")
    if table is None:
        return {}
    headers = [th.get_text(" ", strip=True).lower() for th in table.select("thead th")]
    out: dict[str, dict] = {}
    for tr in table.select("tbody tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) < 3:
            continue
        iso2 = next((to_iso2(c) for c in cells[:3] if to_iso2(c)), None)
        if iso2 is None:
            continue
        rec: dict = {}
        for i, cell in enumerate(cells):
            if i < len(headers) and headers[i]:
                v = _f(cell)
                if v is not None:
                    rec[headers[i].replace(" ", "_")[:40]] = v
        if rec:
            out[iso2] = rec
    return out


def run() -> None:
    banner(SOURCE_ID, NAME)
    countries: dict[int, dict] = {}
    urls: list[str] = []
    failures: list[str] = []

    for year in YEARS:
        try:
            got = country_year(year)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"country {year}: {type(exc).__name__}")
            continue
        if got:
            countries[year] = got
            urls.append(COUNTRY_URL.format(year=year))
            log(f"    country {year}: {len(got)} of our countries")
        time.sleep(DELAY)

    # --- city-level history: probe once, then stop -------------------------
    # Measured 2026-08: the city-history pages return only navigation chrome
    # (~19 KB, identical for every city). The actual year/value series is rendered
    # client-side, and the item picker is JS-built, so ?itemId=NN changes nothing
    # in the HTML. Verified against Berlin for itemIds 1, 26, 27 and 105.
    #
    # We therefore do NOT crawl 73 city pages to collect nothing. We probe one
    # city, record the finding, and fall back to the documented country-trend rule.
    cities: dict[str, dict] = {}
    all_city_ids = [c["id"] for c in load_cities()]
    probe_city = next((c for c in load_cities() if c["id"] == "berlin"), load_cities()[0])
    probe_slug = numbeo_slug(probe_city)
    probe_note: str
    try:
        html = fetch_text(
            CITY_URL.format(slug=probe_slug),
            dest=RAW / SOURCE_ID / f"city_probe_{probe_city['id']}.html",
            retries=1,
        )
        pairs = re.findall(r"\b(20\d{2})\b[^0-9]{0,40}?(\d{2,3}\.\d{1,2})", html)
        if pairs:
            series = []
            seen: set[int] = set()
            for y, v in pairs:
                yi = int(y)
                if 2000 <= yi <= 2026 and yi not in seen:
                    seen.add(yi)
                    series.append({"year": yi, "index": float(v)})
            series.sort(key=lambda r: r["year"])
            cities[probe_city["id"]] = {"slug": probe_slug, "series": series}
            probe_note = (
                "Probe returned parseable data — city history may now be scrapable; "
                "re-enable the full per-city crawl in this script if so."
            )
        else:
            probe_note = (
                "Probe returned navigation chrome only: Numbeo renders city price history "
                "client-side, so no year/value pairs exist in the served HTML (?itemId has no "
                "effect). No per-city crawl was performed."
            )
    except Exception as exc:  # noqa: BLE001
        probe_note = f"Probe failed: {type(exc).__name__}. No per-city crawl was performed."

    city_misses = [c for c in all_city_ids if c not in cities]
    log(f"    country-year snapshots: {len(countries)} years · city histories: {len(cities)}/73")
    log(f"    city-history probe ({probe_city['id']}): {probe_note}")

    write_processed(
        SOURCE_ID,
        {"by_country_year": countries, "by_city": cities},
        meta={
            "confidence": "crowd",
            "level": "country + city",
            "years_requested": YEARS,
            "cities_without_history": city_misses,
            "city_history_probe": probe_note,
            "crowd_caveat": (
                "Numbeo is crowd-sourced. Solid for large cities, thin for small ones (Halifax, "
                "Aarhus, Tampere, Gold Coast, Detroit are known-thin in this dataset). Indices are "
                "relative to Numbeo's own base, so compare shape, not absolute level."
            ),
            "city_fallback_rule": (
                "Cities with no usable history are listed above. Where the UI substitutes a country "
                "trend for them it must say 'city estimate = current value x country trend'."
            ),
            "failures": failures,
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=urls[:6] + ([CITY_URL.format(slug="<city>")] if cities else []),
        license_note=(
            "Numbeo data is crowd-sourced and its terms restrict bulk redistribution. We commit the "
            "derived per-year/per-city aggregates and the fetch script, and cite Numbeo on every figure."
        ),
        transforms=[
            f"Requested country ranking pages for {YEARS[0]}-{YEARS[-1]} via the ?title=YYYY parameter.",
            "Parsed the rankings table, resolving country labels to our ISO2 set.",
            "Probed ONE city-history page rather than crawling all 73: the served HTML contains only "
            "navigation chrome because Numbeo renders the price series client-side (verified for "
            "itemIds 1/26/27/105). The finding is recorded; no data was invented from it.",
            f"Rate-limited to one request per {DELAY}s.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=sum(len(v) for v in countries.values()) + sum(len(c["series"]) for c in cities.values()),
        coverage=f"{len(countries)} country-years, {len(cities)}/73 city histories",
        status="ok" if (countries or cities) else "failed",
        notes="Crowd-sourced; thin for small cities and labelled as such everywhere it appears.",
        redistribution="derived aggregates committed (Numbeo terms restrict bulk redistribution)",
    )


if __name__ == "__main__":
    main_guard(run)
