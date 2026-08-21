"""Package 12, tier 1/2 — Lever postings API. Verified live (work order's
own Tier 1.1 table; re-confirmed this session against palantir): a single
unauthenticated GET (`api.lever.co/v0/postings/{token}?mode=json`) returns
every posting AND its optional `salaryRange` in one call — no fan-out, but
reads time out under real load per the work order's own note, so retries
back off rather than hammering a slow response.

SALARY RANGE IS EMPIRICALLY RARE ON THIS PROVIDER: verified live this
session against Palantir (308 postings, 0 with salaryRange populated) — the
field is real and documented, just optional and, in this pipeline's own
sample, seldom used. Recorded honestly in this file's own meta rather than
assumed populated because the API supports it.

SEEDING: same discipline as the other two providers — data/raw/postings_
seed_hints/lever_companies.json (4,368 tokens, MIT-licensed, third-party
aggregator, SEED HINT ONLY), re-verified live.
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

SOURCE_ID = "postings_lever"
PROVIDER = "lever"
BASE = "https://api.lever.co/v0/postings"
OUT_DIR = POSTINGS_RAW / PROVIDER
MAX_NEW_PER_RUN = 400
THROTTLE_SECONDS = 0.3  # Lever's own reads are slow under load per the work order — pace gently


def _load_candidates() -> list[str]:
    hint_file = SEED_HINTS / "lever_companies.json"
    if not hint_file.exists():
        return []
    return dedupe_seed(json.loads(hint_file.read_text(encoding="utf-8")))


def _parse_salary_range(sr: dict | None) -> dict | None:
    """Lever's own `salaryRange` object -> this pipeline's Compensation shape,
    or None when nothing usable is published. Extracted as its own function
    (package 13) so this exact mapping — the site of two real, historical
    bugs (a `.replace('per-', '')` interval mangler; an `is not None` guard
    that let a real `$0` range through) — has a real regression test
    (`scripts/tests/test_pay_period.py`) that calls this function directly,
    not a re-implementation of it. No behaviour change from the inline
    version this replaced."""
    comp = None
    # `is not None` alone let a real-but-empty $0 range through as a
    # confident figure (found live by this package's own
    # adversarial review) -- `min: 0` is not None. Matches
    # Greenhouse's and USAJOBS's own harvesters, which already
    # reject a zero figure the same way.
    if sr and sr.get("min"):
        # Real values, found live in this pipeline's own cached data
        # (835 per-year-salary, 250 per-hour-wage, 19 per-month-
        # salary, plus one-time/bi-week/semi-month/per-day shapes
        # this Compensation type has no clean bucket for) — an
        # earlier version of this mapping did `.replace('per-', '')`
        # on the raw string, which turns "per-year-salary" into
        # "year-salary", not "year": caught the same way as Ashby's
        # own interval bug (src_postings_ashby.py), by reading the
        # real cached values before trusting the assumption, not by
        # a check that ran before this file first shipped.
        interval = (sr.get("interval") or "").lower()
        if "hour" in interval:
            period = "hour"
        elif "year" in interval:
            period = "year"
        elif "month" in interval and "bi-" not in interval and "semi-" not in interval:
            period = "month"
        else:
            # one-time, bi-week, per-week, bi-month, semi-month,
            # per-day — no bucket in postings.ts's own Compensation
            # type maps onto any of these without either inventing a
            # new period or guessing a conversion factor. Skipped,
            # not forced into the nearest wrong one.
            period = None
        if period:
            min_v, max_v = sr["min"], sr.get("max") or sr["min"]
            raw_text = f"{sr.get('min')}-{sr.get('max')} {sr.get('currency', '')} ({sr.get('interval', '')})"
            # Package 14, Tier 3.2 (external audit Finding 3) — Lever's own
            # interval tag has the identical failure mode as Ashby's own
            # (see src_postings_ashby.py's own comment at the same point):
            # a "per-year-salary" tag on numbers that are plainly hourly
            # ($25-30). USD-only, per reinterpret_implausible_year's own
            # docstring — an adversarial review found this pipeline's own
            # thresholds were never validated against Lever's own EUR/INR
            # postings.
            if period == "year":
                fix = reinterpret_implausible_year(min_v, max_v, raw_text, sr.get("currency"))
                if fix:
                    min_v, max_v, period = fix
            comp = {
                "min": min_v, "max": max_v,
                "currency": sr.get("currency") or "USD", "period": period,
                "raw_text": raw_text,
                "confidence": "structured",
            }
    return comp


def run() -> None:
    banner(SOURCE_ID, "Lever postings API — postings panel")
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
    with_salary_range = 0
    countries: dict[str | None, int] = {}
    for token in to_probe:
        tested += 1
        dest = OUT_DIR / f"{token}.json"
        already_cached_this = dest.exists()
        try:
            # retries=1 during seed probing — a 404 means "not a real
            # board," the common case against a large hint list; see
            # src_postings_ashby.py's own comment on this same point.
            docs = fetch_json(f"{BASE}/{token}?mode=json", dest=dest, cache=True, retries=1)
        except FetchError:
            continue
        if not already_cached_this:
            time.sleep(THROTTLE_SECONDS)
        if not isinstance(docs, list) or not docs:
            continue

        company_rows = []
        for p in docs:
            comp = _parse_salary_range(p.get("salaryRange"))
            if comp:
                with_salary_range += 1
            categories = p.get("categories") or {}
            loc = categories.get("location") or ""
            company_rows.append({
                "id": f"lever:{token}:{p.get('id')}",
                # Lever's own postings API carries no company-display-name
                # field at all -- storing the token here would mean this
                # record's own "company" field silently means two different
                # things across providers (a real name vs. a guessed one).
                # None is the honest value; the UI's fmtCompany() renders a
                # de-slugified label from company_slug when this is absent.
                "provider": PROVIDER, "company": None, "company_slug": token,
                "title": p.get("text"), "location_raw": loc, "country": country_from_location(loc),
                "remote": categories.get("workplaceType") == "remote" if categories.get("workplaceType") else None,
                "url": p.get("hostedUrl") or p.get("applyUrl"),
                "posted_at": None,  # createdAt is epoch ms, not disclosed with enough precision to trust as "posted"
                "compensation": comp,
                "occupation": None,
            })

        postings.extend(company_rows)
        for r in company_rows:
            countries[r["country"]] = countries.get(r["country"], 0) + 1
        this_run_verified[token] = {"company": None, "provider": PROVIDER, "job_count": len(company_rows)}
        if tested % 50 == 0:
            log(f"    ...{tested}/{len(to_probe)} probed, {len(this_run_verified)} verified so far")

    verified_companies, removed = merge_verified_companies(previous, set(to_probe), this_run_verified)
    for r in removed:
        log(f"    REMOVED {r['token']} — {r['consecutive_failures']} consecutive failed probes, "
            f"last verified {r['last_seen_ok']}")

    log_provider_summary(PROVIDER, tested, len(this_run_verified), len(postings), countries)
    log(f"    verified_companies (durable): {len(verified_companies)} ({len(this_run_verified)} reconfirmed "
        f"this run, {len(removed)} removed after repeated failures)")
    log(f"    {with_salary_range} of {len(postings)} postings carried a populated salaryRange "
        f"({with_salary_range / len(postings) * 100 if postings else 0:.1f}%) — real but empirically rare on this provider")

    write_processed(SOURCE_ID, {
        "postings": postings,
        "verified_companies": verified_companies,
    }, meta={
        "candidates_in_hint_file": len(candidates),
        "candidates_probed_this_run": len(to_probe),
        "verified_companies": len(verified_companies),
        "verified_companies_reconfirmed_this_run": len(this_run_verified),
        "verified_companies_removed_this_run": removed,
        "postings_count": len(postings),
        "compensation_present_count": with_salary_range,
    })
    record_provenance(
        source_id=SOURCE_ID,
        name="Lever postings API — advertised pay, optional salaryRange",
        urls=[f"{BASE}/{{token}}?mode=json"],
        license_note="Each company's own postings, published via Lever's own public, unauthenticated "
                      "postings API.",
        redistribution="Only postings from companies whose board was verified live are kept; raw "
                        "per-company responses cached under data/raw/postings/lever/.",
        transforms=[
            "Loaded candidate company tokens from a third-party MIT-licensed aggregator "
            "(github.com/Feashliaa/job-board-aggregator) as SEED HINTS ONLY.",
            "Probed each candidate live; kept only tokens with >=1 real posting.",
            "Read salaryRange directly off each posting — no fan-out needed, but the field is "
            "optional and populated on a small minority of postings in this pipeline's own sample.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(postings),
        coverage=f"{len(verified_companies)} verified companies, {len(postings)} postings, this run",
        notes="Advertised pay — NEVER merged with survey-earnings data. See build_postings.py for the "
              "merged, cross-provider file the site reads.",
    )


if __name__ == "__main__":
    main_guard(run)
