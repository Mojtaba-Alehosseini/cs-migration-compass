"""Monthly climate normals → cities.json climate.monthly.

The curated data already carries annual summaries (sunshine hours, a summer high,
a winter low). Those answer "is it sunny" but not "what is February actually
like", which is the question that decides whether someone can live somewhere.

This computes proper 30-year normals over the WMO standard reference period
1991-2020, per city, per calendar month:

    avg_high_c   mean daily maximum
    avg_low_c    mean daily minimum
    mean_c       mean of the two

Rate limiting is the design constraint here. Open-Meteo's free tier caps request
VOLUME per hour, and 30 years x 73 cities is far past it, so:
  * we request two variables, not three (precipitation was dropped — the
    temperature curve and the climate matcher do not use it, and it cost a third
    of the budget);
  * every response is cached, so a re-run resumes rather than restarting;
  * a 429 stops the run cleanly, keeps what was already fetched, and says when
    to resume. It never leaves a half-written city record.

Source: Open-Meteo's ERA5 reanalysis archive — free, keyless, and the same
underlying dataset national met services publish normals from. It is reanalysis
rather than a station record, so it is tagged confidence "index", not "official",
and it does NOT overwrite the curated annual fields, which came from station
data. Both are kept, and they are allowed to disagree.

Geocoding is disambiguated by our own country code (there are five Valencias)
and by population, with a manual override table for the awkward ones.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA, RAW, banner, fetch_json, load_cities, log, main_guard,
    record_provenance, write_processed,
)

SOURCE_ID = "climate_normals"
NAME = "Open-Meteo ERA5 archive — 1991-2020 monthly climate normals"
GEO = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
START, END = "1991-01-01", "2020-12-31"
PERIOD = "1991-2020 (WMO standard reference period)"
DELAY = 0.6

# Where the city's common name does not geocode cleanly on its own.
GEO_OVERRIDE = {
    "sf_bay_area": "San Francisco",
    "washington_dc": "Washington",
    "new_york": "New York",
    "san_antonio": "San Antonio",
    "salt_lake_city": "Salt Lake City",
    "las_vegas": "Las Vegas",
    "los_angeles": "Los Angeles",
    "san_diego": "San Diego",
    "gold-coast": "Gold Coast",
    "abu-dhabi": "Abu Dhabi",
}


def geocode(city: dict) -> dict | None:
    name = GEO_OVERRIDE.get(city["id"], city["name"])
    doc = fetch_json(
        f"{GEO}?name={name.replace(' ', '+')}&count=10&language=en",
        dest=RAW / SOURCE_ID / f"geo_{city['id']}.json",
        retries=2,
    )
    results = doc.get("results") or []
    # Only accept a hit in the country we already know the city belongs to.
    same_country = [r for r in results if r.get("country_code") == city["country"]]
    if not same_country:
        return None
    same_country.sort(key=lambda r: -(r.get("population") or 0))
    return same_country[0]


class RateLimited(RuntimeError):
    pass


def normals(lat: float, lon: float, city_id: str, cache_only: bool = False) -> list[dict] | None:
    dest = RAW / SOURCE_ID / f"daily_{city_id}.json"
    # Once the hourly limit is hit we stop asking the API entirely, but keep
    # draining whatever is already on disk — the cities cached in earlier runs
    # are still perfectly good and should not be thrown away.
    if cache_only and not dest.exists():
        raise RateLimited("rate limited earlier in this run; nothing cached for this city")
    doc = fetch_json(
        f"{ARCHIVE}?latitude={lat}&longitude={lon}&start_date={START}&end_date={END}"
        "&daily=temperature_2m_max,temperature_2m_min&timezone=UTC",
        dest=dest,
        retries=2,
    )
    daily = doc.get("daily") or {}
    times = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    if not times:
        return None

    buckets: dict[int, dict[str, list]] = {m: {"hi": [], "lo": []} for m in range(1, 13)}

    for i, t in enumerate(times):
        month = int(t[5:7])
        hi = tmax[i] if i < len(tmax) else None
        lo = tmin[i] if i < len(tmin) else None
        if hi is not None:
            buckets[month]["hi"].append(hi)
        if lo is not None:
            buckets[month]["lo"].append(lo)

    out = []
    for m in range(1, 13):
        his, los = buckets[m]["hi"], buckets[m]["lo"]
        if not his or not los:
            continue
        avg_hi = sum(his) / len(his)
        avg_lo = sum(los) / len(los)
        out.append({
            "month": m,
            "avg_high_c": round(avg_hi, 1),
            "avg_low_c": round(avg_lo, 1),
            "mean_c": round((avg_hi + avg_lo) / 2, 1),
        })
    return out if len(out) == 12 else None


def run() -> None:
    banner(SOURCE_ID, NAME)
    cities_doc = json.loads((DATA / "cities.json").read_text(encoding="utf-8"))
    records = cities_doc["records"]

    processed: dict[str, dict] = {}
    failures: list[str] = []
    pending: list[str] = []
    rate_limited = False

    for i, city in enumerate(records, 1):
        try:
            place = geocode(city)
            if place is None:
                failures.append(f"{city['id']}: no geocode match in {city['country']}")
                log(f"    [{i:2}/73] {city['id']:16s} !! no geocode match")
                continue
            lat, lon = place["latitude"], place["longitude"]
            series = normals(lat, lon, city["id"], cache_only=rate_limited)
            if series is None:
                failures.append(f"{city['id']}: incomplete normals")
                log(f"    [{i:2}/73] {city['id']:16s} !! incomplete series")
                continue
        except Exception as exc:  # noqa: BLE001 — one city must not kill the run
            if isinstance(exc, RateLimited):
                pending.append(city["id"])
                continue
            if "429" in str(exc):
                if not rate_limited:
                    log(f"    [{i:2}/73] {city['id']:16s} !! hourly rate limit reached")
                    log("    No further requests this run. Already-cached cities still process;")
                    log("    re-run in the next hour to fetch the rest — nothing is re-downloaded.")
                rate_limited = True
                pending.append(city["id"])
                continue
            failures.append(f"{city['id']}: {type(exc).__name__}")
            log(f"    [{i:2}/73] {city['id']:16s} !! {type(exc).__name__}")
            time.sleep(DELAY)
            continue

        warmest = max(series, key=lambda r: r["avg_high_c"])
        coldest = min(series, key=lambda r: r["avg_low_c"])
        processed[city["id"]] = {
            "lat": lat, "lon": lon,
            "geocoded_as": f"{place.get('name')}, {place.get('admin1') or ''} {place.get('country_code')}".strip(),
            "period": PERIOD,
            "monthly": series,
        }
        # Additive only: the curated annual fields stay exactly as they are.
        city["climate"]["monthly"] = series
        city["climate"]["monthly_source"] = "open-meteo ERA5 1991-2020"
        log(f"    [{i:2}/73] {city['id']:16s} warmest {warmest['month']:2}mo "
            f"{warmest['avg_high_c']:5.1f}C · coldest {coldest['month']:2}mo {coldest['avg_low_c']:6.1f}C")
        time.sleep(DELAY)

    cities_doc["climate_normals_added_at"] = PERIOD
    (DATA / "cities.json").write_text(
        json.dumps(cities_doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    log(f"    wrote monthly normals for {len(processed)}/73 cities into data/cities.json")
    if failures:
        log(f"    !! {len(failures)} failed: {', '.join(failures[:6])}")
    if pending:
        log(f"    {len(pending)} awaiting the next rate-limit window — re-run to continue")

    write_processed(
        SOURCE_ID,
        processed,
        meta={
            "period": PERIOD,
            "fields": {
                "avg_high_c": "mean daily maximum for that calendar month",
                "avg_low_c": "mean daily minimum",
                "mean_c": "mean of the daily max and min",
            },
            "confidence": "index",
            "level": "city",
            "cities_without_normals": failures,
            "cities_pending_rate_limit": pending,
            "reanalysis_caveat": (
                "ERA5 is a global reanalysis on a ~25 km grid, not a station record. It is excellent "
                "for the shape of a year and for comparing cities on a like-for-like basis, but a "
                "coastal or mountain city can differ from its nearest official station by a degree or "
                "two. The curated annual fields, which come from station data, are left untouched and "
                "are allowed to disagree."
            ),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[f"{GEO}?name=<city>", f"{ARCHIVE}?latitude=..&longitude=..&start_date={START}&end_date={END}"],
        license_note=(
            "Open-Meteo data is CC BY 4.0; underlying ERA5 is Copernicus Climate Change Service "
            "information. Cite: Open-Meteo / Copernicus ERA5."
        ),
        transforms=[
            "Geocoded each city, keeping only hits whose country code matches the city's own "
            "(there are five Valencias) and preferring the largest by population.",
            f"Fetched daily max/min temperature and precipitation for {START}..{END} (10,958 days per city).",
            "Aggregated to 12 calendar-month normals: mean daily max, mean daily min and their midpoint. "
            "Precipitation was deliberately not requested — it is unused downstream and cost a third of "
            "the hourly rate-limit budget.",
            "Wrote the series to climate.monthly on each city record. Existing annual climate fields "
            "were NOT modified — they come from station data and are kept as an independent signal.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(processed) * 12,
        coverage=f"{len(processed)}/73 cities x 12 months, {PERIOD}",
        status=("partial" if (failures or rate_limited) else "ok") if processed else "failed",
        notes=(
            "Reanalysis, not station observations — tagged 'index' rather than 'official'. "
            + ("Run stopped early on Open-Meteo's hourly rate limit; re-run to resume from cache."
               if rate_limited else "")
        ),
    )


if __name__ == "__main__":
    main_guard(run)
