"""Package 12 — merges every postings_<provider>.json into the one file the
site actually reads, data/processed/postings.json.

THE BOUNDARY THIS FILE EXISTS TO ENFORCE: advertised pay (this file) and
survey earnings (data/processed/wage_distribution.json, built by
build_wage_distribution.py) are two different quantities from two different
kinds of source — the work order's own Tier 5.1, and phase-4-salary-and-cv-
plan.md's own S2.4, are explicit that they must never be merged into one
number. This file imports NOTHING from build_wage_distribution.py or
normalise.py, reads NOTHING from wage_distribution.json, and writes to a
completely separate output file. Two validate_data.py checks cover this
structurally, not one: check_survey_vs_advertised_pay (package 7) scans
WITHIN a single file for co-occurring hint words, which is real and useful
but not a comparison between this file and wage_distribution.json (an
earlier version of this docstring claimed otherwise — found by this
package's own adversarial review); check_postings_wage_spine_boundary
(package 12) is the genuine cross-file check, confirming postings.json and
wage_distribution.json's own distinctive field names never appear in each
other — no allow-list, since the two schemas share no field this pipeline
needs to permit (a shared word like "country"/"currency"/"period" is
excluded from the check as ordinary, not allow-listed as an exception).

WHAT THIS FILE DOES, PLAINLY: reads every scripts/src_postings_*.json this
package's harvesters produced, concatenates their own `postings` arrays,
computes the per-provider / per-country summary the seed-list transparency
page (tier 4) and the "denominator beside every figure" discipline (gate 8)
both need, and writes the merged result plus that summary in one envelope.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, banner, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "postings"
PROVIDER_FILES = [
    "postings_ashby", "postings_greenhouse", "postings_lever",
    "postings_teamtailor", "postings_usajobs", "postings_hn",
]


def _load(source_id: str) -> dict | None:
    p = PROCESSED / f"{source_id}.json"
    if not p.exists():
        return None
    import json
    return json.loads(p.read_text(encoding="utf-8"))


def run() -> None:
    banner(SOURCE_ID, "merge every postings_<provider>.json into one file")
    all_postings: list[dict] = []
    provider_summary: dict[str, dict] = {}
    seed_companies: dict[str, dict] = {}  # company_slug -> {provider, company, country_guess, job_count, last_fetched}

    for source_id in PROVIDER_FILES:
        provider = source_id.replace("postings_", "")
        doc = _load(source_id)
        if not doc:
            provider_summary[provider] = {"available": False}
            log(f"    {provider}: not built yet (run scripts/{source_id.replace('postings_', 'src_postings_')}.py first)")
            continue
        rows = doc.get("data", {}).get("postings", [])
        all_postings.extend(rows)
        with_comp = sum(1 for r in rows if r.get("compensation"))
        provider_summary[provider] = {
            "available": True, "postings_count": len(rows), "compensation_present_count": with_comp,
            "generated_at": doc.get("generated_at"),
        }
        verified = doc.get("data", {}).get("verified_companies")
        if verified:
            for slug, info in verified.items():
                seed_companies[f"{provider}:{slug}"] = {
                    "provider": provider, "company_slug": slug,
                    "company": info.get("company"), "job_count": info.get("job_count"),
                }
        log(f"    {provider}: {len(rows)} postings ({with_comp} with compensation)")

    country_counts: dict[str, int] = {}
    for p in all_postings:
        c = p.get("country") or "unresolved"
        country_counts[c] = country_counts.get(c, 0) + 1

    with_comp_total = sum(1 for p in all_postings if p.get("compensation"))
    log(f"    TOTAL: {len(all_postings)} postings across {sum(1 for v in provider_summary.values() if v.get('available'))} "
        f"providers, {len(seed_companies)} distinct seeded companies, {with_comp_total} postings with compensation "
        f"({with_comp_total/len(all_postings)*100 if all_postings else 0:.1f}%)")

    write_processed(SOURCE_ID, {
        "postings": all_postings,
        "provider_summary": provider_summary,
        "seed_companies": seed_companies,
        "country_counts": country_counts,
    }, meta={
        "postings_count": len(all_postings),
        "seed_companies_count": len(seed_companies),
        "compensation_present_count": with_comp_total,
        "providers_available": [k for k, v in provider_summary.items() if v.get("available")],
        "boundary_note": "Advertised pay ONLY — never merged with data/processed/wage_distribution.json "
                          "(survey earnings). See this file's own module docstring.",
    })
    record_provenance(
        source_id=SOURCE_ID,
        name="Postings panel — merged advertised-pay data across all providers",
        urls=[],  # derived — each provider's own postings_<provider> entry already carries its own real URLs
        license_note="Inherits each provider source's own license — this file adds no new terms, only "
                      "concatenation and summary computation over already-committed, already-licensed data.",
        redistribution="derived — nothing fetched here; every provider's own provenance entry already "
                        "covers redistribution terms for its own postings.",
        transforms=[
            "Concatenated every provider's own postings array into one list.",
            "Computed per-provider and per-country summary counts for the seed-list transparency page "
            "and the coverage-denominator discipline this site's own other panels already follow.",
            "Never touched wage_distribution.json or normalise.py — the survey/advertised boundary is "
            "enforced structurally by this file's own imports, not just by convention.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(all_postings),
        coverage=f"{len(seed_companies)} companies across {len([v for v in provider_summary.values() if v.get('available')])} providers",
        notes="The site's own postings panel reads ONLY this file, never an individual provider file.",
    )


if __name__ == "__main__":
    main_guard(run)
