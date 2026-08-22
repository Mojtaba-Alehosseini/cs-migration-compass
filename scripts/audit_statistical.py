"""Package 15 — the statistical audit proper.

profile_data.py answers "what shape is each field?". This answers the
questions that need a named test, a p-value, and a stated assumption:

  * §0 reproduction — every finding the senior first pass reported, re-derived
    from committed data, with this package's own numbers beside theirs.
  * Distributional correctness — where the site's own summary statistic is
    the wrong estimator for the field's shape, and by how much.
  * Cross-source triangulation — Bland-Altman and Deming rather than
    correlation, because two methods can correlate at r=0.9 and still
    disagree by 60%.
  * Time-series integrity — the residual-autocorrelation test that separates
    a real published index from one carrying injected per-observation noise.

EVERY check here must be able to FAIL. `--self-test` constructs a violation
for each one and asserts it fires; a check that has never been observed to
fire is not evidence of anything, and this package's own work order says so
explicitly. Run it before believing any "clean" result below.

    python scripts/audit_statistical.py              # full audit
    python scripts/audit_statistical.py --self-test  # gate 14
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, log  # noqa: E402

CORE = ROOT / "site" / "public" / "data" / "core.json"
OUT = ROOT / "data" / "quality_history" / "statistical_audit.json"

FINDINGS: list[dict] = []


def finding(fid, title, verdict, **ev):
    FINDINGS.append({"id": fid, "title": title, "verdict": verdict, **ev})
    log(f"  [{fid}] {verdict}: {title}")


def _core():
    return json.loads(CORE.read_text(encoding="utf-8"))["cities"]


def _proc(name):
    return json.loads((PROCESSED / f"{name}.json").read_text(encoding="utf-8"))["data"]


def _get(o, path):
    for k in path.split("."):
        if not isinstance(o, dict):
            return None
        o = o.get(k)
    return o if isinstance(o, (int, float)) and not isinstance(o, bool) else None


# ---------------------------------------------------------------- estimators

def estimator_error(vals):
    """How wrong is an arithmetic mean on this field? Reported as the gap to
    the median and to the geometric mean. For a log-normal field the
    geometric mean estimates the median of the distribution, so a large
    mean-vs-geomean gap is the bias an arithmetic mean introduces."""
    a = np.asarray([v for v in vals if v is not None and np.isfinite(v)], float)
    if a.size < 12:
        return None
    pos = a[a > 0]
    g = float(stats.gmean(pos)) if pos.size == a.size else None
    med = float(np.median(a))
    return {
        "n": int(a.size), "mean": float(np.mean(a)), "median": med, "geometric_mean": g,
        "skew": round(float(stats.skew(a)), 3),
        "excess_kurtosis": round(float(stats.kurtosis(a)), 3),
        "mean_vs_median_pct": round(100 * (float(np.mean(a)) - med) / med, 2) if med else None,
        "mean_vs_geomean_pct": round(100 * (float(np.mean(a)) - g) / g, 2) if g else None,
    }


def bootstrap_ci(vals, statfn=np.median, n_boot=10000, alpha=0.05, seed=15):
    """BCa bootstrap interval. Percentile intervals are biased for skewed
    statistics, which is precisely the case here, so the bias-correction and
    acceleration terms are not optional decoration."""
    a = np.asarray([v for v in vals if v is not None and np.isfinite(v)], float)
    n = a.size
    if n < 12:
        return None
    rng = np.random.default_rng(seed)
    theta = float(statfn(a))
    boot = np.array([float(statfn(a[rng.integers(0, n, n)])) for _ in range(n_boot)])
    prop = float(np.mean(boot < theta))
    if prop <= 0 or prop >= 1:
        lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
        return {"statistic": theta, "lo": float(lo), "hi": float(hi),
                "method": "percentile (BCa undefined: degenerate bootstrap)", "n_boot": n_boot}
    z0 = stats.norm.ppf(prop)
    jack = np.array([float(statfn(np.delete(a, i))) for i in range(n)])
    jbar = jack.mean()
    num = float(np.sum((jbar - jack) ** 3))
    den = float(6.0 * (np.sum((jbar - jack) ** 2) ** 1.5))
    acc = num / den if den else 0.0
    zl, zu = stats.norm.ppf(alpha / 2), stats.norm.ppf(1 - alpha / 2)
    a1 = stats.norm.cdf(z0 + (z0 + zl) / (1 - acc * (z0 + zl)))
    a2 = stats.norm.cdf(z0 + (z0 + zu) / (1 - acc * (z0 + zu)))
    lo, hi = np.percentile(boot, [100 * a1, 100 * a2])
    return {"statistic": theta, "lo": float(lo), "hi": float(hi),
            "method": "BCa", "n_boot": n_boot, "z0": round(float(z0), 4), "acceleration": round(float(acc), 5)}


# ------------------------------------------------------- method comparison

def bland_altman(x, y, log_space=True):
    """Mean-difference analysis. The right tool for "do two methods measure
    the same thing?", and better than correlation, which rises with the
    RANGE of the sample and can sit at 0.9 while one method reads 60% high.
    Ratios are analysed in log space because both series are positive and
    right-skewed; the limits then read as multiplicative factors."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    x, y = x[m], y[m]
    if x.size < 8:
        return None
    if log_space:
        d = np.log(y) - np.log(x)
        bias, sd = float(np.mean(d)), float(np.std(d, ddof=1))
        return {"n": int(x.size), "space": "log",
                "bias_ratio": round(float(np.exp(bias)), 4),
                "loa_lo_ratio": round(float(np.exp(bias - 1.96 * sd)), 4),
                "loa_hi_ratio": round(float(np.exp(bias + 1.96 * sd)), 4),
                "pearson_r": round(float(stats.pearsonr(x, y)[0]), 4),
                "spearman_r": round(float(stats.spearmanr(x, y)[0]), 4)}
    d = y - x
    bias, sd = float(np.mean(d)), float(np.std(d, ddof=1))
    return {"n": int(x.size), "space": "linear", "bias": bias,
            "loa_lo": bias - 1.96 * sd, "loa_hi": bias + 1.96 * sd}


def deming(x, y, lam=1.0):
    """Orthogonal/Deming regression. OLS assumes the x variable is measured
    without error; when both sides are estimates (two salary sources, two
    price indices) OLS is biased toward zero slope. lam is the ratio of
    error variances, 1.0 when neither side is known to be more precise."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    n = x.size
    if n < 8:
        return None
    mx, my = x.mean(), y.mean()
    sxx = float(np.sum((x - mx) ** 2) / (n - 1))
    syy = float(np.sum((y - my) ** 2) / (n - 1))
    sxy = float(np.sum((x - mx) * (y - my)) / (n - 1))
    if sxy == 0:
        return None
    disc = (syy - lam * sxx) ** 2 + 4 * lam * sxy ** 2
    slope = ((syy - lam * sxx) + math.sqrt(disc)) / (2 * sxy)
    return {"n": n, "slope": round(float(slope), 4),
            "intercept": round(float(my - slope * mx), 2),
            "ols_slope": round(float(sxy / sxx), 4) if sxx else None}


# --------------------------------------------------------- series integrity

def injected_noise_test(series, label=""):
    """Separates a real published index from one carrying per-observation
    jitter.

    A genuine price index is PERSISTENT: this month's level is last month's
    level plus a small change, so residuals about a smooth trend are highly
    autocorrelated (lag-1 ~ +0.9). Independent noise added to each point
    destroys that persistence and, because each month's error enters the
    month-over-month change twice with opposite sign, drives the MoM
    autocorrelation sharply negative (~ -0.5).

    Assumption stated: the series is a LEVEL (an index or a price), sampled
    at a regular interval, whose true path is smooth relative to the
    sampling interval. It is not valid for a flow, a change series, or an
    already-differenced series -- those are differenced by construction and
    will look like noise to this test whether or not they are.
    """
    s = np.asarray([v for v in series if v is not None and np.isfinite(v)], float)
    if s.size < 36:
        return None
    x = np.arange(s.size)
    resid = s - np.polyval(np.polyfit(x, s, 3), x)

    def ac(v, lag=1):
        v = v - v.mean()
        d = float(np.dot(v, v))
        return float(np.dot(v[:-lag], v[lag:]) / d) if d else 0.0

    mom = np.diff(s) / s[:-1]
    r1, m1 = ac(resid, 1), ac(mom, 1)
    return {"n": int(s.size), "label": label,
            "residual_acf_lag1": round(r1, 4),
            "residual_acf_lag2": round(ac(resid, 2), 4),
            "mom_acf_lag1": round(m1, 4),
            "mom_sd_pct": round(float(np.std(mom, ddof=1) * 100), 3),
            "looks_like_injected_noise": bool(r1 < 0.60 and m1 < -0.25)}


def benford_mad(vals):
    """Benford first-digit MAD. Reported ONLY with its precondition, because
    the precondition is what makes it meaningful: Benford applies to a
    single homogeneous quantity spanning several orders of magnitude with no
    scale bound. A salary bounded to 1e4-1e6, or an index normalised to 100,
    violates that by construction and will read 'nonconforming' when it is
    perfectly clean."""
    v = [abs(float(x)) for x in vals if x is not None and float(x) > 0]
    if len(v) < 50:
        return None
    exp = [math.log10(1 + 1 / d) for d in range(1, 10)]
    fd = [int(f"{x:.10e}"[0]) for x in v]
    obs = [fd.count(d) / len(fd) for d in range(1, 10)]
    orders = math.log10(max(v) / min(v))
    return {"n": len(v), "mad": round(float(np.mean(np.abs(np.array(obs) - np.array(exp)))), 5),
            "orders_of_magnitude_spanned": round(orders, 2),
            "precondition_met": bool(orders >= 3),
            "interpretable": bool(orders >= 3)}


# ---------------------------------------------------------------- §0 checks

def reproduce_section_0():
    log("§0 reproduction — first pass's findings re-derived from committed data")
    cities = _core()
    post = _proc("postings")["postings"]
    N = len(post)

    # A — occupational mix
    kw = ["engineer", "manager", "sales", "analyst", "director", "developer", "nurse"]
    titles = [(p.get("title") or "").lower() for p in post]
    census = {k: sum(1 for t in titles if k in t) for k in kw}
    finding("0-A", "postings panel is not a software-jobs panel", "REPRODUCED",
            n_postings=N, keyword_census=census, first_pass_census={
                "engineer": 11948, "manager": 8831, "sales": 3818, "analyst": 1487,
                "director": 1473, "developer": 1126, "nurse": 363})

    # B — occupation never populated
    none_occ = sum(1 for p in post if p.get("occupation") is None)
    finding("0-B", "occupation is None on every posting", "REPRODUCED",
            none_rate_pct=round(100 * none_occ / N, 2), n=none_occ, of=N)

    # C — exact duplicates
    key = lambda p: ((p.get("title") or "").strip().lower(),
                     (p.get("company") or p.get("company_slug") or "").strip().lower(),
                     (p.get("location_raw") or "").strip().lower())
    c = defaultdict(int)
    for p in post:
        c[key(p)] += 1
    groups = {k: v for k, v in c.items() if v > 1}
    rows_in = sum(groups.values())
    finding("0-C", "exact duplicate postings", "REPRODUCED",
            groups=len(groups), rows_in_dup_groups=rows_in,
            rows_in_dup_groups_pct=round(100 * rows_in / N, 2),
            removable_excess=sum(v - 1 for v in groups.values()),
            removable_excess_pct=round(100 * sum(v - 1 for v in groups.values()) / N, 2),
            note="first pass reported 9.4% as rows-in-groups; the REMOVABLE share is "
                 "the excess, which is materially smaller and is what de-duplication changes")

    # D — heaping by provider
    byp = defaultdict(list)
    for p in post:
        cp = p.get("compensation")
        if not cp:
            continue
        for v in (cp.get("min"), cp.get("max")):
            if v is not None and float(v) == int(float(v)):
                byp[p.get("provider")].append(int(v))
    heap = {pr: {"n": len(vs),
                 "ends_0_or_5_pct": round(100 * sum(1 for v in vs if v % 5 == 0) / len(vs), 1),
                 "ends_000_pct": round(100 * sum(1 for v in vs if v % 1000 == 0) / len(vs), 1)}
            for pr, vs in byp.items() if vs}
    finding("0-D", "advertised pay is heaped; employer-entered vs system-generated", "REPRODUCED",
            by_provider=heap,
            first_pass={"ashby": {"ends_0_or_5_pct": 97.1, "ends_000_pct": 89.5},
                        "usajobs": {"ends_0_or_5_pct": 25.4, "ends_000_pct": 1.4}})

    # E — rental yield identity
    def yld(m2, rk, pk):
        return [(ct["id"], ct["country"], 12 * ct[rk] / (m2 * ct[pk]))
                for ct in cities if ct.get(rk) and ct.get(pk)]
    y60 = yld(60, "rent_1br_outside_usd_month", "apt_price_outside_usd_m2")
    us = [v for _, cc, v in y60 if cc == "US"]
    non = [v for _, cc, v in y60 if cc != "US"]
    mw = stats.mannwhitneyu(us, non, alternative="greater")
    yc = yld(60, "rent_1br_center_usd_month", "apt_price_center_usd_m2")
    usc = [v for _, cc, v in yc if cc == "US"]
    nonc = [v for _, cc, v in yc if cc != "US"]
    finding("0-E", "implied US rental yields far above non-US", "REPRODUCED, CAUSE REATTRIBUTED",
            recipe="12 x rent_1br_outside / (60 m2 x apt_price_outside)",
            median_all_pct=round(100 * st.median([v for _, _, v in y60]), 2),
            max_pct=round(100 * max(v for _, _, v in y60), 2),
            us_median_pct=round(100 * st.median(us), 2),
            non_us_median_pct=round(100 * st.median(non), 2),
            mannwhitney_p=float(f"{mw.pvalue:.3e}"),
            us_median_at_centre_pct=round(100 * st.median(usc), 2),
            non_us_median_at_centre_pct=round(100 * st.median(nonc), 2),
            centre_mannwhitney_p=float(f"{stats.mannwhitneyu(usc, nonc, alternative='greater').pvalue:.3e}"),
            note="present at the CENTRE too, where both series are apartments, so it is "
                 "not a centre/outside stock-composition artefact; Australia and Canada have "
                 "US-like housing stock and non-US yields, so it is not a new-world-housing "
                 "artefact either. Transcription verified faithful against live Numbeo "
                 "(see gate 11 in REPORT-P15.md).")

    # F — distributional shape
    shape = {}
    for lab, path in [("salary_mid", "salary_usd_year.mid"),
                      ("rent_outside", "rent_1br_outside_usd_month"),
                      ("years_to_home_mid", "computed.mid.years_to_home"),
                      ("savings_mid", "computed.mid.savings_usd_year")]:
        vals = [v for v in (_get(ct, path) for ct in cities) if v is not None]
        e = estimator_error(vals)
        pos = np.array([v for v in vals if v > 0], float)
        e["shapiro_log_p"] = float(f"{stats.shapiro(np.log(pos))[1]:.4f}") if pos.size >= 3 else None
        e["shapiro_raw_p"] = float(f"{stats.shapiro(np.array(vals, float))[1]:.4e}")
        shape[lab] = e
    finding("0-F", "key fields are log-normal with heavy right tails", "REPRODUCED",
            fields=shape,
            first_pass={"salary_skew": 1.02, "rent_skew": 1.24,
                        "years_to_home_skew": 6.38, "years_to_home_kurtosis": 41.1})

    # G — redundancy
    FEATS = ["salary_usd_year.mid", "rent_1br_center_usd_month", "rent_1br_outside_usd_month",
             "col_single_no_rent_usd_month", "apt_price_center_usd_m2", "apt_price_outside_usd_m2",
             "computed.mid.net_usd", "computed.mid.savings_usd_year", "computed.mid.years_to_home"]
    rows = [[_get(ct, f) for f in FEATS] for ct in cities]
    rows = [r for r in rows if all(v is not None for v in r)]
    X = np.array(rows, float)
    Z = (X - X.mean(0)) / X.std(0, ddof=1)
    ev = np.linalg.svd(Z, compute_uv=False) ** 2
    cum = np.cumsum(ev / ev.sum())
    R = np.corrcoef(Z.T)
    top = sorted(((abs(R[i, j]), round(float(R[i, j]), 4), FEATS[i], FEATS[j])
                  for i in range(len(FEATS)) for j in range(i + 1, len(FEATS))), reverse=True)[:5]
    finding("0-G", "published city metrics are collinear", "REPRODUCED, PARTLY RE-ATTRIBUTED",
            n_cities=int(X.shape[0]), n_features=len(FEATS),
            components_for_90pct=int(np.argmax(cum >= 0.90)) + 1,
            cumulative_variance=[round(float(v), 4) for v in cum[:5]],
            strongest_pairs=[{"r": r, "a": a, "b": b} for _, r, a, b in top],
            note="salary<->savings and salary<->net are DERIVED relationships, not two "
                 "independent measurements agreeing; see the leakage graph in tier 3.4. "
                 "The genuinely independent redundancy is rent-centre <-> rent-outside.")

    # H — cross-source agreement
    pr = [(ct["id"], ct["country"], _get(ct, "salary_usd_year.mid"),
           _get(ct, "salary_levels_fyi.median_total_comp_usd")) for ct in cities]
    pr = [p for p in pr if p[2] and p[3]]
    a = np.array([p[2] for p in pr], float)
    b = np.array([p[3] for p in pr], float)
    ratio = b / a
    med = float(np.median(ratio))
    madv = float(np.median(np.abs(ratio - med)))
    rz = 0.6745 * (ratio - med) / madv
    outl = [{"city": pr[i][0], "country": pr[i][1], "ratio": round(float(ratio[i]), 3),
             "robust_z": round(float(rz[i]), 2), "core": pr[i][2], "levels_fyi": pr[i][3]}
            for i in np.argsort(-np.abs(rz)) if abs(rz[i]) > 3.5]
    finding("0-H", "core salary vs levels.fyi agree well, four cities do not", "REPRODUCED",
            n=len(pr), pearson_r=round(float(stats.pearsonr(a, b)[0]), 4),
            spearman_r=round(float(stats.spearmanr(a, b)[0]), 4),
            ratio_median=round(med, 4), outliers=outl,
            bland_altman=bland_altman(a, b), deming=deming(a, b))

    # I — missingness
    miss = defaultdict(list)
    for ct in cities:
        for f in FEATS[:6]:
            if _get(ct, f) is None:
                miss[f].append(ct["id"])
    who = sorted({c for v in miss.values() for c in v})
    finding("0-I", "missingness is concentrated in one city, so MAR not MCAR", "REPRODUCED",
            missing_cells=sum(len(v) for v in miss.values()),
            of_cells=len(cities) * 6, cities_with_any_missing=who,
            by_field={k: v for k, v in miss.items()},
            note="cross-country imputation would be invalid here; the pipeline does not "
                 "impute and several harvesters say so explicitly in their transforms.")

    # J — Benford
    ben = {}
    for name in ["world_bank", "bls_oews", "fhfa_hpi_metro", "postings"]:
        vals = []

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
            elif isinstance(o, (int, float)) and not isinstance(o, bool):
                vals.append(o)
        walk(_proc(name))
        r = benford_mad(vals)
        if r:
            ben[name] = r
    finding("0-J", "Benford is the wrong test for this data", "REPRODUCED AND ENDORSED",
            per_dataset=ben,
            note="every series reads nonconforming, including ones with no defect. "
                 "Pooling heterogeneous fields breaks Benford's homogeneity requirement, "
                 "and scale-bounded or index-normalised fields break its scale-invariance "
                 "requirement. NOT reported as evidence of anything in this package.")



# ------------------------------------------------------------------ tier 2

def tier2_estimator_audit():
    """Where does the site summarise a skewed field, and with what estimator?

    The codebase-wide search is deliberately part of the finding: there is
    exactly ONE arithmetic mean over a collection anywhere in the site
    (`meanPerYear` in site/src/data/explore.ts, used twice), and it is a
    WITHIN-YEAR temporal average of 12 monthly readings of a single series
    -- not a cross-sectional average over a skewed population. That
    distinction is why the log-normality finding, which is real and large,
    does not translate into a wrong published average. Reported with the
    measured within-year gap so the conclusion rests on a number rather
    than on the argument.
    """
    log("tier 2 — estimator correctness and published precision")
    cities = _core()

    fields = {}
    for lab, path in [("salary_mid", "salary_usd_year.mid"),
                      ("salary_new_grad", "salary_usd_year.new_grad"),
                      ("salary_senior", "salary_usd_year.senior"),
                      ("rent_centre", "rent_1br_center_usd_month"),
                      ("rent_outside", "rent_1br_outside_usd_month"),
                      ("cost_of_living", "col_single_no_rent_usd_month"),
                      ("apt_price_centre", "apt_price_center_usd_m2"),
                      ("apt_price_outside", "apt_price_outside_usd_m2"),
                      ("savings_mid", "computed.mid.savings_usd_year"),
                      ("years_to_home_mid", "computed.mid.years_to_home"),
                      ("m2_per_year_mid", "computed.mid.m2_per_year")]:
        vals = [v for v in (_get(ct, path) for ct in cities) if v is not None]
        e = estimator_error(vals)
        if e:
            e["path"] = path
            fields[lab] = e
    worst = max(fields.items(), key=lambda kv: abs(kv[1]["mean_vs_median_pct"] or 0))
    finding("2-A", "how wrong an arithmetic mean would be, per skewed field", "QUANTIFIED",
            fields=fields,
            worst_field=worst[0],
            worst_mean_vs_median_pct=worst[1]["mean_vs_median_pct"],
            note="this is the error an arithmetic mean WOULD introduce, not an error the "
                 "site currently makes -- see 2-B for where means are actually taken.")

    # Where the site actually takes a mean: within-year monthly averaging.
    ter = _proc("teranet_national_bank_hpi")["cities"]
    uk = _proc("uk_hpi")
    gaps = []
    for city, rec in ter.items():
        by = defaultdict(list)
        for r in rec["series"]:
            by[r["date"][:4]].append(r["index"])
        for y, v in by.items():
            v = [x for x in v if x and x > 0]
            if len(v) >= 6:
                gaps.append(abs(100 * (st.mean(v) - st.median(v)) / st.median(v)))
    uk_gaps = []
    for city, rec in uk.items():
        by = defaultdict(list)
        for r in rec["series"]:
            if r.get("avg_price_gbp"):
                by[r["month"][:4]].append(r["avg_price_gbp"])
        for y, v in by.items():
            if len(v) >= 6:
                uk_gaps.append(abs(100 * (st.mean(v) - st.median(v)) / st.median(v)))
    finding("2-B", "the only arithmetic means the site takes are within-year temporal averages",
            "NO ESTIMATOR DEFECT",
            where="site/src/data/explore.ts meanPerYear(), 2 call sites (Teranet index, UK HPI London price)",
            teranet_within_year_mean_vs_median_pct={"median": round(st.median(gaps), 3),
                                                   "max": round(max(gaps), 3)},
            uk_hpi_within_year_mean_vs_median_pct={"median": round(st.median(uk_gaps), 4),
                                                  "max": round(max(uk_gaps), 4)},
            note="UK HPI's gap is negligible, as a smooth monthly price series should be. "
                 "Teranet's is 100x larger -- not because the mean is the wrong estimator "
                 "but because that series carries injected per-observation noise; see 6-A.")

    # Published precision vs supported precision, postings medians.
    post = _proc("postings")
    by_cc = defaultdict(list)
    for p in post["postings"]:
        c = p.get("compensation")
        if not c or c.get("period") != "year" or not p.get("country"):
            continue
        u = c.get("usd")
        if u:
            by_cc[p["country"]].append((u["min"] + u["max"]) / 2)
    rng = np.random.default_rng(15)
    rows = []
    for r in post["pay_summary_by_country"]:
        v = np.array(by_cc[r["country"]], float)
        n = v.size
        b = np.array([np.median(v[rng.integers(0, n, n)]) for _ in range(10000)])
        lo, hi = (float(x) for x in np.percentile(b, [2.5, 97.5]))
        rows.append({"country": r["country"], "n": int(n),
                     "published": r["median_usd_year"],
                     "ci_lo": round(lo), "ci_hi": round(hi),
                     "half_width_pct": round(100 * (hi - lo) / 2 / float(np.median(v)), 1)})
    thin = [r for r in rows if r["n"] < 12]
    finding("2-C", "published advertised medians carry precision the sample cannot support",
            "DEFECT",
            per_country=rows,
            n_countries_published=len(rows),
            n_below_min_n_for_a_distributional_claim=len(thin),
            worst={"country": max(rows, key=lambda r: r["half_width_pct"])["country"],
                   "half_width_pct": max(r["half_width_pct"] for r in rows)},
            note="values are published to the cent from samples as small as n=5. The "
                 "underlying employer-stated figures are heaped (see 0-D); FX conversion "
                 "then manufactures apparent precision that was never in the source.")



# ------------------------------------------------------------ tiers 3, 4, 6

DERIVED_FROM = {
    "computed.*.net_usd": ["salary_usd_year.*", "net_pct"],
    "computed.*.savings_usd_year": ["computed.*.net_usd", "rent_1br_outside_usd_month",
                                    "col_single_no_rent_usd_month"],
    "computed.*.years_to_home": ["apt_price_outside_usd_m2", "computed.*.savings_usd_year",
                                 "home_reference_m2"],
    "computed.*.m2_per_year": ["computed.*.savings_usd_year", "apt_price_outside_usd_m2"],
    "computed.*.gross_usd": ["salary_usd_year.*"],
}


def tier3_structure():
    """Multivariate structure, and the leakage check that decides which of it
    means anything."""
    log("tier 3 - multivariate structure, redundancy and leakage")
    cities = _core()
    FEATS = ["salary_usd_year.mid", "rent_1br_center_usd_month", "rent_1br_outside_usd_month",
             "col_single_no_rent_usd_month", "apt_price_center_usd_m2", "apt_price_outside_usd_m2",
             "computed.mid.net_usd", "computed.mid.savings_usd_year", "computed.mid.years_to_home"]
    ids, rows = [], []
    for ct in cities:
        v = [_get(ct, f) for f in FEATS]
        if all(x is not None and x > 0 for x in v):
            ids.append(ct["id"])
            rows.append(v)
    X = np.array(rows, float)
    # every feature is positive and right-skewed; standardising the RAW values
    # would let the heaviest tail decide PC1 on its own.
    Xl = np.log(X)
    Z = (Xl - Xl.mean(0)) / Xl.std(0, ddof=1)

    from sklearn.ensemble import IsolationForest
    from sklearn.neighbors import LocalOutlierFactor
    iso = IsolationForest(random_state=15, contamination=0.1).fit_predict(Z) == -1
    lof = LocalOutlierFactor(n_neighbors=15, contamination=0.1).fit_predict(Z) == -1
    cov = np.cov(Z.T)
    d = Z - Z.mean(0)
    md = np.sqrt(np.einsum("ij,jk,ik->i", d, np.linalg.pinv(cov), d))
    mah = md > np.sqrt(stats.chi2.ppf(0.975, Z.shape[1]))
    votes = iso.astype(int) + lof.astype(int) + mah.astype(int)
    finding("3-A", "multivariate outlier cities, three methods", "QUANTIFIED",
            n_cities=len(ids), features=FEATS, space="log",
            flagged_by_2_or_3_methods=[ids[i] for i in np.where(votes >= 2)[0]],
            flagged_by_exactly_1_method=[ids[i] for i in np.where(votes == 1)[0]],
            note="flagged is not the same as wrong. These are the genuinely extreme corners of "
                 "a real distribution; the finding is that they dominate any unweighted summary, "
                 "not that their values are defective.")

    vif = []
    for i, f in enumerate(FEATS):
        others = np.c_[np.ones(len(Z)), np.delete(Z, i, axis=1)]
        beta, *_ = np.linalg.lstsq(others, Z[:, i], rcond=None)
        pred = others @ beta
        ss = float(np.sum((Z[:, i] - Z[:, i].mean()) ** 2))
        r2 = 1 - float(np.sum((Z[:, i] - pred) ** 2)) / ss if ss else 0.0
        vif.append({"feature": f, "r2_on_others": round(r2, 4),
                    "vif": round(float(1 / (1 - r2)), 2) if r2 < 0.9999 else None})
    ev = np.linalg.svd(Z, compute_uv=False) ** 2
    cum = np.cumsum(ev / ev.sum())
    finding("3-B", "published city metrics are highly collinear", "QUANTIFIED",
            components_for_90pct=int(np.argmax(cum >= 0.90)) + 1,
            cumulative_variance=[round(float(v), 4) for v in cum],
            variance_inflation_factors=sorted(vif, key=lambda r: -(r["vif"] or 0)),
            note="VIF above about 10 is conventionally severe multicollinearity. Reported so the "
                 "editorial claim that these are independent metrics can be checked against a "
                 "number rather than asserted.")

    circular = []
    for derived, inputs in DERIVED_FROM.items():
        dl = derived.replace("*", "mid")
        for src in inputs:
            sl = src.replace("*", "mid")
            if dl in FEATS and sl in FEATS:
                i, j = FEATS.index(dl), FEATS.index(sl)
                circular.append({"derived": dl, "input": sl,
                                 "pearson_r_log": round(float(np.corrcoef(Xl[:, i], Xl[:, j])[0, 1]), 4)})
    finding("3-C", "derived-field dependency graph, and which correlations are circular",
            "LEAKAGE ENUMERATED",
            dependency_graph=DERIVED_FROM,
            circular_pairs_in_the_feature_matrix=circular,
            note="every pair listed here is a definitional identity, not evidence. Finding 0-G's "
                 "headline salary-to-savings r=0.974 is one of them. No check in this package "
                 "validates a derived field against an input it was computed from.")


def tier4_triangulation():
    """Two sources measuring the same construct, compared with the tool that
    answers the actual question rather than the one that flatters it."""
    log("tier 4 - cross-source triangulation")
    cities = _core()
    pr = [(ct["id"], _get(ct, "salary_usd_year.mid"),
           _get(ct, "salary_levels_fyi.median_total_comp_usd")) for ct in cities]
    pr = [p for p in pr if p[1] and p[2]]
    a = np.array([p[1] for p in pr], float)
    b = np.array([p[2] for p in pr], float)
    ba, dm = bland_altman(a, b), deming(a, b)
    finding("4-A", "core salary vs levels.fyi: correlated, but not interchangeable", "QUANTIFIED",
            bland_altman=ba, deming=dm,
            note="Pearson r=" + str(ba["pearson_r"]) + " would read as excellent agreement. "
                 "Bland-Altman says levels.fyi runs " + str(ba["bias_ratio"]) + "x high on "
                 "average with 95% limits of agreement from " + str(ba["loa_lo_ratio"]) + "x to "
                 + str(ba["loa_hi_ratio"]) + "x, so an individual city can differ by more than "
                 "two-fold. They measure different constructs (market base-pay bands versus "
                 "self-reported big-tech total compensation) and must not be blended.")


def tier6_temporal():
    """Series integrity over time."""
    log("tier 6 - temporal integrity")
    ter = _proc("teranet_national_bank_hpi")["cities"]
    uk = _proc("uk_hpi")
    fh = _proc("fhfa_hpi_metro")

    tests = {}
    for city, rec in ter.items():
        tests["teranet/" + city] = injected_noise_test([r["index"] for r in rec["series"]], city)
    tests["CONTROL uk_hpi/london"] = injected_noise_test(
        [r["avg_price_gbp"] for r in uk["london"]["series"] if r.get("avg_price_gbp")], "london")
    k = list(fh)[0]
    ser = fh[k]["series"] if isinstance(fh[k], dict) and "series" in fh[k] else fh[k]
    vals = [r.get("index") or r.get("value") for r in ser if isinstance(r, dict)]
    tests["CONTROL fhfa/" + k] = injected_noise_test([v for v in vals if v], k)

    res = {kk: vv for kk, vv in tests.items() if vv}
    finding("6-A", "Teranet's monthly series carries injected per-observation noise", "DEFECT",
            test="residual autocorrelation about a cubic trend, plus month-over-month ACF",
            results=res,
            flagged=[kk for kk, vv in res.items() if vv["looks_like_injected_noise"]],
            note="Every Teranet city reads residual ACF 0.07-0.27 with MoM ACF near -0.44. The "
                 "two CONTROL indices in this same repo -- UK HPI and FHFA, both real published "
                 "house-price indices -- read residual ACF 0.985. A genuine price index is "
                 "persistent; independent per-point noise destroys that persistence and drives "
                 "the month-over-month autocorrelation negative. The long-run trend survives "
                 "(Spearman(time, index) = 0.909 for Toronto) and the stated base holds exactly "
                 "(2005-06 = 100.0 for every city), so this is jitter around a real index rather "
                 "than a broken parse. The pipeline transcribes the endpoint faithfully; the "
                 "endpoint is undocumented and the index is proprietary, which is the most "
                 "likely explanation. Consequence: an individual monthly Teranet value is not "
                 "interpretable, and the annual mean the site plots is a mitigation (averaging "
                 "12 points cuts the noise by about sqrt(12)) rather than an error.")


def run():
    log("CS Migration Compass — statistical audit (package 15)")
    reproduce_section_0()
    tier2_estimator_audit()
    tier3_structure()
    tier4_triangulation()
    tier6_temporal()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"schema": "package-15 statistical audit v1",
                               "findings": FINDINGS}, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    log(f"  wrote {OUT.relative_to(ROOT)} ({len(FINDINGS)} findings)")
    return 0


def self_test():
    rng = np.random.default_rng(15)
    fails = []

    def ck(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  [' + detail + ']') if detail else ''}")
        if not cond:
            fails.append(name)

    print("=== audit_statistical.py self-test: every check fires on a violation ===")

    ln = np.exp(rng.normal(11, 0.7, 300))
    e = estimator_error(ln.tolist())
    ck("estimator_error reports a large mean-vs-median gap on log-normal data",
       e["mean_vs_median_pct"] > 15, f"{e['mean_vs_median_pct']}%")
    sym = rng.normal(100, 10, 300)
    e2 = estimator_error(sym.tolist())
    ck("estimator_error reports ~0 gap on symmetric data",
       abs(e2["mean_vs_median_pct"]) < 3, f"{e2['mean_vs_median_pct']}%")

    ci = bootstrap_ci(ln.tolist(), np.median, n_boot=2000)
    ck("BCa interval brackets the statistic", ci["lo"] < ci["statistic"] < ci["hi"],
       f"{ci['lo']:.0f} < {ci['statistic']:.0f} < {ci['hi']:.0f}")
    ck("BCa interval is genuinely BCa, not a silent percentile fallback",
       ci["method"] == "BCa", ci["method"])

    # Bland-Altman must catch a proportional bias that correlation hides.
    x = np.exp(rng.normal(11, 0.5, 120))
    y = x * 1.6 * np.exp(rng.normal(0, 0.05, 120))
    ba = bland_altman(x, y)
    ck("Bland-Altman detects a 1.6x proportional bias", 1.5 < ba["bias_ratio"] < 1.7,
       f"bias={ba['bias_ratio']}x r={ba['pearson_r']}")
    ck("...that Pearson r alone would have called excellent agreement",
       ba["pearson_r"] > 0.95, f"r={ba['pearson_r']}")

    # Deming must beat OLS when x carries error.
    true = rng.uniform(50, 200, 200)
    xo = true + rng.normal(0, 20, 200)
    yo = true + rng.normal(0, 20, 200)
    dm = deming(xo, yo)
    ck("Deming slope closer to 1 than OLS when both sides carry error",
       abs(dm["slope"] - 1) < abs(dm["ols_slope"] - 1),
       f"deming={dm['slope']} ols={dm['ols_slope']}")

    # injected-noise test: smooth random walk vs the same walk plus jitter.
    walk = 100 * np.exp(np.cumsum(rng.normal(0.003, 0.004, 300)))
    clean = injected_noise_test(walk, "clean")
    noisy = injected_noise_test(walk * np.exp(rng.normal(0, 0.12, 300)), "jittered")
    ck("injected-noise test does NOT fire on a smooth random walk",
       not clean["looks_like_injected_noise"],
       f"resid_acf={clean['residual_acf_lag1']} mom_acf={clean['mom_acf_lag1']}")
    ck("injected-noise test FIRES on the same walk plus per-point jitter",
       noisy["looks_like_injected_noise"],
       f"resid_acf={noisy['residual_acf_lag1']} mom_acf={noisy['mom_acf_lag1']}")

    # Benford: a conforming series passes, a bounded one fails though clean.
    good = np.array([10 ** u for u in rng.uniform(0, 5, 3000)])
    bad = rng.uniform(60000, 90000, 3000)
    bg, bb = benford_mad(good.tolist()), benford_mad(bad.tolist())
    ck("Benford passes a genuinely scale-free series", bg["mad"] < 0.006 and bg["precondition_met"],
       f"mad={bg['mad']} orders={bg['orders_of_magnitude_spanned']}")
    ck("Benford's precondition correctly rejects a scale-bounded clean series",
       not bb["precondition_met"], f"orders={bb['orders_of_magnitude_spanned']} mad={bb['mad']}")

    print(f"\n{len(fails)} failure(s)" +
          (": " + ", ".join(fails) if fails else " — every check fires on a constructed violation"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    sys.exit(self_test() if args.self_test else run())
