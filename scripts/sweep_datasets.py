"""Package 16, Tier 4 — the package 15 battery applied to the 22 datasets it never reached.

Package 15 profiled 54 datasets but deeply analysed four: postings, the city
data, the wage spine and Teranet. Everything else got shape statistics and
nothing more. These 22 feed real site features and had never been asked whether
they support the claims made on them.

WHAT THIS RUNS, AND WHAT IT REFUSES TO RUN. The headline check is the
residual-autocorrelation test that found the Teranet defect. That test has a
stated precondition: the series must be a LEVEL sampled at a regular interval.
It is NOT valid for a rate, a growth figure, or anything already differenced --
those are differenced by construction and will look like injected noise whether
or not they are. Roughly half the numeric series here are rates
(`inflation_pct`, `unemployment_pct`, `real_gdp_growth_pct`), so running the
test across everything would have produced a page of confident false findings.
Each series is classified first, the classification is published per series, and
rates are reported as SKIPPED WITH A REASON rather than silently dropped -- an
omission nobody can see is indistinguishable from a check that passed.

The same discipline applies to n. The test needs 36 points; most of these are
annual series of 10-25. Those are skipped too, and counted.

    python scripts/sweep_datasets.py
    python scripts/sweep_datasets.py --self-test
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, log  # noqa: E402
from audit_statistical import injected_noise_test  # noqa: E402

OUT = ROOT / "data" / "quality_history" / "dataset_sweep.json"

DATASETS = [
    "climate_normals", "mipex", "un_wpp", "world_happiness_report", "rsf_press_freedom",
    "ef_epi", "wipo_gii", "numbeo_history", "eurostat_ict_specialists",
    "eurostat_total_employment", "un_migrant_stock", "indeed_hiring_lab_job_postings",
    "bls_oews", "oecd_indicators", "oecd_economic_outlook", "wikipedia_english_speakers",
    "levels_fyi", "world_bank", "fx_rates", "hours_worked", "experience_gradient",
    "city_coordinates",
]

# A series whose name says it is a rate, a change or a share is already
# differenced or bounded, and the persistence test does not apply to it.
_RATE = re.compile(r"(_pct|_rate|growth|change|inflation|unemploy|balance|net_lending|"
                   r"_share|share_of|yoy|per_year)", re.I)
# A count or a price or an index is a level.
_LEVEL = re.compile(r"(index|price|wage|salary|comp|gdp|population|employment|thousands|"
                    r"count|stock|usd|eur|total|specialists|hours)", re.I)

MIN_N_FOR_ACF = 36

# Teranet's month-over-month spread was 22-31%. A real published index sat at
# ~2%. Injected per-observation noise of the kind that test detects moves a
# series by that much between consecutive points; a series that moves 1% cannot
# be carrying it, whatever its autocorrelation says.
MOM_SD_PCT_CONSISTENT_WITH_INJECTED_NOISE = 8.0


def corroborate(flagged, family):
    """Is a low-autocorrelation reading a DEFECT, or is the test simply not
    valid for this kind of series?

    What made the Teranet finding trustworthy was not the threshold. It was the
    SEPARATION: six Teranet cities clustered at 0.11-0.27 while the two real
    published indices in the same repo sat at 0.985, with nothing between them.
    An absolute threshold alone has no such backing, and this sweep proved it --
    it flagged four of thirteen national annual hours-worked series, whose
    readings run 0.095 to 0.748 in one unbroken continuum with a median of
    0.485. There is no gap there. Those four are the low tail of a distribution,
    not a defective subgroup, and annual hours worked genuinely moves year to
    year (recessions, holiday reform, part-time share), so the test's own stated
    precondition -- a path smooth relative to the sampling interval -- does not
    hold for it at all.

    A flag is therefore corroborated only when the series is an OUTLIER against
    its own peers AND its point-to-point movement is large enough for injected
    noise to be a plausible explanation."""
    peers = [f["residual_acf_lag1"] for f in family]
    med = float(np.median(peers)) if peers else None
    separated = bool(med is not None and len(peers) >= 3
                     and flagged["residual_acf_lag1"] < med - 0.30)
    big_moves = flagged.get("mom_sd_pct", 0) >= MOM_SD_PCT_CONSISTENT_WITH_INJECTED_NOISE
    return {
        "peer_family_n": len(peers),
        "peer_median_residual_acf": round(med, 3) if med is not None else None,
        "peer_min": round(float(np.min(peers)), 3) if peers else None,
        "peer_max": round(float(np.max(peers)), 3) if peers else None,
        "is_outlier_against_peers": separated,
        "movement_large_enough_for_injected_noise": bool(big_moves),
        "corroborated": bool(separated and big_moves),
        "why": ("outlier against its own peer family AND moves enough per point for injected "
                "noise to explain it" if separated and big_moves else
                "the whole peer family reads low, so this is the tail of one distribution rather "
                "than a defective subgroup — the test's precondition (a path smooth relative to "
                "the sampling interval) most likely does not hold for this kind of series"
                if not separated else
                "an outlier, but its point-to-point movement is far too small for injected noise "
                "of the kind this test detects"),
    }


def spine_countries() -> set[str]:
    return {c["country"] for c in json.loads((ROOT / "data" / "cities.json")
                                             .read_text(encoding="utf-8"))["records"]}


def spine_cities() -> set[str]:
    return {c["id"] for c in json.loads((ROOT / "data" / "cities.json")
                                        .read_text(encoding="utf-8"))["records"]}


def classify_series(path: str) -> str:
    """level | rate | ambiguous — published per series so the choice is auditable.

    Matches the WHOLE path, not just its last segment. An earlier version looked
    only at the tail, so `NO/inflation_pct/value` classified on "value" and was
    tested as a level -- and duly flagged, because an inflation rate is
    differenced by construction and cannot pass a persistence test. The check
    fired, the finding was spurious, and the cause was the classifier rather than
    the data.
    """
    if _RATE.search(path):
        return "rate"
    if _LEVEL.search(path):
        return "level"
    return "ambiguous"


def find_series(node, path="", out=None):
    """Every (path, [(x, value)]) time series in a payload, however nested.

    A series is a list of dicts each carrying one time key (year/date/period)
    and one numeric value, OR a dict mapping a year-like key to a number.
    """
    if out is None:
        out = []
    if isinstance(node, dict):
        yearish = [k for k in node if re.fullmatch(r"(19|20)\d\d", str(k))]
        if len(yearish) >= 4 and all(isinstance(node[k], (int, float, type(None))) for k in yearish):
            pts = [(int(k), float(node[k])) for k in sorted(yearish) if node[k] is not None]
            if len(pts) >= 4:
                out.append((path, pts))
        for k, v in node.items():
            find_series(v, f"{path}/{k}" if path else str(k), out)
    elif isinstance(node, list) and node and isinstance(node[0], dict):
        tk = next((k for k in ("year", "date", "period", "y") if k in node[0]), None)
        vks = [k for k, v in node[0].items()
               if k != tk and isinstance(v, (int, float)) and not isinstance(v, bool)]
        if tk:
            for vk in vks:
                pts = []
                for r in node:
                    if not isinstance(r, dict) or r.get(vk) is None or r.get(tk) is None:
                        continue
                    m = re.match(r"(\d{4})", str(r[tk]))
                    if m:
                        pts.append((int(m.group(1)) * 12 + (int(str(r[tk])[5:7]) if len(str(r[tk])) >= 7
                                                            and str(r[tk])[5:7].isdigit() else 0),
                                    float(r[vk])))
                if len(pts) >= 4:
                    out.append((f"{path}/{vk}" if path else vk, sorted(pts)))
        for i, v in enumerate(node):
            find_series(v, path, out)
    return out


def numeric_leaves(node, path="", out=None):
    if out is None:
        out = []
    if isinstance(node, dict):
        for k, v in node.items():
            numeric_leaves(v, f"{path}/{k}" if path else str(k), out)
    elif isinstance(node, list):
        for v in node:
            numeric_leaves(v, path, out)
    elif isinstance(node, (int, float)) and not isinstance(node, bool) and math.isfinite(node):
        out.append((path, float(node)))
    return out


def sweep_one(sid: str, doc: dict, controls: dict) -> dict:
    data = doc.get("data", doc)
    rec: dict = {"source_id": sid, "generated_at": doc.get("generated_at")}

    # ---- vintage / staleness
    all_series = find_series(data)
    years = [x for _, pts in all_series for x, _ in pts]
    latest = max((y // 12 if y > 3000 else y) for y in years) if years else None
    rec["vintage"] = {
        "latest_period_in_data": latest,
        "generated_at": (doc.get("generated_at") or "")[:10],
        "years_behind_generation": ((int((doc.get("generated_at") or "2026")[:4]) - latest)
                                    if latest else None),
    }

    # ---- coverage against the site's own scope
    keys = set(data) if isinstance(data, dict) else set()
    sc, sci = spine_countries(), spine_cities()
    by_country = keys & sc
    by_city = keys & sci
    if by_country:
        rec["coverage"] = {"keyed_by": "country", "present": len(by_country),
                           "of_spine": len(sc),
                           "missing": sorted(sc - by_country)}
    elif by_city:
        rec["coverage"] = {"keyed_by": "city", "present": len(by_city), "of_spine": len(sci),
                           "missing": sorted(sci - by_city)[:20],
                           "n_missing": len(sci - by_city)}
    else:
        nested = set()
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, dict):
                    nested |= set(v)
        rec["coverage"] = {"keyed_by": "other/nested",
                           "spine_countries_found_one_level_down": len(nested & sc),
                           "spine_cities_found_one_level_down": len(nested & sci)}

    # ---- the persistence test, on series it is VALID for
    tested, skipped = [], Counter()
    skipped_examples: dict[str, str] = {}
    for path, pts in all_series:
        kind = classify_series(path)
        vals = [v for _, v in pts]
        if kind == "rate":
            skipped["already a rate or a change — the test does not apply"] += 1
            skipped_examples.setdefault("already a rate or a change — the test does not apply", path)
            continue
        if len(vals) < MIN_N_FOR_ACF:
            skipped[f"fewer than {MIN_N_FOR_ACF} points"] += 1
            skipped_examples.setdefault(f"fewer than {MIN_N_FOR_ACF} points", path)
            continue
        r = injected_noise_test(vals, path)
        if r:
            r["series_kind"] = kind
            tested.append(r)
    # Group tested series into FAMILIES -- the same measured quantity across
    # countries or cities -- so a flag can be judged against its own peers
    # instead of against an absolute threshold alone.
    families: dict[str, list] = {}
    for r in tested:
        fam = "/".join(p for p in r["label"].split("/")[1:] if p) or r["label"]
        families.setdefault(fam, []).append(r)
    for r in tested:
        if r.get("looks_like_injected_noise"):
            fam = "/".join(p for p in r["label"].split("/")[1:] if p) or r["label"]
            r["corroboration"] = corroborate(r, families.get(fam, []))

    rec["persistence_test"] = {
        "n_series_found": len(all_series),
        "n_tested": len(tested),
        "n_skipped": sum(skipped.values()),
        "skipped_reasons": {k: {"count": v, "example": skipped_examples.get(k)}
                            for k, v in skipped.items()},
        "flagged_by_threshold": [t for t in tested if t.get("looks_like_injected_noise")],
        "flagged": [t for t in tested if t.get("looks_like_injected_noise")
                    and (t.get("corroboration") or {}).get("corroborated")],
        "uncorroborated_flags": [
            {"label": t["label"], "residual_acf_lag1": t["residual_acf_lag1"],
             "mom_sd_pct": t.get("mom_sd_pct"), "corroboration": t.get("corroboration")}
            for t in tested if t.get("looks_like_injected_noise")
            and not (t.get("corroboration") or {}).get("corroborated")],
        "controls": controls,
        "all_results": tested,
    }

    # ---- distributional shape of every numeric leaf, one line
    leaves = numeric_leaves(data)
    if leaves:
        v = np.array([x for _, x in leaves], float)
        rec["numeric_leaves"] = {
            "n": int(v.size),
            "n_negative": int((v < 0).sum()),
            "n_zero": int((v == 0).sum()),
            "min": float(v.min()), "max": float(v.max()),
        }
    return rec


IDENTITIES = {
    "eurostat_ict_specialists": "ict_specialists_thousands / total employment should ≈ "
                                "ict_share_of_employment_pct — checked against "
                                "eurostat_total_employment",
    "un_wpp": "total_population / land area should ≈ population_density",
    "world_bank": "gdp_per_capita_usd and gdp_per_capita_ppp_intl must agree in rank order for "
                  "countries with similar price levels",
}


def check_identities() -> dict:
    """Accounting identities that must hold BETWEEN two committed datasets. A
    dataset can be internally tidy and still contradict its neighbour."""
    out = {}
    try:
        ict = json.loads((PROCESSED / "eurostat_ict_specialists.json")
                         .read_text(encoding="utf-8"))["data"]["countries"]
        emp = json.loads((PROCESSED / "eurostat_total_employment.json")
                         .read_text(encoding="utf-8"))["data"]
        rows = []
        for cc, rec in ict.items():
            spec = {x["year"]: x["value"] for x in (rec.get("ict_specialists_thousands") or [])
                    if x.get("value") is not None}
            share = {x["year"]: x["value"] for x in (rec.get("ict_share_of_employment_pct") or [])
                     if x.get("value") is not None}
            tot = {x["year"]: x["value"]
                   for x in ((emp.get(cc) or {}).get("total_employment_thousands") or [])
                   if x.get("value") is not None}
            for y in sorted(set(spec) & set(share) & set(tot)):
                if tot[y]:
                    implied = 100 * spec[y] / tot[y]
                    rows.append({"country": cc, "year": y,
                                 "published_share_pct": share[y],
                                 "implied_share_pct": round(implied, 3),
                                 "abs_diff_pp": round(abs(implied - share[y]), 3)})
        if rows:
            d = [r["abs_diff_pp"] for r in rows]
            worst = max(rows, key=lambda r: r["abs_diff_pp"])
            out["eurostat_ict_share_identity"] = {
                "n_country_years": len(rows),
                "median_abs_diff_pp": round(float(np.median(d)), 3),
                "max_abs_diff_pp": round(float(np.max(d)), 3),
                "worst": worst,
                "reading": ("ICT specialists divided by total employment should reproduce the "
                            "published ICT share. Both come from Eurostat but from different "
                            "tables, so a large gap would mean the two are not the denominators "
                            "they appear to be — which matters, because package 15 already "
                            "corrected a selection-bias figure for using the wrong one."),
                "verdict": ("consistent" if float(np.median(d)) < 0.5 else
                            "INCONSISTENT — the two tables do not share a denominator"),
            }
    except (OSError, KeyError, json.JSONDecodeError) as e:
        out["eurostat_ict_share_identity"] = {"error": str(e)}
    return out


def run() -> int:
    log("sweeping the 22 datasets package 15 profiled but never analysed")

    # Controls for the persistence test: two real published indices, so a
    # "clean" result on any dataset below is read against a series KNOWN to
    # pass and one KNOWN to fail.
    controls = {}
    try:
        uk = json.loads((PROCESSED / "uk_hpi.json").read_text(encoding="utf-8"))["data"]
        ser = uk["london"]["series"] if "london" in uk else list(uk.values())[0]["series"]
        vals = [r.get("avg_price_gbp") or r.get("index") for r in ser]
        controls["CONTROL real published index (UK HPI London)"] = injected_noise_test(
            [v for v in vals if v], "uk_hpi/london")
    except (OSError, KeyError, IndexError, json.JSONDecodeError):
        pass
    try:
        ter = json.loads((PROCESSED / "teranet_national_bank_hpi.json")
                         .read_text(encoding="utf-8"))["data"]["cities"]
        controls["CONTROL known-defective index (Teranet Toronto)"] = injected_noise_test(
            [r["index"] for r in ter["toronto"]["series"]], "teranet/toronto")
    except (OSError, KeyError, json.JSONDecodeError):
        pass

    results, missing = {}, []
    for sid in DATASETS:
        p = PROCESSED / f"{sid}.json"
        if not p.exists():
            missing.append(sid)
            log(f"  MISSING {sid}")
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        rec = sweep_one(sid, doc, controls)
        results[sid] = rec
        pt = rec["persistence_test"]
        flag = f"  {len(pt['flagged'])} FLAGGED" if pt["flagged"] else ""
        log(f"  {sid:<32} series {pt['n_series_found']:>4}  tested {pt['n_tested']:>3}  "
            f"skipped {pt['n_skipped']:>4}{flag}")

    art = {
        "schema": "package-16 dataset sweep v1",
        "datasets_requested": len(DATASETS),
        "datasets_swept": len(results),
        "datasets_missing": missing,
        "persistence_test_preconditions": (
            "the residual-autocorrelation test is valid only for a LEVEL series sampled at a "
            "regular interval, with at least 36 points. Rates, growth figures and shares are "
            "already differenced or bounded and are SKIPPED WITH A REASON, not silently dropped: "
            "running the test on them would have produced confident false findings across roughly "
            "half the numeric series here."),
        "controls": controls,
        "cross_dataset_identities": check_identities(),
        "by_dataset": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"  wrote {OUT.relative_to(ROOT)}")

    unc = sum(len(v["persistence_test"]["uncorroborated_flags"]) for v in results.values())
    if unc:
        log(f"  {unc} series crossed the threshold but were NOT corroborated against their own "
            f"peer family — reported, not claimed")
        for k, v in results.items():
            for u in v["persistence_test"]["uncorroborated_flags"]:
                c = u["corroboration"]
                log(f"    {k}/{u['label']}: ACF {u['residual_acf_lag1']:+.3f} vs peer median "
                    f"{c['peer_median_residual_acf']:+.3f} (range {c['peer_min']:+.3f}.."
                    f"{c['peer_max']:+.3f}), MoM sd {u['mom_sd_pct']:.2f}%")
    flagged = {k: v["persistence_test"]["flagged"] for k, v in results.items()
               if v["persistence_test"]["flagged"]}
    if flagged:
        log("  SERIES FLAGGED AS CARRYING INJECTED NOISE:")
        for k, v in flagged.items():
            for f in v:
                log(f"    {k}/{f['label']}: residual ACF {f['residual_acf_lag1']:+.3f}, "
                    f"MoM ACF {f['mom_acf_lag1']:+.3f}")
    else:
        log("  no second Teranet: no series outside Teranet itself trips the persistence test")
    return 0


def self_test() -> int:
    fails = []

    def ck(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  [' + detail + ']') if detail else ''}")
        if not cond:
            fails.append(name)

    print("=== sweep_datasets.py self-test ===")

    ck("a rate is classified as a rate", classify_series("US/inflation_pct") == "rate")
    ck("a rate is still a rate when the VALUE key is the last path segment",
       classify_series("NO/inflation_pct/value") == "rate",
       "the tail is 'value'; the rate word is mid-path")
    ck("a growth series is classified as a rate",
       classify_series("GB/real_gdp_growth_pct") == "rate")
    ck("a price index is classified as a level", classify_series("london/house_prices") == "level")
    ck("a share is NOT treated as a level",
       classify_series("DE/ict_share_of_employment_pct") == "rate")

    # the persistence test must FIRE on constructed noise and PASS on a real walk
    rng = np.random.default_rng(16)
    smooth = list(100 * np.exp(np.cumsum(rng.normal(0.003, 0.004, 240))))
    noisy = [v * float(np.exp(rng.normal(0, 0.18))) for v in smooth]
    r_ok = injected_noise_test(smooth, "smooth")
    r_bad = injected_noise_test(noisy, "noisy")
    ck("persistence test PASSES a smooth random walk", not r_ok["looks_like_injected_noise"],
       f"resid ACF {r_ok['residual_acf_lag1']:+.3f}")
    ck("persistence test FIRES on the same walk with per-point noise added",
       r_bad["looks_like_injected_noise"], f"resid ACF {r_bad['residual_acf_lag1']:+.3f}")

    ck("a series shorter than the minimum is refused rather than guessed at",
       injected_noise_test(list(range(10)), "short") is None)

    # corroboration: the Teranet shape must survive, the hours-worked shape must not
    teranet_like = {"residual_acf_lag1": 0.24, "mom_sd_pct": 24.6}
    teranet_family = [{"residual_acf_lag1": v} for v in (0.985, 0.985, 0.24)]
    ck("CORROBORATES a Teranet-shaped flag (outlier vs peers, huge point-to-point moves)",
       corroborate(teranet_like, teranet_family)["corroborated"])
    hours_like = {"residual_acf_lag1": 0.095, "mom_sd_pct": 2.67}
    hours_family = [{"residual_acf_lag1": v} for v in
                    (0.413, 0.327, 0.285, 0.512, 0.270, 0.583, 0.095, 0.663, 0.184, 0.485,
                     0.607, 0.748, 0.677)]
    ck("REFUSES to corroborate an hours-worked-shaped flag (tail of one continuum)",
       not corroborate(hours_like, hours_family)["corroborated"],
       corroborate(hours_like, hours_family)["why"][:60])
    ck("refuses a peer outlier whose movement is far too small for injected noise",
       not corroborate({"residual_acf_lag1": 0.05, "mom_sd_pct": 0.4},
                       [{"residual_acf_lag1": v} for v in (0.9, 0.9, 0.9)])["corroborated"])

    # series discovery
    doc = {"US": {"gdp": [{"year": 2000 + i, "value": 1.0 * i} for i in range(12)]},
           "GB": {"pop": {str(2000 + i): float(i) for i in range(8)}}}
    found = dict(find_series(doc))
    ck("finds a list-of-records series", any("gdp" in k for k in found), str(list(found))[:70])
    ck("finds a year-keyed dict series", any("pop" in k for k in found))
    ck("a series with too few points is not reported",
       not find_series({"X": {"v": [{"year": 2000, "value": 1}]}}))

    print(f"\n{len(fails)} failure(s)" + (" — all controls hold" if not fails else f": {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    raise SystemExit(self_test() if a.self_test else run())
