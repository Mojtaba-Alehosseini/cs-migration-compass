"""Build the site's data bundle — runs automatically before `npm run dev|build`.

Splits the dataset by how urgently the browser needs it, because the primary
visitor arrives from a Reddit link and leaves in five seconds if nothing renders:

  site/public/data/core.json        countries + cities + metrics + derived defaults
                                    (loaded immediately, kept small)
  site/public/data/history/*.json   per-source historical series (lazy, per theme)
  site/public/data/provenance.json  every source, licence and transform
  site/public/data/sources-index.json  metric -> source/confidence/as_of lookup

Derived values are precomputed ONLY as defaults. Every input that feeds them is
shipped too, so the client recomputes live when the user edits the budget — the
site never shows a number it cannot re-derive and explain.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA, PROCESSED, PROVENANCE, ROOT, load_cities, load_countries, log,
)

SITE_DATA = ROOT / "site" / "public" / "data"
HISTORY_DIR = SITE_DATA / "history"

# Which processed datasets ship as lazily-loaded history files, and under which
# theme the UI groups them.
HISTORY_SETS = {
    "world_bank": "money",
    "bis_property_prices": "housing",
    "oecd_indicators": "housing",
    "fhfa_hpi_metro": "housing",
    "uk_hpi": "housing",
    "teranet_national_bank_hpi": "housing",
    "numbeo_history": "housing",
    "eurostat_ict_specialists": "jobs",
    "eurostat_total_employment": "jobs",
    "indeed_hiring_lab_job_postings": "jobs",
    "bls_oews": "jobs",
    "stackoverflow_survey": "jobs",
    "wage_distribution": "money",
    "experience_gradient": "money",
    "postings": "jobs",
    # Package 14 — a small, separate slice of postings.json (provider_summary/
    # seed_companies/country_counts only) for PostingsSeed.tsx, which never
    # needs the full ~20MB `postings` array. See build_postings.py's own
    # comment at this file's construction for why.
    "postings_seed_summary": "jobs",
    "world_happiness_report": "life",
    "rsf_press_freedom": "life",
    "wipo_gii": "jobs",
    "mipex": "people",
    "un_migrant_stock": "people",
    "wikipedia_english_speakers": "people",
    "ef_epi": "people",
    # institutional forecasts
    "oecd_economic_outlook": "forecast",
    "un_wpp": "forecast",
    "imf_weo": "forecast",
    "worldbank_gep": "forecast",
}

# A 90 m2 apartment is the reference home, matching metrics.json.
HOME_M2 = 90

# Is years-to-home bigger than its own error bars?
#
# savings is a DIFFERENCE of two large numbers and years-to-home divides by it.
# Rent and living costs are each published to $10/month, so both moving one step
# is $240/year. A savings figure smaller than that is the rounding on its inputs,
# not a measurement, and dividing by it reports a ratio the inputs cannot
# support. The threshold is the inputs' own precision, not a chosen number.
#
# This mirrors yearsToHomeStability() in site/src/data/compute.ts exactly; the
# client recomputes it when the user edits the budget. Against the live data it
# flags exactly Milan and Valencia — the worst of the other 70 moves 11%.
SAVINGS_PRECISION_USD_YEAR = 12 * 10 * 2
STABILITY_TOLERANCE = 0.25


def _stability(savings: float, apt: float) -> str:
    base = (HOME_M2 * apt) / savings
    for delta in (SAVINGS_PRECISION_USD_YEAR, -SAVINGS_PRECISION_USD_YEAR):
        shifted = savings + delta
        if shifted <= 0:
            return "unstable"
        if abs((HOME_M2 * apt) / shifted - base) / base > STABILITY_TOLERANCE:
            return "unstable"
    return "stable"


def load_processed(source_id: str) -> dict | None:
    path = PROCESSED / f"{source_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def derive_city(city: dict, country: dict) -> dict:
    """Attach default computed values plus the formula that produced them."""
    sal = city.get("salary_usd_year") or {}
    net_pct = ((country.get("tax") or {}).get("net_pct_single_mid_dev"))
    rent = city.get("rent_1br_outside_usd_month")
    col = city.get("col_single_no_rent_usd_month")
    apt = city.get("apt_price_outside_usd_m2")

    # Every computed key is ALWAYS emitted, with an explicit null and the list of
    # inputs that were missing. A silently absent key is indistinguishable from a
    # bug; "no data, because we have no living-cost figure for Aarhus" is honest
    # and is what the UI renders. (Aarhus and Doha are the standing null tests.)
    out: dict = {"computed": {}}
    for band in ("new_grad", "mid", "senior"):
        gross = sal.get(band)
        missing: list[str] = []
        if not isinstance(gross, (int, float)):
            missing.append("salary")
        if net_pct is None:
            missing.append("net_tax_pct")
        if not isinstance(rent, (int, float)):
            missing.append("rent_1br_outside_usd_month")
        if not isinstance(col, (int, float)):
            missing.append("col_single_no_rent_usd_month")
        if not isinstance(apt, (int, float)):
            missing.append("apt_price_outside_usd_m2")

        entry: dict = {
            "gross_usd": gross if isinstance(gross, (int, float)) else None,
            "net_usd": None,
            "monthly_rent_usd": rent if isinstance(rent, (int, float)) else None,
            "monthly_living_usd": col if isinstance(col, (int, float)) else None,
            "savings_usd_year": None,
            "years_to_home": None,
            "years_to_home_stability": None,
            "m2_per_year": None,
            "missing_inputs": missing,
        }

        if isinstance(gross, (int, float)) and net_pct is not None:
            net = gross * net_pct / 100
            entry["net_usd"] = round(net)
            if isinstance(rent, (int, float)) and isinstance(col, (int, float)):
                savings = net - 12 * (rent + col)
                entry["savings_usd_year"] = round(savings)
                if isinstance(apt, (int, float)):
                    if savings > 0:
                        entry["years_to_home"] = round((HOME_M2 * apt) / savings, 1)
                        entry["m2_per_year"] = round(savings / apt, 1)
                        entry["years_to_home_stability"] = _stability(savings, apt)
                    else:
                        # Zero or negative savings means "never on this income",
                        # not a very large number. The UI says so in words.
                        entry["m2_per_year"] = 0
                        entry["never_note"] = "savings are zero or negative at this band"
        out["computed"][band] = entry

    out["formulas"] = {
        "net_usd": "gross x country net-take-home %",
        "savings_usd_year": "net - 12 x (rent outside centre + living costs)",
        "years_to_home": f"({HOME_M2} m2 x price per m2 outside centre) / savings per year",
        "m2_per_year": "savings per year / price per m2 outside centre",
    }
    out["inputs_editable"] = ["monthly_rent_usd", "monthly_living_usd", "net_pct"]
    out["net_pct"] = net_pct
    return out


def build_core() -> dict:
    countries = load_countries()
    cities = load_cities()
    metrics = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in countries}

    # --- cross-source country enrichment -------------------------------------
    migrants = load_processed("un_migrant_stock")
    wb = load_processed("world_bank")
    ict = load_processed("eurostat_ict_specialists")
    emp = load_processed("eurostat_total_employment")
    whr = load_processed("world_happiness_report")

    for country in countries:
        cid = country["id"]
        extra: dict = {}

        if migrants:
            md = migrants["data"]
            totals = md["total_foreign_born"].get(cid) or []
            latest_total = totals[-1] if totals else None
            pop_series = ((wb or {}).get("data", {}).get(cid, {}) or {}).get("population") or []
            pop = pop_series[-1]["value"] if pop_series else None
            if latest_total and pop:
                extra["foreign_born"] = {
                    "count": latest_total["value"],
                    "year": latest_total["year"],
                    "share_pct": round(latest_total["value"] / pop * 100, 1),
                    "formula": "UN DESA foreign-born stock / World Bank population",
                }
            iran = md["iranian_born"].get(cid) or []
            if iran:
                extra["iranian_born"] = {"count": iran[-1]["value"], "year": iran[-1]["year"]}
            origins = (md["origins_latest"].get(cid) or [])[:12]
            if origins:
                extra["top_origins"] = origins

        if ict:
            block = ict["data"]["countries"].get(cid) or {}
            counts = block.get("ict_specialists_thousands") or []
            shares = block.get("ict_share_of_employment_pct") or []
            if counts:
                extra["ict_specialists"] = {
                    "thousands": counts[-1]["value"], "year": counts[-1]["year"],
                    "share_pct": shares[-1]["value"] if shares else None,
                }
        if emp:
            tot = (emp["data"].get(cid) or {}).get("total_employment_thousands") or []
            if tot:
                extra["total_employment"] = {"thousands": tot[-1]["value"], "year": tot[-1]["year"]}

        if whr:
            series = whr["data"]["countries"].get(cid) or []
            if series:
                latest = series[-1]
                denom = whr["data"]["ranked_countries_per_year"].get(str(latest["year"])) \
                    or whr["data"]["ranked_countries_per_year"].get(latest["year"])
                extra["happiness"] = {
                    "score": latest.get("score"), "rank": latest.get("rank"),
                    "of": denom, "year": latest["year"],
                }
        country["enriched"] = extra

    for city in cities:
        country = by_id.get(city.get("country"))
        if country:
            city.update(derive_city(city, country))

    return {
        "generated_from": "data/countries.json, data/cities.json, data/metrics.json + data/processed/*",
        "as_of": json.loads((DATA / "cities.json").read_text(encoding="utf-8")).get("as_of"),
        "metrics": metrics,
        "countries": countries,
        "cities": cities,
        "home_reference_m2": HOME_M2,
        "principles": {
            "no_recommendation": (
                "This dataset carries no ranking, score or verdict. Any ordering exists only "
                "because a user constructed it."
            ),
            "nulls": "null means no data. It is never replaced with 0 or an estimate.",
        },
    }


def _slim_postings(doc: dict) -> dict:
    """Ship the postings annotations the UI reads, not the diagnostics.

    Package 16 joined a class and a duplicate pointer onto all 48,267 rows. In
    data/processed/postings.json -- the source of truth, which is what every
    analysis script reads -- each row carries the full record. Shipping the same
    thing to the browser cost 4.9 MB on top of a payload that was already the
    site's worst (NEEDS-DECISION #38), and pushed /postings from 0.80 to 0.71 on
    Lighthouse.

    So the per-row annotations are NOT shipped at all, and the aggregates that
    the UI does read -- title_class_summary, duplicate_summary,
    pay_summary_by_country -- are, at a few hundred bytes each.

    That is not a guess about cost. Measured on one build, swapping only this
    file and running Lighthouse three times each: the pre-package-16 payload
    scores 0.87 with LCP 2.44s, and the same build carrying per-row annotations
    scores 0.72 with LCP 2.50s. 160 KiB gzipped, 15 points, on the one route
    that was already the site's worst. Nothing in site/src reads either field --
    the page still says category is not filterable yet -- so the browser was
    paying for data no code opened.

    When a category filter is built, ship them again and pay the cost knowingly.
    Until then the source of truth carries the full record and the wire does
    not."""
    import copy
    doc = copy.deepcopy(doc)
    rows = doc.get("data", {}).get("postings") or []
    for r in rows:
        # Package 17 — ONE key, not the whole block. Package 16 dropped
        # title_class entirely because shipping it cost 15 Lighthouse points,
        # and the merged page then had to guess at software from the title with
        # a regex. Measured, that regex disagreed with the real classifier on
        # about 20% of rows in both directions — it missed 2,427 the model calls
        # software and added ~2,950 it does not — which is a second, worse
        # classifier deciding what a reader sees while the published medians come
        # from the first. `sw` is emitted only where true: 13,463 rows, ~92 KB
        # raw, against the ~1,000 KB the full block cost.
        if (r.pop("title_class", None) or {}).get("class") == "SW":
            r["sw"] = True
        r.pop("duplicate_of", None)
    doc.setdefault("meta", {})["shipped_row_shape"] = (
        "`sw: true` marks a row the classifier calls software, and is present only where true. The "
        "full title_class block and duplicate_of are NOT shipped -- they cost 15 Lighthouse points "
        "on this payload and nothing renders them. The complete record is in "
        "data/processed/postings.json; the aggregates are shipped as data.title_class_summary, "
        "data.duplicate_summary and data.pay_summary_by_country. The flag exists so the page shows "
        "the SAME software set the published medians are computed from, rather than re-deriving it "
        "from titles and disagreeing with itself.")
    return doc


def main() -> int:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    log("building site data bundle")
    core = build_core()
    (SITE_DATA / "core.json").write_text(
        json.dumps(core, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    size = (SITE_DATA / "core.json").stat().st_size
    log(f"  core.json            {size/1024:8.1f} KB  "
        f"({len(core['countries'])} countries, {len(core['cities'])} cities)")

    manifest: dict[str, dict] = {}
    for source_id, theme in HISTORY_SETS.items():
        doc = load_processed(source_id)
        if doc is None:
            log(f"  ! {source_id}: no processed file — skipped")
            continue
        if source_id == "postings":
            doc = _slim_postings(doc)
        dest = HISTORY_DIR / f"{source_id}.json"
        dest.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        kb = dest.stat().st_size / 1024
        manifest[source_id] = {
            "theme": theme,
            "file": f"history/{source_id}.json",
            "kb": round(kb, 1),
            "kind": doc.get("meta", {}).get("kind"),
            "confidence": doc.get("meta", {}).get("confidence"),
            "institution": doc.get("meta", {}).get("institution"),
            "attribution_chip": doc.get("meta", {}).get("attribution_chip"),
            "status": doc.get("meta", {}).get("status", "ok"),
            "empty": not doc.get("data"),
        }
        log(f"  {source_id:34s} {kb:8.1f} KB  [{theme}]")

    (SITE_DATA / "history-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    if PROVENANCE.exists():
        shutil.copyfile(PROVENANCE, SITE_DATA / "provenance.json")
        log(f"  provenance.json      {(SITE_DATA / 'provenance.json').stat().st_size/1024:8.1f} KB")

    # Raw curated files are offered as downloads on the Data & Methods page.
    # pay_composition.json also feeds the <Derived> method card's concept-name/
    # includes-excludes/pay-cycle-context content directly (see store.ts's
    # loadPayComposition(), not explore.ts's loadWages() — corrected, tier 7,
    # finding F21) — it is fetched by the app itself, not just downloadable.
    for name in ("countries.json", "cities.json", "metrics.json", "data-pipeline-sources.json",
                 "pay_composition.json", "occupations.json"):
        src = DATA / name
        if src.exists():
            shutil.copyfile(src, SITE_DATA / name)

    total = sum(p.stat().st_size for p in SITE_DATA.rglob("*.json")) / 1024 / 1024
    log(f"  total bundle {total:.1f} MB (core is the only blocking load)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
