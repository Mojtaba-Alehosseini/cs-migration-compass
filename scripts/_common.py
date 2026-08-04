"""Shared plumbing for every CS Migration Compass pipeline script.

Design rules (these are why this file exists):
  * Every download lands in data/raw/<source_id>/ verbatim, then is transformed
    into data/processed/<source_id>.json. Raw is committed so the repo is
    self-contained and any transform can be re-audited without network access.
  * Every run appends an entry to data/provenance.json: url, fetched_at,
    license, transforms. docs/SOURCES.md is GENERATED from that file.
  * Several hosts (UN DESA, the BLS website, EF, WIPO) return HTTP 403 to
    default Python user agents. We always send a browser-like User-Agent.
    This is documented and verified in data/data-pipeline-sources.json.
  * Nothing here fabricates a value. A failed fetch yields None and is recorded
    as a failure in provenance; it never yields a plausible-looking number.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import requests

# housepriceindex.ca (Teranet) serves a chain whose intermediate is absent from
# certifi's bundle, so requests fails TLS verification against it. Using the OS
# trust store fixes it properly — we never disable certificate verification.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover - optional but listed in requirements.txt
    pass

# Windows consoles default to cp1252 and choke on the box-drawing characters and
# country names (Montréal, Türkiye) this pipeline prints. Force UTF-8 output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass

# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
PROVENANCE = DATA / "provenance.json"
SOURCES_FILE = DATA / "data-pipeline-sources.json"

RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# HTTP — browser-like UA is mandatory for several hosts (verified 403 otherwise)
# --------------------------------------------------------------------------

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 90


class FetchError(RuntimeError):
    pass


def fetch(
    url: str,
    *,
    dest: Path | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    json_body: Any = None,
    retries: int = 3,
    backoff: float = 2.0,
    cache: bool = True,
) -> bytes:
    """Download `url` to `dest` (if given) and return the body bytes.

    Re-uses an existing `dest` when `cache` is True so repeated pipeline runs
    do not hammer the upstream host. `make pipeline-fresh` clears data/raw to
    force a true from-scratch run.
    """
    if dest is not None and cache and dest.exists() and dest.stat().st_size > 0:
        log(f"    cached  {dest.relative_to(ROOT)}")
        return dest.read_bytes()

    h = dict(DEFAULT_HEADERS)
    if headers:
        h.update(headers)

    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if method.upper() == "POST":
                r = requests.post(url, headers=h, json=json_body, timeout=TIMEOUT)
            else:
                r = requests.get(url, headers=h, timeout=TIMEOUT)
            r.raise_for_status()
            body = r.content
            if not body:
                raise FetchError("empty response body")
            if dest is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(body)
                log(f"    saved   {dest.relative_to(ROOT)}  ({len(body):,} bytes)")
            return body
        except Exception as exc:  # noqa: BLE001 - we retry on anything transient
            last = exc
            if attempt < retries:
                wait = backoff ** attempt
                log(f"    retry {attempt}/{retries} in {wait:.0f}s — {type(exc).__name__}: {exc}")
                time.sleep(wait)

    raise FetchError(f"{url} failed after {retries} attempts: {last}")


def fetch_json(url: str, **kw: Any) -> Any:
    return json.loads(fetch(url, **kw))


def fetch_text(url: str, encoding: str = "utf-8", **kw: Any) -> str:
    return fetch(url, **kw).decode(encoding, errors="replace")


# --------------------------------------------------------------------------
# logging
# --------------------------------------------------------------------------

def log(msg: str) -> None:
    print(msg, flush=True)


def banner(source_id: str, name: str) -> None:
    log("")
    log(f"── {source_id} — {name}")


# --------------------------------------------------------------------------
# provenance
# --------------------------------------------------------------------------

def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def load_provenance() -> dict:
    if PROVENANCE.exists():
        return json.loads(PROVENANCE.read_text(encoding="utf-8"))
    return {"schema": "cs-migration-compass/provenance@1", "entries": []}


def record_provenance(
    *,
    source_id: str,
    name: str,
    urls: Iterable[str],
    license_note: str,
    transforms: list[str],
    output: str | None,
    status: str = "ok",
    rows: int | None = None,
    coverage: str | None = None,
    notes: str | None = None,
    redistribution: str = "raw committed",
) -> None:
    """Append (replacing any prior entry for the same source_id) a provenance record."""
    prov = load_provenance()
    entry = {
        "source_id": source_id,
        "name": name,
        "urls": list(urls),
        "fetched_at": _now(),
        "license": license_note,
        "redistribution": redistribution,
        "transforms": transforms,
        "output": output,
        "status": status,
        "rows": rows,
        "coverage": coverage,
        "notes": notes,
    }
    prov["entries"] = [e for e in prov["entries"] if e.get("source_id") != source_id]
    prov["entries"].append(entry)
    prov["entries"].sort(key=lambda e: e["source_id"])
    prov["updated_at"] = _now()
    PROVENANCE.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"    provenance recorded ({status})")


def write_processed(source_id: str, payload: Any, *, meta: dict | None = None) -> Path:
    """Write data/processed/<source_id>.json with a standard envelope."""
    out = PROCESSED / f"{source_id}.json"
    envelope = {
        "source_id": source_id,
        "generated_at": _now(),
        "meta": meta or {},
        "data": payload,
    }
    out.write_text(json.dumps(envelope, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"    wrote   {out.relative_to(ROOT)}")
    return out


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------
# JSON-stat 2.0 decoding (Eurostat dissemination API)
# --------------------------------------------------------------------------

def jsonstat_rows(doc: dict) -> Iterable[dict]:
    """Yield {dim_id: category_key, ..., '_value': v} for every non-null cell.

    JSON-stat packs values into a flat map keyed by a row-major linear index over
    the dimensions listed in doc['id'] with sizes doc['size']. Sparse datasets use
    a dict; dense ones use a list. Both are handled.
    """
    dims: list[str] = doc["id"]
    sizes: list[int] = doc["size"]
    # ordered category keys per dimension
    cats: list[list[str]] = []
    for d in dims:
        index = doc["dimension"][d]["category"]["index"]
        if isinstance(index, dict):
            keys = sorted(index, key=lambda k: index[k])
        else:
            keys = list(index)
        cats.append(keys)

    # strides for row-major decoding
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    values = doc["value"]
    items = values.items() if isinstance(values, dict) else enumerate(values)
    for raw_idx, v in items:
        if v is None:
            continue
        idx = int(raw_idx)
        row: dict = {}
        for i, dim in enumerate(dims):
            row[dim] = cats[i][(idx // strides[i]) % sizes[i]]
        row["_value"] = v
        yield row


def jsonstat_labels(doc: dict, dim: str) -> dict[str, str]:
    cat = doc["dimension"][dim]["category"]
    return cat.get("label", {})


# --------------------------------------------------------------------------
# the 15 countries and 73 cities we actually cover
# --------------------------------------------------------------------------

def load_countries() -> list[dict]:
    return json.loads((DATA / "countries.json").read_text(encoding="utf-8"))["records"]


def load_cities() -> list[dict]:
    return json.loads((DATA / "cities.json").read_text(encoding="utf-8"))["records"]


def load_source_spec(source_id: str) -> dict:
    """Pull the verified URL + gotchas for a source from data-pipeline-sources.json.

    We trust that file's URLs over guessing — they were verified by hand.
    """
    spec = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    for s in spec["sources"]:
        if s["id"] == source_id:
            return s
    raise KeyError(f"{source_id} not in data-pipeline-sources.json")


COUNTRY_IDS = ["AU", "US", "CA", "GB", "IE", "DE", "NL", "IT", "ES", "SE", "DK", "NO", "FI", "AE", "QA"]

ISO2_TO_ISO3 = {
    "AU": "AUS", "US": "USA", "CA": "CAN", "GB": "GBR", "IE": "IRL",
    "DE": "DEU", "NL": "NLD", "IT": "ITA", "ES": "ESP", "SE": "SWE",
    "DK": "DNK", "NO": "NOR", "FI": "FIN", "AE": "ARE", "QA": "QAT",
}
ISO3_TO_ISO2 = {v: k for k, v in ISO2_TO_ISO3.items()}

# UN M49 numeric codes (UN DESA migrant stock, UN WPP)
ISO2_TO_M49 = {
    "AU": 36, "US": 840, "CA": 124, "GB": 826, "IE": 372, "DE": 276,
    "NL": 528, "IT": 380, "ES": 724, "SE": 752, "DK": 208, "NO": 578,
    "FI": 246, "AE": 784, "QA": 634,
}
IRAN_M49 = 364

# Eurostat geo codes: mostly ISO2, but GB->UK and GR->EL.
ISO2_TO_EUROSTAT = {c: c for c in COUNTRY_IDS}
ISO2_TO_EUROSTAT["GB"] = "UK"

# Full country names as they appear in loosely-typed sources (WHR, MIPEX, RSF, Numbeo).
COUNTRY_NAMES = {
    "AU": "Australia", "US": "United States", "CA": "Canada",
    "GB": "United Kingdom", "IE": "Ireland", "DE": "Germany",
    "NL": "Netherlands", "IT": "Italy", "ES": "Spain", "SE": "Sweden",
    "DK": "Denmark", "NO": "Norway", "FI": "Finland",
    "AE": "United Arab Emirates", "QA": "Qatar",
}

# Aliases seen across sources — matched case-insensitively after stripping.
NAME_ALIASES = {
    "united states of america": "US", "usa": "US", "u.s.": "US", "united states": "US",
    "united kingdom of great britain and northern ireland": "GB",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "britain": "GB",
    "netherlands (kingdom of the)": "NL", "the netherlands": "NL", "holland": "NL",
    "korea, rep.": None,
    "united arab emirates": "AE", "uae": "AE",
    "russian federation": None,
    "türkiye": None, "turkiye": None,
    "czechia": None,
    "germany": "DE", "france": None,
    "australia": "AU", "canada": "CA", "ireland": "IE", "italy": "IT",
    "spain": "ES", "sweden": "SE", "denmark": "DK", "norway": "NO",
    "finland": "FI", "qatar": "QA",
}


def to_iso2(name_or_code: Any) -> str | None:
    """Best-effort resolve any country label to one of our 15 ISO2 codes, else None.

    Deliberately conservative: an unrecognised label returns None rather than a
    guess. Callers count and report the misses.
    """
    if name_or_code is None:
        return None
    s = str(name_or_code).strip()
    if not s:
        return None
    up = s.upper()
    if up in ISO2_TO_ISO3:
        return up
    if up in ISO3_TO_ISO2:
        return ISO3_TO_ISO2[up]
    if up == "UK":
        return "GB"
    if up == "EL":
        return None
    low = s.lower().strip()
    for iso2, nm in COUNTRY_NAMES.items():
        if low == nm.lower():
            return iso2
    if low in NAME_ALIASES:
        return NAME_ALIASES[low]
    return None


# --------------------------------------------------------------------------
# city-level identifier maps (US CBSA, UK HPI region, Teranet series)
# --------------------------------------------------------------------------

# US metro CBSA codes (2020 delineations) — drive both FHFA metro HPI and
# BLS OEWS metro series IDs.
US_CITY_CBSA = {
    "new_york": "35620",       # New York-Newark-Jersey City, NY-NJ-PA
    "boston": "14460",         # Boston-Cambridge-Newton, MA-NH
    "chicago": "16980",        # Chicago-Naperville-Elgin, IL-IN-WI
    "atlanta": "12060",        # Atlanta-Sandy Springs-Alpharetta, GA
    "raleigh": "39580",        # Raleigh-Cary, NC
    "dallas": "19100",         # Dallas-Fort Worth-Arlington, TX
    "houston": "26420",        # Houston-The Woodlands-Sugar Land, TX
    "san_antonio": "41700",    # San Antonio-New Braunfels, TX
    "miami": "33100",          # Miami-Fort Lauderdale-Pompano Beach, FL
    "tampa": "45300",          # Tampa-St. Petersburg-Clearwater, FL
    "orlando": "36740",        # Orlando-Kissimmee-Sanford, FL
    "nashville": "34980",      # Nashville-Davidson--Murfreesboro--Franklin, TN
    "charlotte": "16740",      # Charlotte-Concord-Gastonia, NC-SC
    "washington_dc": "47900",  # Washington-Arlington-Alexandria, DC-VA-MD-WV
    "philadelphia": "37980",   # Philadelphia-Camden-Wilmington, PA-NJ-DE-MD
    "sf_bay_area": "41860",    # San Francisco-Oakland-Berkeley, CA (see note below)
    "seattle": "42660",        # Seattle-Tacoma-Bellevue, WA
    "austin": "12420",         # Austin-Round Rock-Georgetown, TX
    "denver": "19740",         # Denver-Aurora-Lakewood, CO
    "los_angeles": "31080",    # Los Angeles-Long Beach-Anaheim, CA
    "san_diego": "41740",      # San Diego-Chula Vista-Carlsbad, CA
    "sacramento": "40900",     # Sacramento-Roseville-Folsom, CA
    "portland": "38900",       # Portland-Vancouver-Hillsboro, OR-WA
    "phoenix": "38060",        # Phoenix-Mesa-Chandler, AZ
    "salt_lake_city": "41620", # Salt Lake City, UT
    "las_vegas": "29820",      # Las Vegas-Henderson-Paradise, NV
    "pittsburgh": "38300",     # Pittsburgh, PA
    "minneapolis": "33460",    # Minneapolis-St. Paul-Bloomington, MN-WI
    "columbus": "18140",       # Columbus, OH
    "detroit": "19820",        # Detroit-Warren-Dearborn, MI
}

# Our "sf_bay_area" record spans SF + San Jose. San Jose is a separate CBSA and
# is where the big-tech pay actually concentrates, so we fetch BOTH and label
# which is which rather than silently averaging.
US_CITY_CBSA_SECONDARY = {
    "sf_bay_area": "41940",  # San Jose-Sunnyvale-Santa Clara, CA
}

# FHFA's metro HPI file uses the 2023 CBSA delineations, and for 13 of our 30
# metros it publishes only the METROPOLITAN DIVISION (MSAD), not the whole MSA.
# A division is a *subset* of the metro area (e.g. "Detroit-Dearborn-Livonia"
# is the inner part of "Detroit-Warren-Dearborn"), so these codes are NOT
# interchangeable with the OEWS CBSA codes above. Keeping them in a separate map
# — and labelling the division in the UI — is the honest handling.
# Verified against the live file: all 30 resolve.
US_CITY_FHFA = {
    "new_york": "35614",       # New York-Jersey City-White Plains, NY-NJ (MSAD)
    "boston": "14454",         # Boston, MA (MSAD)
    "chicago": "16984",        # Chicago-Naperville-Schaumburg, IL (MSAD)
    "atlanta": "12054",        # Atlanta-Sandy Springs-Roswell, GA (MSAD)
    "raleigh": "39580",
    "dallas": "19124",         # Dallas-Plano-Irving, TX (MSAD)
    "houston": "26420",
    "san_antonio": "41700",
    "miami": "33124",          # Miami-Miami Beach-Kendall, FL (MSAD)
    "tampa": "45294",          # Tampa, FL (MSAD)
    "orlando": "36740",
    "nashville": "34980",
    "charlotte": "16740",
    "washington_dc": "47764",  # Washington, DC-MD (MSAD)
    "philadelphia": "37964",   # Philadelphia, PA (MSAD)
    "sf_bay_area": "41884",    # San Francisco-San Mateo-Redwood City, CA (MSAD)
    "seattle": "42644",        # Seattle-Bellevue-Kent, WA (MSAD)
    "austin": "12420",
    "denver": "19740",
    "los_angeles": "31084",    # Los Angeles-Long Beach-Glendale, CA (MSAD)
    "san_diego": "41740",
    "sacramento": "40900",
    "portland": "38900",
    "phoenix": "38060",
    "salt_lake_city": "41620",
    "las_vegas": "29820",
    "pittsburgh": "38300",
    "minneapolis": "33460",
    "columbus": "18140",
    "detroit": "19804",        # Detroit-Dearborn-Livonia, MI (MSAD)
}

# Second FHFA series for the Bay Area, same reasoning as the salary two-tier story.
US_CITY_FHFA_SECONDARY = {
    "sf_bay_area": "41940",  # San Jose-Sunnyvale-Santa Clara, CA (full MSA)
}

# Teranet–National Bank series keys (housepriceindex.ca), province-prefixed.
# Verified live: all 6 of our Canadian cities exist.
CA_CITY_TERANET_KEY = {
    "toronto": "on_toronto",
    "vancouver": "bc_vancouver",
    "montreal": "qc_montreal",
    "ottawa": "on_ottawa",     # published as "Ottawa-Gatineau"
    "calgary": "ab_calgary",
    "halifax": "ns_halifax",
}

# UK HPI "RegionName" values (full file uses local authority / city names).
UK_CITY_HPI_REGION = {
    "london": "London",
    "manchester": "Manchester",
    "edinburgh": "City of Edinburgh",
}

# Teranet–National Bank city series labels (housepriceindex.ca).
CA_CITY_TERANET = {
    "toronto": "Toronto",
    "vancouver": "Vancouver",
    "montreal": "Montreal",
    "ottawa": "Ottawa-Gatineau",
    "calgary": "Calgary",
    "halifax": "Halifax",
}

# Numbeo city-history slugs (city page URL segment).
NUMBEO_CITY_SLUG_OVERRIDES = {
    "sf_bay_area": "San-Francisco",
    "new_york": "New-York",
    "washington_dc": "Washington",
    "san_antonio": "San-Antonio",
    "salt_lake_city": "Salt-Lake-City",
    "las_vegas": "Las-Vegas",
    "los_angeles": "Los-Angeles",
    "san_diego": "San-Diego",
    "gold-coast": "Gold-Coast",
    "abu-dhabi": "Abu-Dhabi",
}


def numbeo_slug(city: dict) -> str:
    cid = city["id"]
    if cid in NUMBEO_CITY_SLUG_OVERRIDES:
        return NUMBEO_CITY_SLUG_OVERRIDES[cid]
    return city["name"].replace(" ", "-")


# --------------------------------------------------------------------------
# script entry-point helper
# --------------------------------------------------------------------------

def main_guard(fn) -> None:
    """Run `fn`, turning any exception into a recorded failure + non-zero exit.

    The orchestrator keeps going when one source is down; it reports at the end.
    """
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        log(f"    FAILED: {type(exc).__name__}: {exc}")
        sys.exit(1)
