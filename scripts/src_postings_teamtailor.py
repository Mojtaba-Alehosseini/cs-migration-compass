"""Package 12, tier 1/2 — Teamtailor's public jobs.json feed. NOT the
authenticated partner API (api.teamtailor.com, requires a per-customer key
and an API-Version header — confirmed live this session, 406 without one).
The PUBLIC surface every Teamtailor career site exposes for free —
`{subdomain}.teamtailor.com/jobs.json`, a real JSON Feed
(https://jsonfeed.org/version/1.1) with an embedded schema.org JobPosting
per item — needs no key at all. This corrects the plan document's own older
assumption (phase-4-salary-and-cv-plan.md S2.3: "Teamtailor (per-customer
key)") — verified live against nordicknotsab and ictnordics before this
file was written.

NO COMPENSATION OBSERVED IN THIS PIPELINE'S OWN SAMPLE: schema.org's
JobPosting spec supports a `baseSalary` field, so SOME Teamtailor customer
could in principle populate it, but it was absent from every posting sampled
live this session. Taken for volume and Nordic-market coverage — the work
order's own explicit instruction for salary-free sources ("take it for
volume and coverage, clearly marked as salary-free") — not dropped for
lacking pay data.

SEEDING: Teamtailor has no equivalent entry in the third-party aggregator
this package uses for Ashby/Greenhouse/Lever (github.com/Feashliaa/job-
board-aggregator does not index it), so this file's own candidate list is
hand-seeded with real, live-verified Nordic and European companies rather
than probed from a large hint file — a materially smaller, hand-curated seed
until a proper Teamtailor-specific candidate source is found (see
NEEDS-DECISION.md).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import FetchError, banner, fetch_json, log, main_guard, record_provenance, write_processed  # noqa: E402
from postings_common import (  # noqa: E402
    POSTINGS_RAW, country_from_location, load_previously_verified, log_provider_summary,
    merge_verified_companies,
)

SOURCE_ID = "postings_teamtailor"
PROVIDER = "teamtailor"
OUT_DIR = POSTINGS_RAW / PROVIDER
THROTTLE_SECONDS = 0.3

# Hand-seeded, live-verified this session (nordicknotsab, ictnordics — real
# open postings observed; allentenordic — empty response, kept anyway since
# a company with zero CURRENT postings is still a real, working board, and
# gate 4 needs an honest denominator including boards that currently have no
# openings, not just ones that happened to have some the day this ran).
# The rest are well-known Teamtailor customers per the platform's own public
# case-study pages — each is still independently verified live below before
# it counts as "verified", never guessed in. A token that 404s here on its
# FIRST-ever probe is never added; one that was already verified in a past
# run and later 404s is kept through a bounded number of consecutive misses
# (merge_verified_companies(), postings_common.py) rather than dropped on one.
CANDIDATES = [
    "nordicknotsab", "ictnordics", "nordtechgroup", "allentenordic",
    "polestar", "hemnet", "tink", "instabox", "budbee", "kry", "epidemicsound",
    "voi", "northvolt", "einride", "klarna", "truecaller", "mathem",
]


def run() -> None:
    banner(SOURCE_ID, "Teamtailor public jobs.json feed — postings panel")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    previous = load_previously_verified(SOURCE_ID)
    postings: list[dict] = []
    this_run_verified: dict[str, dict] = {}
    tested = 0
    countries: dict[str | None, int] = {}
    for token in CANDIDATES:
        tested += 1
        dest = OUT_DIR / f"{token}.json"
        already = dest.exists()
        try:
            # retries=1 — a 404 here means "not a real board" (this file's
            # own candidate list is hand-guessed, so this fires often); see
            # src_postings_ashby.py's own comment on this same point.
            doc = fetch_json(f"https://{token}.teamtailor.com/jobs.json", dest=dest, cache=True, retries=1)
        except FetchError:
            continue
        if not already:
            time.sleep(THROTTLE_SECONDS)
        items = doc.get("items", [])
        rows = []
        for it in items:
            jp = it.get("_jobposting") or {}
            loc_list = jp.get("jobLocation") or []
            addr = (loc_list[0].get("address") if loc_list else {}) or {}
            loc_raw = ", ".join(x for x in (addr.get("addressLocality"), addr.get("addressRegion"),
                                             addr.get("addressCountry")) if x)
            base_salary = jp.get("baseSalary")  # schema.org field — present for the rare customer who fills it in
            comp = None
            if isinstance(base_salary, dict):
                val = base_salary.get("value", {})
                if isinstance(val, dict) and val.get("minValue"):
                    comp = {"min": val["minValue"], "max": val.get("maxValue") or val["minValue"],
                            "currency": base_salary.get("currency", "USD"),
                            "period": (val.get("unitText") or "YEAR").lower(),
                            "raw_text": str(base_salary), "confidence": "structured"}
            rows.append({
                "id": f"teamtailor:{token}:{it.get('id')}",
                "provider": PROVIDER, "company": doc.get("title") or token, "company_slug": token,
                "title": it.get("title"), "location_raw": loc_raw or None,
                "country": country_from_location(loc_raw) or country_from_location(addr.get("addressCountry")),
                "remote": None, "url": it.get("url"),
                "posted_at": (it.get("date_published") or "")[:10] or None,
                "compensation": comp, "occupation": None,
            })
        postings.extend(rows)
        for r in rows:
            countries[r["country"]] = countries.get(r["country"], 0) + 1
        this_run_verified[token] = {"company": doc.get("title") or token, "provider": PROVIDER, "job_count": len(rows)}

    # Every candidate is probed every run (the hand-seeded list is small
    # enough that there is no cache/new-candidate split to make) — so
    # probed_tokens is simply every candidate, and the merge below only
    # ever protects against a genuine transient failure, never a starved
    # probe budget the way the three larger, hint-file-driven providers
    # can be.
    verified_companies, removed = merge_verified_companies(previous, set(CANDIDATES), this_run_verified)
    for r in removed:
        log(f"    REMOVED {r['token']} — {r['consecutive_failures']} consecutive failed probes, "
            f"last verified {r['last_seen_ok']}")

    log_provider_summary(PROVIDER, tested, len(this_run_verified), len(postings), countries)

    write_processed(SOURCE_ID, {"postings": postings, "verified_companies": verified_companies}, meta={
        "candidates_hand_seeded": len(CANDIDATES),
        "verified_companies": len(verified_companies),
        "verified_companies_reconfirmed_this_run": len(this_run_verified),
        "verified_companies_removed_this_run": removed,
        "postings_count": len(postings),
        "compensation_present_count": sum(1 for p in postings if p["compensation"]),
        "seeding_method": "hand-curated (no third-party candidate list available for this provider)",
    })
    record_provenance(
        source_id=SOURCE_ID,
        name="Teamtailor public jobs.json feed — advertised pay, Nordic/European coverage",
        urls=["https://{subdomain}.teamtailor.com/jobs.json"],
        license_note="Each company's own postings, published via Teamtailor's own public, "
                      "unauthenticated JSON Feed — no Teamtailor-specific license terms apply.",
        redistribution="Raw per-company responses cached under data/raw/postings/teamtailor/.",
        transforms=[
            "Hand-seeded candidate list (no third-party aggregator indexes this provider) — every "
            "token verified live against the real endpoint; a 404 or connection failure drops it.",
            "Parsed the embedded schema.org JobPosting per item; baseSalary read when present "
            "(observed absent in every sampled posting this session, kept in the parser for the "
            "customers who do populate it).",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(postings),
        coverage=f"{len(verified_companies)} verified companies, {len(postings)} postings",
        notes="Advertised pay — NEVER merged with survey-earnings data. Salary-free in this session's "
              "own sample; kept for volume and Nordic-market coverage per the work order's own "
              "explicit instruction for sources like this.",
    )


if __name__ == "__main__":
    main_guard(run)
