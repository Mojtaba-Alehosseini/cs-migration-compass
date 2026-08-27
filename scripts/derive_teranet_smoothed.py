"""Package 21, Tier 1, item #43 — recover Teranet's signal instead of disclosing
it away.

Package 15/16 measured that Teranet's monthly index carries per-observation
noise larger than the trend it describes (residual autocorrelation 0.11-0.27
against 0.985 for two real published indices) and concluded "no single value
is interpretable, monthly or annual." That conclusion is correct about the RAW
series and goes no further than that: month-over-month differences show a
lag-1 autocorrelation near -0.5 for every city, the textbook signature of a
smooth signal plus independent additive noise -- a signature that, if it
holds, means the trend is recoverable with a noise model, not just discardable.

This script fits that model (a state-space local linear trend, i.e. a Kalman
smoother) per city, estimates how much of the noise is real signal, and checks
the recovered trend against an INDEPENDENT source -- OECD's own Canadian house
price index -- rather than trusting the model's own goodness-of-fit. A
recovered signal that tracks OECD is a recovered signal; one that doesn't is a
smoothing artefact, and this script reports it as such per city rather than
assuming every city passes because most do.

Reads two already-processed, already-committed files and writes a NEW derived
one -- data/processed/teranet_national_bank_hpi.json (the raw series) is never
opened for writing by this script, only for reading. Smoothing is a derived
layer on top of the raw data, never a replacement for it.

    python scripts/derive_teranet_smoothed.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, banner, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "teranet_smoothed"
NAME = "Teranet–National Bank HPI, Kalman-smoothed with OECD cross-validation"
INPUT_SOURCE_ID = "teranet_national_bank_hpi"
Z95 = 1.959963985425145  # two-sided 95% normal critical value

# EARLIER DESIGNS, KEPT AS COMMENTS BECAUSE THE FAILURES THEY DOCUMENT ARE
# THE REASON THE CURRENT DESIGN EXISTS. Two rounds, both found by adversarial
# review before this shipped, not by inspection:
#
# Round 1 -- the comparison basis. The first version correlated quarterly
# LEVELS (smoothed vs OECD) and required >=0.85. Direct testing proved that
# unsafe: substituting pure i.i.d. noise for a real city's raw series,
# smoothing it with the SAME model, and correlating LEVELS against the SAME
# real OECD series produced |corr| 0.9-0.97 for 5 of 6 cities -- one of them
# (Montreal) landed on the POSITIVE side and would have "passed" outright on
# pure noise. This is the textbook spurious-regression problem: any two
# series with a slow drift correlate at the level whether or not the drifts
# share a cause. Fixed by differencing before correlating (below), which
# removes the shared trend structure.
#
# Round 2 -- the null hypothesis itself. Differencing needed a threshold, and
# an asserted one (however defensible-sounding) is still just asserted until
# it's shown to separate real cities from noise on THIS data -- which is what
# a Monte Carlo null test is for. The FIRST version of that null simulated
# i.i.d. noise (matched to the city's own raw mean/sd/length) and fit the
# SAME model to it. That is unsafe in the opposite direction from round 1's
# defect: MLE-fitting a local-linear-trend model to i.i.d. noise drives the
# trend-innovation variances to ~0 (there is no genuine trend-shaped
# structure in pure noise for the model to find), so the "smoothed" fit
# collapses to a dead-straight line -- a null with almost no real
# variability, far too easy for a genuine but OECD-unrelated trend to beat.
# Verified live: that null's own reported standard deviation sat BELOW the
# elementary large-sample benchmark for two INDEPENDENT series of the same
# length (1/sqrt(k-1)) for every one of the six cities -- a null for an
# autocorrelated series must be WIDER than that benchmark, never narrower.
# Two cities (Calgary, Montreal) cleared that too-weak null and would have
# shipped as "RECOVERED" on evidence that, re-measured against the corrected
# null below, does not clear it (p=0.078-0.095 against the required 0.05).
#
# Fixed by resampling from the FITTED process instead of i.i.d. noise:
# `_null_pvalue`'s own docstring has the full account.
#
# A city's recovered trend counts as validated only if ALL of:
#   1. the DIFFERENCED correlation (quarter-over-quarter change, not level)
#      against OECD is positive;
#   2. it does not measurably underperform the same differenced correlation
#      computed on the raw, unsmoothed series (the -0.02 slack absorbs
#      sampling noise over ~110-150 quarterly differences, not a wide berth);
#   3. a Monte Carlo null test rejects "this could plausibly be this city's
#      own genuine trend-wandering, unrelated to OECD": a parametric
#      bootstrap from the city's own fitted noise model, run through the
#      IDENTICAL fit -> quarterly -> difference -> correlate pipeline against
#      the SAME real OECD series, produces a correlation this large or larger
#      no more than 5% of the time.
VALIDATION_MAX_SHORTFALL_VS_RAW = 0.02
VALIDATION_MAX_P_VALUE = 0.05
NULL_DRAWS = 500
# Fixed, not derived from wall-clock time: this script's own output must be
# byte-reproducible on a re-run against the same input, which a time-seeded
# RNG would break.
NULL_SEED_BASE = 20260827

# A Monte Carlo p-value's own standard error shrinks as 1/sqrt(n_draws)
# (~sqrt(p(1-p)/n) at p near VALIDATION_MAX_P_VALUE) -- a FIXED margin
# applied at every draw count is wrong on its own terms: adversarial review
# (package 21) found the first version of this refinement used the SAME
# 0.02 margin to decide whether the REFINED (5,000-draw) result was itself
# still borderline, when the refined tier's own margin should be ~3x
# tighter (SE ~0.003 at 5,000 draws vs ~0.01 at 500) -- a result landing
# exactly on the first margin's boundary was never re-checked against the
# tighter one it should have earned. `_borderline_margin()` below scales
# with the draw count actually used, not a single constant reused at every
# tier.
_MARGIN_Z = 1.96  # 95% two-sided normal critical value, matching Z95 in spirit


def _borderline_margin(n_draws: int) -> float:
    p = VALIDATION_MAX_P_VALUE
    return _MARGIN_Z * (p * (1 - p) / n_draws) ** 0.5


REFINED_NULL_DRAWS = 5000


def _quarterly_mean(dates: list[str], values: np.ndarray) -> dict[str, float]:
    """'YYYY-MM' + value -> {'YYYY-Qn': mean of that quarter's months}.

    Mean-of-months, not last-month: explore.ts's own convention for this
    exact source ("Teranet, UK monthly price -> the MEAN of the year's
    months... these are transaction prices, so the year's average is the
    real quantity") applies at quarterly resolution for the same reason.
    """
    buckets: dict[str, list[float]] = {}
    for d, v in zip(dates, values):
        y, m = d.split("-")
        q = (int(m) - 1) // 3 + 1
        buckets.setdefault(f"{y}-Q{q}", []).append(float(v))
    return {k: float(np.mean(v)) for k, v in buckets.items()}


def _log_linear_pct_per_year(dates: list[str], values: np.ndarray) -> float | None:
    """OLS slope of log(annual mean) on calendar year -> annualised % change.

    Same method AND same resolution as the frontend's own trendPctPerYear()
    (Housing.tsx): annual means first, then a log-linear slope over the whole
    series -- an endpoint ratio inherits the noise of both endpoints, a
    regression over ~28 annual points averages it down. Reducing to annual
    means BEFORE the regression (rather than regressing the 337 monthly
    points directly) is deliberate, not a resolution downgrade: partial
    first/last calendar years (1998 has 7 months, 2026 has 6) would otherwise
    get the same regression weight as a full year, which measurably moves the
    slope (verified: 5.02%/yr monthly vs 4.94%/yr annual for Toronto, a
    partial-year weighting artefact, not a smoothing one -- both raw and
    smoothed monthly regressions shift by about the same amount). Annual
    means also keep this number directly comparable to package 16's own
    disclosed 3.1-4.9%/yr range, computed the same way on the raw series.
    """
    by_year: dict[int, list[float]] = {}
    for d, v in zip(dates, values):
        if not np.isfinite(v) or v <= 0:
            continue
        by_year.setdefault(int(d[:4]), []).append(float(v))
    if len(by_year) < 8:
        return None
    years = np.array(sorted(by_year), dtype=float)
    means = np.array([np.mean(by_year[int(y)]) for y in years])
    x = years - years.mean()
    y = np.log(means) - np.log(means).mean()
    den = float((x ** 2).sum())
    if den == 0:
        return None
    slope = float((x * y).sum() / den)
    return (float(np.exp(slope)) - 1.0) * 100.0


def _null_pvalue(dates: list[str], n: int, fitted_params: dict[str, float], initial_state: np.ndarray,
                  oecd_q: dict[str, float], observed_diff_corr: float, seed: int,
                  n_draws: int = NULL_DRAWS) -> dict:
    """A PARAMETRIC BOOTSTRAP from this city's own fitted noise model: how
    often does a local-linear-trend process carrying EXACTLY this city's own
    MLE-estimated innovation variances (sigma2.irregular/level/trend) --
    genuine autocorrelated trend-wandering, at this city's own measured
    scale, but with NO relationship to OECD built in, a fresh random walk
    every draw -- produce a differenced correlation against the SAME real
    OECD series this large or larger, by chance alone?

    NOT i.i.d. noise, which an earlier version of this function used and
    which adversarial review (package 21) proved unsafe in the OTHER
    direction from the levels-correlation defect this module's own docstring
    already documents: MLE-fitting a local-linear-trend model to i.i.d.
    noise drives sigma2.level and sigma2.trend to ~0 (there is no genuine
    trend-shaped structure in pure noise for the model to find), so the
    "smoothed" fit collapses to a dead-straight line -- a null with almost
    no real variability, far too easy for a genuine but unrelated trend to
    beat. Verified live: the i.i.d.-noise null's own reported standard
    deviation sat BELOW the elementary large-sample benchmark for two
    INDEPENDENT series of the same length (1/sqrt(k-1)) for every one of the
    six cities, and the inversion is what let Calgary and Montreal clear a
    null too weak to mean anything. That benchmark turned out not to be the
    right floor for THIS design either, though, once anchoring (below) was
    added: anchoring deliberately makes every draw share the real fit's own
    starting level and slope, a MORE CONSTRAINED null than "two independent
    series", and even healthy real-city parameters now sit below it too
    (verified live across all six committed cities). What actually
    distinguishes a healthy fit from the collapsed one above is
    sigma2.level specifically -- holding sigma2.irregular fixed, a
    collapsed sigma2.level reproducibly narrows null_sd to roughly half of
    what a healthy one produces (see the test suite's own controlled
    comparison, not a fixed external benchmark). This version
    resamples from the actual fitted process instead: each draw is refit
    with the identical model, so the null's own difficulty adapts to how
    much genuine wandering this SPECIFIC city's data actually supports.

    A SECOND bug, found the same way (adversarial review, running the FIRST
    version of this parametric bootstrap against real data before trusting
    it): simulating from an unanchored/default initial state lets a local-
    linear-trend process explode. The model integrates its own slope TWICE
    (level absorbs slope, slope is itself a random walk) over n~300-430
    steps -- even the tiny fitted sigma2.trend values compound into a slope
    that can drift arbitrarily far from zero, and an unanchored simulation
    starting near 0 (Montreal, verified live) produced synthetic series
    ranging into the HUNDREDS OF THOUSANDS (real index values run 80-430).
    Those explosive draws do not represent "this city's genuine trend,
    unrelated to OECD" -- they represent an unconstrained mathematical
    edge case a real house-price index never approaches, and their own
    differenced correlation with OECD came out as near-pure noise
    (|corr| mostly under 0.02), making the resulting null artificially
    EASY to beat -- the opposite failure from the i.i.d. bug, arrived at by
    a different path, and it flipped Montreal's own verdict: unanchored,
    p=0.004-0.01 (passes); anchored to this city's own real starting
    level and slope (below), the null is properly calibrated to the
    city's own realistic scale. Fixed by anchoring every simulated draw to
    the REAL fit's own initial state (level and slope at t=0) -- the
    alternative universe this null represents starts exactly where the
    real data does, and only the innovations differ draw to draw.
    """
    rng = np.random.default_rng(seed)

    # The OECD side of the comparison does not depend on the draw -- the
    # quarters it overlaps with this city's own date axis, and whether its
    # own differenced series is degenerate (zero variance -- see _fit_city's
    # own guard for why that matters), are the same every iteration. Checked
    # once, outside the loop, rather than n_draws times for the same answer.
    # Zeros, not real values -- only the quarter KEYS are needed here (the
    # bucketing depends on `dates` alone, confirmed by _fit_city's own
    # identical use), and this function has no raw series to draw them from
    # by design: the null must not depend on any particular noise draw.
    all_common = sorted(set(_quarterly_mean(dates, np.zeros(n))) & set(oecd_q))
    do = np.diff([oecd_q[k] for k in all_common])
    if len(all_common) < 9 or do.std() == 0:
        return {"n_draws": 0, "null_mean": None, "null_sd": None, "null_p95": None, "p_value": None}

    params = np.array([fitted_params["sigma2.irregular"], fitted_params["sigma2.level"],
                        fitted_params["sigma2.trend"]])
    template = sm.tsa.UnobservedComponents(np.zeros(n), level="local linear trend")

    null_corrs: list[float] = []
    for _ in range(n_draws):
        synthetic = np.asarray(template.simulate(params, nsimulations=n, initial_state=initial_state))
        mod = sm.tsa.UnobservedComponents(synthetic, level="local linear trend")
        res = mod.fit(disp=False, maxiter=200)
        if not res.mle_retvals.get("converged", False):
            continue
        q_sim = _quarterly_mean(dates, res.smoothed_state[0])
        # No `if common != all_common` guard here (an earlier version had
        # one): _quarterly_mean's own keys depend on `dates` alone, which is
        # fixed and identical to what produced all_common above -- the two
        # sets are provably always equal, and adversarial review confirmed
        # the guard could never fire. Removed rather than kept as unreachable
        # defensive code.
        dn = np.diff([q_sim[k] for k in all_common])
        if dn.std() == 0:
            continue
        null_corrs.append(float(np.corrcoef(dn, do)[0, 1]))

    arr = np.array(null_corrs, dtype=float)
    if arr.size == 0:
        return {"n_draws": 0, "null_mean": None, "null_sd": None, "null_p95": None, "p_value": None}
    # (+1)/(n+1), not the raw k/n: a Monte Carlo p-value of exactly 0.0 from
    # a finite sample overclaims precision it doesn't have -- with zero
    # exceedances in n draws the honest statement is "smaller than about
    # 1/n", not "exactly zero" (Davison & Hinkley's own convention for
    # permutation/bootstrap p-values). Adversarial review finding: this
    # module previously reported a bare 0.0, and the frontend rendered that
    # as literal "p=0.000".
    exceed = int(np.sum(arr >= observed_diff_corr))
    return {
        "n_draws": int(arr.size),
        "null_mean": float(arr.mean()),
        "null_sd": float(arr.std()),
        "null_p95": float(np.percentile(arr, 95)),
        # One-sided: the hypothesis under test is genuine POSITIVE co-movement
        # with OECD, not merely a correlation magnitude distinguishable from
        # zero in either direction.
        "p_value": float((exceed + 1) / (arr.size + 1)),
    }


def _fit_city(dates: list[str], raw: np.ndarray, oecd_q: dict[str, float],
              null_seed: int | None = None, null_draws: int = NULL_DRAWS) -> dict:
    mod = sm.tsa.UnobservedComponents(raw, level="local linear trend")
    res = mod.fit(disp=False, maxiter=200)
    converged = bool(res.mle_retvals.get("converged", False))
    noise = dict(zip(mod.param_names, (float(p) for p in res.params)))

    smoothed = res.smoothed_state[0]
    se = np.sqrt(np.clip(res.smoothed_state_cov[0, 0, :], 0, None))

    d_raw = np.diff(raw)
    d_smooth = np.diff(smoothed)
    signal_share_pct = (
        100.0 * float(d_smooth.var() / d_raw.var()) if d_raw.var() > 0 else None
    )
    harvey_q = (
        noise["sigma2.level"] / noise["sigma2.irregular"]
        if noise.get("sigma2.irregular") else None
    )

    q_raw = _quarterly_mean(dates, raw)
    q_smooth = _quarterly_mean(dates, smoothed)
    common = sorted(set(q_smooth) & set(oecd_q))
    common_raw = sorted(set(q_raw) & set(oecd_q))
    n_overlap = len(common)

    corr_smooth_level = corr_raw_level = None
    corr_smooth_diff = corr_raw_diff = None
    null = None
    passed = False

    if n_overlap >= 8:
        q_smooth_vals = np.array([q_smooth[k] for k in common])
        q_oecd_vals = np.array([oecd_q[k] for k in common])
        q_raw_vals = np.array([q_raw[k] for k in common_raw])
        q_oecd_raw_vals = np.array([oecd_q[k] for k in common_raw])
        # np.corrcoef divides by each array's own stddev -- a constant array
        # (zero variance) produces NaN, not an error, and NaN survives
        # straight into json.dumps as literal `NaN`, invalid JSON that
        # Python's encoder writes anyway. Verified reachable: a reference
        # series with a perfectly straight (zero-curvature) trend has
        # constant DIFFERENCES by construction -- real OECD/Teranet data
        # never is, but "never in practice" is not a guarantee, and a
        # guarded None is a legible result where an unguarded NaN is not.
        if q_smooth_vals.std() > 0 and q_oecd_vals.std() > 0:
            corr_smooth_level = float(np.corrcoef(q_smooth_vals, q_oecd_vals)[0, 1])
        if q_raw_vals.std() > 0 and q_oecd_raw_vals.std() > 0:
            corr_raw_level = float(np.corrcoef(q_raw_vals, q_oecd_raw_vals)[0, 1])

        dq_smooth = np.diff(q_smooth_vals)
        dq_oecd = np.diff(q_oecd_vals)
        dq_raw = np.diff(q_raw_vals)
        dq_oecd_raw = np.diff(q_oecd_raw_vals)
        if dq_smooth.std() > 0 and dq_oecd.std() > 0:
            corr_smooth_diff = float(np.corrcoef(dq_smooth, dq_oecd)[0, 1])
        if dq_raw.std() > 0 and dq_oecd_raw.std() > 0:
            corr_raw_diff = float(np.corrcoef(dq_raw, dq_oecd_raw)[0, 1])

        if null_seed is not None and corr_smooth_diff is not None:
            null = _null_pvalue(dates, len(raw), noise, res.smoothed_state[:, 0], oecd_q,
                                 corr_smooth_diff, null_seed, n_draws=null_draws)

        passed = bool(
            converged
            and corr_smooth_diff is not None
            and corr_raw_diff is not None
            and corr_smooth_diff > 0
            and corr_smooth_diff >= corr_raw_diff - VALIDATION_MAX_SHORTFALL_VS_RAW
            and null is not None
            and null["p_value"] is not None
            and null["p_value"] <= VALIDATION_MAX_P_VALUE
        )

    return {
        "mle_converged": converged,
        "noise": {
            "sigma2_irregular": noise.get("sigma2.irregular"),
            "sigma2_level": noise.get("sigma2.level"),
            "sigma2_trend": noise.get("sigma2.trend"),
            "harvey_q": harvey_q,
            "harvey_q_note": "sigma2_level / sigma2_irregular -- the standard structural-"
                              "time-series signal-to-noise ratio; small q means the level "
                              "barely moves relative to observation noise.",
            "signal_share_pct": signal_share_pct,
            "signal_share_note": "var(diff(smoothed)) / var(diff(raw)) x 100 -- a CONSERVATIVE, "
                                  "SHRUNK estimate of the share of raw month-to-month VARIANCE "
                                  "attributable to genuine trend movement: the Kalman SMOOTHER "
                                  "itself dampens the estimated trend to avoid overfitting single "
                                  "noisy points, so this reads lower than the model's own implied "
                                  "share (model_implied_signal_share_pct below) -- never higher. "
                                  "Adversarial review, package 21: an earlier version of this note "
                                  "did not say 'conservative', which read as a precise figure when "
                                  "it is a lower bound.",
            "model_implied_signal_share_pct": (
                100.0 * noise["sigma2.level"] / (noise["sigma2.level"] + 2 * noise["sigma2.irregular"])
                if noise.get("sigma2.irregular") else None
            ),
            "model_implied_signal_share_note": "sigma2_level / (sigma2_level + 2*sigma2_irregular) x "
                                                "100 -- the share of raw month-to-month VARIANCE the "
                                                "fitted model itself implies is genuine trend "
                                                "movement (var(diff(raw)) ~= sigma2_level + "
                                                "2*sigma2_irregular for a local-linear-trend "
                                                "process), before the smoother's own shrinkage. "
                                                "Typically several times signal_share_pct, not a "
                                                "contradiction of it -- the two answer 'how much "
                                                "trend does the fitted MODEL say is there' vs 'how "
                                                "much trend did the smoothed OUTPUT actually keep'.",
        },
        "validation": {
            "n_quarters_overlap": n_overlap,
            "corr_smoothed_vs_oecd_levels": corr_smooth_level,
            "corr_raw_vs_oecd_levels": corr_raw_level,
            "levels_corr_caveat": "NOT the validation basis -- verified directly (see module "
                                   "docstring) that smoothed pure noise can show 0.9+ level-"
                                   "correlation with an unrelated real trend. Shown for "
                                   "reference only; corr_*_diff and null_test below decide "
                                   "'passed'.",
            "corr_smoothed_vs_oecd_diff": corr_smooth_diff,
            "corr_raw_vs_oecd_diff": corr_raw_diff,
            "diff_note": "Correlation of QUARTER-OVER-QUARTER CHANGES, not levels -- removes "
                         "the shared trend structure that makes levels-correlation spurious-"
                         "prone on two series that both drift.",
            "null_test": null,
            "passed": passed,
        },
        "trend_pct_per_year": _log_linear_pct_per_year(dates, smoothed),
        "series": [
            {
                "date": d,
                "smoothed": round(float(s), 3),
                "lo95": round(float(s - Z95 * e), 3),
                "hi95": round(float(s + Z95 * e), 3),
            }
            for d, s, e in zip(dates, smoothed, se)
        ],
    }


def run() -> None:
    banner(SOURCE_ID, NAME)
    raw_doc = json.loads((PROCESSED / f"{INPUT_SOURCE_ID}.json").read_text(encoding="utf-8"))
    oecd_doc = json.loads((PROCESSED / "oecd_indicators.json").read_text(encoding="utf-8"))
    oecd_q = {
        r["period"]: float(r["value"])
        for r in oecd_doc["data"]["CA"]["house_prices"]["HPI_YDH_IX"]
    }

    def _run_and_log(city: str, seed: int, null_draws: int, tag: str) -> dict:
        block = raw_doc["data"]["cities"][city]
        series = block["series"]
        dates = [r["date"] for r in series]
        raw = np.array([r["index"] for r in series], dtype=float)
        fit = _fit_city(dates, raw, oecd_q, null_seed=seed, null_draws=null_draws)
        v = fit["validation"]
        status = "RECOVERED" if v["passed"] else "FALLBACK (raw disclosure stands)"
        share = fit["noise"]["signal_share_pct"]
        cd = v["corr_smoothed_vs_oecd_diff"]
        p = v["null_test"]["p_value"] if v["null_test"] else None
        log(f"    {tag}{city:10s} signal_share={share:6.3f}%  "
            f"corr_diff_vs_oecd={cd if cd is None else round(cd, 4)}  "
            f"null_p={p if p is None else round(p, 4)} (n={null_draws})  {status}")
        return {"area_name": block.get("area_name", city), "null_draws_used": null_draws, **fit}

    cities_out: dict[str, dict] = {}
    # Sorted, not dict-insertion-order: the null test's seed is derived from
    # this index, and the output must be reproducible independent of however
    # teranet_national_bank_hpi.json happens to order its city keys.
    city_order = sorted(raw_doc["data"]["cities"])
    for i, city in enumerate(city_order):
        cities_out[city] = _run_and_log(city, NULL_SEED_BASE + i, NULL_DRAWS, "")

    # Second pass -- see _borderline_margin()'s own comment: any city whose
    # p-value landed close enough to VALIDATION_MAX_P_VALUE that 500 draws
    # cannot tell it apart from the threshold gets re-measured at 10x the
    # precision before its pass/fail call is treated as final. A different
    # seed offset, not the same one at a higher count, so this is a fresh
    # draw rather than the first 500 with 4,500 appended behind them.
    for i, city in enumerate(city_order):
        p = cities_out[city]["validation"]["null_test"]["p_value"] \
            if cities_out[city]["validation"]["null_test"] else None
        margin = _borderline_margin(NULL_DRAWS)
        if p is None or abs(p - VALIDATION_MAX_P_VALUE) > margin:
            continue
        log(f"    !! {city}: p={p:.4f} landed within {margin:.4f} of the "
            f"{VALIDATION_MAX_P_VALUE} decision threshold at {NULL_DRAWS} draws "
            f"(SE~{(0.05*0.95/NULL_DRAWS)**0.5:.4f}); refining")
        cities_out[city] = _run_and_log(
            city, NULL_SEED_BASE + 1000 + i, REFINED_NULL_DRAWS, "REFINED  ")
        # The refined tier gets its OWN, tighter margin -- adversarial review
        # (package 21) found the first version of this refinement reused the
        # 500-draw margin to judge the 5,000-draw result too, so a value
        # sitting exactly on the coarse boundary was never re-checked against
        # the finer one it should have earned. Not silently trusted either
        # way here: stated plainly, whichever side it lands on.
        rp = cities_out[city]["validation"]["null_test"]["p_value"] \
            if cities_out[city]["validation"]["null_test"] else None
        rmargin = _borderline_margin(REFINED_NULL_DRAWS)
        if rp is not None and abs(rp - VALIDATION_MAX_P_VALUE) <= rmargin:
            log(f"    !! {city}: STILL within {rmargin:.4f} of the threshold at "
                f"{REFINED_NULL_DRAWS} draws (p={rp:.4f}) -- reported as measured, not "
                f"further refined; a genuinely close case, not a precision artefact.")

    n_passed = sum(1 for c in cities_out.values() if c["validation"]["passed"])

    write_processed(
        SOURCE_ID,
        {"cities": cities_out},
        meta={
            "kind": "derived",
            "confidence": "index",
            "method": "State-space local linear trend (Kalman smoother), fit per city via "
                       "statsmodels.tsa.UnobservedComponents(level='local linear trend'); "
                       "observation and innovation variances estimated by MLE from the data, "
                       "not assumed.",
            "input_source": INPUT_SOURCE_ID,
            "input_generated_at": raw_doc.get("generated_at"),
            "validation_method": "The smoothed monthly level, aggregated to quarterly means and "
                                  "then DIFFERENCED (quarter-over-quarter change, not level), "
                                  "correlated against the same treatment of OECD's independently-"
                                  "published Canadian house-price index (oecd_indicators.json, "
                                  "data.CA.house_prices.HPI_YDH_IX). Differencing first is "
                                  "deliberate: an earlier levels-based version of this check was "
                                  "proven unsafe by direct adversarial testing -- smoothed pure "
                                  "noise showed 0.9+ LEVEL correlation with this same OECD series "
                                  "for 5 of 6 cities (one landed positive and would have 'passed' "
                                  "outright), the textbook spurious-regression problem for two "
                                  "series that both drift. A city passes only if the differenced "
                                  "correlation is positive, does not fall more than "
                                  f"{VALIDATION_MAX_SHORTFALL_VS_RAW} below the same differenced "
                                  f"correlation on the raw series, AND a {NULL_DRAWS}-draw Monte "
                                  "Carlo null test (a parametric bootstrap FROM THE CITY'S OWN "
                                  "FITTED NOISE MODEL -- genuine trend-wandering at this city's "
                                  "own measured scale, but unrelated to OECD -- run through the "
                                  "identical pipeline; an earlier i.i.d.-noise version of this null "
                                  "was proven too weak by the same adversarial process, see "
                                  "_null_pvalue's own docstring) shows a correlation this large "
                                  f"occurring by chance no more than "
                                  f"{int(VALIDATION_MAX_P_VALUE * 100)}% of the time.",
            "band_note": "lo95/hi95 are the Kalman smoother's own 95% interval on the "
                          "SMOOTHED level (smoothed_state_cov) -- the model's own uncertainty "
                          "about the trend, not a prediction interval for next month's raw "
                          "reading.",
            "raw_series_unmodified": "data/processed/teranet_national_bank_hpi.json is read "
                                      "here, never written -- this file is an additional "
                                      "derived layer, not a replacement.",
            "cities_passed_validation": n_passed,
            "cities_total": len(cities_out),
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[],
        license_note="Derived entirely from two already-committed processed files "
                      "(teranet_national_bank_hpi, oecd_indicators); no new fetch.",
        transforms=[
            "Fit statsmodels.tsa.UnobservedComponents(level='local linear trend') per city, "
            "MLE for observation/innovation variances.",
            "Computed a 95% CI band from the Kalman smoother's own state covariance.",
            "Computed two SNR-style summaries per city: Harvey's q "
            "(sigma2_level / sigma2_irregular) and a variance-share metric "
            "(var(diff(smoothed)) / var(diff(raw))).",
            "Validated by aggregating to quarterly means, DIFFERENCING, and correlating against "
            "OECD's independent CA house-price index (same treatment), compared against the "
            "raw series' own differenced correlation AND a Monte Carlo null (noise matched to "
            "each city, run through the identical pipeline) -- a levels-based version of this "
            "check was tried first and proven unsafe by direct adversarial testing.",
            "No rebasing of the underlying index; no modification of the raw input file.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=sum(len(c["series"]) for c in cities_out.values()),
        coverage=f"{n_passed}/{len(cities_out)} Canadian cities pass independent OECD validation",
        notes="Recovers a monthly trend + uncertainty band from Teranet's noisy raw series; "
              "falls back per-city (not site-wide) if a city fails validation.",
        redistribution="derived output committed; no raw third-party payload involved",
    )
    if n_passed < len(cities_out):
        log(f"    !! {len(cities_out) - n_passed} of {len(cities_out)} cities did NOT clear "
            f"validation -- the frontend must keep those on the raw disclosure, not the band.")


if __name__ == "__main__":
    main_guard(run)
