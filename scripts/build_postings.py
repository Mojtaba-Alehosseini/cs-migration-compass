"""Package 12 — merges every postings_<provider>.json into the one file the
site actually reads, data/processed/postings.json.

THE BOUNDARY THIS FILE EXISTS TO ENFORCE: advertised pay (this file) and
survey earnings (data/processed/wage_distribution.json, built by
build_wage_distribution.py) are two different quantities from two different
kinds of source — the work order's own Tier 5.1, and phase-4-salary-and-cv-
plan.md's own S2.4, are explicit that they must never be merged into one
number. This file reads NOTHING from wage_distribution.json, writes to a
completely separate output file, and never blends a wage-spine VALUE into a
posting. Two validate_data.py checks cover this structurally, not one:
check_survey_vs_advertised_pay (package 7) scans WITHIN a single file for
co-occurring hint words, which is real and useful but not a comparison
between this file and wage_distribution.json (an earlier version of this
docstring claimed otherwise — found by this package's own adversarial
review); check_postings_wage_spine_boundary (package 12) is the genuine
cross-file check, confirming postings.json and wage_distribution.json's own
distinctive field names never appear in each other — no allow-list, since
the two schemas share no field this pipeline needs to permit (a shared word
like "country"/"currency"/"period" is excluded from the check as ordinary,
not allow-listed as an exception).

Package 14, Tier 3.1 (external audit Finding 3) narrowed the boundary above
by exactly one import: this file now imports normalise.to_usd() (via
postings_common.convert_compensation_to_usd()) for CURRENCY CONVERSION
ONLY — the same year-matched-FX machinery the wage spine uses, applied
entirely within postings' own data. It never reads wage_distribution.json,
never touches comparison_basis()/crosswalk.compare() (the wage-spine-only
machinery this boundary was always actually about), and the converted
value lands in a NEW field name, compensation.usd, that
check_postings_wage_spine_boundary's own field-name sets do not and must
not include — a real, narrow exception, not a quiet abandonment of the
boundary. See postings_common.py's own CURRENCY_TO_FX_COUNTRY for why
converting NINE postings currencies (versus the wage spine's own 15
countries' worth of FX needs) required extending fx_rates.json itself.

WHAT THIS FILE DOES, PLAINLY: reads every scripts/src_postings_*.json this
package's harvesters produced, concatenates their own `postings` arrays,
converts each one's own native compensation to USD at its own effective
year's FX rate (Tier 3.1), computes the per-provider / per-country summary
the seed-list transparency page (tier 4) and the "denominator beside every
figure" discipline (gate 8) both need, and writes the merged result plus
that summary in one envelope.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, banner, log, main_guard, record_provenance, write_processed  # noqa: E402
from postings_common import convert_compensation_to_usd  # noqa: E402

SOURCE_ID = "postings"
PROVIDER_FILES = [
    "postings_ashby", "postings_greenhouse", "postings_lever",
    "postings_teamtailor", "postings_usajobs", "postings_hn",
]


def _effective_year(posting: dict, provider_generated_at: str | None) -> int | None:
    """Package 14, Tier 3.1 — the year a posting's own compensation gets
    FX-converted at. Prefers the posting's own posted_at (a real, sourced
    date most providers publish); falls back to the harvest run's own
    generated_at year when posted_at is absent (Lever's own postings never
    carry one at all — src_postings_lever.py's own comment: createdAt is
    epoch ms, not disclosed with enough precision to trust as 'posted').
    This is a disclosed, defensible choice, not a guess: a live-scraped
    posting has no fixed historical 'reference year' the way a government
    wage survey does — it is inherently current AS OF whenever this
    pipeline harvested it, so the harvest date is a genuine fact about the
    posting, not a substitute for a fact this pipeline lacks. Returns None
    (never converted) only when NEITHER is parseable."""
    posted = posting.get("posted_at")
    if posted:
        try:
            return int(str(posted)[:4])
        except ValueError:
            pass
    if provider_generated_at:
        try:
            return int(str(provider_generated_at)[:4])
        except ValueError:
            pass
    return None


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
        # Package 14, Tier 3.1 — convert each row's own native compensation
        # to USD in place, at ITS OWN effective year's FX rate (never a
        # blanket modern rate). Mutates compensation.usd only; min/max/
        # currency/raw_text (native) are untouched — normalise.py's own
        # rule 5.
        converted = 0
        for row in rows:
            comp = row.get("compensation")
            if not comp:
                continue
            year = _effective_year(row, doc.get("generated_at"))
            comp["usd"] = convert_compensation_to_usd(comp, year) if year else None
            if comp["usd"]:
                converted += 1
        all_postings.extend(rows)
        with_comp = sum(1 for r in rows if r.get("compensation"))
        provider_summary[provider] = {
            "available": True, "postings_count": len(rows), "compensation_present_count": with_comp,
            "compensation_converted_to_usd_count": converted,
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
    converted_total = sum(1 for p in all_postings if (p.get("compensation") or {}).get("usd"))
    # Package 14, Tier 3.4 (external audit Finding 3) — investigated:
    # company is null on Ashby, Lever and HN's own postings for the same
    # reason across all three, verified live, not assumed (see
    # postings_common.py's own record-shape docstring) — their own public
    # APIs never publish a company DISPLAY NAME field at all, only a board
    # TOKEN (Ashby/Lever) or none at all (HN's own free text). Not fixable
    # by this pipeline without inventing a name the source never published
    # — disclosed instead: fmtCompany() (site/src/data/postings.ts,
    # package 12) already renders a readable label from the token rather
    # than a literal null, and this meta field states the real, measured
    # rate plainly for anyone reading the data directly, not just the UI.
    company_null_by_provider: dict[str, int] = {}
    for p in all_postings:
        if not p.get("company"):
            prov = p.get("provider", "unknown")
            company_null_by_provider[prov] = company_null_by_provider.get(prov, 0) + 1
    log(f"    TOTAL: {len(all_postings)} postings across {sum(1 for v in provider_summary.values() if v.get('available'))} "
        f"providers, {len(seed_companies)} distinct seeded companies, {with_comp_total} postings with compensation "
        f"({with_comp_total/len(all_postings)*100 if all_postings else 0:.1f}%), {converted_total} converted to USD "
        f"({converted_total/with_comp_total*100 if with_comp_total else 0:.1f}% of those with compensation)")

    # Package 14 -- moved here from the client (site/src/routes/Postings.tsx's
    # own advertisedByCountryCfg()), a real Lighthouse performance regression
    # this package's own postings recovery caused: history/postings.json grew
    # to a ~20MB JSON payload (46,040 real postings, up from 19,463), and the
    # client was re-scanning the FULL raw array on every page load just to
    # compute a per-country median that is the same for every visitor until
    # this file is next rebuilt. This is a deterministic, build-time-only
    # aggregate -- computing it here means the client ships ~12 small numbers
    # instead of re-deriving them from 46,040 records in the browser. The
    # FULL raw postings array is still shipped (the filterable list view
    # genuinely needs individual records) -- this does not reduce payload
    # size, only removes one expensive, avoidable re-computation from it.
    MIN_ADVERTISED_CHART_N, MAX_ADVERTISED_CHART_COUNTRIES = 5, 12
    by_country_usd_year: dict[str, list[float]] = {}
    for p in all_postings:
        c = p.get("compensation")
        if not c or c.get("currency") != "USD" or c.get("period") != "year" or not p.get("country"):
            continue
        by_country_usd_year.setdefault(p["country"], []).append((c["min"] + c["max"]) / 2)

    def _median(nums: list[float]) -> float:
        s = sorted(nums)
        mid = len(s) // 2
        return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2

    advertised_by_country = sorted(
        (
            {"country": cc, "n": len(vals), "median": round(_median(vals), 2)}
            for cc, vals in by_country_usd_year.items() if len(vals) >= MIN_ADVERTISED_CHART_N
        ),
        key=lambda r: -r["median"],
    )[:MAX_ADVERTISED_CHART_COUNTRIES]
    log(f"    advertised-by-country (USD/year, n>={MIN_ADVERTISED_CHART_N}): "
        f"{len(advertised_by_country)} countries")

    write_processed(SOURCE_ID, {
        "postings": all_postings,
        "provider_summary": provider_summary,
        "seed_companies": seed_companies,
        "country_counts": country_counts,
        "advertised_by_country": advertised_by_country,
    }, meta={
        "postings_count": len(all_postings),
        "seed_companies_count": len(seed_companies),
        "compensation_present_count": with_comp_total,
        "compensation_converted_to_usd_count": converted_total,
        "company_null_count": sum(company_null_by_provider.values()),
        "company_null_by_provider": company_null_by_provider,
        "company_null_note": "Ashby, Lever and Hacker News' own APIs never publish a company DISPLAY "
                              "NAME field (Ashby/Lever: a board token only; HN: free text with no "
                              "company field at all) — verified live, not this pipeline failing to "
                              "extract one. site/src/data/postings.ts's own fmtCompany() renders a "
                              "readable label from the token for display; this field states the real, "
                              "measured null rate for anyone reading the data directly.",
        "providers_available": [k for k, v in provider_summary.items() if v.get("available")],
        "boundary_note": "Advertised pay ONLY — never merged with data/processed/wage_distribution.json "
                          "(survey earnings), never compared against it, never shares a chart series with "
                          "it. Package 14, Tier 3.1 narrowed the boundary by exactly one import — "
                          "normalise.to_usd(), for currency conversion only. See this file's own module "
                          "docstring.",
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
            "Converted each posting's own native compensation to USD at its own effective year's "
            "year-matched FX rate (Tier 3.1) — normalise.to_usd(), the same machinery the wage spine "
            "uses, applied entirely within postings' own data; never reads wage_distribution.json.",
            "Computed per-provider and per-country summary counts for the seed-list transparency page "
            "and the coverage-denominator discipline this site's own other panels already follow.",
            "Never touched wage_distribution.json, crosswalk.compare(), or comparison_basis() — the "
            "survey/advertised boundary is enforced structurally by check_postings_wage_spine_boundary, "
            "not just by convention.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(all_postings),
        coverage=f"{len(seed_companies)} companies across {len([v for v in provider_summary.values() if v.get('available')])} providers",
        notes="The site's own postings panel reads ONLY this file, never an individual provider file.",
    )


if __name__ == "__main__":
    main_guard(run)
