"""Package 12, tier 1/2 — Greenhouse Job Board API. Verified live (work
order's own Tier 1.1 table; re-confirmed this session against stripe): the
LIST endpoint (`boards-api.greenhouse.io/v1/boards/{token}/jobs`) is cheap
and unauthenticated, but `pay_input_ranges` is EMPTY on it — compensation
only appears on the DETAIL endpoint, and only with `?pay_transparency=true`,
one request per job. That fan-out is the real cost of this source, and it is
throttled deliberately (see MAX_JOBS_PER_COMPANY and the sleep below) —
gate 2 of this package's own report shows this throttling with real numbers,
not just asserts that it exists.

SEEDING: same discipline as src_postings_ashby.py — data/raw/postings_seed_
hints/greenhouse_companies.json (8,333 tokens, MIT-licensed, third-party
aggregator, SEED HINT ONLY) is probed live; a token only enters this
pipeline's own output once its list endpoint actually resolves with >=1 job.
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
    load_previously_verified, log_provider_summary, merge_verified_companies,
)

SOURCE_ID = "postings_greenhouse"
PROVIDER = "greenhouse"
BASE = "https://boards-api.greenhouse.io/v1/boards"
OUT_DIR = POSTINGS_RAW / PROVIDER
MAX_NEW_COMPANIES_PER_RUN = 250
# Fetching every job's own detail (one request each, for pay_input_ranges) is
# the real cost of this source — a company with 800 open roles would cost 800
# requests on its own. Capped per company so one large employer cannot starve
# the rest of the run's own request budget; the list endpoint itself (which
# still names every job, just without a range) has no such cap.
MAX_JOBS_PER_COMPANY_FOR_COMPENSATION = 40
THROTTLE_SECONDS = 0.4


def _load_candidates() -> list[str]:
    hint_file = SEED_HINTS / "greenhouse_companies.json"
    if not hint_file.exists():
        return []
    return dedupe_seed(json.loads(hint_file.read_text(encoding="utf-8")))


def _parse_pay_input_ranges(ranges: list) -> dict | None:
    """Greenhouse's own `pay_input_ranges` -> this pipeline's Compensation
    shape, or None. Extracted as its own function (package 13) so the
    magnitude-based period inference — a real, disclosed heuristic, and the
    thing an earlier version of this code got wrong by assuming every range
    was annual — has a real regression test
    (`scripts/tests/test_pay_period.py`) that calls this function directly.
    No behaviour change from the inline version this replaced."""
    if not ranges:
        return None
    r = ranges[0]
    lo, hi = (r.get("min_cents") or 0) / 100, (r.get("max_cents") or 0) / 100
    # Greenhouse's own pay_input_ranges carries NO period field at
    # all — found live, not assumed: the SAME company (10beauty)
    # posts both "$100,000-$125,000" and "$30.00-$35.00" ranges
    # under the identical "Salary Range" title, with nothing in
    # the response distinguishing annual from hourly. An earlier
    # version of this code assumed every range was annual, which
    # would have shown "$30-35/yr" for what is unmistakably an
    # hourly rate. No real full-time annual salary is under
    # $1,000/year and no real hourly wage is over $1,000/hour, so
    # a magnitude threshold is a genuine, disclosed inference
    # here, not a guess dressed up as data — see NEEDS-DECISION.md
    # for the residual ambiguity this doesn't resolve (a role paid
    # $1,000-$5,000 could misclassify either way; none observed
    # live in this pipeline's own sample).
    period = "hour" if 0 < hi < 1000 else "year"
    return {
        "min": lo, "max": hi,
        "currency": r.get("currency_type") or "USD", "period": period,
        "raw_text": f"{lo:,.0f}-{hi:,.0f} "
                    f"{r.get('currency_type', '')} (period inferred from magnitude — Greenhouse's own API does not disclose it)",
        "confidence": "structured",
    } if r.get("min_cents") else None


def run() -> None:
    banner(SOURCE_ID, "Greenhouse Job Board API — postings panel")
    (OUT_DIR / "lists").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "details").mkdir(parents=True, exist_ok=True)
    candidates = _load_candidates()
    log(f"    {len(candidates)} candidate tokens loaded from the seed hint file")

    previous = load_previously_verified(SOURCE_ID)
    already_cached = {p.stem for p in (OUT_DIR / "lists").glob("*.json")}
    to_probe = build_probe_order(candidates, already_cached, set(previous.keys()), MAX_NEW_COMPANIES_PER_RUN)
    log(f"    {len(already_cached)} already cached from prior runs, {len(previous)} previously "
        f"committed as verified, probing {len(to_probe)} this run (cap {MAX_NEW_COMPANIES_PER_RUN} new)")

    postings: list[dict] = []
    this_run_verified: dict[str, dict] = {}
    tested = 0
    fanout_requests = 0
    countries: dict[str | None, int] = {}
    for token in to_probe:
        tested += 1
        list_dest = OUT_DIR / "lists" / f"{token}.json"
        already_had_list = list_dest.exists()
        try:
            # retries=1 during seed probing — see src_postings_ashby.py's
            # own comment: a 404 here means "not a real board," not a
            # transient failure worth retrying.
            doc = fetch_json(f"{BASE}/{token}/jobs", dest=list_dest, cache=True, retries=1)
        except FetchError:
            continue
        if not already_had_list:
            time.sleep(THROTTLE_SECONDS)
        jobs = doc.get("jobs") or []
        if not jobs:
            continue

        company_name = jobs[0].get("company_name") or token
        company_rows: list[dict] = []
        # THE THROTTLED FAN-OUT — one request per job, capped, deliberately
        # slower than the list call above (gate 2's own evidence point).
        for j in jobs[:MAX_JOBS_PER_COMPANY_FOR_COMPENSATION]:
            jid = j.get("id")
            detail_dest = OUT_DIR / "details" / f"{token}_{jid}.json"
            already_had_detail = detail_dest.exists()
            try:
                detail = fetch_json(f"{BASE}/{token}/jobs/{jid}?pay_transparency=true",
                                     dest=detail_dest, cache=True, retries=2, backoff=1.5)
            except FetchError:
                detail = None
            if not already_had_detail:
                fanout_requests += 1
                time.sleep(THROTTLE_SECONDS)
            ranges = (detail or {}).get("pay_input_ranges") or []
            comp = _parse_pay_input_ranges(ranges)
            loc = j.get("location", {}).get("name") or ""
            company_rows.append({
                "id": f"greenhouse:{token}:{jid}",
                "provider": PROVIDER, "company": company_name, "company_slug": token,
                "title": j.get("title"), "location_raw": loc, "country": country_from_location(loc),
                "remote": None,
                "url": j.get("absolute_url"),
                "posted_at": (j.get("updated_at") or "")[:10] or None,
                "compensation": comp,
                "occupation": None,
            })
        # jobs beyond the compensation-fan-out cap still get counted and
        # listed (title/location/url), just without a pay attempt — showing
        # fewer POSTINGS than the company really has would be a silent cap
        # this project's own no-silent-caps discipline forbids; only the
        # PAY LOOKUP is capped, disclosed in this file's own meta below.
        for j in jobs[MAX_JOBS_PER_COMPANY_FOR_COMPENSATION:]:
            loc = j.get("location", {}).get("name") or ""
            company_rows.append({
                "id": f"greenhouse:{token}:{j.get('id')}",
                "provider": PROVIDER, "company": company_name, "company_slug": token,
                "title": j.get("title"), "location_raw": loc, "country": country_from_location(loc),
                "remote": None, "url": j.get("absolute_url"),
                "posted_at": (j.get("updated_at") or "")[:10] or None,
                "compensation": None, "occupation": None,
            })

        postings.extend(company_rows)
        for r in company_rows:
            countries[r["country"]] = countries.get(r["country"], 0) + 1
        this_run_verified[token] = {"company": company_name, "provider": PROVIDER, "job_count": len(company_rows)}
        if tested % 25 == 0:
            log(f"    ...{tested}/{len(to_probe)} probed, {len(this_run_verified)} verified, "
                f"{fanout_requests} compensation look-ups so far")

    verified_companies, removed = merge_verified_companies(previous, set(to_probe), this_run_verified)
    for r in removed:
        log(f"    REMOVED {r['token']} ({r['company']}) — {r['consecutive_failures']} consecutive "
            f"failed probes, last verified {r['last_seen_ok']}")

    log_provider_summary(PROVIDER, tested, len(this_run_verified), len(postings), countries)
    log(f"    verified_companies (durable): {len(verified_companies)} ({len(this_run_verified)} reconfirmed "
        f"this run, {len(removed)} removed after repeated failures)")
    log(f"    compensation fan-out: {fanout_requests} per-job requests this run, throttled at "
        f"{THROTTLE_SECONDS}s each, capped at {MAX_JOBS_PER_COMPANY_FOR_COMPENSATION} jobs/company")

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
        "compensation_present_count": sum(1 for p in postings if p["compensation"]),
        "compensation_fanout_requests_this_run": fanout_requests,
        "compensation_lookup_cap_per_company": MAX_JOBS_PER_COMPANY_FOR_COMPENSATION,
        "compensation_lookup_throttle_seconds": THROTTLE_SECONDS,
    })
    record_provenance(
        source_id=SOURCE_ID,
        name="Greenhouse Job Board API — advertised pay, per-job pay_transparency fan-out",
        urls=[f"{BASE}/{{token}}/jobs", f"{BASE}/{{token}}/jobs/{{id}}?pay_transparency=true"],
        license_note="Each company's own postings, published via Greenhouse's own public, "
                      "unauthenticated Job Board API.",
        redistribution="Only postings from companies whose board was verified live are kept; raw "
                        "list and per-job detail responses cached under data/raw/postings/greenhouse/.",
        transforms=[
            "Loaded candidate company tokens from a third-party MIT-licensed aggregator "
            "(github.com/Feashliaa/job-board-aggregator) as SEED HINTS ONLY.",
            "Probed each candidate's list endpoint live; kept only tokens with >=1 real job.",
            "Fetched pay_input_ranges via the detail endpoint's own ?pay_transparency=true flag, "
            f"one request per job, throttled to {THROTTLE_SECONDS}s apart, capped at "
            f"{MAX_JOBS_PER_COMPANY_FOR_COMPENSATION} jobs/company/run — every job still appears "
            "in the output with its title/location/url even past that cap, just without a pay "
            "attempt that run (grows on the next scheduled run via the same on-disk cache).",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(postings),
        coverage=f"{len(verified_companies)} verified companies, {len(postings)} postings, this run",
        notes="Advertised pay — NEVER merged with survey-earnings data. See build_postings.py for the "
              "merged, cross-provider file the site reads.",
    )


if __name__ == "__main__":
    main_guard(run)
