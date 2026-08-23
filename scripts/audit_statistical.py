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


def bootstrap_ci(vals, statfn=np.median, n_boot=10000, alpha=0.05, seed=15,
                 min_n=12, allow_percentile_fallback=True):
    """Bootstrap confidence interval, BCa where the sample can support it.

    An adversarial review found this function defined, self-tested, and then
    NEVER CALLED by the audit: finding 2-C computed its intervals with a plain
    percentile bootstrap inline while the report claimed "BCa where n permits".
    It is now the single entry point, and it REPORTS which method it used, so
    the claim and the computation cannot drift apart again.

    Below `min_n` the BCa machinery is not merely imprecise, it is
    meaningless -- the jackknife acceleration is estimated from n-1 leave-one-out
    replicates, and at n=5 the 2.5/97.5 percentiles of the bootstrap are just
    the sample min and max. Those cases fall back to a percentile interval and
    say so in `method`, rather than being silently dropped or silently
    upgraded."""
    a = np.asarray([v for v in vals if v is not None and np.isfinite(v)], float)
    n = a.size
    if n < 3:
        return None
    rng = np.random.default_rng(seed)
    theta = float(statfn(a))
    boot = np.array([float(statfn(a[rng.integers(0, n, n)])) for _ in range(n_boot)])

    def _pct(why):
        lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
        out = {"statistic": theta, "lo": float(lo), "hi": float(hi),
               "method": f"percentile ({why})", "n": n, "n_boot": n_boot,
               "asymmetric": True,
               "lo_pct_from_statistic": round(100 * (float(lo) - theta) / theta, 2) if theta else None,
               "hi_pct_from_statistic": round(100 * (float(hi) - theta) / theta, 2) if theta else None}
        # At tiny n the bootstrap has no resolution: its 2.5/97.5 percentiles
        # ARE the sample extremes, so the "interval" is the observed range.
        out["equals_sample_range"] = bool(np.isclose(lo, a.min()) and np.isclose(hi, a.max()))
        # A heaped field can put most of the bootstrap mass on one atom.
        out["bootstrap_mass_at_point_estimate_pct"] = round(100 * float(np.mean(boot == theta)), 1)
        return out

    if n < min_n:
        if not allow_percentile_fallback:
            return None
        return _pct(f"n={n} below BCa floor {min_n}")
    prop = float(np.mean(boot < theta))
    if prop <= 0 or prop >= 1:
        return _pct("BCa undefined: degenerate bootstrap")
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
            "method": "BCa", "n": n, "n_boot": n_boot,
            "z0": round(float(z0), 4), "acceleration": round(float(acc), 5),
            "asymmetric": True,
            "lo_pct_from_statistic": round(100 * (float(lo) - theta) / theta, 2) if theta else None,
            "hi_pct_from_statistic": round(100 * (float(hi) - theta) / theta, 2) if theta else None,
            "equals_sample_range": bool(np.isclose(lo, a.min()) and np.isclose(hi, a.max())),
            "bootstrap_mass_at_point_estimate_pct": round(100 * float(np.mean(boot == theta)), 1)}


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


def deming(x, y, lam=1.0, log_space=True):
    """Orthogonal/Deming regression. OLS assumes the x variable is measured
    without error; when both sides are estimates (two salary sources, two
    price indices) OLS is biased toward zero slope. lam is the ratio of
    error variances, 1.0 when neither side is known to be more precise.

    Runs in LOG space by default. An adversarial review caught this running in
    raw dollars with lam=1 while the Bland-Altman on the identical pair ran in
    log space -- and the two then reported slopes on opposite sides of unity
    (1.125 raw vs 0.878 log). lam=1 in raw dollars asserts equal ABSOLUTE
    error variances, which is false here: the residual sd is materially larger
    in the upper half of the salary range than the lower. Errors are
    proportional, which is exactly why the Bland-Altman was put in log space,
    so the Deming belongs there too."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    if log_space:
        m &= (x > 0) & (y > 0)
    x, y = x[m], y[m]
    if log_space:
        x, y = np.log(x), np.log(y)
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
    return {"n": n, "space": "log" if log_space else "linear",
            "slope": round(float(slope), 4),
            "intercept": round(float(my - slope * mx), 4),
            "ols_slope": round(float(sxy / sxx), 4) if sxx else None,
            "lambda": lam}


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


def benford_mad(vals, homogeneous=False):
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
            "scale_span_ok": bool(orders >= 3),
            # Benford needs a single HOMOGENEOUS quantity. Pooling every numeric
            # leaf of a dataset (counts, percentages, prices, indices) breaks
            # that no matter how many orders of magnitude the pool spans, so
            # the span test alone must never be read as "precondition met".
            # An adversarial review found an earlier version reporting
            # precondition_met: true for all four pooled datasets, which is the
            # opposite of this finding's own conclusion.
            "homogeneous_quantity": bool(homogeneous),
            "precondition_met": bool(orders >= 3 and homogeneous),
            "interpretable": bool(orders >= 3 and homogeneous),
            "why_not_interpretable": None if (orders >= 3 and homogeneous) else (
                "spans fewer than 3 orders of magnitude" if orders < 3 else
                "pooled heterogeneous fields; Benford requires ONE homogeneous, scale-free "
                "quantity, and a wide pooled span does not satisfy that")}


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
    # The 30 US cities are ONE country; the 42 non-US cities are 14. Treating
    # 72 clustered observations as 72 independent draws inflates significance,
    # so the country-collapsed test is reported ALONGSIDE the raw one rather
    # than instead of it -- and neither is the headline, because the argument
    # for the conclusion is the non-statistical evidence below.
    by_country = defaultdict(list)
    for _, cc, v in y60:
        by_country[cc].append(v)
    non_us_country_medians = [st.median(v) for cc, v in by_country.items() if cc != "US"]
    us_country_median = st.median(by_country["US"])
    mw_country = stats.mannwhitneyu([us_country_median], non_us_country_medians,
                                    alternative="greater")
    finding("0-E", "implied US rental yields far above non-US", "REPRODUCED, CAUSE REATTRIBUTED",
            recipe="12 x rent_1br_outside / (60 m2 x apt_price_outside)",
            median_all_pct=round(100 * st.median([v for _, _, v in y60]), 2),
            max_pct=round(100 * max(v for _, _, v in y60), 2),
            us_median_pct=round(100 * st.median(us), 2),
            non_us_median_pct=round(100 * st.median(non), 2),
            mannwhitney_p_city_level=float(f"{mw.pvalue:.3e}"),
            mannwhitney_p_two_sided=float(f"{stats.mannwhitneyu(us, non, alternative='two-sided').pvalue:.3e}"),
            pseudo_replication={
                "problem": "the 30 US cities are ONE country and the 42 non-US cities are 14, so "
                           "the city-level test treats clustered observations as independent draws "
                           "and its p-value is inflated",
                "n_non_us_countries": len(non_us_country_medians),
                "us_country_median_pct": round(100 * us_country_median, 2),
                "non_us_country_median_pct": round(100 * st.median(non_us_country_medians), 2),
                "country_collapsed_p": float(f"{mw_country.pvalue:.3e}"),
                "caveat": "even the country-collapsed test has n=1 in the group of interest, so no "
                          "p-value here is a sound test of the US-vs-rest contrast. The DIRECTION "
                          "and SIZE of the gap are solid; the significance level is not, and the "
                          "conclusion below does not rest on it.",
            },
            us_median_at_centre_pct=round(100 * st.median(usc), 2),
            non_us_median_at_centre_pct=round(100 * st.median(nonc), 2),
            centre_mannwhitney_p=float(f"{stats.mannwhitneyu(usc, nonc, alternative='greater').pvalue:.3e}"),
            centre_test_is_not_independent={
                "spearman_centre_vs_outside_yield": round(float(stats.spearmanr(
                    [v for _, _, v in yc], [v for _, _, v in y60]).statistic), 4),
                "why_it_matters": "the centre test runs on the SAME 72 cities and its yields "
                                  "correlate strongly with the outside ones, so it is a "
                                  "near-duplicate of the first test rather than independent "
                                  "corroboration. It still rules OUT the centre/outside "
                                  "stock-composition story, which is what it was run for.",
            },
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
        r = benford_mad(vals, homogeneous=False)
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
    finding("2-B", "where this repo takes an arithmetic mean, and whether each is the wrong estimator",
            "NO ESTIMATOR DEFECT FOUND, THIRD REVISION OF THIS CLAIM",
            where_site="site/src/data/explore.ts meanPerYear(), 2 call sites (Teranet index, "
                       "UK HPI London price)",
            where_pipeline=[
                "scripts/src_climate_normals.py:124-125 — daily highs/lows averaged into a "
                "monthly normal. An 'average high' IS definitionally a mean; there is no "
                "alternative estimator to prefer. Measured anyway: |mean-median| across the 12 "
                "monthly values is 0.45 C median, 0.96 C max across 21 cities.",
                "scripts/src_indeed_postings.py:63 — ~30 daily index readings averaged into a "
                "monthly index. Same class as meanPerYear: a temporal average of a smooth "
                "series (month-over-month sd 5.3%), not a cross-sectional average over a "
                "skewed population.",
            ],
            where_cross_sectional=[
                "scripts/build_wage_distribution.py:389 — Qatar's overall mean wage as a "
                "count-weighted mean of the separately-published male and female MEANS. This IS "
                "a cross-sectional mean over a wage population, and a mean-of-means. It is also "
                "the arithmetically CORRECT way to pool two sub-population means into an overall "
                "mean, and Qatar publishes no median, so the site labels the result 'mean'. Not "
                "an estimator defect; but it falsifies any blanket 'no cross-sectional means' "
                "claim.",
                "site/src/data/compute.ts composite() — a weighted mean over normalised metric "
                "scores driving the weights tool. A mean of user-weighted scores, not of a "
                "skewed measured quantity.",
                "site/src/components/ClimateMatcher.tsx — a hand-rolled penalty average over "
                "climate dimensions. Same character.",
            ],
            arithmetic_midpoint_of_advertised_ranges={
                "where": "scripts/build_postings.py and scripts/rederive_postings_pay.py — every "
                         "posting is reduced to (usd.min + usd.max) / 2 before any median is "
                         "taken. That midpoint is the ATOM under gate 5, gate 9 and finding 2-C, "
                         "and it is an arithmetic mean of a right-skewed range, which is the very "
                         "thing 2-A quantifies as dangerous.",
                "measured_effect": "small, because advertised ranges are narrow: max/min has "
                                   "median 1.30 and p95 2.11. Median arithmetic midpoint 83,994 "
                                   "vs median geometric midpoint 82,285, a gap of +2.08%; "
                                   "per-range the two agree within 0.86% for the median row.",
                "verdict": "real, disclosed, and an order of magnitude smaller than the errors "
                           "2-A warns about -- but it should have been stated when the headline "
                           "numbers were first published, not after a review asked.",
            },
            correction="This claim has now been wrong TWICE and corrected twice. The first "
                       "version said the site takes exactly ONE arithmetic mean anywhere; that "
                       "search covered site/src only. The second added two Python temporal "
                       "averages and asserted that EVERY mean in the repo is temporal; an "
                       "adversarial review then found genuine cross-sectional means (Qatar's "
                       "pooled wage mean above) and, more importantly, the arithmetic midpoint "
                       "this package's own headline numbers are built on. The conclusion -- no "
                       "estimator DEFECT -- has survived both corrections, but the scope of the "
                       "claim was overstated each time, and a reader should weight the verdict "
                       "accordingly.",
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
    rows = []
    for r in post["pay_summary_by_country"]:
        v = by_cc[r["country"]]
        ci = bootstrap_ci(v, np.median, n_boot=10000)
        if ci is None:
            # Package 16 — the summary now lists every country with an annual
            # USD posting, so countries with n=2 reach here. bootstrap_ci
            # returns None rather than manufacture an interval from two points.
            # Recorded as uncomputable instead of skipped, so the row's absence
            # is never mistaken for the country being fine.
            rows.append({"country": r["country"], "n": len(v),
                         "published": r.get("median_as_published_usd_year"),
                         "ci_lo": None, "ci_hi": None,
                         "ci_method": "not computable",
                         "why_no_interval": f"n={len(v)} is below the minimum at which a bootstrap "
                                            f"of the median describes anything"})
            continue
        rows.append({"country": r["country"], "n": len(v),
                     # Package 16 — a country below the publication floor no
                     # longer carries a median at all, which is the point of the
                     # floor. The as-published figure (every occupation,
                     # duplicates included) is what this comparison wants, and it
                     # is kept under its own name precisely so the two are never
                     # confused.
                     "published": r.get("median_as_published_usd_year") or r.get("median_usd_year"),
                     "ci_lo": round(ci["lo"]), "ci_hi": round(ci["hi"]),
                     "ci_method": ci["method"],
                     # reported as SIGNED, ASYMMETRIC deviations: these intervals
                     # are not symmetric and a single +/- figure misrepresents
                     # them (GB is -4.3%/+26.1%, FR -17.4%/+66.7%).
                     "lo_pct": ci["lo_pct_from_statistic"],
                     "hi_pct": ci["hi_pct_from_statistic"],
                     "interval_is_just_the_sample_range": ci["equals_sample_range"],
                     "bootstrap_mass_on_point_estimate_pct": ci["bootstrap_mass_at_point_estimate_pct"]})
    thin = [r for r in rows if r["n"] < 12]
    # Rows too thin for ANY interval carry no lo_pct/hi_pct at all. Ranking over
    # them with `or 0` would silently treat "no interval" as "a zero-width
    # interval" and could hand the "widest" title to the wrong country, so they
    # are excluded from the ranking and counted separately instead.
    measurable = [r for r in rows if r.get("lo_pct") is not None and r.get("hi_pct") is not None]
    finding("2-C", "published advertised medians carry precision the sample cannot support",
            "DEFECT",
            per_country=rows,
            n_countries_published=len(rows),
            n_below_min_n_for_a_distributional_claim=len(thin),
            n_with_no_computable_interval_at_all=len(rows) - len(measurable),
            widest=({"country": max(measurable, key=lambda r: r["hi_pct"] - r["lo_pct"])["country"],
                     "span_pct": round(max(r["hi_pct"] - r["lo_pct"] for r in measurable), 1)}
                    if measurable else None),
            n_intervals_that_are_just_the_sample_range=sum(
                1 for r in rows if r.get("interval_is_just_the_sample_range")),
            method_note="BCa where n permits, percentile below n=12, and each row states which it "
                        "got. An adversarial review found an earlier version computing percentile "
                        "intervals inline while the report claimed BCa; the BCa implementation was "
                        "self-tested but never actually called.",
            interval_caveats="These intervals are strongly ASYMMETRIC and are reported as signed "
                             "lo/hi deviations rather than a single +/-. At the smallest n the "
                             "bootstrap has no resolution and its 2.5/97.5 percentiles are simply "
                             "the sample min and max, which is flagged per row. For the US, most "
                             "of the bootstrap mass sits on a single heaped value, so its very "
                             "narrow interval reflects heaping as much as precision.",
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

    # Mahalanobis on this matrix is a LEAKAGE trap, and an adversarial review
    # caught it as the same failure gate 6 declined a gradient-boosted residual
    # model to avoid. Three of these nine features are definitional functions
    # of the others (3-C), so the covariance matrix has near-null directions
    # that ARE those identities -- and the quadratic form weights a direction
    # by the INVERSE of its variance, i.e. maximally. np.linalg.pinv does not
    # rescue this: it keeps full rank and silently inverts a badly conditioned
    # matrix, which is worse than failing.
    cov = np.cov(Z.T)
    evals = np.linalg.eigvalsh(cov)
    cond = float(evals[-1] / evals[0]) if evals[0] > 0 else float("inf")
    d = Z - Z.mean(0)
    md = np.sqrt(np.einsum("ij,jk,ik->i", d, np.linalg.pinv(cov), d))
    # how much of the distance comes from the near-null (identity) directions?
    w, V = np.linalg.eigh(cov)
    proj = (d @ V) ** 2 / np.maximum(w, 1e-12)
    share_smallest3 = float(proj[:, :3].sum() / proj.sum())
    mah = md > np.sqrt(stats.chi2.ppf(0.975, Z.shape[1]))

    # An INDEPENDENT-FEATURE variant: drop the three derived features so no
    # identity can dominate. This is the one whose flags are interpretable.
    indep_idx = [i for i, f in enumerate(FEATS) if not f.startswith("computed.")]
    Zi = Z[:, indep_idx]
    covi = np.cov(Zi.T)
    di = Zi - Zi.mean(0)
    mdi = np.sqrt(np.einsum("ij,jk,ik->i", di, np.linalg.inv(covi), di))
    mah_indep = mdi > np.sqrt(stats.chi2.ppf(0.975, Zi.shape[1]))

    votes = iso.astype(int) + lof.astype(int) + mah_indep.astype(int)
    finding("3-A", "multivariate outlier cities, three methods", "QUANTIFIED, WITH TWO CAVEATS",
            n_cities=len(ids), features=FEATS, space="log",
            flagged_by_2_or_3_methods=[ids[i] for i in np.where(votes >= 2)[0]],
            flagged_by_exactly_1_method=[ids[i] for i in np.where(votes == 1)[0]],
            mahalanobis_leakage={
                "problem": "on the full 9-feature matrix, Mahalanobis measures deviation from "
                           "identities the pipeline computed itself -- the same failure gate 6 "
                           "declined a GBM residual model to avoid",
                "covariance_condition_number": round(cond, 1),
                "share_of_squared_distance_from_3_smallest_eigen_directions":
                    round(share_smallest3, 4),
                "fix": "the reported votes use a Mahalanobis computed on the SIX independently "
                       "sourced features only (the three computed.* fields dropped), so no "
                       "definitional identity can drive a flag",
                "flags_full_matrix": [ids[i] for i in np.where(mah)[0]],
                "flags_independent_features_only": [ids[i] for i in np.where(mah_indep)[0]],
            },
            contamination_artefact={
                "problem": "IsolationForest and LocalOutlierFactor were both given "
                           "contamination=0.1, so each flags exactly 10% of cities BY "
                           "CONSTRUCTION. Neither can ever return 'no multivariate outliers', "
                           "and most of the votes below are set by that parameter rather than "
                           "by the data.",
                "iso_flagged": int(iso.sum()), "lof_flagged": int(lof.sum()),
                "mahalanobis_flagged": int(mah_indep.sum()),
                "only_the_mahalanobis_count_is_data_driven": True,
            },
            distributional_caveat="the chi-square(9) cut assumes joint multivariate normality "
                                  "with KNOWN mean and covariance; both are estimated here from "
                                  "n=72, for which a Beta-based cut is the correct reference. "
                                  "Checked: it changes the cut from 19.02 to 17.68 and flags the "
                                  "same cities, so this is a disclosure issue rather than a "
                                  "result issue.",
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

    # H2: the site plots the ANNUAL mean, and an earlier version of this finding
    # called that "a mitigation rather than an error" without ever testing it.
    # Averaging 12 points does cut the noise by sqrt(12) -- but the residual
    # noise that survives is still LARGER than the real year-on-year signal.
    annual = {}
    for city, rec in ter.items():
        s = np.array([r["index"] for r in rec["series"]], float)
        x = np.arange(s.size)
        resid = np.log(s) - np.polyval(np.polyfit(x, np.log(s), 3), x)
        per_pt = float(resid.std(ddof=1))
        by = defaultdict(list)
        for r in rec["series"]:
            by[r["date"][:4]].append(r["index"])
        yrs = sorted(y for y, v in by.items() if len(v) >= 6)
        ann = [st.mean(by[y]) for y in yrs]
        yoy = [100 * (ann[i] - ann[i - 1]) / ann[i - 1] for i in range(1, len(ann))]
        # The trend must not be read off the ENDPOINTS. A CAGR is
        # ann[-1]/ann[0], which inherits the error in both -- the very error
        # this finding exists to report -- so calling it "the true trend" was
        # self-contradictory. Package 16 found it while building the site's
        # replacement for the plotted level. A log-linear OLS slope over all
        # ~28 annual points averages the per-observation noise down instead of
        # concentrating it in two values, and it moves the answer materially:
        # Vancouver reads 3.1%/yr by CAGR and 4.4%/yr by slope. Both are
        # reported, the slope is the one to quote, and the CONCLUSION is
        # unchanged either way -- noise alone implies a year-over-year spread
        # of 7.0-8.7%, which still exceeds the trend on either estimator.
        ax = np.arange(len(ann), dtype=float)
        ly = np.log(np.asarray(ann, float))
        slope = float(np.polyfit(ax, ly, 1)[0])
        trend = 100 * (math.exp(slope) - 1)
        cagr = 100 * ((ann[-1] / ann[0]) ** (1 / (len(ann) - 1)) - 1)
        annual[city] = {
            "per_point_log_noise_pct": round(100 * per_pt, 1),
            "implied_annual_mean_noise_pct": round(100 * per_pt / math.sqrt(12), 1),
            "implied_yoy_sd_from_noise_alone_pct": round(100 * per_pt / math.sqrt(12) * math.sqrt(2), 1),
            "observed_yoy_sd_pct": round(float(np.std(yoy)), 1),
            "trend_pct_per_year_log_linear_slope": round(trend, 1),
            "trend_pct_per_year_endpoint_cagr": round(cagr, 1),
            "trend_estimator_note": "quote the slope. The CAGR is a ratio of the first and last "
                                    "annual values and inherits the per-observation noise in both, "
                                    "which is the defect this finding reports.",
            "annual_series_residual_acf_lag1": (injected_noise_test(ann, city) or {}).get("residual_acf_lag1"),
        }

    # M6: the payload's own blocks are mutually inconsistent. indx_ch must be
    # the month-over-month change of indx; it is not, by any reading.
    raw = json.loads((ROOT / "data" / "raw" / "teranet_national_bank_hpi" /
                      "indx_data.json").read_text(encoding="utf-8"))["data"]
    i_ser = [x for x in raw["indx"]["on_toronto"] if x is not None]
    ch = [x for x in raw["indx_ch"]["on_toronto"] if x is not None]
    implied = [100 * (i_ser[k] - i_ser[k - 1]) / i_ser[k - 1] for k in range(1, len(i_ser))]
    m = min(len(implied), len(ch))
    internal = {
        "indx_implied_mom_pct_negative": round(100 * sum(1 for v in implied if v < 0) / len(implied), 1),
        "indx_ch_pct_negative": round(100 * sum(1 for v in ch if v < 0) / len(ch), 1),
        "correlation_between_them": round(float(np.corrcoef(implied[:m], ch[:m])[0, 1]), 4),
        "verdict": "indx_ch is defined as the change in indx and cannot be: it is never negative "
                   "across 27 years while indx implies a negative change in half of all months, "
                   "and the two are uncorrelated. The payload's blocks do not cohere with each "
                   "other, so this is not one noisy series inside an otherwise sound feed.",
    }

    finding("6-A", "Teranet's series is unusable except as a multi-year trend", "DEFECT",
            test="residual autocorrelation about a cubic trend, plus month-over-month ACF",
            results=res,
            flagged=[kk for kk, vv in res.items() if vv["looks_like_injected_noise"]],
            annual_series_is_NOT_sound=annual,
            annual_verdict="An earlier version of this finding said the annual mean the site "
                           "plots was 'a mitigation rather than an error'. That was never tested "
                           "and it is wrong. Averaging 12 monthly points cuts the per-observation "
                           "noise (17-21%) to about 5-6% on the annual level, which implies a "
                           "year-on-year sd of 7.0-8.7% from noise ALONE -- and the observed "
                           "year-on-year sd is 6.7-10.8%, against a true underlying trend of only "
                           "3.1-4.1% a year. Year-to-year movement in the published annual series "
                           "is therefore dominated by noise, not signal. Only a multi-year trend "
                           "survives.",
            payload_internal_inconsistency=internal,
            note="Every Teranet city reads residual ACF 0.07-0.27 with MoM ACF near -0.44. The "
                 "two CONTROL indices in this same repo -- UK HPI and FHFA, both real published "
                 "house-price indices -- read residual ACF 0.985. A genuine price index is "
                 "persistent; independent per-point noise destroys that persistence and drives "
                 "the month-over-month autocorrelation negative. The long-run trend survives "
                 "(Spearman(time, index) = 0.909 for Toronto) and the stated base holds exactly "
                 "(2005-06 = 100.0 for every city), so this is jitter around a real index rather "
                 "than a broken parse. The pipeline transcribes the endpoint faithfully; the "
                 "endpoint is undocumented and the index is proprietary, which is the most "
                 "likely explanation -- though the block-level inconsistency above means "
                 "'faithfully transcribed but jittered' is too generous a reading: the feed is "
                 "internally incoherent, not merely noisy. Consequence: neither a monthly value "
                 "NOR a year-on-year change is interpretable. Only the multi-year trend "
                 "(Spearman with time 0.909) survives.")


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
    dm = deming(xo, yo, log_space=False)  # additive-error scenario: linear is the right space
    ck("Deming slope closer to 1 than OLS when both sides carry error",
       abs(dm["slope"] - 1) < abs(dm["ols_slope"] - 1),
       f"deming={dm['slope']} ols={dm['ols_slope']}")
    # The audit runs Deming in LOG space, because the real pair has
    # proportional error. Assert the default is that, so the space the
    # self-test blesses is the space the audit uses.
    ck("Deming defaults to the log space the audit actually uses",
       deming(xo, yo)["space"] == "log", deming(xo, yo)["space"])
    # And that a percentile fallback is labelled rather than passed off as BCa.
    tiny = bootstrap_ci([1.0, 2, 3, 4, 5], np.median, n_boot=500)
    ck("small-n interval is labelled percentile, not silently called BCa",
       tiny["method"].startswith("percentile") and tiny["equals_sample_range"],
       f"{tiny['method']} range-only={tiny['equals_sample_range']}")

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
    bg = benford_mad(good.tolist(), homogeneous=True)
    bb = benford_mad(bad.tolist(), homogeneous=True)
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
