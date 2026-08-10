"""City coordinates → cities.json lat/lon, for the Compare map.

The Compare browser draws all 73 cities on a Mercator map, so each city needs a
point. This project does not hold unsourced numbers, so the coordinates come
from the same geocoding step the climate normals already use — Open-Meteo's
geocoding API, which serves GeoNames populated places — with the same
disambiguation rules (accept only a hit whose country code matches the city's
own, then prefer the largest by population; there are five Valencias).

Convention, stated once: the point is the GeoNames populated-place point — the
settlement's own principal point, roughly the city centre. It is NOT a
metro-area centroid, and for the two records that name a region rather than a
single settlement (`sf_bay_area`, `washington_dc`) it is the point of the named
city in GEO_OVERRIDE. `geocoded_as` on every row records exactly which place was
matched, so the substitution is visible rather than implied.

The fetch reuses src_climate_normals' cache path, so a warm data/raw makes this
step free and guarantees the two steps can never disagree about where a city is.

This module also records the provenance of the OTHER half of the map's
geography — the Natural Earth 110m land outline drawn under the dots. That
outline is a committed derived asset rather than a download (see the entry's
transforms), so it has no fetch of its own but still needs its citation line in
docs/SOURCES.md.

Additive only: no existing field in cities.json is read, moved or changed.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, banner, log, main_guard, record_provenance, write_processed  # noqa: E402
from src_climate_normals import GEO, geocode  # noqa: E402

SOURCE_ID = "city_coordinates"
NAME = "Open-Meteo geocoding (GeoNames) — city coordinates"
LAND_SOURCE_ID = "natural_earth_land"
LAND_NAME = "Natural Earth 110m physical land — map outline"
DELAY = 0.2

CONVENTION = (
    "GeoNames populated-place point (the settlement's principal point, roughly the city "
    "centre) — not a metro-area centroid."
)


def run() -> None:
    banner(SOURCE_ID, NAME)
    cities_doc = json.loads((DATA / "cities.json").read_text(encoding="utf-8"))
    records = cities_doc["records"]

    processed: dict[str, dict] = {}
    failures: list[str] = []
    changed: list[str] = []

    for i, city in enumerate(records, 1):
        try:
            place = geocode(city)
        except Exception as exc:  # noqa: BLE001 — one city must not kill the run
            failures.append(f"{city['id']}: {type(exc).__name__}")
            log(f"    [{i:2}/73] {city['id']:16s} !! {type(exc).__name__}")
            time.sleep(DELAY)
            continue
        if place is None:
            failures.append(f"{city['id']}: no geocode match in {city['country']}")
            log(f"    [{i:2}/73] {city['id']:16s} !! no geocode match")
            continue

        lat, lon = round(float(place["latitude"]), 4), round(float(place["longitude"]), 4)
        as_ = f"{place.get('name')}, {place.get('admin1') or ''} {place.get('country_code')}".strip()
        processed[city["id"]] = {"lat": lat, "lon": lon, "geocoded_as": as_}

        # Additive: write the two new keys and touch nothing else. If a previous
        # run already wrote a different point, say so rather than silently moving
        # a city — a coordinate that changes under you is a data change, and this
        # step is only ever allowed to add.
        prev = (city.get("lat"), city.get("lon"))
        if prev != (None, None) and prev != (lat, lon) and prev[0] is not None:
            log(f"    [{i:2}/73] {city['id']:16s} !! would move {prev} -> {(lat, lon)} — kept the existing point")
            failures.append(f"{city['id']}: refused to move an existing point")
            continue
        if prev[0] is None:
            changed.append(city["id"])
        city["lat"] = lat
        city["lon"] = lon
        log(f"    [{i:2}/73] {city['id']:16s} {lat:8.4f} {lon:9.4f}  {as_}")

    (DATA / "cities.json").write_text(
        json.dumps(cities_doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    log(f"    wrote lat/lon for {len(processed)}/73 cities into data/cities.json ({len(changed)} newly added)")
    if failures:
        log(f"    !! {len(failures)} failed: {', '.join(failures[:6])}")

    write_processed(
        SOURCE_ID,
        processed,
        meta={
            "convention": CONVENTION,
            "fields": {
                "lat": "decimal degrees north, WGS 84",
                "lon": "decimal degrees east, WGS 84",
                "geocoded_as": "the place the geocoder actually matched, so a substitution is visible",
            },
            "confidence": "official",
            "level": "city",
            "cities_without_coordinates": failures,
            "precision_note": (
                "Rounded to four decimals (~11 m), far finer than anything the map draws. The map "
                "nudges overlapping dots apart for tappability and says so on screen; the list "
                "below the map is the exact, geography-free browser."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[f"{GEO}?name=<city>&count=10&language=en"],
        license_note=(
            "Open-Meteo's geocoding API serves GeoNames data — GeoNames is CC BY 4.0, "
            "Open-Meteo's own API terms are CC BY 4.0. Cite: GeoNames / Open-Meteo."
        ),
        redistribution="lat/lon per city committed in data/cities.json",
        transforms=[
            "Geocoded each of the 73 cities by name, accepting only hits whose country code "
            "matches the city's own and preferring the largest by population — the same rule, and "
            "the same cached responses, as the climate-normals step, so the two can never "
            "disagree about where a city is.",
            f"Kept latitude/longitude as decimal degrees (WGS 84), rounded to 4 dp. {CONVENTION}",
            "Recorded the matched place name in geocoded_as, so the two region-named records "
            "(sf_bay_area -> San Francisco, washington_dc -> Washington) show their substitution.",
            "Added lat and lon to each record in data/cities.json. No existing field was read, "
            "moved or modified; the step refuses to move a point it did not itself add.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(processed),
        coverage=f"{len(processed)}/73 cities",
        status="ok" if len(processed) == len(records) else ("partial" if processed else "failed"),
        notes=(
            "Feeds the Compare map only. Every figure on the site remains reachable without it — "
            "the country list under the map is the canonical browser."
        ),
    )

    # ---- the other half of the map's geography ---------------------------
    record_provenance(
        source_id=LAND_SOURCE_ID,
        name=LAND_NAME,
        urls=["https://www.naturalearthdata.com/downloads/110m-physical-vectors/110m-land/"],
        license_note=(
            "Public domain. Natural Earth asks for attribution but imposes no restriction: "
            "\"Made with Natural Earth.\""
        ),
        redistribution="derived outline committed in site/src/data/land.ts",
        transforms=[
            "Natural Earth 110m physical land, projected to the Compare map's Mercator box "
            "(lon -128..157, lat -45..62, 980x440 units) and decimated to ~14 KB of SVG path "
            "data — small enough to ship inline with no request and no map library.",
            "Committed as a derived asset rather than re-derived at build time: it is fixed "
            "geometry that never changes between runs, and shipping it inline is what keeps the "
            "map free of a runtime dependency.",
        ],
        output="site/src/data/land.ts",
        rows=None,
        coverage="world coastline within the map's crop",
        status="ok",
        notes=(
            "Decorative context for the dots. It carries no data: every value on the site is read "
            "from the list, never from the map."
        ),
    )


if __name__ == "__main__":
    main_guard(run)
