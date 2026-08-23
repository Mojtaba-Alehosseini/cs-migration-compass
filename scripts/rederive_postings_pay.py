"""Package 15, Tier 5.3-5.5 — re-derive per-country advertised pay on the
classified, de-duplicated, software-only subset, and report how far the
published figure moves.

That delta is the size of the error the site has been publishing. It is
reported per country rather than as one headline, because the occupational
mix differs by country and so the error does too -- which is the whole
substance of finding 0-A.

Also here, because they need the same clean subset:
  5.4 selection bias, measured against the site's own Eurostat ICT-employment
      series rather than asserted, and turned into a per-country
      representativeness score the UI could show.
  5.5 the transfer assumption -- whether a role sits at the same percentile
      of the official wage distribution in every country that publishes
      both. If it drifts, transfer is not defensible into the countries
      where it drifts, and this names them.

    python scripts/rederive_postings_pay.py
    python scripts/rederive_postings_pay.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, log  # noqa: E402

OUT = ROOT / "data" / "quality_history" / "postings_pay_rederived.json"
# Two different sample-size floors exist in this package and they are not the
# same quantity, so both are named here to stop them being read as one:
#   * audit_statistical.bootstrap_ci(min_n=12) gates whether an INTERVAL can be
#     computed at all -- below ~12 a resample cannot explore the distribution
#     and the interval degenerates towards the sample range.
#   * MIN_N_PUBLISH gates whether a country median is fit to PUBLISH. 30 is the
#     conventional floor for treating a median's sampling distribution as
#     tractable, and it is applied as a hard gate rather than a hint: a country
#     below it gets no published figure regardless of how tight its interval
#     happens to look.
# A country can therefore have a computable CI and still be unpublishable, which
# is the case for CA (n=6) and GB (n=13).
MIN_N_PUBLISH = 30
SEED = 15


def _load():
    post = json.loads((PROCESSED / "postings.json").read_text(encoding="utf-8"))["data"]
    raw = json.loads((PROCESSED / "postings_title_classes.json").read_text(encoding="utf-8"))["data"]
    cls = {r["title"]: r for r in raw["classified_titles"]}
    dup = json.loads((PROCESSED / "postings_duplicate_clusters.json").read_text(encoding="utf-8"))["data"]
    return post, cls, dup


def _samples(rows, keep_idx=None, sw_only=False, cls=None):
    by = defaultdict(list)
    for i, p in enumerate(rows):
        if keep_idx is not None and i not in keep_idx:
            continue
        if sw_only:
            t = (p.get("title") or "").strip()
            if (cls.get(t) or {}).get("class") != "SW":
                continue
        c = p.get("compensation")
        if not c or c.get("period") != "year" or not p.get("country"):
            continue
        u = c.get("usd")
        if u:
            by[p["country"]].append((u["min"] + u["max"]) / 2)
    return by


def _median_ci(v, n_boot=10000, seed=SEED):
    v = np.asarray(v, float)
    n = v.size
    rng = np.random.default_rng(seed)
    b = np.array([np.median(v[rng.integers(0, n, n)]) for _ in range(n_boot)])
    lo, hi = (float(x) for x in np.percentile(b, [2.5, 97.5]))
    return float(np.median(v)), lo, hi


def run():
    post, cls, dup = _load()
    rows = post["postings"]
    N = len(rows)

    removed = set()
    for g in dup["clusters"]:
        for i in sorted(g)[1:]:
            removed.add(i)
    keep = set(range(N)) - removed
    log(f"corpus {N} -> {len(keep)} after removing {len(removed)} near-duplicate rows")

    published = {r["country"]: r for r in post["pay_summary_by_country"]}
    base = _samples(rows)                                   # as published today
    deduped = _samples(rows, keep_idx=keep)                 # + de-duplicated
    clean = _samples(rows, keep_idx=keep, sw_only=True, cls=cls)  # + software only

    countries = sorted(set(published) | {c for c, v in clean.items() if len(v) >= 5})
    out = []
    for cc in countries:
        rec = {"country": cc,
               "published": published.get(cc, {}).get("median_usd_year"),
               "n_published_basis": len(base.get(cc, [])),
               "n_after_dedupe": len(deduped.get(cc, [])),
               "n_software_only": len(clean.get(cc, []))}
        v = clean.get(cc, [])
        if len(v) >= 5:
            m, lo, hi = _median_ci(v)
            rec.update({"software_median_usd_year": round(m, 2),
                        "ci_lo": round(lo), "ci_hi": round(hi),
                        "ci_half_width_pct": round(100 * (hi - lo) / 2 / m, 1)})
            if rec["published"]:
                rec["delta_vs_published_pct"] = round(100 * (m - rec["published"]) / rec["published"], 1)
        rec["publishable_at_min_n"] = bool(len(v) >= MIN_N_PUBLISH)
        out.append(rec)

    movers = [r for r in out if r.get("delta_vs_published_pct") is not None]
    log("  per-country delta of the software-only, de-duplicated median vs what is published:")
    for r in sorted(movers, key=lambda r: -abs(r["delta_vs_published_pct"])):
        log(f"    {r['country']:<4} published {r['published']:>10,.0f}  software-only "
            f"{r['software_median_usd_year']:>10,.0f}  delta {r['delta_vs_published_pct']:>+7.1f}%  "
            f"n {r['n_published_basis']:>4} -> {r['n_software_only']:<4} "
            f"{'PUBLISHABLE' if r['publishable_at_min_n'] else 'below min n'}")

    # ---- 5.4 selection bias against the site's own ICT-employment series
    #
    # The expected share of a pan-European panel is a country's share of
    # EUROPEAN ICT specialists, which needs an ABSOLUTE count. An earlier
    # revision normalised `ict_share_of_employment_pct` -- a WITHIN-country
    # percentage -- across countries, which asks "what fraction of the sum of
    # national percentages is this country's percentage?", a quantity with no
    # interpretation: it makes a small country with a high domestic ICT share
    # look as though it should supply as many postings as a large one with the
    # same share. `ict_specialists_thousands` is the correct basis and was
    # sitting unread in the same payload.
    ict = json.loads((PROCESSED / "eurostat_ict_specialists.json").read_text(encoding="utf-8"))["data"]["countries"]
    panel = Counter(p.get("country") for p in rows if p.get("country"))
    tot = sum(panel.values())
    bias = []
    for cc, rec in ict.items():
        abs_series = [x for x in ((rec or {}).get("ict_specialists_thousands") or [])
                      if isinstance(x, dict) and x.get("value") is not None]
        pct_series = [x for x in ((rec or {}).get("ict_share_of_employment_pct") or [])
                      if isinstance(x, dict) and x.get("value") is not None]
        if not abs_series:
            continue
        bias.append({"country": cc,
                     "panel_share_pct": round(100 * panel.get(cc, 0) / tot, 3),
                     "ict_specialists_thousands": abs_series[-1]["value"],
                     "ict_year": abs_series[-1].get("year"),
                     "ict_pct_of_employment": pct_series[-1]["value"] if pct_series else None,
                     "panel_postings": panel.get(cc, 0)})
    eu = [b for b in bias if b["panel_postings"] > 0]
    year_mismatch = sorted({b["ict_year"] for b in eu})
    if eu:
        ps = np.array([b["panel_share_pct"] for b in eu], float)
        rep = ps / ps.sum()
        iv = np.array([b["ict_specialists_thousands"] for b in eu], float)
        exp = iv / iv.sum()
        for b, r, e in zip(eu, rep, exp):
            b["expected_share_pct"] = round(100 * float(e), 3)
            b["representativeness"] = round(float(r / e), 3)
            # Eurostat dropped UK coverage after Brexit, so GB's most recent
            # observation is 2019 while every other country's is 2025. That is
            # a real comparability limit and it lands on the country with the
            # largest over-representation, so it is flagged per row rather
            # than buried in a footnote.
            if len(year_mismatch) > 1 and b["ict_year"] != max(year_mismatch):
                b["basis_year_is_stale"] = (
                    f"basis year {b['ict_year']} vs {max(year_mismatch)} for the rest of the panel; "
                    f"Eurostat stopped covering this country. The ratio mixes vintages and is "
                    f"indicative only.")
        worst = sorted(eu, key=lambda b: b["representativeness"])[:5]
        best = sorted(eu, key=lambda b: -b["representativeness"])[:5]
        log(f"  selection bias vs Eurostat ICT specialist HEADCOUNT, {len(eu)} countries:")
        log(f"    most OVER-represented: {[(b['country'], b['representativeness']) for b in best]}")
        log(f"    most UNDER-represented: {[(b['country'], b['representativeness']) for b in worst]}")
        if len(year_mismatch) > 1:
            log(f"    basis years are NOT aligned: {year_mismatch} "
                f"({[b['country'] for b in eu if b['ict_year'] != max(year_mismatch)]} are stale)")

    art = {
        "schema": "package-15 postings pay re-derivation v1",
        "min_n_to_publish": MIN_N_PUBLISH,
        "corpus": {"n_postings": N, "n_after_dedupe": len(keep), "n_removed": len(removed)},
        "pipeline": ["as published today (all occupations, duplicates included)",
                     "+ near-duplicate rows removed (threshold 0.98, precision 0.958)",
                     "+ restricted to titles the classifier ships as SW"],
        "per_country": out,
        "selection_bias_vs_eurostat_ict": {
            "basis": "share of European ICT specialist HEADCOUNT (ict_specialists_thousands), not "
                     "the within-country employment percentage, which does not normalise across "
                     "countries of different size",
            "representativeness": "panel share / expected share; 1.0 is proportional, >1 over-represented",
            "basis_years": year_mismatch,
            "basis_years_aligned": len(year_mismatch) == 1,
            "countries": sorted(eu, key=lambda b: -b["panel_share_pct"]),
        } if eu else {},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


def self_test():
    fails = []

    def ck(n, c, d=""):
        print(f"  {'PASS' if c else 'FAIL'}  {n}{('  [' + d + ']') if d else ''}")
        if not c:
            fails.append(n)

    print("=== rederive_postings_pay.py self-test ===")
    rows = [
        {"title": "Software Engineer", "country": "XX",
         "compensation": {"period": "year", "usd": {"min": 100000, "max": 100000}}},
        {"title": "Sales Associate", "country": "XX",
         "compensation": {"period": "year", "usd": {"min": 20000, "max": 20000}}},
        {"title": "Software Engineer", "country": "XX",
         "compensation": {"period": "year", "usd": {"min": 120000, "max": 120000}}},
    ]
    cls = {"Software Engineer": {"class": "SW"}, "Sales Associate": {"class": "SVC"}}
    allc = _samples(rows)
    swc = _samples(rows, keep_idx=set(range(3)), sw_only=True, cls=cls)
    ck("all-occupation sample includes the non-software row", len(allc["XX"]) == 3)
    ck("software-only sample excludes it", len(swc["XX"]) == 2, str(swc["XX"]))
    ck("restricting to software MOVES the median (the whole point of 5.3)",
       float(np.median(allc["XX"])) != float(np.median(swc["XX"])),
       f"all={np.median(allc['XX']):,.0f} sw={np.median(swc['XX']):,.0f}")
    ck("de-duplication drops the right row",
       len(_samples(rows, keep_idx={0, 1})["XX"]) == 2)
    m, lo, hi = _median_ci([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], n_boot=2000)
    ck("bootstrap CI brackets the median", lo <= m <= hi, f"{lo:.1f} <= {m:.1f} <= {hi:.1f}")

    print(f"\n{len(fails)} failure(s)" + (": " + ", ".join(fails) if fails else " — all controls hold"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    sys.exit(self_test() if a.self_test else run())
