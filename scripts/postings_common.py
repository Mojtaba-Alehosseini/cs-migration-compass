"""Package 12 — shared plumbing for every postings-panel harvester.

WHY THIS FILE IS SEPARATE FROM _common.py: postings are a genuinely different
kind of data from everything else this pipeline touches (see the work order's
own Tier 5.1 and phase-4-salary-and-cv-plan.md's own S2.4). _common.py's own
`fetch()`/`write_processed()`/`record_provenance()` are reused as-is — this
file adds ONLY what's specific to job postings: a common Posting shape every
provider harvester normalises into, currency/compensation-range text parsing,
and the ISO2 best-effort location resolver. Nothing here ever touches
data/processed/wage_distribution.json or any file scripts/normalise.py owns —
that boundary is enforced by not importing this module from anywhere in the
survey-earnings pipeline, and by two validate_data.py checks: the package-7
check_survey_vs_advertised_pay (which scans WITHIN one file for co-occurring
hint words, not a cross-file comparison — an earlier version of this
docstring described it as comparing the two files, which this package's own
adversarial review found it does not do), and check_postings_wage_spine_
boundary (package 12, genuinely cross-file: postings.json and
wage_distribution.json's own distinctive field names, checked never to
appear in the other).

A POSTING RECORD, THE COMMON SHAPE EVERY PROVIDER HARVESTER PRODUCES:
{
  "id": "ashby:ramp:abc123",          # provider:company_token:native_id — globally unique, stable across runs
  "provider": "ashby",
  "company": "Ramp" | None,             # from the API's own response WHEN IT PUBLISHES ONE -- Greenhouse
                                        # and Teamtailor always do; Ashby's public job-board API and
                                        # Lever's public postings API do not publish a display name
                                        # anywhere in their response (checked live against real cached
                                        # responses, not assumed -- an earlier version of this docstring
                                        # claimed "never guessed from the token" as if a name were always
                                        # available, which this package's own adversarial review found
                                        # was false 100% of the time for both providers). The UI falls
                                        # back to a de-slugified token for display (postings.ts's own
                                        # fmtCompany()) when this field is None -- the token itself, not
                                        # a guessed name.
  "company_slug": "ramp",              # the seed token — what re-identifies this board next run
  "title": "Security Engineer, Cloud",
  "location_raw": "New York, NY (HQ)", # the source's own text, never rewritten
  "country": "US",                     # best-effort ISO2 from location_raw, or None — never guessed silently
  "remote": True | False | None,
  "url": "https://...",
  "posted_at": "2026-08-01" | None,    # ISO date, best-effort from the source's own field
  "compensation": {
    "min": 211400, "max": 290600, "currency": "USD", "period": "year",
    "raw_text": "$211.4K – $290.6K",
    "confidence": "structured",        # "structured" (a real API field) | "parsed_text" (regex from prose) | "none"
  } | None,                            # None, not a zero-valued dict, when nothing was published
  "occupation": None,                  # filled by classify_postings.py (tier 3) — never populated here
}
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, PROCESSED, log, to_iso2  # noqa: E402
import normalise  # noqa: E402

SEED_HINTS = DATA / "raw" / "postings_seed_hints"
POSTINGS_RAW = DATA / "raw" / "postings"

# Package 14, Tier 0.2 — three consecutive weekly runs (~3 weeks) unreachable
# before a board is dropped from the committed verified_companies ledger.
# Long enough that one bad week (a timeout, a rate-limited run, a transient
# 5xx) never costs a company its place; short enough that a board that is
# actually gone does not linger for months. The external audit's Finding 3
# ("verified companies fell 1,419 -> 606 on one scheduled run") is what a
# max_consecutive_failures of 1 (the previous, implicit behaviour -- any
# miss at all meant instant removal, since verified_companies was rebuilt
# from scratch every run with no memory of the prior commit) looks like.
DEFAULT_MAX_CONSECUTIVE_FAILURES = 3


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_previously_verified(source_id: str) -> dict[str, dict]:
    """The CURRENTLY COMMITTED verified_companies for a postings provider,
    read straight from data/processed/<source_id>.json -- the durable
    ledger build_probe_order() and merge_verified_companies() both build
    on. {} for a provider that has never been built."""
    p = PROCESSED / f"{source_id}.json"
    if not p.exists():
        return {}
    doc = json.loads(p.read_text(encoding="utf-8"))
    return doc.get("data", {}).get("verified_companies", {}) or {}


def build_probe_order(candidates: list[str], already_cached: set[str],
                       previously_verified: set[str], max_new_per_run: int) -> list[str]:
    """Package 14, Tier 0.1/0.2 fix. Three buckets, in priority order, each
    disjoint by construction (no token appears twice):

    1. Already cached this run -- a real on-disk cache hit, free and
       instant. Empty at the START of every scheduled GitHub Actions run:
       data/raw/ is gitignored and this workflow persists nothing between
       runs (no actions/cache step), so a runner never sees a previous
       run's cache. This bucket only ever does real work on a repeated
       LOCAL run within one session.
    2. Previously COMMITTED as verified, but not currently cached. Probed
       UNCONDITIONALLY, every run, uncapped. This is the actual fix: WITHOUT
       this bucket, a board that fell out of an (always-empty-in-CI) cache
       competed with thousands of never-tried candidates for a few hundred
       CAPPED "new" slots, and reliably lost -- confirmed live, not just
       theorised: this is exactly how Ashby went from 862 verified
       companies (package 12) to 304 (this package's own preflight
       investigation), while Greenhouse (max_new_per_run 250, closer to its
       own ~300-company baseline) and Lever (max_new_per_run 400, likewise)
       degraded less severely. See NEEDS-DECISION.md for the runtime
       tradeoff this creates as the committed list keeps growing.
    3. Genuinely new candidates -- never cached, never verified. Capped at
       max_new_per_run, same cap this pipeline already had; this is what
       still bounds a single run's worst-case new-request volume.
    """
    cached = [c for c in candidates if c in already_cached]
    reclaim = [c for c in candidates if c not in already_cached and c in previously_verified]
    fresh = [c for c in candidates if c not in already_cached and c not in previously_verified]
    return cached + reclaim + fresh[:max_new_per_run]


def merge_verified_companies(
    previous: dict[str, dict], probed_tokens: set[str], this_run_verified: dict[str, dict],
    *, max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
) -> tuple[dict[str, dict], list[dict]]:
    """Package 14, Tier 0.2 fix -- the additive merge that replaces "write
    this run's verified_companies straight over the committed file," which
    is the destructive-refresh bug Finding 3 describes: a single truncated
    or rate-limited run permanently erased every company it didn't happen
    to re-verify that run.

    Four cases, and what happens to each:
    - Verified THIS run (>=1 real posting): written fresh, failure streak
      reset to 0, last_seen_ok set to now.
    - Previously committed, PROBED this run, but did not verify (a real
      404/timeout/empty response): RETAINED with its last-known job data,
      failure streak incremented by one -- dropped only once that streak
      reaches max_consecutive_failures, and the drop is returned in
      `removed` so the caller can log it. This is "a board should leave
      the list only after repeated failures": one bad week is never
      enough on its own to erase a company this pipeline has verified.
    - Previously committed but NOT probed this run at all (no cache slot,
      lost the "new candidate" lottery, whatever the reason): retained
      completely unchanged. Not attempting a company is not the same as
      it failing, and must never cost it a strike.
    - Brand new (not previously committed, verified this run): added
      fresh with a 0 failure streak.

    Deliberately a pure function of its three arguments -- no network
    access, no disk I/O -- so this, the actual destructive-vs-additive
    logic, is directly unit-testable without mocking an HTTP call."""
    now = _now_iso()
    merged: dict[str, dict] = {}
    removed: list[dict] = []

    for token, prev in previous.items():
        if token in this_run_verified:
            merged[token] = {
                **this_run_verified[token],
                "last_seen_ok": now,
                "consecutive_failures": 0,
                "first_verified_at": prev.get("first_verified_at", now),
            }
        elif token in probed_tokens:
            streak = prev.get("consecutive_failures", 0) + 1
            if streak >= max_consecutive_failures:
                removed.append({
                    "token": token, "company": prev.get("company"), "provider": prev.get("provider"),
                    "last_seen_ok": prev.get("last_seen_ok"), "consecutive_failures": streak,
                })
                continue
            merged[token] = {**prev, "consecutive_failures": streak}
        else:
            merged[token] = prev

    for token, verified in this_run_verified.items():
        if token not in previous:
            merged[token] = {**verified, "last_seen_ok": now, "consecutive_failures": 0,
                              "first_verified_at": now}

    return merged, removed

# The 15 countries this site otherwise covers, PLUS a handful more that show
# up often enough in postings data to be worth keeping distinct rather than
# collapsing into "other" — country coverage here is deliberately wider than
# the wage spine's own 15 (a posting panel that only kept postings from the
# wage spine's own countries would silently under-represent exactly the
# geographic reach Tier 2's own brief asks for). `to_iso2` (from _common.py)
# already resolves far more than 15 countries; this module adds nothing to
# that list, it just doesn't restrict postings to it.


# A currency marker BOUND TO the number pattern, not just present anywhere
# in the line — the bug this fixes (found live, not caught before shipping:
# HN's own free text regularly has an unrelated number range earlier in the
# same line, e.g. "Full-time | $160-170K CAD" preceded by "hybrid, 2-3 days
# /week onsite" — a regex requiring only SOME currency symbol somewhere in
# the string, with the actual number match unconstrained, matched "2-3"
# first and never reached the real "$160-170K" at all). Each alternative
# below requires the number-dash-number to sit directly against its own
# currency symbol or a 3-letter code, so a bare "2-3" with no currency
# marker touching it can never match.
_RANGE_PATTERNS = [
    # "$155,000-$165,000", "£40k-£55k", "€100k - €130k"
    (re.compile(r"([\$£€])\s*([\d.]+)\s*([kK])?\s*-\s*[\$£€]?\s*([\d.]+)\s*([kK])?"), "symbol"),
    # "160-170K CAD", "100-130K USD" — currency CODE after the range, not a symbol before it
    (re.compile(r"(?<![\d.])([\d.]+)\s*-\s*([\d.]+)\s*([kK])?\s*(USD|CAD|EUR|GBP|AUD|NZD|SEK|NOK|DKK|CHF|SGD|INR)\b"), "code"),
]
_CODE_TO_ISO = {"USD": "USD", "CAD": "CAD", "EUR": "EUR", "GBP": "GBP", "AUD": "AUD", "NZD": "NZD",
                "SEK": "SEK", "NOK": "NOK", "DKK": "DKK", "CHF": "CHF", "SGD": "SGD", "INR": "INR"}
_SYMBOL_TO_ISO = {"$": "USD", "£": "GBP", "€": "EUR"}


def parse_compensation_text(text: str) -> dict | None:
    """Best-effort parse of a free-text compensation range ("$155,000 -
    $165,000 per year", "£40k-£55k", "$211.4K – $290.6K • Offers Equity",
    "160-170K CAD") into {min, max, currency, period, raw_text,
    confidence: 'parsed_text'}.

    Conservative by design (matches the work order's own instruction for HN:
    "where a range cannot be parsed with confidence, store the text and no
    number"): returns None rather than a guess when the pattern doesn't
    clearly hold two numbers bound to a real currency marker. Never returns
    a range with min > max, and never a currency this pipeline cannot name
    (a bare "$" defaults to USD only when no 3-letter code sits next to the
    range — an explicit code, e.g. "CAD", always wins, closing a real bug:
    an earlier version of this function saw ANY "$" anywhere in the line and
    called every such range USD even when the text itself said "CAD" a few
    words later).
    """
    if not text:
        return None
    t = text.replace("–", "-").replace("—", "-").replace(",", "")

    # An explicit 3-letter code beats a bare currency symbol whenever both
    # appear in the same line — "$160-170K CAD" is Canadian dollars, not
    # US, even though '$' (checked first by the symbol pattern below) would
    # otherwise default to USD. Checked once, up front, against the WHOLE
    # line rather than per-pattern, so neither branch can re-introduce the
    # bug of trusting the symbol when a code is right there in the text.
    code_m = re.search(r"\b(USD|CAD|EUR|GBP|AUD|NZD|SEK|NOK|DKK|CHF|SGD|INR)\b", t, re.I)
    code_currency = _CODE_TO_ISO.get(code_m.group(1).upper()) if code_m else None

    for pattern, kind in _RANGE_PATTERNS:
        m = pattern.search(t)
        if not m:
            continue
        if kind == "symbol":
            sym, lo, lo_k, hi, hi_k = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            currency = code_currency or _SYMBOL_TO_ISO.get(sym)
        else:
            lo, hi, hi_k = m.group(1), m.group(2), m.group(3)
            lo_k = hi_k
            currency = code_currency or _CODE_TO_ISO.get(m.group(4).upper())
        if not currency:
            continue
        # "$160-170K" / "$146-220k" — English shorthand where a 'k' suffix
        # on only the SECOND number applies to both ("160 to 170 thousand",
        # not "160 to 170000"). Missing this made every such range parse as
        # roughly 1/1000th of its real minimum — found live, not caught
        # before shipping, by noticing "$146-220k" turned into a $146
        # minimum next to a $220,000 maximum.
        if hi_k and not lo_k:
            lo_k = hi_k
        try:
            lo_v = float(lo) * (1000 if lo_k else 1)
            hi_v = float(hi) * (1000 if hi_k else 1)
        except ValueError:
            continue
        if lo_v <= 0 or hi_v <= 0 or lo_v > hi_v:
            continue
        # A number under 12 with no 'k' suffix at all ("2-3" for years of
        # experience, "3-5" for a headcount) is never a real, standalone
        # salary figure regardless of currency proximity — the smallest
        # plausible real value here is an hourly wage, always >= a few
        # units; this floor exists specifically to reject the "2-3
        # days/week" class of false match the symbol pattern can still
        # produce when a currency symbol happens to precede an unrelated
        # small number earlier in the same line.
        if hi_v < 12:
            continue
        period = "year"
        if re.search(r"/\s*hour|hourly|per\s*hour|\bhr\b", t, re.I):
            period = "hour"
        elif re.search(r"/\s*month|monthly|per\s*month", t, re.I):
            period = "month"
        return {"min": lo_v, "max": hi_v, "currency": currency, "period": period,
                "raw_text": text.strip(), "confidence": "parsed_text"}
    return None


# A postings panel is explicitly NOT scoped to the wage spine's own 15
# countries (the work order's own brief is "every posting we can
# legitimately reach") — _common.py's own to_iso2() is deliberately narrow
# to those 15, so it resolves a real minority of what a global postings feed
# actually contains. Found live, not assumed: probing 400 Ashby boards, the
# single largest "country" bucket was "unresolved" (4,535 of 6,925 postings)
# BEFORE this wider table existed — dominated by bare city names ("San
# Francisco", "London", "Berlin", "Seoul") and non-wage-spine country names
# ("Malaysia", "Vietnam", "China") to_iso2() was never built to catch. This
# table is deliberately much wider than the site's own 15-country wage
# spine — a posting from Kuala Lumpur is real data worth keeping and
# labelling, even though this site has no salary distribution for Malaysia
# to ever compare it against (see build_postings.py's own header for why
# that's fine: this file never feeds the wage spine).
_COUNTRY_NAMES_WIDE = {
    "united states": "US", "usa": "US", "u.s.": "US", "u.s.a.": "US", "united states of america": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "germany": "DE", "deutschland": "DE", "france": "FR", "canada": "CA", "ireland": "IE",
    "netherlands": "NL", "holland": "NL", "spain": "ES", "italy": "IT", "sweden": "SE", "denmark": "DK",
    "norway": "NO", "finland": "FI", "australia": "AU", "india": "IN", "poland": "PL", "portugal": "PT",
    "singapore": "SG", "japan": "JP", "china": "CN", "hong kong": "HK", "taiwan": "TW", "south korea": "KR",
    "korea": "KR", "malaysia": "MY", "indonesia": "ID", "thailand": "TH", "vietnam": "VN", "philippines": "PH",
    "mexico": "MX", "brazil": "BR", "argentina": "AR", "chile": "CL", "colombia": "CO", "peru": "PE",
    "switzerland": "CH", "austria": "AT", "belgium": "BE", "luxembourg": "LU", "iceland": "IS",
    "czech republic": "CZ", "czechia": "CZ", "slovakia": "SK", "hungary": "HU", "romania": "RO",
    "bulgaria": "BG", "greece": "GR", "croatia": "HR", "slovenia": "SI", "estonia": "EE", "latvia": "LV",
    "lithuania": "LT", "ukraine": "UA", "russia": "RU", "turkey": "TR", "türkiye": "TR", "israel": "IL",
    "united arab emirates": "AE", "uae": "AE", "saudi arabia": "SA", "qatar": "QA", "egypt": "EG",
    "south africa": "ZA", "nigeria": "NG", "kenya": "KE", "new zealand": "NZ", "pakistan": "PK",
    "bangladesh": "BD", "sri lanka": "LK", "nepal": "NP", "serbia": "RS", "bosnia": "BA",
    "north macedonia": "MK", "moldova": "MD", "georgia": "GE", "armenia": "AM", "azerbaijan": "AZ",
    "kazakhstan": "KZ", "uzbekistan": "UZ", "cyprus": "CY", "malta": "MT",
}

# Major tech-hub cities that routinely appear bare (no country/state suffix)
# in ATS location fields — found live in this pipeline's own Ashby sample,
# not a generic world-cities list. A city NOT in this table resolves to
# None, honestly, rather than a guess; this table only grows from what's
# actually been observed to matter, matching this project's own "no
# invented resolution" discipline elsewhere (to_iso2's own docstring).
_CITY_TO_COUNTRY = {
    "san francisco": "US", "new york": "US", "new york city": "US", "los angeles": "US", "austin": "US",
    "seattle": "US", "boston": "US", "chicago": "US", "miami": "US", "denver": "US", "atlanta": "US",
    "washington": "US", "washington dc": "US", "san diego": "US", "san jose": "US", "houston": "US",
    "dallas": "US", "philadelphia": "US", "phoenix": "US", "portland": "US", "minneapolis": "US",
    "detroit": "US", "nashville": "US", "raleigh": "US", "salt lake city": "US", "las vegas": "US",
    "london": "GB", "manchester": "GB", "edinburgh": "GB", "birmingham": "GB", "bristol": "GB",
    "berlin": "DE", "munich": "DE", "münchen": "DE", "hamburg": "DE", "frankfurt": "DE", "cologne": "DE",
    "paris": "FR", "lyon": "FR", "toulouse": "FR",
    "dublin": "IE", "cork": "IE",
    "amsterdam": "NL", "rotterdam": "NL", "utrecht": "NL", "the hague": "NL",
    "madrid": "ES", "barcelona": "ES", "valencia": "ES",
    "milan": "IT", "rome": "IT", "turin": "IT",
    "stockholm": "SE", "gothenburg": "SE", "malmo": "SE", "malmö": "SE",
    "copenhagen": "DK", "aarhus": "DK",
    "oslo": "NO", "bergen": "NO",
    "helsinki": "FI", "espoo": "FI",
    "sydney": "AU", "melbourne": "AU", "brisbane": "AU", "perth": "AU",
    "toronto": "CA", "vancouver": "CA", "montreal": "CA", "montréal": "CA", "ottawa": "CA", "calgary": "CA",
    "beijing": "CN", "shanghai": "CN", "shenzhen": "CN", "guangzhou": "CN",
    "hong kong": "HK", "taipei": "TW", "seoul": "KR", "tokyo": "JP", "osaka": "JP",
    "fukuoka": "JP", "yokosuka": "JP", "yokohama": "JP", "nagoya": "JP",
    "indianapolis": "US", "lausanne": "CH",
    "bangalore": "IN", "bengaluru": "IN", "mumbai": "IN", "delhi": "IN", "new delhi": "IN",
    "hyderabad": "IN", "pune": "IN", "chennai": "IN", "gurgaon": "IN", "gurugram": "IN", "noida": "IN",
    "kuala lumpur": "MY", "jakarta": "ID", "bangkok": "TH", "ho chi minh city": "VN", "hanoi": "VN",
    "manila": "PH", "mexico city": "MX", "sao paulo": "BR", "são paulo": "BR", "rio de janeiro": "BR",
    "buenos aires": "AR", "santiago": "CL", "bogota": "CO", "bogotá": "CO", "lima": "PE",
    "zurich": "CH", "zürich": "CH", "geneva": "CH", "vienna": "AT", "brussels": "BE",
    "warsaw": "PL", "krakow": "PL", "kraków": "PL", "prague": "CZ", "bucharest": "RO", "budapest": "HU",
    "athens": "GR", "lisbon": "PT", "porto": "PT", "tel aviv": "IL", "tallinn": "EE", "riga": "LV",
    "vilnius": "LT", "kyiv": "UA", "kiev": "UA", "istanbul": "TR", "dubai": "AE", "abu dhabi": "AE",
    "doha": "QA", "riyadh": "SA", "cairo": "EG", "cape town": "ZA", "johannesburg": "ZA", "lagos": "NG",
    "nairobi": "KE", "auckland": "NZ", "wellington": "NZ", "pangyo": "KR",
}


# Full US state names (plus DC), checked BEFORE the country-name table
# below. Package 12's own adversarial review found this pipeline's first
# version resolved "Atlanta, Georgia" to Georgia-the-country and
# "Albuquerque, New Mexico" to Mexico — the country-name table's own plain
# substring match had no way to prefer a spelled-out US state name over a
# same-spelled (or same-prefixed) country name. Checking full state names
# first, as their own table, fixes both: "new mexico" is a more specific
# 2-word phrase than the country table's own bare "mexico" entry, so it
# wins by being checked first rather than by being longer. "Georgia" is
# the one genuine, irreducible collision (the US state and the country
# share an identical name) — checked live, not assumed: of the 143
# "Georgia"-labelled postings this pipeline had actually harvested when
# this fix was made, zero were Tbilisi; every one was a real Georgia,
# USA city (Atlanta, Athens, Savannah, Columbus, Dalton, ...). Resolving
# "Georgia" to US is therefore the empirically better default, disclosed
# here and in NEEDS-DECISION.md rather than silently chosen — a future
# Tbilisi-based posting would need a country name spelled out elsewhere
# in its own location text to resolve correctly, the same as any location
# this table doesn't otherwise recognise.
_US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
    "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
    "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico",
    "new york", "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming", "district of columbia",
}


def _word_match(name: str, low: str) -> bool:
    """Whole-word/whole-phrase containment, not a bare substring test. Not
    `\\b...\\b` either: a plain word-boundary regex fails around punctuation
    -- "u.s." followed by a space has no \\b between the trailing "." and
    the space, since neither is a word character, so `\\bu\\.s\\.\\b` never
    matches "u.s. remote" at all. This checks "not immediately preceded or
    followed by a letter" instead, which handles both plain words ("uk"
    inside "milwaukee" correctly fails: 'a' precedes it) and punctuated
    abbreviations ("u.s." correctly matches: a space, not a letter, follows
    the trailing period) the same way. Found live, not assumed: this exact
    gap was caught by testing "U.S. Remote"-shaped location text against an
    early version of this fix that used plain `\\b` and silently stopped
    resolving it."""
    return re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", low) is not None


def country_from_location(location_raw: str | None) -> str | None:
    """Best-effort ISO2 from a free-text location string. Order: an exact
    ISO2/ISO3/name match (_common.py's own to_iso2); a full US state name;
    an exact country-name match (this module's own wide table, deliberately
    broader than to_iso2's 15 countries); a bare US state code; a known
    city name. Every match uses whole-word containment (`_word_match`), not
    a bare substring test -- an earlier version used plain substring
    matching and silently misassigned "Atlanta, Georgia" to Georgia the
    country, "Milwaukee, Wisconsin" to the UK ("uk" is a substring of
    "milwaukee"), "Ukraine" to the UK (same reason), "China Lake,
    California" to China, and "King of Prussia, PA" to Russia ("russia" is
    a substring of "prussia") -- found live via this package's own
    adversarial review, re-verified against the real committed dataset
    before this fix shipped (2,108 of 35,936 postings' own country field
    changed; the corrections and the reasoning behind each are recorded in
    NEEDS-DECISION.md). Never guesses past what one of these signals
    actually supports -- an unresolved location stays None rather than
    being coerced into a country the text doesn't actually name."""
    if not location_raw:
        return None
    low = location_raw.lower()
    direct = to_iso2(location_raw)
    if direct:
        return direct
    for state in _US_STATE_NAMES:
        if _word_match(state, low):
            return "US"
    for name, iso2 in _COUNTRY_NAMES_WIDE.items():
        if _word_match(name, low):
            return iso2
    US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
        "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
        "VA", "WA", "WV", "WI", "WY", "DC",
    }
    m = re.search(r"\b([A-Z]{2})\b", location_raw)
    if m and m.group(1) in US_STATES:
        return "US"
    # City match last — a country NAME in the string is a stronger signal
    # than a city name (a title like "APAC - Singapore" already resolved
    # above; this catches the bare "San Francisco" / "Berlin" shape).
    # KNOWN RESIDUAL AMBIGUITY, disclosed rather than silently accepted --
    # two related, small-scale cases where this function's own checking
    # ORDER, not a missing signal, produces the wrong of two genuinely
    # plausible answers (confirmed against the real committed dataset,
    # 10 of 43,034 postings total at the time this was measured):
    #   1. A bare 2-letter code checked just above can outrank a city match
    #      that would otherwise disambiguate it correctly in the other
    #      direction -- "CA - Toronto" (an internal office-label prefix some
    #      Ashby boards use, 9 postings) resolves to US (California) rather
    #      than CA (Canada), because the 2-letter-code check runs before
    #      this city table gets a chance to see "toronto".
    #   2. A country-name-table entry checked further above can similarly
    #      outrank this same bare 2-letter code -- "China Lake, CA" (1
    #      posting) resolves to CN rather than US, because "china" matches
    #      the country-name table before the 2-letter "CA" is ever checked
    #      (its own sibling record, "China Lake, California" -- the state
    #      spelled out in full -- correctly resolves to US, confirming this
    #      is specifically an abbreviation-vs-word-order issue, not a
    #      missing city-table entry).
    # Reordering either check would fix its own case but break the mirror
    # case the OTHER direction (a genuine "Vancouver, WA" is the US city,
    # not Vancouver BC) -- there is no ordering that gets both right without
    # a genuine city+state/country co-occurrence check this function does
    # not build. See NEEDS-DECISION.md.
    for city, iso2 in _CITY_TO_COUNTRY.items():
        if _word_match(city, low):
            return iso2
    return None


# Package 14, Tier 3.2 — the external audit's own "thousands-suffix parser"
# finding, investigated: on inspection, the 64 low-annualised records were
# NOT this pipeline's own text-parsing regex dropping a "K" (parse_compensation_
# text, above, already handles that shorthand correctly — see its own "$146-
# 220k" comment). They were structured, provider-supplied compensation whose
# OWN period tag (Ashby's own interval, USAJOBS' own salaryType) disagreed
# with its own numbers: an employer's ATS form entry, or a federal listing's
# default salaryType, not this pipeline mis-reading real text. Two narrow,
# magnitude-anchored corrections below, each matching a precedent already
# shipped in this codebase (src_postings_greenhouse.py's own
# _parse_pay_input_ranges) rather than inventing a new threshold.
_YEAR_LOOKS_HOURLY_THRESHOLD = 100
# Ashby's real, live data draws a clean line here: every genuinely
# hourly-shaped value mistagged 'year' this package found live tops out at
# 59.6 (a skilled-trade/manufacturing wage); genuinely thousands-shaped
# values start at 230 and up (a senior-role figure). 100 sits in the real
# gap between the two clusters with margin on both sides — no observed
# hourly wage this pipeline has ever seen approaches $100/hour, and no
# observed "meant thousands" figure comes in under 230. Deliberately NOT
# src_postings_greenhouse.py's own $1,000 threshold: that source's own
# min_cents/max_cents never carries this specific "bare number meant in
# thousands" ambiguity at all (Greenhouse's own employers don't hand-type a
# number into a "$1-1000" field the way Ashby's compensationTiers form
# apparently lets some employers do) — so Greenhouse's own 1,000 has never
# had to separate an hourly cluster from a thousands cluster the way this
# threshold does, and reusing it here would have swallowed every one of the
# 4 real "meant thousands" records this package found into "hourly" instead
# (all sit at 230-500, comfortably under 1,000).
_BARE_THOUSANDS_LOWER_BOUND, _BARE_THOUSANDS_UPPER_BOUND = 250, 12000
# The audit's own reporting threshold ("64 records annualise below
# $12,000") sets the ceiling. The floor (250) is this package's own,
# chosen the same way as the hourly threshold above: every real "meant
# thousands" record found live sits at 230+ (a senior-role, sales-OTE, or
# director-level figure a bare-number reading makes plainly implausible
# either as an hourly wage or a literal annual one) — work order's own
# example, "OTE $250 - $300 /year" for an Enterprise Account Executive, is
# "plainly $250k-$300k". The 100-250 gap between the two thresholds is
# left DELIBERATELY untouched: real records in it (a $150-155/hour
# "Physician, Virtual Care" rate; a $135-150 "Associate Software Engineer"
# figure that could plausibly be EITHER a high hourly contract rate or an
# abbreviated annual one) do not resolve cleanly by magnitude alone, and
# guessing between two real, physically different interpretations with no
# further evidence is exactly what this project's own rules forbid — see
# Tier 3.3's plausibility gate, which flags these for review instead of
# silently picking one.
_HAS_K_MARKER_RE = re.compile(r"\d\s*[kK]\b")


def reinterpret_implausible_year(min_v: float, max_v: float, raw_text: str) -> tuple[float, float, str] | None:
    """Package 14, Tier 3.2. Given a compensation range ALREADY tagged
    'year' by its own source, returns (new_min, new_max, new_period) if the
    range is implausible as a literal annual figure and a specific,
    text-grounded correction applies — otherwise None (leave it alone,
    including every genuinely low-but-real wage this project has no
    business overriding: Appen's own $2.40/hour Myanmar rate, ansiblehealth's
    own $500-900/month remote-VA rate, a real EU internship's own monthly
    stipend — none of those are 'year'-tagged in the first place, so this
    function is never even called for them; see this file's own module
    docstring header for the two rules this applies, in order, and their
    own thresholds' docstrings for exactly why each number was chosen from
    this package's own live data, not picked in the abstract.

    WHY THIS IS A METHOD FIX, NOT A CHANGE TO A PUBLISHED VALUE (the work
    order's own line: "never change a number to make a check pass... every
    correction here is to a method, never to a published value"): a source
    like Spain's own government wage statistics is a genuine, deliberately
    published figure -- there is no evidence it is a transcription error,
    so it is never touched, however implausible the ratio it produces looks
    (see Tier 1's own audit_data.py check, which flags exactly that instead
    of guessing at a fix). An Ashby posting reading "$250 - $300" for an
    "Enterprise Account Executive" is different in kind: nothing about that
    number was ever the EMPLOYER'S own intended figure -- no real
    salaried role pays $250-$300 for a year of work, and Ashby's own API
    has no separate "in thousands" flag, so an employer typing "250"
    meaning "250,000" (a common informal shorthand) and Ashby passing it
    through literally is a TRANSCRIPTION gap between what was meant and
    what was stored, the same category of thing as Lever's own historical
    `.replace('per-', '')` bug (R15) turning "per-year-salary" into
    "year-salary" -- a real, sourced number, MIS-INTERPRETED on the way
    into this pipeline. Rule 2 below corrects the interpretation (what the
    stored number actually means), never invents a number Ashby's own API
    did not report -- min_v and max_v are the exact same integers the API
    returned, scaled by a fixed, disclosed, documented factor of 1,000,
    not replaced by a guess.

    1. max < 100 -- clearly hourly-shaped, mistagged 'year' by its own
       source. Reinterpreted as period='hour', values UNCHANGED (they were
       already the real hourly numbers, just mislabelled).
    2. 250 <= max < 12,000 AND raw_text carries no k/K marker -- a bare,
       unscaled number an employer meant in thousands (raw_text carrying a
       real 'k'/'K', e.g. Ashby's own '2K-2.5K' tierSummary, means the
       value is ALREADY correctly scaled -- that case returns None,
       deliberately not touched here).

    100-250 is left alone on purpose -- see _BARE_THOUSANDS_LOWER_BOUND's
    own docstring for the real, disclosed residual this leaves (Tier 3.3's
    plausibility gate flags it instead of this function guessing at it)."""
    if max_v is None or max_v <= 0:
        return None
    if max_v < _YEAR_LOOKS_HOURLY_THRESHOLD:
        return (min_v, max_v, "hour")
    if _BARE_THOUSANDS_LOWER_BOUND <= max_v < _BARE_THOUSANDS_UPPER_BOUND and not _HAS_K_MARKER_RE.search(raw_text or ""):
        return (min_v * 1000, max_v * 1000, "year")
    return None


# Package 14, Tier 3.1 — the external audit's Finding 3: postings compensation
# spans nine currencies with no conversion layer, so any cross-country
# aggregate over it was meaningless. normalise.to_usd() is keyed by COUNTRY
# (it looks up data/processed/fx_rates.json, itself country-keyed, following
# the World Bank's own PA.NUS.FCRF shape), not by currency — this maps each
# currency this pipeline's postings actually carry to ONE representative
# country whose own FX series IS that currency (EUR -> DE rather than IE/NL/
# ES/FI: all four are the same EUR/USD rate from 1999 on, DE's own series is
# simply the one already fetched furthest back). SG/JP/KH/IN/AM were added to
# fx_rates.json specifically for this (src_fx_rates.py's own
# POSTINGS_EXTRA_FX_COUNTRIES) -- none of the five were part of the 15-country
# wage spine before this package. A currency this pipeline sees in a FUTURE
# posting with no entry here fails honestly (normalise.to_usd() itself
# refuses an unmapped country/year, rule 1) rather than silently not
# converting or guessing a rate.
CURRENCY_TO_FX_COUNTRY = {
    "USD": "US", "EUR": "DE", "GBP": "GB", "CAD": "CA",
    "SGD": "SG", "JPY": "JP", "KHR": "KH", "INR": "IN", "AMD": "AM",
    # AUD/SEK/NOK/DKK/AED: NOT in Finding 3's own named list, added anyway
    # -- each maps to a country ALREADY IN fx_rates.json as one of the
    # original 15 wage-spine countries (AU/SE/NO/DK/AE), so this costs
    # zero new fetching and closes a real, measured gap live data exposed
    # (37 AUD-denominated postings converting to 0 under the audit's own
    # named 9-currency list alone; SEK/NOK/DKK/AED each smaller but the
    # same free win). Every other real currency observed live in postings
    # (PHP, PLN, CNY, HUF, THB, MXN, BRL, CZK, KRW, RON, CHF, MYR, HKD,
    # TWD, ARS -- each single- to low-double-digit counts, none a country
    # this pipeline already has FX history for) is a disclosed residual,
    # not silently dropped -- see NEEDS-DECISION.md.
    "AUD": "AU", "SEK": "SE", "NOK": "NO", "DKK": "DK", "AED": "AE",
}


def convert_compensation_to_usd(comp: dict, effective_year: int) -> dict | None:
    """Package 14, Tier 3.1. Given a posting's own native `compensation`
    dict and an effective year (that posting's own posted_at year when
    known, else the harvest run's own year -- see build_postings.py's own
    comment on why a live-scraped posting has no fixed 'reference year' the
    way a government wage survey does), returns the SAME year-matched-FX
    machinery the wage spine uses (normalise.to_usd(), rule 1: no fallback
    to a different year) applied to this posting's own min/max, or None
    when the currency isn't mapped or that year has no rate -- never a
    guessed or nearby-year conversion. Native values are UNTOUCHED by this
    function; the caller attaches the result as a new, clearly-derived
    'usd' sub-field, never overwriting the native min/max/currency
    (normalise.py's own rule 5, "native is the source of truth")."""
    currency = comp.get("currency")
    fx_country = CURRENCY_TO_FX_COUNTRY.get(currency)
    if not fx_country or comp.get("min") is None or comp.get("max") is None:
        return None
    lo = normalise.to_usd(comp["min"], fx_country, effective_year)
    hi = normalise.to_usd(comp["max"], fx_country, effective_year)
    if not lo["ok"] or not hi["ok"]:
        return None
    return {
        "min": lo["value_usd"], "max": hi["value_usd"],
        "fx_rate": lo["fx_rate"], "fx_year": lo["fx_year"], "fx_source": lo["fx_source"],
        "fx_country_used": fx_country,
    }


def dedupe_seed(candidates: list[str]) -> list[str]:
    """Lowercase, strip, drop empties/dupes — the aggregated hint lists
    (github.com/Feashliaa/job-board-aggregator, MIT-licensed, re-verified
    live per company below, never trusted as-is per the work order's own
    instruction) occasionally repeat a token in different case."""
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        c2 = c.strip().lower()
        if c2 and c2 not in seen:
            seen.add(c2)
            out.append(c2)
    return out


def log_provider_summary(provider: str, tested: int, verified: int, jobs_total: int, countries: dict[str, int]) -> None:
    top = sorted(countries.items(), key=lambda kv: -kv[1])[:8]
    log(f"    {provider}: {tested} candidates tested, {verified} verified (>=1 posting), "
        f"{jobs_total} postings total")
    log(f"    {provider} top countries: " + ", ".join(f"{k or 'unresolved'}={v}" for k, v in top))
