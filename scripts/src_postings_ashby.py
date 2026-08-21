"""Package 12, tier 1/2 — Ashby job-board API. Verified live (see the work
order's own Tier 1.1 table, and this session's own re-verification against
ramp/notion/vercel/linear before writing this file): unauthenticated,
`api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true`,
richest payload of the three "verified" providers — real compensationTiers
with currencyCode/minValue/maxValue, no per-job fan-out needed (the list
endpoint IS the full payload).

SEEDING: this script does not invent candidate company slugs. It reads
data/raw/postings_seed_hints/ashby_companies.json (3,161 tokens, MIT-licensed,
pulled from github.com/Feashliaa/job-board-aggregator — a third-party
aggregator, explicitly treated as a SEED HINT only, per the work order's own
instruction: "re-verify every token yourself against the live endpoint before
it enters the list"). Every token below is hit against the real live
endpoint; only ones that resolve with >=1 posting count as newly verified
THIS run. A token that 404s, times out, or returns zero postings is never
guessed into the output — but, since Package 14 Tier 0.2, is not dropped
from the accumulated seed list on one miss either: merge_verified_companies()
(postings_common.py) retains an already-verified company through a bounded
number of consecutive failed probes (a strike, not an eviction), removing it
only after DEFAULT_MAX_CONSECUTIVE_FAILURES in a row and logging the
removal — see that function's own docstring for the full rule this replaced
a from-scratch overwrite with.

RESUMABLE, POLITE: each company's raw response is cached to
data/raw/postings/ashby/<token>.json via _common.py's own fetch() — a second
run skips everything already fetched. MAX_NEW_PER_RUN caps how many NEW
(not-yet-cached) candidates a single run probes, so this can be re-run by the
scheduled workflow (tier 2's own cron) to grow coverage over many runs
without one run hammering Ashby's API or blowing past its own time budget.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import FetchError, banner, fetch_json, log, main_guard, record_provenance, write_processed  # noqa: E402
from postings_common import (  # noqa: E402
    POSTINGS_RAW, SEED_HINTS, build_probe_order, country_from_location, dedupe_seed,
    load_previously_verified, log_provider_summary, merge_verified_companies, reinterpret_implausible_year,
)

SOURCE_ID = "postings_ashby"
PROVIDER = "ashby"
BASE = "https://api.ashbyhq.com/posting-api/job-board"
OUT_DIR = POSTINGS_RAW / PROVIDER
MAX_NEW_PER_RUN = 400  # ~400 candidates x ~1 req each, polite pacing below -> a few minutes


def _load_candidates() -> list[str]:
    hint_file = SEED_HINTS / "ashby_companies.json"
    if not hint_file.exists():
        log(f"    no seed hints at {hint_file} — nothing to probe")
        return []
    raw = json.loads(hint_file.read_text(encoding="utf-8"))
    return dedupe_seed(raw)


def _fetch_board(token: str) -> dict | None:
    dest = OUT_DIR / f"{token}.json"
    already_cached = dest.exists()
    try:
        # retries=1 (no retry): a 404 during seed probing means "this
        # candidate isn't a real board," the overwhelmingly common outcome
        # against a large third-party hint list — retrying it 2-3x each
        # (the default) wastes real time for zero chance of success. A
        # genuinely transient failure just gets picked up on the NEXT run
        # via the same on-disk cache, which only persists real successes.
        doc = fetch_json(f"{BASE}/{token}?includeCompensation=true", dest=dest, cache=True, retries=1)
    except FetchError:
        return None
    if not already_cached:
        time.sleep(0.15)  # polite pacing — only for genuinely new requests, cached hits are instant
    return doc


def _normalise(token: str, doc: dict) -> list[dict]:
    # organizationName is never actually present in this endpoint's own
    # response (checked live against every cached board this pipeline has,
    # not assumed) -- so this always fell back to the token, in violation
    # of postings_common.py's own record-shape docstring ("never guessed
    # from the token"). Store the real absence as None; the UI's own
    # fmtCompany() renders a de-slugified label from company_slug, not this
    # code inventing one.
    company = doc.get("organizationName") or None
    out = []
    for j in doc.get("jobs", []):
        comp = j.get("compensation") or {}
        tiers = comp.get("compensationTiers") or []
        parsed_comp = None
        for tier in tiers:
            for c in tier.get("components", []):
                # `is None` alone let a real-but-empty $0 range through as a
                # confident figure (found live by this package's own
                # adversarial review: 9+ postings rendering "$0-$0" in bold,
                # not "not stated") -- `minValue: 0` is not None, so the old
                # guard passed it straight through. Matches Greenhouse's and
                # USAJOBS's own harvesters, which already reject a zero
                # figure the same way.
                if not c.get("minValue") or not c.get("currencyCode"):
                    continue
                # Real values, found live in this pipeline's own cached data,
                # NOT the "HOURLY"/"YEARLY"/"MONTHLY" enum this code
                # originally assumed (which matched NOTHING and silently
                # defaulted every single posting to "year" — caught only by
                # noticing "EUR200-250/yr" on a posting whose own tierSummary
                # said "per hour", not by any check run before this shipped).
                # Ashby's own interval is "<n> <UNIT>": "1 HOUR", "1 YEAR",
                # "1 MONTH", "1 WEEK", "6 MONTH", "NONE" (equity only).
                interval = (c.get("interval") or "").upper()
                if "HOUR" in interval:
                    period = "hour"
                elif "MONTH" in interval:
                    period = "month"
                elif "YEAR" in interval:
                    period = "year"
                else:
                    # "1 WEEK" (no weekly bucket in postings.ts's own
                    # Compensation type — mapping it to month would
                    # understate by ~4x, so skipped rather than guessed),
                    # "NONE" (equity-only, no minValue in practice), or any
                    # future value this pipeline hasn't seen.
                    continue
                raw_text = tier.get("tierSummary") or comp.get("compensationTierSummary") or ""
                min_v, max_v = c["minValue"], c.get("maxValue") or c["minValue"]
                # Package 14, Tier 3.2 (external audit Finding 3) — Ashby's
                # own interval tag is real but not always right for the
                # specific numbers attached to it: an employer's own ATS
                # form entry, not this pipeline mis-reading real text (see
                # reinterpret_implausible_year's own docstring for the one
                # narrow, text-grounded, USD-only correction this applies).
                if period == "year":
                    fix = reinterpret_implausible_year(min_v, max_v, raw_text, c["currencyCode"])
                    if fix:
                        min_v, max_v, period = fix
                parsed_comp = {
                    "min": min_v, "max": max_v,
                    "currency": c["currencyCode"], "period": period,
                    "raw_text": raw_text,
                    "confidence": "structured",
                }
                break
            if parsed_comp:
                break
        loc = j.get("location") or j.get("locationName") or ""
        out.append({
            "id": f"ashby:{token}:{j.get('id')}",
            "provider": PROVIDER, "company": company, "company_slug": token,
            "title": j.get("title"), "location_raw": loc, "country": country_from_location(loc),
            "remote": (j.get("isRemote") if "isRemote" in j else None),
            "url": j.get("jobUrl") or j.get("applyUrl"),
            "posted_at": j.get("publishedAt"),
            "compensation": parsed_comp,
            "occupation": None,
        })
    return out


def run() -> None:
    banner(SOURCE_ID, "Ashby job-board API — postings panel")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = _load_candidates()
    log(f"    {len(candidates)} candidate tokens loaded from the seed hint file")

    previous = load_previously_verified(SOURCE_ID)
    already_cached = {p.stem for p in OUT_DIR.glob("*.json")}
    to_probe = build_probe_order(candidates, already_cached, set(previous.keys()), MAX_NEW_PER_RUN)
    log(f"    {len(already_cached)} already cached from prior runs, {len(previous)} previously "
        f"committed as verified, probing {len(to_probe)} this run (cap {MAX_NEW_PER_RUN} new)")

    postings: list[dict] = []
    this_run_verified: dict[str, dict] = {}
    tested = 0
    countries: dict[str | None, int] = {}
    for token in to_probe:
        tested += 1
        doc = _fetch_board(token)
        if not doc or not doc.get("jobs"):
            continue
        rows = _normalise(token, doc)
        if not rows:
            continue
        postings.extend(rows)
        for r in rows:
            countries[r["country"]] = countries.get(r["country"], 0) + 1
        this_run_verified[token] = {
            "company": doc.get("organizationName") or None, "provider": PROVIDER,
            "job_count": len(rows),
        }
        if tested % 50 == 0:
            log(f"    ...{tested}/{len(to_probe)} probed, {len(this_run_verified)} verified so far")

    verified_companies, removed = merge_verified_companies(previous, set(to_probe), this_run_verified)
    for r in removed:
        log(f"    REMOVED {r['token']} ({r['company']}) — {r['consecutive_failures']} consecutive "
            f"failed probes, last verified {r['last_seen_ok']}")

    log_provider_summary(PROVIDER, tested, len(this_run_verified), len(postings), countries)
    log(f"    verified_companies (durable): {len(verified_companies)} ({len(this_run_verified)} reconfirmed "
        f"this run, {len(removed)} removed after repeated failures)")

    write_processed(SOURCE_ID, {
        "postings": postings,
        "verified_companies": verified_companies,
    }, meta={
        "candidates_in_hint_file": len(candidates),
        "candidates_probed_this_run": len(to_probe),
        "candidates_probed_cumulative": len(already_cached | set(to_probe)),
        "verified_companies": len(verified_companies),
        "verified_companies_reconfirmed_this_run": len(this_run_verified),
        "verified_companies_removed_this_run": removed,
        "postings_count": len(postings),
        "compensation_present_count": sum(1 for p in postings if p["compensation"]),
    })
    record_provenance(
        source_id=SOURCE_ID,
        name="Ashby job-board API — advertised pay, structured compensation",
        urls=[f"{BASE}/{{token}}?includeCompensation=true"],
        license_note="Each company's own postings, published by that company via Ashby's own public, "
                      "unauthenticated job-board API — no Ashby-specific license terms apply beyond "
                      "the postings being intentionally public.",
        redistribution="Only postings from companies whose board was verified live are kept; the raw "
                        "per-company response is cached under data/raw/postings/ashby/ (gitignored, "
                        "matching this pipeline's existing data/raw/ convention).",
        transforms=[
            "Loaded candidate company tokens from a third-party MIT-licensed aggregator "
            "(github.com/Feashliaa/job-board-aggregator) as SEED HINTS ONLY.",
            "Probed each candidate live against api.ashbyhq.com; a token is never guessed into the "
            "output, only counted verified once it resolves with at least one real posting. An "
            "already-verified company that later 404s, times out, or returns zero postings is kept "
            "through a bounded number of consecutive failed probes (a strike, not an eviction) and "
            "removed, with the removal logged, only after repeated consecutive failures.",
            "Parsed each posting's own compensationTiers into a common {min,max,currency,period} shape, "
            "preferring the first component with a real minValue+currencyCode.",
            "Resolved each posting's own free-text location to a best-effort ISO2 country code — never "
            "invented when the text doesn't resolve.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(postings),
        coverage=f"{len(verified_companies)} verified companies, {len(postings)} postings, this run",
        notes="Advertised pay — NEVER merged with survey-earnings data (validate_data.py's own "
              "assertion, package 7, guards this). See data/processed/postings.json (build_postings.py) "
              "for the merged, cross-provider file the site actually reads.",
    )


if __name__ == "__main__":
    main_guard(run)
