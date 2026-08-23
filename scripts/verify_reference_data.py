"""Package 16, Tier 4 — verify two datasets nothing else can catch, against genuinely independent sources.

Most quality checks in this repo are internal: shape, identity, coverage,
persistence. Two datasets cannot be checked that way at all, because nothing
else in the repo knows the right answer.

CITY COORDINATES. A wrong latitude does not fail any invariant. It does not
break a total, it does not shift a distribution, it does not look odd in a
profile. It silently puts a dot in the wrong place on a map, and it was added
late and never validated. The only way to check it is against a different
gazetteer -- and it must be a DIFFERENT one: `city_coordinates` came from
Open-Meteo's geocoder, which is GeoNames-derived, so `climate_normals` (same
geocoder, coordinates identical to five decimal places) is not a second opinion.
OpenStreetMap's Nominatim is built from independent survey and import data, so
it is.

FX RATES. Every converted figure on the site rests on these. They come from the
World Bank's PA.NUS.FCRF, an ANNUAL PERIOD AVERAGE of local currency per USD.
The independent check is the ECB's own daily reference rates, averaged over the
same calendar year -- averaged, not sampled, because a single day's rate is a
different quantity from a year's mean and comparing them would manufacture a
discrepancy that is really just a definition difference.

Both endpoints are public and unauthenticated. Nominatim's usage policy asks for
an identifying User-Agent and at most one request per second; both are honoured.

    python scripts/verify_reference_data.py
    python scripts/verify_reference_data.py --self-test
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, log  # noqa: E402

OUT = ROOT / "data" / "quality_history" / "reference_verification.json"
UA = "cs-migration-compass/data-quality-check (github.com/mojtaba-alehosseini/cs-migration-compass)"

# Beyond this, a coordinate is not "a slightly different city point", it is a
# different place. 25 km comfortably contains any reasonable disagreement about
# where a large city's centre is (Nominatim often returns an administrative
# centroid, GeoNames the settlement point) while still catching a wrong city,
# a wrong country, or a transposed sign.
MAX_ACCEPTABLE_KM = 25.0

# FX: the two sources are the same quantity by construction (annual mean of
# LCU/USD), so agreement should be tight. 2% allows for ECB business-day
# weighting against the World Bank's own averaging convention.
FX_TOLERANCE_PCT = 2.0


def _get(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def haversine_km(a_lat, a_lon, b_lat, b_lon) -> float:
    R = 6371.0088
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def verify_coordinates(limit: int | None = None) -> dict:
    cities = json.loads((ROOT / "data" / "cities.json").read_text(encoding="utf-8"))["records"]
    coords = json.loads((PROCESSED / "city_coordinates.json").read_text(encoding="utf-8"))["data"]
    by_id = {c["id"]: c for c in cities}

    rows, unchecked = [], []
    todo = [cid for cid in coords if cid in by_id]
    if limit:
        todo = todo[:limit]
    log(f"  checking {len(todo)} city coordinates against OpenStreetMap Nominatim "
        f"(1 req/sec, ~{len(todo)}s)")

    for i, cid in enumerate(todo):
        ours = coords[cid]
        city = by_id[cid]
        q = urllib.parse.urlencode({
            "q": f"{city['name']}, {city['country']}", "format": "json", "limit": 1,
            "addressdetails": 0,
        })
        try:
            time.sleep(1.1)
            hits = _get(f"https://nominatim.openstreetmap.org/search?{q}")
        except Exception as e:                                    # noqa: BLE001
            unchecked.append({"city": cid, "reason": f"{type(e).__name__}: {e}"})
            continue
        if not hits:
            unchecked.append({"city": cid, "reason": "no Nominatim match for the queried name"})
            continue
        h = hits[0]
        km = haversine_km(ours["lat"], ours["lon"], float(h["lat"]), float(h["lon"]))
        rows.append({
            "city": cid, "name": city["name"], "country": city["country"],
            "ours": [ours["lat"], ours["lon"]],
            "nominatim": [round(float(h["lat"]), 5), round(float(h["lon"]), 5)],
            "km_apart": round(km, 2),
            "our_geocoded_as": ours.get("geocoded_as"),
            "nominatim_matched": h.get("display_name", "")[:90],
            "within_tolerance": km <= MAX_ACCEPTABLE_KM,
        })
        if (i + 1) % 20 == 0:
            log(f"    {i+1}/{len(todo)}")

    bad = [r for r in rows if not r["within_tolerance"]]
    km = sorted(r["km_apart"] for r in rows)
    return {
        "independent_source": "OpenStreetMap Nominatim",
        "why_independent": ("city_coordinates was geocoded with Open-Meteo, which is "
                            "GeoNames-derived. climate_normals used the same geocoder and its "
                            "coordinates agree to 5 dp, so it is not a second opinion. Nominatim "
                            "is built from independent OSM survey and import data."),
        "tolerance_km": MAX_ACCEPTABLE_KM,
        "n_checked": len(rows), "n_unchecked": len(unchecked), "unchecked": unchecked,
        "max_discrepancy_km": km[-1] if km else None,
        "median_discrepancy_km": km[len(km) // 2] if km else None,
        "p90_discrepancy_km": km[int(0.9 * (len(km) - 1))] if km else None,
        "n_outside_tolerance": len(bad),
        "outside_tolerance": sorted(bad, key=lambda r: -r["km_apart"]),
        "worst_10": sorted(rows, key=lambda r: -r["km_apart"])[:10],
    }


FX_SPOT_CHECKS = [("GBP", 2015), ("SEK", 2018), ("JPY", 2020), ("CAD", 2022), ("AUD", 2023)]
CURRENCY_OF = {"GB": "GBP", "SE": "SEK", "JP": "JPY", "CA": "CAD", "AU": "AUD",
               "NO": "NOK", "DK": "DKK", "IN": "INR", "SG": "SGD"}


def verify_fx() -> dict:
    fx = json.loads((PROCESSED / "fx_rates.json").read_text(encoding="utf-8"))["data"]
    iso_of = {v: k for k, v in CURRENCY_OF.items()}
    rows = []
    for cur, year in FX_SPOT_CHECKS:
        cc = iso_of[cur]
        ours = next((r["value"] for r in fx.get(cc, [])
                     if r.get("year") == year and r.get("value") is not None), None)
        if ours is None:
            rows.append({"currency": cur, "year": year, "ours": None,
                         "note": "not present in fx_rates.json"})
            continue
        try:
            # ECB daily reference rates for the whole year, EUR-based.
            d = _get(f"https://api.frankfurter.app/{year}-01-01..{year}-12-31"
                     f"?from=EUR&to={cur},USD")
            rates = d.get("rates", {})
            per_day = [(v[cur] / v["USD"]) for v in rates.values()
                       if cur in v and v.get("USD")]
            if not per_day:
                rows.append({"currency": cur, "year": year, "ours": ours,
                             "note": "ECB returned no usable days"})
                continue
            theirs = sum(per_day) / len(per_day)
            diff = 100 * (ours - theirs) / theirs
            rows.append({
                "currency": cur, "year": year,
                "ours_worldbank_lcu_per_usd": round(ours, 5),
                "theirs_ecb_annual_mean_lcu_per_usd": round(theirs, 5),
                "n_business_days_averaged": len(per_day),
                "diff_pct": round(diff, 3),
                "agrees": abs(diff) <= FX_TOLERANCE_PCT,
            })
        except Exception as e:                                    # noqa: BLE001
            rows.append({"currency": cur, "year": year, "ours": ours,
                         "note": f"{type(e).__name__}: {e}"})
    checked = [r for r in rows if "diff_pct" in r]
    return {
        "independent_source": "European Central Bank daily reference rates (via frankfurter.app)",
        "method": ("both quantities are an ANNUAL MEAN of local currency per USD. The ECB side is "
                   "computed by averaging every business day's LCU/EUR divided by USD/EUR across "
                   "the calendar year -- averaged rather than sampled, because one day's rate is a "
                   "different quantity from a year's mean and comparing them would manufacture a "
                   "discrepancy that is only a definition difference."),
        "tolerance_pct": FX_TOLERANCE_PCT,
        "checks": rows,
        "n_checked": len(checked),
        "n_agreeing": sum(1 for r in checked if r["agrees"]),
        "max_abs_diff_pct": round(max((abs(r["diff_pct"]) for r in checked), default=0), 3),
    }


def run(limit: int | None = None) -> int:
    log("verifying two datasets against independent external sources")
    art = {"schema": "package-16 reference verification v1"}

    art["city_coordinates"] = verify_coordinates(limit=limit)
    c = art["city_coordinates"]
    log(f"  coordinates: {c['n_checked']} checked, median {c['median_discrepancy_km']} km, "
        f"max {c['max_discrepancy_km']} km, {c['n_outside_tolerance']} outside "
        f"{c['tolerance_km']} km")
    for b in c["outside_tolerance"][:8]:
        log(f"    {b['city']:<18} {b['km_apart']:>8.1f} km   ours={b['our_geocoded_as']!r} "
            f"osm={b['nominatim_matched']!r}")

    art["fx_rates"] = verify_fx()
    f = art["fx_rates"]
    log(f"  fx: {f['n_agreeing']}/{f['n_checked']} agree within {f['tolerance_pct']}%, "
        f"max |diff| {f['max_abs_diff_pct']}%")
    for r in f["checks"]:
        if "diff_pct" in r:
            log(f"    {r['currency']} {r['year']}: ours {r['ours_worldbank_lcu_per_usd']:>10.4f} "
                f"vs ECB {r['theirs_ecb_annual_mean_lcu_per_usd']:>10.4f}  "
                f"{r['diff_pct']:+.2f}%  {'ok' if r['agrees'] else 'DISAGREES'}")
        else:
            log(f"    {r['currency']} {r['year']}: {r.get('note')}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


def self_test() -> int:
    fails = []

    def ck(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  [' + detail + ']') if detail else ''}")
        if not cond:
            fails.append(name)

    print("=== verify_reference_data.py self-test ===")

    # distance maths, against known separations
    ck("identical points are 0 km apart", haversine_km(51.5, -0.12, 51.5, -0.12) < 0.001)
    d = haversine_km(51.5074, -0.1278, 48.8566, 2.3522)          # London -> Paris
    ck("London to Paris is ~344 km", 330 < d < 355, f"{d:.0f} km")
    d2 = haversine_km(-33.8678, 151.2073, -37.8136, 144.9631)    # Sydney -> Melbourne
    ck("Sydney to Melbourne is ~714 km", 690 < d2 < 730, f"{d2:.0f} km")

    # the check must FIRE on the failure modes it exists for
    ck("a flipped latitude sign is caught",
       haversine_km(-33.8678, 151.2073, 33.8678, 151.2073) > MAX_ACCEPTABLE_KM,
       f"{haversine_km(-33.8678, 151.2073, 33.8678, 151.2073):.0f} km")
    ck("transposed lat/lon is caught",
       haversine_km(51.5074, -0.1278, -0.1278, 51.5074) > MAX_ACCEPTABLE_KM)
    ck("the wrong city in the right country is caught",
       haversine_km(40.7128, -74.0060, 34.0522, -118.2437) > MAX_ACCEPTABLE_KM,
       "New York vs Los Angeles")
    ck("a genuine centroid-vs-settlement-point difference is NOT flagged",
       haversine_km(51.5074, -0.1278, 51.5285, -0.2416) <= MAX_ACCEPTABLE_KM,
       f"{haversine_km(51.5074, -0.1278, 51.5285, -0.2416):.1f} km apart")

    # FX comparison must be a RATIO test, not an absolute one
    ck("a 1% FX difference is within tolerance", abs(100 * (1.01 - 1.0) / 1.0) <= FX_TOLERANCE_PCT)
    ck("a 10% FX difference is not", abs(100 * (1.10 - 1.0) / 1.0) > FX_TOLERANCE_PCT)

    print(f"\n{len(fails)} failure(s)" + (" — all controls hold" if not fails else f": {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="check only the first N cities")
    a = ap.parse_args()
    raise SystemExit(self_test() if a.self_test else run(limit=a.limit))
