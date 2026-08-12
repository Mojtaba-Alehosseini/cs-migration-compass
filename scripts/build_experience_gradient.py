"""Package 10, tier 3 — the experience-gradient control points behind the
site's "estimate" (the second number, beside the position). Build-time only:
computes a small set of (years, relative_premium) points from real,
committed source data and writes them to
data/processed/experience_gradient.json. The browser interpolates between
these points for an arbitrary user-typed years-of-experience value — it
never re-derives them from raw salary_*.json, the same "compute once at
build time, only interpolate client-side" split normalise.py's own
docstring establishes for wage_distribution.json.

WHY SPAIN, NOT SWEDEN OR NORWAY, DRIVES THE UNIVERSAL CURVE: of the three
sources that cross occupation pay with anything experience-related in this
spine (see docs/METHODOLOGY.md and NEEDS-DECISION.md's own account of
which sources exist), only Spain's INE table (`broader_category_context`
in data/processed/salary_es.json, tables 70706/70707) crosses by TENURE —
years actually worked. Sweden (SCB LonYrkeAlder4AN) and Norway (SSB 11658)
cross by AGE, which the work order's own plan document flags as a weak
proxy specifically for software ("35% of Stack Overflow 2025 respondents
have under ten years of professional coding, so a 35-year-old is often a
junior" — age and tenure diverge more in this field than in most). Given a
choice between the one source that measures the actual variable
(`yearsProfessional`) and two that measure a correlated but distinct one,
this pipeline anchors the ONE universal gradient on the direct measurement
and carries Sweden's and Norway's own age-band premiums alongside it as
CORROBORATING CONTEXT (a same-shape sanity check, not a second input
blended into the curve) — this is what the work order's own "where only an
age cross exists, say so in the method card" is answered by here: this
pipeline explains why it did NOT lean on the age crosses as the gradient
itself, rather than silently using age as if it were experience.

THE ASSUMPTION THIS RESTS ON, STATED EXPLICITLY: Spain's tenure cross is at
CNO-11's broader "Scientific and intellectual technicians and
professionals" category, not an IT-specific occupation (INE crosses tenure
at no finer grain — see salary_es.json's own broader_category_context.note).
The RELATIVE premium by tenure band (each band's own average versus that
same table's own "Total" average) is computed within that one, internally
consistent population, then applied as a relative shift to whichever
target country's own IT-specific median — i.e., this assumes the SHAPE of
the tenure-pay relationship (junior earns X% below average, senior earns Y%
above) transfers across occupations and countries even though the
ABSOLUTE wage level does not. That is a real, disclosed assumption, not a
hidden one — every consumer of this file's data can see it stated here and
in the method card the site renders from it.

WHY LINEAR INTERPOLATION, NOT A FITTED CURVE: six real data points, no
claim to know the true functional form between them. Piecewise-linear
interpolation is the minimal assumption a reader can verify by hand from
the cited table without needing to trust a fitted model's own choices —
"a statistical estimator written in this repo... reproducible by hand from
the cited tables" (work order, tier 3). Beyond the top band's own upper
edge, the curve is CLAMPED to the top band's own premium, not extrapolated
— the same discipline the work order applies to the distribution itself
(P1-P99 clamp): this pipeline does not claim to know what happens beyond
what a real table measured.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, log, main_guard, record_provenance, write_processed  # noqa: E402

# (years-of-experience midpoint, upper edge EXCLUSIVE for bucketing a real
# yearsProfessional value into this band (a value belongs here if
# years < upper_edge; None = open-ended, the top band), band label, source
# field key) — ES's own tenure_bands_eur_year, in the order INE itself
# publishes them. The midpoint drives the gradient's own continuous
# interpolation (gradientPremiumPct in profile.ts); the upper edge is a
# SEPARATE, discrete field used only to bucket a real years value into its
# real band (computePosition in profile.ts) — conflating the two was a real
# bug caught before shipping (comparing a years value against midpoints
# misclassified boundary years, e.g. 3 years landing in "4 to 10" instead
# of "1 to 3"). Edges follow INE's own whole-year band definitions exactly
# ("1 to 3 years" runs through the year someone turns 4, i.e. years < 4).
# "30 and above" has no upper edge in the source; its own midpoint (32) is
# this pipeline's own stated representative point (not sourced), a modest
# 2-year step past the band's 30-year floor — never extrapolated further,
# since nothing about the true shape past 30 years is measured here.
ES_TENURE_BANDS = [
    (0.5, 1, "Less than 1 year", "Less than 1 year. Average gross salary."),
    (2.0, 4, "1 to 3 years", "From 1 to 3 years. Average gross salary."),
    (7.0, 11, "4 to 10 years", "From 4 to 10 years. Average gross salary."),
    (15.5, 21, "11 to 20 years", "From 11 to 20 years. Average gross salary."),
    (25.0, 30, "21 to 29 years", "From 21 to 29 years. Average gross salary."),
    (32.0, None, "30 years and above", "30 and above. Average gross salary."),
]
ES_TENURE_TOTAL_KEY = "Total. Average gross salary."

# Sweden's age bands (SCB LonYrkeAlder4AN via salary_se.json's age_by_year) —
# context only, not blended into the universal curve. Band midpoints are
# this pipeline's own stated approximation of each band's centre, used only
# to plot the context curve on the same years-like axis as Spain's tenure
# curve for visual comparison — never fed into the actual gradient math.
SE_AGE_BANDS = [
    (21, "18-24"), (29.5, "25-34"), (39.5, "35-44"),
    (49.5, "45-54"), (59.5, "55-64"), (66.5, "65-68"),
]
SE_AGE_TOTAL_KEY = "tot"

# Norway's age bands (SSB 11658) — context only, same reason. Coarser than
# Sweden's (3 bands, one spanning the entire 0-39 range) — its own midpoint
# approximation is correspondingly cruder and is disclosed as such.
# (years_midpoint_approx, band_code, band_label)
NO_AGE_BANDS = [(19.5, "0-39", "under 40 (0-39)"), (47, "40-54", "40-54"), (60, "55+", "55+")]
NO_AGE_TOTAL_KEY = "999D"


def _latest(by_year: dict) -> tuple[str, dict]:
    return max(by_year.items(), key=lambda kv: kv[0])


def _es_tenure_curve() -> tuple[list[dict], dict]:
    doc = __import__("json").loads((PROCESSED / "salary_es.json").read_text(encoding="utf-8"))
    ctx = doc["data"]["broader_category_context"]
    bands = ctx["tenure_bands_eur_year"]
    total = bands[ES_TENURE_TOTAL_KEY]
    points = []
    for years, upper_edge, label, key in ES_TENURE_BANDS:
        value = bands[key]
        points.append({
            "years": years, "upper_edge_years_exclusive": upper_edge, "band_label": label,
            "eur_year": value, "premium_pct": round((value / total - 1) * 100, 2),
        })
    meta = {
        "source": "INE EES tenure cross (tables 70706/70707), CNO-11 'Scientific and intellectual "
                   "technicians and professionals' — NOT IT-specific, the finest grain INE crosses "
                   "tenure at (see salary_es.json's own broader_category_context.note)",
        "year": ctx["tenure_year"], "total_eur_year": total, "measures": "years of experience (tenure) — "
                   "the direct variable, not a proxy",
    }
    return points, meta


def _se_age_context() -> tuple[list[dict], dict]:
    doc = __import__("json").loads((PROCESSED / "salary_se.json").read_text(encoding="utf-8"))
    year, row = _latest(doc["data"]["occupations"]["2512"]["age_by_year"])
    total = row[SE_AGE_TOTAL_KEY]["monthly_salary_sek"]
    points = []
    for years_mid, band in SE_AGE_BANDS:
        cell = row.get(band)
        if not cell:
            continue
        value = cell["monthly_salary_sek"]
        points.append({
            "years_midpoint_approx": years_mid, "band_label": band, "sek_month": value,
            "premium_pct": round((value / total - 1) * 100, 2),
        })
    return points, {"source": "SCB LonYrkeAlder4AN, occupation 2512", "year": int(year),
                     "total_sek_month": total,
                     "measures": "age — a proxy for experience, not experience itself; see module "
                                 "docstring for why this is context, not the gradient's own input"}


def _no_age_context() -> tuple[list[dict], dict]:
    doc = __import__("json").loads((PROCESSED / "salary_no.json").read_text(encoding="utf-8"))
    aq = doc["data"]["occupations"]["2512"]["age_at_quarter"]
    total = aq["bands"][NO_AGE_TOTAL_KEY]["median_nok_month"]
    points = []
    for years_mid, code, label in NO_AGE_BANDS:
        cell = aq["bands"].get(code)
        if not cell:
            continue
        value = cell["median_nok_month"]
        points.append({
            "years_midpoint_approx": years_mid, "band_label": label, "nok_month": value,
            "premium_pct": round((value / total - 1) * 100, 2),
        })
    return points, {"source": "SSB 11658, occupation 2512", "quarter": aq["quarter"],
                     "total_nok_month": total,
                     "measures": "age — a proxy for experience, not experience itself; coarser bands "
                                 "than Sweden's (one spans the entire 0-39 range) — see module "
                                 "docstring for why this is context, not the gradient's own input"}


def run() -> None:
    log("── experience_gradient — package 10, tier 3: the universal premium curve behind the estimate")

    es_points, es_meta = _es_tenure_curve()
    se_points, se_meta = _se_age_context()
    no_points, no_meta = _no_age_context()

    def _fmt(pts: list[dict], years_key: str) -> str:
        return ", ".join(f"{p[years_key]}y={p['premium_pct']:+.1f}%" for p in pts)

    log(f"  ES tenure curve (primary, drives the gradient): {_fmt(es_points, 'years')}")
    log(f"  SE age curve (context only): {_fmt(se_points, 'years_midpoint_approx')}")
    log(f"  NO age curve (context only): {_fmt(no_points, 'years_midpoint_approx')}")

    # Monotonicity sanity check on the curve that actually drives the estimate
    # — a real regression could produce a non-monotonic result from noisy
    # source data; this pipeline's own design assumes "more experience does
    # not on average pay less", so a violation here is a signal to look at
    # the source data again, not silently ship a curve that dips.
    premiums = [p["premium_pct"] for p in es_points]
    if any(b < a - 0.01 for a, b in zip(premiums, premiums[1:])):
        raise RuntimeError(f"experience_gradient: ES tenure curve is not monotonically "
                            f"non-decreasing ({premiums}) — investigate before shipping a dip "
                            "the site would present as a real finding")

    payload = {
        "gradient": {
            "curve": es_points,
            "meta": es_meta,
            "interpolation": "piecewise-linear between points; clamped to the first point's premium "
                              "below its own years value and the last point's premium above it — "
                              "never extrapolated past what the cited table measures",
        },
        "context": {
            "se_age": {"curve": se_points, "meta": se_meta},
            "no_age": {"curve": no_points, "meta": no_meta},
        },
    }

    write_processed(
        "experience_gradient",
        payload,
        meta={
            "purpose": "The relative pay-by-experience curve behind package 10's estimate (Tier 3) — "
                       "computed here at build time from real tenure/age crosses, interpolated "
                       "client-side for an arbitrary user-entered years value. See module docstring "
                       "for why Spain's tenure cross (not Sweden's or Norway's age crosses) drives the "
                       "one universal curve.",
            "confidence": "derived", "level": "cross-country (one curve, applied everywhere)",
        },
    )
    record_provenance(
        source_id="experience_gradient",
        name="Experience-pay gradient — INE tenure cross (primary), SCB/SSB age crosses (context)",
        urls=[],  # derived from already-committed, already-provenanced salary_es/se/no.json
        license_note="Inherits salary_es.json / salary_se.json / salary_no.json's own licences — this "
                      "file adds no new licensing terms, only computation over already-committed data.",
        redistribution="derived — nothing fetched; every input file's own provenance entry already "
                        "covers redistribution terms for the raw figures this derives from.",
        transforms=[
            "Computed each of Spain's 6 tenure bands' own average salary as a % premium/discount "
            "against that same table's own 'Total' average (INE tables 70706/70707, CNO-11 broader "
            "category) — the ONE curve package 10's estimate actually uses.",
            "Computed the same relative-premium transform for Sweden's 6 age bands (SCB "
            "LonYrkeAlder4AN, occupation 2512) and Norway's 3 age bands (SSB 11658, occupation 2512, "
            "plus a same-quarter 'all ages' total added this package specifically for this "
            "computation) — kept as disclosed context, never blended into the gradient itself.",
            "Verified the primary (ES) curve is monotonically non-decreasing in years before shipping "
            "— a real build-time check, not just a claim.",
        ],
        output="data/processed/experience_gradient.json",
        rows=len(es_points) + len(se_points) + len(no_points),
        coverage="1 universal gradient curve (6 points, Spain) + 2 context curves (Sweden 6, Norway 3)",
        notes="Every premium is a relative %, computed within one internally consistent source table — "
              "applying it to a different country's own median is this pipeline's own disclosed "
              "assumption (see module docstring), not a claim the source itself makes.",
    )
    log(f"  wrote data/processed/experience_gradient.json")


if __name__ == "__main__":
    main_guard(run)
