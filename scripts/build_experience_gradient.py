"""Package 11, tier 1 — per-country experience-premium curves behind the
site's position (when personalised) and estimate. Build-time only: computes
a small set of (years, relative_premium) points from real, committed source
data and writes them to data/processed/experience_gradient.json. The browser
interpolates between these points for an arbitrary user-typed
years-of-experience value — it never re-derives them from raw salary_*.json.

PACKAGE 10 SHIPPED ONE UNIVERSAL CURVE, ANCHORED ON SPAIN'S TENURE CROSS,
APPLIED TO EVERY COUNTRY. RETIRED HERE. That curve was built on a real
mismatch: Spain's own INE tenure cross (`broader_category_context` in
salary_es.json — the key names the problem) measures a BROADER occupational
population (CNO-11 "Scientific and intellectual technicians and
professionals") than the IT-specific distribution it was shifting, and
applying its relative-premium SHAPE to every other country's own median was
the identical population-borrowing mistake finding F2/F3 (package 10's own
adversarial review) had already found and fixed for the position — just
still live, on the estimate. See NEEDS-DECISION.md #20's "same package,
tier 7" update, and its own further update from this package.

THE RULE NOW: a country's own experience cross personalises ONLY that
country's own position and estimate, and ONLY when the cross and the
percentile distribution describe the SAME population — same statistical
office, same classification, same occupation depth. Verified before this
module was written, not assumed:

  SE  SCB LonYrkeAlder4AN (age_by_year) crosses SSYK 2512 — the SAME 4-digit
      code, SAME office (SCB), SAME table family (AM0110A) as
      dispersion_by_year. Personalised.
  NO  SSB 11658 (age_at_quarter) crosses STYRK-08 2512 — the SAME 4-digit
      code, SAME office (SSB) as dispersion_by_year (table 11418). A
      different table number, but the same occupation depth and office.
      Personalised.
  ES  INE's tenure cross is at CNO-11's BROADER category, not the IT-specific
      occupation salary_es.json's own dispersion table covers — the
      `broader_category_context` key says so in its own name. NOT
      personalised. Its own it_professionals distribution still gets a
      published median, with the reason shown.
  Every other country: no occupation x experience/age/tenure cross exists in
      this pipeline at all. NOT personalised, same reason category as ES,
      different cause (absence, not a population mismatch).

This reduces the feature's apparent reach from thirteen countries (package
10's universal curve) to two. That is the honest number, the same trade the
crosswalk already makes when it refuses to compare a 4-digit occupation
against a 2-digit one rather than pretend the depths match.

THE PROXY, NAMED: SCB's and SSB's own crosses are AGE, not experience.
Neither office publishes an occupation x tenure cross the way INE does for
Spain's broader category — age is what's available, so age is what SE's and
NO's own curves use, standing in for years of professional experience.
That is a real, disclosed substitution, not a synonym: age is a WEAK proxy
for experience specifically in software (35% of Stack Overflow's 2025
survey respondents report under ten years of professional coding, so a
35-year-old is often still early-career — age and tenure diverge more in
this field than in most). Every consumer of this file, and the method card
the site renders from it, states this plainly rather than labelling an age
band as if it measured experience directly.

WHY LINEAR INTERPOLATION, NOT A FITTED CURVE: same reasoning package 10's
version of this module used — a handful of real data points, no claim to
know the true functional form between them. Piecewise-linear is the minimal
assumption a reader can verify by hand from the cited table. Clamped past
the first/last point, never extrapolated.

WHY NO MONOTONICITY ASSERTION HERE, UNLIKE PACKAGE 10'S VERSION: that
version's ES tenure curve was asserted monotonically non-decreasing (more
tenure should not on average pay less) and that held on real data. Age
curves are a different shape of claim: SE's own 65-68 band pays LESS than
its 55-64 band in every year this pipeline has (a real, plausible
semi-retirement / reduced-hours effect near pension age, not a data error)
— asserting monotonicity here would be asserting something the source data
itself does not show, so this module logs the shape instead of gating on
it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, log, main_guard, record_provenance, write_processed  # noqa: E402

PROXY_CAVEAT = (
    "This is an age band standing in for years of professional experience — SCB/SSB do not publish "
    "an occupation x tenure cross the way INE does for Spain's broader category, so age is what this "
    "pipeline has. Age is a weak proxy specifically in software: 35% of Stack Overflow's 2025 survey "
    "respondents report under ten years of professional coding, so a 35-year-old is often still "
    "early-career. The band's own relative premium is shown as itself — a real number from a real "
    "table — but the AGE axis it is plotted against is an approximation of the band's own centre, and "
    "the site's own conversion from years of professional experience to an assumed age (career start "
    "~22) is its own separate, disclosed assumption — see profile.ts's own ASSUMED_CAREER_START_AGE."
)

# (age_midpoint_approx, band_key, band_label) — SCB's own age bands
# (AM0110A/LonYrkeAlder4AN via salary_se.json's age_by_year). Midpoints are
# this pipeline's own stated approximation of each band's centre; SCB
# publishes the band, not a single representative age.
SE_AGE_BANDS = [
    (21, "18-24", "18-24"), (29.5, "25-34", "25-34"), (39.5, "35-44", "35-44"),
    (49.5, "45-54", "45-54"), (59.5, "55-64", "55-64"), (66.5, "65-68", "65-68"),
]
SE_AGE_TOTAL_KEY = "tot"

# Norway's age bands (SSB 11658 via salary_no.json's age_at_quarter) — coarser
# than Sweden's (3 bands, one spanning the entire 0-39 range).
NO_AGE_BANDS = [(19.5, "0-39", "under 40 (0-39)"), (47, "40-54", "40-54"), (60, "55+", "55+")]
NO_AGE_TOTAL_KEY = "999D"


def _latest(by_year: dict) -> tuple[str, dict]:
    return max(by_year.items(), key=lambda kv: kv[0])


def _se_curve() -> tuple[list[dict], dict]:
    doc = __import__("json").loads((PROCESSED / "salary_se.json").read_text(encoding="utf-8"))
    year, row = _latest(doc["data"]["occupations"]["2512"]["age_by_year"])
    total = row[SE_AGE_TOTAL_KEY]["monthly_salary_sek"]
    points = []
    for age_mid, band, label in SE_AGE_BANDS:
        cell = row.get(band)
        if not cell:
            continue
        value = cell["monthly_salary_sek"]
        points.append({
            "age_midpoint_approx": age_mid, "band_label": label,
            "value_sek_month": value, "premium_pct": round((value / total - 1) * 100, 2),
        })
    meta = {
        "source": "SCB LonYrkeAlder4AN, occupation 2512 (same 4-digit SSYK code, same office and table "
                   "family as this country's own dispersion_by_year)",
        "year": int(year), "total_sek_month": total, "currency": "SEK", "period": "month",
        "measures": "age", "proxy_caveat": PROXY_CAVEAT,
    }
    return points, meta


def _no_curve() -> tuple[list[dict], dict]:
    doc = __import__("json").loads((PROCESSED / "salary_no.json").read_text(encoding="utf-8"))
    aq = doc["data"]["occupations"]["2512"]["age_at_quarter"]
    total = aq["bands"][NO_AGE_TOTAL_KEY]["median_nok_month"]
    points = []
    for age_mid, code, label in NO_AGE_BANDS:
        cell = aq["bands"].get(code)
        if not cell:
            continue
        value = cell["median_nok_month"]
        points.append({
            "age_midpoint_approx": age_mid, "band_label": label,
            "value_nok_month": value, "premium_pct": round((value / total - 1) * 100, 2),
        })
    meta = {
        "source": "SSB 11658, occupation 2512 (same 4-digit STYRK-08 code, same office as this "
                   "country's own dispersion_by_year, table 11418)",
        "quarter": aq["quarter"], "total_nok_month": total, "currency": "NOK", "period": "month",
        "measures": "age", "proxy_caveat": PROXY_CAVEAT,
        "vintage_note": f"This cross is measured at {aq['quarter']!r}, a single quarter — this "
                         "country's own dispersion_by_year is annual. Both are SSB's own figures, but "
                         "they do not share a reference period exactly; disclosed rather than treated "
                         "as if they were the same moment in time.",
    }
    return points, meta


def run() -> None:
    log("── experience_gradient — package 11, tier 1: per-country premium curves (SE, NO only)")

    se_points, se_meta = _se_curve()
    no_points, no_meta = _no_curve()

    def _fmt(pts: list[dict]) -> str:
        return ", ".join(f"{p['age_midpoint_approx']}y={p['premium_pct']:+.1f}%" for p in pts)

    log(f"  SE curve: {_fmt(se_points)}")
    premiums_se = [p["premium_pct"] for p in se_points]
    if any(b < a - 0.01 for a, b in zip(premiums_se, premiums_se[1:])):
        log(f"    note: SE's own curve is NOT monotonically non-decreasing ({premiums_se}) — "
            "real, plausible (semi-retirement near pension age), not asserted as an invariant here; "
            "see module docstring")

    log(f"  NO curve: {_fmt(no_points)}")
    premiums_no = [p["premium_pct"] for p in no_points]
    if any(b < a - 0.01 for a, b in zip(premiums_no, premiums_no[1:])):
        log(f"    note: NO's own curve is NOT monotonically non-decreasing ({premiums_no}) — "
            "see module docstring")

    payload = {
        "by_country": {
            "SE": {"curve": se_points, "meta": se_meta},
            "NO": {"curve": no_points, "meta": no_meta},
        },
        "interpolation": "piecewise-linear between a country's own points, against an ASSUMED AGE "
                          "(years of professional experience + a stated career-start-age constant — "
                          "see profile.ts's own ASSUMED_CAREER_START_AGE, not this file's own concern); "
                          "clamped to the first point's premium below its own age_midpoint_approx and "
                          "the last point's premium above it — never extrapolated past what the cited "
                          "table measures",
    }

    write_processed(
        "experience_gradient",
        payload,
        meta={
            "purpose": "Per-country relative pay-by-experience curves — SE and NO only, the two "
                       "countries whose own occupation-level cross shares the same office, "
                       "classification and depth as their own wage distribution. Package 10 shipped "
                       "one universal curve anchored on Spain's tenure cross and applied it to every "
                       "country; retired here (package 11) after re-examination found the identical "
                       "population-borrowing problem the position's own F2/F3 fix had already been "
                       "built to prevent, just moved to the estimate. Spain's own tenure cross "
                       "(salary_es.json's broader_category_context) remains real, committed data, "
                       "just not consumed by this file — see NEEDS-DECISION.md #20.",
            "confidence": "derived", "level": "per-country (SE, NO) — not applied cross-country",
        },
    )
    record_provenance(
        source_id="experience_gradient",
        name="Experience-pay gradient — SCB (Sweden) and SSB (Norway) age crosses, per-country only",
        urls=[],  # derived from already-committed, already-provenanced salary_se/no.json
        license_note="Inherits salary_se.json / salary_no.json's own licences — this file adds no new "
                      "licensing terms, only computation over already-committed data.",
        redistribution="derived — nothing fetched; every input file's own provenance entry already "
                        "covers redistribution terms for the raw figures this derives from.",
        transforms=[
            "Computed each of Sweden's 6 age bands' own salary as a % premium/discount against that "
            "same table's own 'tot' total (SCB LonYrkeAlder4AN, occupation 2512).",
            "Computed the same relative-premium transform for Norway's 3 age bands against the same "
            "quarter's own all-ages total (SSB 11658, occupation 2512, band '999D').",
            "Logged (not asserted — see module docstring) whether each curve is monotonically "
            "non-decreasing in years.",
            "Retired package 10's universal Spain-tenure-anchored curve entirely — no country other "
            "than Spain ever consumed it, and Spain's own case was itself a population mismatch.",
        ],
        output="data/processed/experience_gradient.json",
        rows=len(se_points) + len(no_points),
        coverage="2 country-specific curves (Sweden 6 points, Norway 3 points) — thirteen fewer "
                 "countries than package 10's own universal curve claimed to cover, deliberately",
        notes="Every premium is a relative %, computed within one internally consistent source table, "
              "consumed only by that SAME country's own position and estimate — never applied to a "
              "different country the way package 10's universal curve did.",
    )
    log(f"  wrote data/processed/experience_gradient.json")


if __name__ == "__main__":
    main_guard(run)
