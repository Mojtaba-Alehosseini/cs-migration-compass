"""Package 15, Tier 1 — a reproducible statistical profiling harness.

Walks every dataset in data/processed/ plus site/public/data/core.json and
emits, per numeric field: distributional moments, shape tests (Shapiro-Wilk
on raw AND on log, Anderson-Darling), tail behaviour (Hill estimator),
three DIFFERENT univariate outlier rules and where they disagree, and
terminal-digit heaping with an inferred rounding granularity. Categorical
fields get cardinality, mode share and a rare-level census.

WHY THIS EXISTS, and why it is not `audit_data.py` with more checks:
audit_data.py asserts invariants -- it answers "is this value legal?".
This answers a different question: "what SHAPE is this data, and is the
summary statistic the site publishes on it the right one?". A file can
pass every invariant in the repo and still be summarised with a mean when
it is log-normal with skew 6.4. That is not an invariant violation; it is
a fitness-for-purpose failure, and it needs distributional evidence rather
than a threshold.

DESIGN NOTE -- why a generic walker rather than per-dataset code: the 53
processed datasets use at least three unrelated shapes (per-country dicts,
[{year,value}] series, flat record lists). Hand-writing an extractor per
dataset guarantees the next dataset is silently unprofiled. This flattens
every JSON to (path, leaf) pairs and collapses array indices, so a field
is found wherever it lives and a NEW dataset is profiled the day it lands
with no code change. The cost is that some collapsed paths mix populations;
MIN_N and the identifier exclusions below carry that weight, and every
excluded path is recorded in the artifact rather than silently dropped.

    python scripts/profile_data.py                 # write the artifact + print summary
    python scripts/profile_data.py --self-test     # gate 14: every rule fires on a violation
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, log  # noqa: E402

OUT_JSON = ROOT / "data" / "quality_history" / "profile.json"
CORE = ROOT / "site" / "public" / "data" / "core.json"

# A field needs enough points for a distributional claim to mean anything.
# Shapiro-Wilk is undefined below 3 and useless below ~8; skew and kurtosis
# are wildly unstable on tiny n. 12 is this harness's own floor, stated here
# rather than buried, because "not profiled" must never read as "clean".
MIN_N = 12

# Paths that are identifiers, coordinates or calendar positions rather than
# measurements. Profiling a latitude's skew is noise; profiling a year's
# "outliers" flags the oldest observation in every series. Excluded BY NAME
# and recorded in the artifact's own excluded_paths, never dropped quietly.
_NOT_A_MEASUREMENT = re.compile(
    r"^(id|ids|lat|lon|latitude|longitude|year|years_requested|period|month|"
    r"rank|index_rank|position|code|iso|iso2|iso3|fips|zip|postcode)$", re.I)


def _leaves(obj, path="", out=None):
    """Flatten to (collapsed_path, values). Array indices collapse to [] so
    every element of a series lands in one bucket."""
    if out is None:
        out = defaultdict(list)
    if isinstance(obj, dict):
        for k, v in obj.items():
            _leaves(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(obj, list):
        for item in obj:
            _leaves(item, f"{path}[]", out)
    else:
        out[path].append(obj)
    return out


def _hill(x, k=None):
    """Hill tail-index estimator: the fitted Pareto alpha of the right tail,
    or None when the tail is too short to estimate. alpha < 2 means infinite
    variance -- the sample sd is then not estimating anything, which is
    exactly the kind of thing an arithmetic mean hides."""
    x = np.asarray([v for v in x if v > 0], float)
    if x.size < 20:
        return None
    x = np.sort(x)[::-1]
    k = k or max(5, min(x.size // 5, 50))
    if k >= x.size:
        return None
    denom = float(np.mean(np.log(x[:k])) - math.log(x[k]))
    return round(1.0 / denom, 4) if denom > 0 else None


def _granularity(vals):
    """The effective rounding step of a numeric field, inferred rather than
    assumed: the largest step at least 90% of values are multiples of. This
    is what makes "published to the dollar" checkable instead of a matter
    of taste."""
    ints = [int(v) for v in vals if float(v) == int(float(v))]
    if len(ints) < MIN_N:
        return None
    for step in (100_000, 50_000, 25_000, 10_000, 5_000, 1_000, 500, 100, 50, 10, 5, 1):
        if sum(1 for v in ints if v % step == 0) / len(ints) >= 0.90:
            return step
    return None


def _digit_heaping(vals):
    """Terminal-digit distribution against uniform. Heaping stops being a
    judgement call once this chi-square rejects: employer-entered pay is a
    negotiating anchor rounded to a round number, and that is visible in
    the last digit."""
    ints = [int(v) for v in vals if float(v) == int(float(v)) and v != 0]
    if len(ints) < MIN_N:
        return None
    n = len(ints)
    last = Counter(abs(v) % 10 for v in ints)
    obs = np.array([last.get(d, 0) for d in range(10)], float)
    try:
        chi2, p = stats.chisquare(obs)
    except Exception:
        chi2, p = float("nan"), float("nan")
    return {
        "n": n,
        "ends_in_0_or_5_pct": round(100 * sum(1 for v in ints if v % 5 == 0) / n, 2),
        "ends_in_00_pct": round(100 * sum(1 for v in ints if v % 100 == 0) / n, 2),
        "ends_in_000_pct": round(100 * sum(1 for v in ints if v % 1000 == 0) / n, 2),
        "terminal_digit_chi2": round(float(chi2), 2) if chi2 == chi2 else None,
        "terminal_digit_p": float(f"{p:.3e}") if p == p else None,
        "uniform_terminal_digits_rejected": bool(p == p and p < 0.01),
    }


def _outliers(a):
    """Three rules, deliberately NOT reconciled into one verdict.

    The IQR fence assumes rough symmetry; robust-z (MAD) assumes a symmetric
    unimodal core; the log-space fence is the only one of the three that is
    honest about a right-skewed positive field. Where they disagree, the
    disagreement IS the finding: it means the field's shape breaks at least
    one rule's assumptions, and any single-rule outlier list on that field
    is reporting a property of the rule rather than of the data.
    """
    a = np.asarray(a, float)
    q1, q3 = np.percentile(a, [25, 75])
    iqr = q3 - q1
    iqr_out = set(np.where((a < q1 - 1.5 * iqr) | (a > q3 + 1.5 * iqr))[0].tolist())

    med = float(np.median(a))
    mad = float(np.median(np.abs(a - med)))
    rz_out = set(np.where(np.abs(0.6745 * (a - med) / mad) > 3.5)[0].tolist()) if mad > 0 else set()

    if (a > 0).all() and stats.skew(a) > 0.5:
        la = np.log(a)
        lq1, lq3 = np.percentile(la, [25, 75])
        liqr = lq3 - lq1
        sk_out = set(np.where((la < lq1 - 1.5 * liqr) | (la > lq3 + 1.5 * liqr))[0].tolist())
    else:
        sk_out = set(iqr_out)

    methods = [iqr_out, rz_out, sk_out]
    consensus = set.intersection(*methods)
    any_ = set.union(*methods)
    return {
        "iqr_fence_n": len(iqr_out),
        "robust_z_mad_n": len(rz_out),
        "skew_adjusted_log_fence_n": len(sk_out),
        "flagged_by_all_three_n": len(consensus),
        "flagged_by_any_n": len(any_),
        "methods_disagree": len(any_) != len(consensus),
        "disagreement_n": len(any_) - len(consensus),
    }


def profile_numeric(path, vals):
    raw_n = len(vals)
    a = np.asarray(vals, float)
    a = a[np.isfinite(a)]
    n = a.size
    if n < MIN_N:
        return None
    pos = a[a > 0]
    out = {
        "path": path, "kind": "numeric", "n": int(n),
        "n_missing": int(raw_n - n),
        "missing_rate_pct": round(100 * (raw_n - n) / raw_n, 2) if raw_n else None,
        "n_distinct": int(np.unique(a).size),
        "duplicate_rate_pct": round(100 * (1 - np.unique(a).size / n), 2),
        "min": float(np.min(a)), "max": float(np.max(a)),
        "mean": float(np.mean(a)), "median": float(np.median(a)),
        "sd": float(np.std(a, ddof=1)) if n > 1 else None,
        "iqr": float(np.percentile(a, 75) - np.percentile(a, 25)),
        "skew": round(float(stats.skew(a)), 4),
        "excess_kurtosis": round(float(stats.kurtosis(a)), 4),
    }
    out["geometric_mean"] = float(stats.gmean(pos)) if pos.size == n else None
    if out["median"]:
        out["mean_vs_median_pct"] = round(100 * (out["mean"] - out["median"]) / out["median"], 2)
    if out["geometric_mean"]:
        out["mean_vs_geomean_pct"] = round(100 * (out["mean"] - out["geometric_mean"]) / out["geometric_mean"], 2)

    def _sw(x):
        # Shapiro-Wilk rejects almost anything at large n, so raw and log are
        # reported as a COMPARISON. "log fits better" is the usable signal;
        # "p < 0.05" on its own at n=5000 is not.
        if x.size < 3 or x.size > 5000 or np.allclose(x, x[0]):
            return None
        try:
            s, p = stats.shapiro(x)
            return {"W": round(float(s), 4), "p": float(f"{p:.3e}")}
        except Exception:
            return None

    out["shapiro_raw"] = _sw(a)
    out["shapiro_log"] = _sw(np.log(pos)) if pos.size == n else None
    try:
        ad = stats.anderson(a, dist="norm")
        out["anderson_darling_norm"] = {
            "statistic": round(float(ad.statistic), 4),
            "crit_5pct": float(ad.critical_values[2]),
            "rejects_normal_at_5pct": bool(ad.statistic > ad.critical_values[2]),
        }
    except Exception:
        out["anderson_darling_norm"] = None
    p_raw = (out["shapiro_raw"] or {}).get("p")
    p_log = (out["shapiro_log"] or {}).get("p")
    if p_raw is not None and p_log is not None:
        out["better_fit"] = "log-normal" if p_log > p_raw else "normal-ish"
    out["hill_tail_alpha"] = _hill(a)
    out["heavy_tailed_infinite_variance"] = bool(
        out["hill_tail_alpha"] is not None and out["hill_tail_alpha"] < 2)
    out["granularity_step"] = _granularity(a)
    out["digit_heaping"] = _digit_heaping(a)
    out["outliers"] = _outliers(a)
    return out


def profile_categorical(path, vals):
    v = [x for x in vals if x is not None]
    if len(v) < MIN_N:
        return None
    c = Counter(map(str, v))
    n = len(v)
    top, top_n = c.most_common(1)[0]
    return {
        "path": path, "kind": "categorical", "n": n,
        "n_missing": len(vals) - n,
        "missing_rate_pct": round(100 * (len(vals) - n) / len(vals), 2),
        "cardinality": len(c),
        "mode": top[:80],
        "mode_share_pct": round(100 * top_n / n, 2),
        "singleton_levels": sum(1 for k in c.values() if k == 1),
        "rare_levels_lt_1pct": sum(1 for k in c.values() if k / n < 0.01),
    }


def profile_file(p: Path):
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"file": p.name, "error": str(e), "fields": []}
    payload = doc.get("data", doc) if isinstance(doc, dict) else doc
    leaves = _leaves(payload)
    fields, excluded = [], []
    for path, vals in sorted(leaves.items()):
        leaf_name = path.split(".")[-1].replace("[]", "")
        if _NOT_A_MEASUREMENT.match(leaf_name):
            excluded.append({"path": path, "why": "identifier/coordinate/calendar, not a measurement"})
            continue
        nums = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(nums) >= MIN_N and len(nums) >= 0.5 * len(vals):
            r = profile_numeric(path, nums)
            if r:
                fields.append(r)
        else:
            strs = [v for v in vals if isinstance(v, str)]
            if len(strs) >= MIN_N:
                r = profile_categorical(path, strs)
                if r:
                    fields.append(r)
    return {"file": p.name, "n_fields_profiled": len(fields),
            "n_paths_excluded": len(excluded), "excluded_paths": excluded[:50],
            "fields": fields}


def run():
    files = sorted(PROCESSED.glob("*.json")) + ([CORE] if CORE.exists() else [])
    log(f"profiling {len(files)} datasets")
    results = [profile_file(p) for p in files]
    numeric = [f for r in results for f in r.get("fields", []) if f.get("kind") == "numeric"]
    art = {
        "schema": "package-15 profile v1",
        "min_n_for_a_distributional_claim": MIN_N,
        "n_datasets": len(files),
        "n_numeric_fields": len(numeric),
        "n_categorical_fields": sum(1 for r in results for f in r.get("fields", [])
                                    if f.get("kind") == "categorical"),
        "summary": {
            "log_normal_better_fit": sum(1 for f in numeric if f.get("better_fit") == "log-normal"),
            "rejects_normal_ad_5pct": sum(1 for f in numeric
                                          if (f.get("anderson_darling_norm") or {}).get("rejects_normal_at_5pct")),
            "heavy_tailed_alpha_lt_2": sum(1 for f in numeric if f.get("heavy_tailed_infinite_variance")),
            "digit_heaped": sum(1 for f in numeric
                                if (f.get("digit_heaping") or {}).get("uniform_terminal_digits_rejected")),
            "outlier_methods_disagree": sum(1 for f in numeric
                                            if (f.get("outliers") or {}).get("methods_disagree")),
        },
        "datasets": results,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(art, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"  wrote {OUT_JSON.relative_to(ROOT)}")
    s = art["summary"]
    log(f"  {art['n_numeric_fields']} numeric fields, {art['n_categorical_fields']} categorical")
    log(f"  log-normal fits better than normal: {s['log_normal_better_fit']}")
    log(f"  Anderson-Darling rejects normality at 5%: {s['rejects_normal_ad_5pct']}")
    log(f"  heavy-tailed (Hill alpha < 2, infinite variance): {s['heavy_tailed_alpha_lt_2']}")
    log(f"  digit-heaped (terminal-digit uniformity rejected): {s['digit_heaped']}")
    log(f"  fields where the 3 outlier rules disagree: {s['outlier_methods_disagree']}")
    return 0


def self_test():
    """Gate 14: every rule fires on a constructed violation. A check that has
    never been observed to fail is not evidence of anything."""
    rng = np.random.default_rng(15)
    fails = []

    def ck(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  [' + detail + ']') if detail else ''}")
        if not cond:
            fails.append(name)

    print("=== profile_data.py self-test: does each rule FIRE on a violation? ===")
    ln = np.exp(rng.normal(11, 0.6, 400))
    p_ln = profile_numeric("t.lognormal", ln.tolist())
    ck("log-normal field detected as log-normal", p_ln["better_fit"] == "log-normal",
       f"skew={p_ln['skew']}")

    nrm = rng.normal(100, 15, 400)
    p_n = profile_numeric("t.normal", nrm.tolist())
    ck("normal field NOT called log-normal", p_n["better_fit"] == "normal-ish")

    heaped = [int(round(v / 5000) * 5000) for v in rng.uniform(60000, 250000, 400)]
    p_h = profile_numeric("t.heaped", heaped)
    ck("heaping fires on 5k-rounded data",
       p_h["digit_heaping"]["uniform_terminal_digits_rejected"],
       f"p={p_h['digit_heaping']['terminal_digit_p']}")
    ck("granularity recovers the planted 5000 step", p_h["granularity_step"] == 5000,
       f"got {p_h['granularity_step']}")

    smooth = [int(v) for v in rng.uniform(60000, 250000, 400)]
    p_s = profile_numeric("t.smooth", smooth)
    ck("heaping does NOT fire on unrounded data",
       not p_s["digit_heaping"]["uniform_terminal_digits_rejected"],
       f"p={p_s['digit_heaping']['terminal_digit_p']}")

    pareto = (rng.pareto(1.2, 600) + 1) * 1000
    p_p = profile_numeric("t.pareto", pareto.tolist())
    ck("Hill flags infinite variance at planted alpha=1.2",
       p_p["heavy_tailed_infinite_variance"], f"alpha={p_p['hill_tail_alpha']}")
    ck("Hill does NOT flag a normal field", not p_n["heavy_tailed_infinite_variance"],
       f"alpha={p_n['hill_tail_alpha']}")

    mixed = np.concatenate([rng.normal(100, 5, 200), [400.0, 450.0]])
    p_o = profile_numeric("t.outlier", mixed.tolist())
    ck("outlier rules find the planted extremes", p_o["outliers"]["flagged_by_any_n"] >= 2,
       f"any={p_o['outliers']['flagged_by_any_n']}")
    ck("outlier rules disagree on a skewed field", p_ln["outliers"]["methods_disagree"],
       f"any={p_ln['outliers']['flagged_by_any_n']} all3={p_ln['outliers']['flagged_by_all_three_n']}")

    ck("tiny n returns None rather than a fabricated statistic",
       profile_numeric("t.tiny", [1.0, 2.0, 3.0]) is None)

    cat = profile_categorical("t.cat", ["a"] * 50 + ["b"] * 5 + [f"x{i}" for i in range(20)])
    ck("categorical census counts levels and mode share",
       cat["cardinality"] == 22 and cat["singleton_levels"] == 20,
       f"cardinality={cat['cardinality']} singletons={cat['singleton_levels']} mode={cat['mode_share_pct']}%")

    print(f"\n{len(fails)} failure(s)" +
          (": " + ", ".join(fails) if fails else " — every rule fires on a constructed violation"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    sys.exit(self_test() if args.self_test else run())
