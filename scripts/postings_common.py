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

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, log, to_iso2  # noqa: E402

SEED_HINTS = DATA / "raw" / "postings_seed_hints"
POSTINGS_RAW = DATA / "raw" / "postings"

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
