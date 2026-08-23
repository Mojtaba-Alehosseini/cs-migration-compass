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
    # Package 16 — the three house-price indices are swept too, though the work
    # order's list does not name them. Two are the controls this sweep judges
    # everything else against, and the third is the known defect. Running the
    # pipeline over all three means the control readings and the confirmed
    # finding are PRODUCED by the code rather than asserted beside it, so the
    # claim "no second Teranet" is checked by a run that demonstrably still
    # finds the first one.
    "uk_hpi", "fhfa_hpi_metro", "teranet_national_bank_hpi",
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


# A real published index reads ~0.985 on this test. Anything this far below a
# known-good control of the same kind is behaving differently from a series we
# KNOW is sound -- which is the comparison that made the original Teranet
# finding trustworthy, and the one this rule got wrong on its first attempt.
ACF_GAP_FROM_GOOD_CONTROL = 0.30


def corroborate(flagged, family, good_control_acf=None):
    """Is a low-autocorrelation reading a DEFECT, or is the test simply not
    valid for this kind of series?

    THIS RULE WAS WRONG THE FIRST TIME AND THE ERROR IS WORTH RECORDING,
    because it is the exact failure the work order asked the reviewer to hunt
    for: a check too weak to fail, dressed as rigour.

    The first version required a flagged series to be an OUTLIER AGAINST ITS
    OWN PEER FAMILY. Fed the six Teranet cities package 15 actually measured,
    it confirmed ZERO of them. A whole-family defect -- one bad extractor
    corrupting every series it produces -- has no outlier by construction: the
    peer median is dragged down with the defect, so `flagged < median - gap`
    can never fire. That is precisely Teranet's shape, so "no second Teranet"
    was being asserted by a rule that could not have found the first one.

    What actually made the original finding trustworthy was never the peer
    spread. It was the SEPARATION FROM A KNOWN-GOOD CONTROL: Teranet at
    0.11-0.27 against UK HPI and FHFA at 0.985, two real published indices in
    the same repo. So that is the test now. The peer family is still computed
    and reported, because a whole family reading low is INFORMATIVE -- it
    points at a shared extractor rather than one bad series -- but it can no
    longer veto a finding.

    The movement threshold stays, and it is what correctly rejects the annual
    hours-worked readings: they sit far below the control too, but they move
    0.5-2.7% point to point where injected noise of this kind moves 22-31%.
    Being unlike a price index is not the same as being corrupted, and annual
    hours worked is genuinely unlike one."""
    peers = [f["residual_acf_lag1"] for f in family]
    med = float(np.median(peers)) if peers else None
    acf = flagged["residual_acf_lag1"]
    separated = bool(good_control_acf is not None
                     and acf < good_control_acf - ACF_GAP_FROM_GOOD_CONTROL)
    big_moves = flagged.get("mom_sd_pct", 0) >= MOM_SD_PCT_CONSISTENT_WITH_INJECTED_NOISE
    family_low = bool(med is not None and good_control_acf is not None
                      and med < good_control_acf - ACF_GAP_FROM_GOOD_CONTROL)
    return {
        "good_control_residual_acf": (round(good_control_acf, 3)
                                      if good_control_acf is not None else None),
        "separated_from_known_good_control": separated,
        "movement_large_enough_for_injected_noise": bool(big_moves),
        "peer_family_n": len(peers),
        "peer_median_residual_acf": round(med, 3) if med is not None else None,
        "peer_min": round(float(np.min(peers)), 3) if peers else None,
        "peer_max": round(float(np.max(peers)), 3) if peers else None,
        "whole_peer_family_also_low": family_low,
        "corroborated": bool(separated and big_moves),
        "why": (
            "cannot judge: no known-good control series was available to compare against"
            if good_control_acf is None else
            ("behaves unlike a known-good index of the same kind AND moves enough per point "
             "for injected noise to explain it"
             + (" -- and its whole peer family reads low too, which points at a shared "
                "extractor rather than one bad series" if family_low else ""))
            if separated and big_moves else
            "behaves unlike a known-good index, but its point-to-point movement is far too small "
            "for injected noise of the kind this test detects -- more likely the test's "
            "precondition (a path smooth relative to the sampling interval) does not hold for "
            "this kind of series at all"
            if separated else
            "sits close to a known-good index of the same kind"),
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
        # "month" was missing, and it cost the most valuable 30 series in the
        # sweep: indeed_hiring_lab_job_postings keys its records by `month` and
        # holds 30 metro index series of 78 points each -- monthly index levels,
        # precisely the shape the persistence test is built for and the same
        # shape as Teranet. They were reported as "0 series found", which reads
        # as "nothing here to test" rather than "this reader cannot see it".
        tk = next((k for k in ("year", "date", "period", "month", "y") if k in node[0]), None)
        # A numeric field is not automatically a measurement. FHFA records read
        # {year, quarter, index}: treating `quarter` as a value builds the
        # series 4,1,2,3,4,1,2,3... which of course fails a persistence test,
        # and produced 15 confident false flags against the very index this
        # sweep uses as a KNOWN-GOOD control. Time components and record
        # bookkeeping are excluded from the value side; they are coordinates,
        # not observations.
        _NOT_A_MEASUREMENT = {"year", "quarter", "month", "week", "day", "days",
                              "period", "y", "n", "count", "rank"}
        vks = [k for k, v in node[0].items()
               if k != tk and k.lower() not in _NOT_A_MEASUREMENT
               and isinstance(v, (int, float)) and not isinstance(v, bool)]
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
    # Group by the measured QUANTITY, not by position. An earlier version
    # dropped exactly one leading path segment on the assumption that segment 0
    # is the entity -- true for `US/hours_worked/...`, false for Teranet's
    # `cities/<city>/series/index`, where segment 0 is the constant "cities" and
    # every city therefore became a family of one. A singleton family made the
    # peer comparison arithmetically incapable of firing. Dropping the segment
    # that VARIES across series leaves the quantity, whatever its depth.
    def _family_key(label):
        return "/".join(p for i, p in enumerate(label.split("/")) if p and i != _varying[0])

    parts = [r["label"].split("/") for r in tested]
    depth = min((len(p) for p in parts), default=0)
    _varying = [0]
    best = -1
    for i in range(depth):
        k = len({p[i] for p in parts})
        if k > best:
            best, _varying[0] = k, i
    families: dict[str, list] = {}
    for r in tested:
        families.setdefault(_family_key(r["label"]), []).append(r)
    good = (controls.get("CONTROL real published index (UK HPI London)") or {})
    good_acf = good.get("residual_acf_lag1")
    for r in tested:
        if r.get("looks_like_injected_noise"):
            r["corroboration"] = corroborate(r, families.get(_family_key(r["label"]), []),
                                             good_control_acf=good_acf)

    rec["persistence_test"] = {
        "no_time_series_present": len(all_series) == 0,
        "no_time_series_reason": ("this dataset holds point-in-time values or per-category "
                                  "records, not a series over time, so the persistence test has "
                                  "nothing to apply to. Reported explicitly: a silent zero is "
                                  "indistinguishable from a check that passed."
                                  if len(all_series) == 0 else None),
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

    # THE control that matters: the rule must confirm the defect it exists to
    # find. These are the six Teranet cities package 15 actually measured,
    # against the real UK HPI control reading. The first version of this rule,
    # which required a flag to be an outlier against its own peer family,
    # confirmed ZERO of them -- so this control is built from real measured
    # values rather than a convenient hand-picked family.
    UK_HPI_GOOD = 0.9849
    TERANET = [("toronto", 0.2372, 24.649), ("vancouver", 0.2679, 29.115),
               ("montreal", 0.1771, 30.588), ("ottawa", 0.1131, 25.538),
               ("calgary", 0.2354, 22.048), ("halifax", 0.1686, 31.322)]
    ter_family = [{"residual_acf_lag1": a} for _, a, _ in TERANET]

    def _corr(a, m, fam):
        return corroborate({"residual_acf_lag1": a, "mom_sd_pct": m}, fam,
                           good_control_acf=UK_HPI_GOOD)

    confirmed = sum(_corr(a, m, ter_family)["corroborated"] for _, a, m in TERANET)
    ck("CONFIRMS all six real Teranet cities -- the defect this rule exists to find",
       confirmed == 6, f"{confirmed}/6")
    ck("...and confirms one as a SINGLETON family, with no peers to compare against",
       _corr(0.2372, 24.649, [{"residual_acf_lag1": 0.2372}])["corroborated"],
       "a whole-family defect has no outlier by construction")
    ck("reports a whole low-reading family as a corroborating signal, never a veto",
       _corr(0.2372, 24.649, ter_family)["whole_peer_family_also_low"])

    HOURS = [("GB", 0.095, 2.67), ("DE", 0.285, 1.11), ("IT", 0.184, 2.45), ("ES", 0.270, 1.50)]
    hours_family = [{"residual_acf_lag1": v} for v in
                    (0.413, 0.327, 0.285, 0.512, 0.270, 0.583, 0.095, 0.663, 0.184, 0.485,
                     0.607, 0.748, 0.677)]
    ck("REJECTS all four annual hours-worked readings",
       sum(not _corr(a, m, hours_family)["corroborated"] for _, a, m in HOURS) == 4)
    ck("...and rejects them on MOVEMENT, not on peer separation",
       all(_corr(a, m, hours_family)["separated_from_known_good_control"]
           and not _corr(a, m, hours_family)["movement_large_enough_for_injected_noise"]
           for _, a, m in HOURS),
       "all four ARE far from the control; none moves enough to be injected noise")
    ck("a series close to the known-good control is not corroborated",
       not _corr(0.97, 25.0, ter_family)["corroborated"])
    ck("with no control available it refuses to judge rather than guessing",
       corroborate({"residual_acf_lag1": 0.1, "mom_sd_pct": 30.0}, ter_family,
                   good_control_acf=None)["corroborated"] is False)

    # series discovery
    doc = {"US": {"gdp": [{"year": 2000 + i, "value": 1.0 * i} for i in range(12)]},
           "GB": {"pop": {str(2000 + i): float(i) for i in range(8)}}}
    found = dict(find_series(doc))
    ck("finds a list-of-records series", any("gdp" in k for k in found), str(list(found))[:70])
    ck("finds a year-keyed dict series", any("pop" in k for k in found))
    ck("a series with too few points is not reported",
       not find_series({"X": {"v": [{"year": 2000, "value": 1}]}}))
    fhfa_like = {"seattle": {"series": [{"year": 1975 + i // 4, "quarter": i % 4 + 1,
                                        "index": 20.0 + i} for i in range(80)]}}
    found2 = dict(find_series(fhfa_like))
    ck("a time COMPONENT is not mistaken for a measurement",
       not any(k.endswith("quarter") for k in found2) and any(k.endswith("index") for k in found2),
       f"extracted {sorted(found2)}")
    monthly = {"atlanta": {"series": [{"month": f"2020-{m:02d}", "index": 100.0 + m, "days": 30}
                                      for m in range(1, 13)]}}
    found3 = dict(find_series(monthly))
    ck("a month-keyed series is discovered at all",
       any(k.endswith("index") for k in found3), f"extracted {sorted(found3)}")

    print(f"\n{len(fails)} failure(s)" + (" — all controls hold" if not fails else f": {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    raise SystemExit(self_test() if a.self_test else run())
