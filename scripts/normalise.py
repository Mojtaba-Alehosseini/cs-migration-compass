"""The conversion module — every wage-figure conversion in this pipeline goes
through here. No component converts inline, anywhere else.

Seven rules (package 9's work order, Tier 5.1), each enforced by a function
below, not by convention alone:

  1. Year-matching is mandatory. fx_rate() looks up the rate for the exact
     year requested and returns None — never a nearby year — if that year
     is absent. There is no fallback path that silently substitutes a
     different year's rate.
  2. Subtract, never add. subtract_component() is the only way this module
     removes a component from a figure, and it requires the caller name a
     component pay_composition.json actually lists as
     separately_published_components — there is no add_component().
  3. x12, always, for monthly->annual. MONTHLY_MULTIPLIER is a single
     constant, used in exactly one place. Germany's own -0034 (mit
     Sonderzahlungen) is used directly when Germany has data, never
     manufactured by multiplying -0030 by anything other than 12 — but
     Germany has no live source this package (NEEDS-DECISION.md #15), so
     this rule currently has nothing DE to apply to.
  4. Two comparison bases (regular_pay / total_earnings), and a comparison
     only happens on a basis both sides can express — comparison_basis()
     is the pay-composition analogue of scripts/crosswalk.py's
     compare(), deliberately reusing that "meet in the middle, or refuse"
     shape.
  5. Native is the source of truth. Nothing in this module writes back to
     data/processed/salary_*.json — every function here is pure, taking a
     value in and returning a NEW dict; the caller decides what to do with
     the result.
  6. Hourly->annual requires a sourced hours figure. annualise() returns
     {"ok": False, ...} rather than falling back to a flat 2080 (the US
     40x52 convention) — a refusal the caller must check, not an
     exception (an earlier version of this line said "raises", which was
     never what the code below actually does; caught by tier 7's
     adversarial review, finding F21). See hours_for()'s own docstring
     for why that convention would specifically overstate Denmark.
  7. The chain is inspectable. Every function here returns the intermediate
     steps (rate, year, source, what was subtracted and why), not just a
     final number — see ConversionChain.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, PROCESSED  # noqa: E402

MONTHLY_MULTIPLIER = 12
WEEKS_PER_YEAR = 52


class ConversionStep(TypedDict):
    op: str
    detail: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fx_series(country: str) -> list[dict]:
    doc = _load_json(PROCESSED / "fx_rates.json")
    return doc.get("data", {}).get(country, [])


def _hours_series(country: str) -> dict[str, dict]:
    doc = _load_json(PROCESSED / "hours_worked.json")
    return doc.get("data", {}).get("countries", {}).get(country, {}).get("by_year", {})


def _composition(source_id: str) -> dict | None:
    doc = _load_json(DATA / "pay_composition.json")
    return next((s for s in doc.get("sources", []) if s["source_id"] == source_id), None)


# How many years a conversion may reach for a rate before it is refused
# outright. Chosen from this repo's own FX series, not by feel.
#
# The World Bank's annual PA.NUS.FCRF series publishes with a lag: in August
# 2026 it ends at 2025. Rule 1 (no nearby-year substitution) was written for a
# HISTORICAL series, where pricing a 1968 London house at a 2026 rate would be a
# lie of fifty-eight years. Applied to a job posted this month it discards the
# posting to avoid an error of one or two percent — 88-92% of the annual-pay
# postings for GB, CA, DE and FR, almost all of them 2026.
#
# Measured across all 20 currencies in fx_rates.json, restricted to 2015 onward
# because that is the regime a current posting sits in:
#
#     gap    n    median    p90     max
#      1    200     2.0%    8.3%   19.8%
#      2    180     3.0%    9.6%   28.0%
#      3    160     3.3%   11.6%   37.9%
#
# Two years covers the publication lag with a year of slack and keeps the median
# error at 3%. Three begins to reach, and the tail grows faster than the median.
# The worst case at two years is still ~28%, which is precisely why a substituted
# conversion is MARKED AS AN ESTIMATE rather than presented as exact.
#
# The full history has far worse moves — 3,070% for AM 1993-94, 100% for IT, ES
# and FI in 1998-99 — but every one is a redenomination or a currency
# introduction (the euro replacing the lira, peseta and markka), all before 2000,
# and none can fall within two years of a posting dated now.
#
# This is a CEILING, not a default. to_usd() still refuses any substitution
# unless a caller asks for one explicitly, so every historical series keeps the
# exact year-matching package 9 built for it.
MAX_FX_GAP_YEARS = 2


def fx_rate(country: str, year: int) -> dict | None:
    """The FX rate for EXACTLY this country and year, or None. Rule 1: no
    nearby-year fallback exists in this function on purpose — a caller
    that wants one must say so explicitly by trying a different year
    itself, not receive one silently."""
    for row in _fx_series(country):
        if row["year"] == year:
            return {"rate": row["value"], "year": year, "country": country,
                     "source": "fx_rates (World Bank PA.NUS.FCRF, period average)"}
    return None


def fx_rate_within(country: str, year: int, max_gap_years: int) -> dict | None:
    """The rate for `year` if it exists, else the NEAREST year within
    `max_gap_years`, preferring the smaller gap and, on a tie, the earlier year
    (a published past rate over an implied future one).

    Returns the same shape as fx_rate() plus `gap_years` and `estimated`, so a
    caller can never receive a substituted rate without also receiving the fact
    that it was substituted. There is no code path that returns a substituted
    rate looking like an exact one.
    """
    # MAX_FX_GAP_YEARS is a ceiling, and a ceiling a caller can step over by
    # passing a bigger number is a suggestion. Adversarial review reached
    # gap_years=75 with to_usd(1000, "GB", 2100, 100); nothing in the pipeline
    # does that, but nothing stopped it either, and the whole argument for
    # relaxing rule 1 rests on the bound being real. The year is coerced too:
    # a float year produced a float gap and rendered as "a gap of
    # 1.400000000000091 years".
    year = int(year)
    max_gap_years = min(int(max_gap_years), MAX_FX_GAP_YEARS)
    exact = fx_rate(country, year)
    if exact:
        return {**exact, "gap_years": 0, "estimated": False}
    if max_gap_years <= 0:
        return None
    best = None
    for row in _fx_series(country):
        gap = abs(row["year"] - year)
        if gap > max_gap_years:
            continue
        key = (gap, row["year"] > year)      # nearer first; on a tie prefer the past
        if best is None or key < best[0]:
            best = (key, row)
    if best is None:
        return None
    row = best[1]
    return {"rate": row["value"], "year": row["year"], "country": country,
            "source": "fx_rates (World Bank PA.NUS.FCRF, period average)",
            "gap_years": abs(row["year"] - year), "estimated": True}


def to_usd(value: float, country: str, year: int, max_gap_years: int = 0) -> dict:
    """Convert a native-currency value to USD at the rate from ITS OWN year.
    Returns {"ok": False, "reason": ...} rather than a number if that
    year's rate is unavailable — never substitutes a different year.

    USD is the IDENTITY and needs no rate. That is not an exception to rule 1
    ("no fallback to a different year") — it is the observation that rule 1
    exists to stop a 2024 rate standing in for a 2026 one, and there is no
    substitution happening when the conversion is x -> x. The World Bank's
    PA.NUS.FCRF for the US is 1.0 in every year it publishes, by definition.

    Requiring that published 1.0 was doing real damage. The series stops at
    2025, so every 2026-dated US posting quoted in USD failed conversion, and
    1,566 US software postings — the entire current year — were dropped from
    the site's only published pay figure. What survived was 77% 2016-2017
    USAJOBS listings, and the published median moved from $217,000 (2025) to
    $99,000 purely through which years happened to have an FX rate. Found by an
    adversarial review of package 16, which asked what the headline number was
    actually made of.

    Deliberately narrow: this short-circuits only when the source currency is
    itself USD. Every other currency still requires its own year's rate, and
    still refuses rather than reaching for a neighbouring one."""
    if country == "US":
        return {
            "ok": True,
            "value_usd": float(value),
            "chain": [{"op": "fx_convert",
                       "detail": f"{value} USD is already USD — identity, no rate applied"}],
            "fx_rate": 1.0, "fx_year": year, "fx_source": "identity (USD to USD)",
            # fx_year_requested belongs here too. Both successful return paths
            # must carry the SAME keys, or a caller that reads them without a
            # default — which is the only safe way to read the estimate flag —
            # works for one currency and raises for another. Found by making
            # postings_common.py fail closed: the identity path had quietly
            # omitted this since the field was introduced.
            "estimated": False, "fx_gap_years": 0, "fx_year_requested": int(year),
        }
    rate = fx_rate_within(country, year, max_gap_years)
    if rate is None:
        why = (f"no FX rate for {country} in {year}, and none within {max_gap_years} "
               f"year(s) either" if max_gap_years > 0 else
               f"no FX rate for {country} in {year} — not converted, never substituted from a "
               f"different year")
        return {"ok": False, "reason": why}
    detail = (f"{value} / {rate['rate']} ({country} {rate['year']} period-average rate, "
              f"{rate['source']})")
    if rate["estimated"]:
        detail += (f" — ESTIMATE: no {year} rate is published, so the {rate['year']} rate was used "
                   f"({rate['gap_years']} year gap)")
    return {
        "ok": True,
        "value_usd": value / rate["rate"],
        "chain": [{"op": "fx_convert", "detail": detail}],
        "fx_rate": rate["rate"], "fx_year": rate["year"], "fx_source": rate["source"],
        "estimated": rate["estimated"], "fx_gap_years": rate["gap_years"],
        "fx_year_requested": year,
    }


def hours_for(country: str, year: int | None = None) -> dict | None:
    """A sourced usual-weekly-hours figure for `country`. If `year` is
    given and present, uses it; otherwise uses the latest year the source
    publishes (hours-worked figures move slowly year to year, unlike FX,
    so this module does not require an exact year match for hours the way
    rule 1 requires for FX — but the year actually used is always
    returned, never hidden).

    Never returns a flat 2080 (40h x 52wk, the US convention) as a
    fallback for a country with no sourced figure — Denmark's own usual
    full-time hours (~38.2-38.4/week depending on year, verified live in
    scripts/src_hours_worked.py) would be overstated under that assumption
    by a measured 4.2-4.7% depending which year's sourced hours the wage
    figure is matched to (2080/1996.8 = 4.17% at 2024's 38.4h/week;
    2080/1985.6 = 4.75% at 2025's 38.2h/week) — see
    .status/evidence/p9-gates.txt gate 6 for the year-matched calculation
    against a real wage figure; a fixed "~7%" appeared here through
    package 9's own tier 5 and 6, uncorrected against the actual
    measurement until tier 7's adversarial review caught it (finding F19).
    A country with no entry in hours_worked.json gets None here, and
    annualise() refuses to guess past that."""
    series = _hours_series(country)
    if not series:
        return None
    use_year = str(year) if year is not None and str(year) in series else max(series, key=int)
    row = series[use_year]
    return {"hours_per_week": row["usual_weekly_hours"], "year": int(use_year), "country": country,
            "reliability_flag": row.get("reliability_flag"),
            "source": "hours_worked (Eurostat lfsa_ewhun2 / Statistics Canada WDS)"}


def annualise(value: float, period: str, country: str, hours_year: int | None = None,
              explicit_hours: dict | None = None) -> dict:
    """period is 'hour', 'month' or 'year'. 'year' returns the value
    unchanged (already annual). 'month' multiplies by MONTHLY_MULTIPLIER
    (12) — rule 3, the only multiplier this module uses for that
    conversion, anywhere. 'hour' requires a real, sourced hours figure —
    by default from hours_for(country), the cross-country Eurostat/StatCan
    file; if it does not resolve, this returns {"ok": False, ...} rather
    than assuming 2080 — rule 6.

    `explicit_hours` (package 9, tier 7, adversarial review finding F2):
    {"hours_per_week": float, "year": int, "source": str}, when given, is
    used INSTEAD of hours_for(country, hours_year). For sources that
    publish their OWN matched hours figure for the exact same cell as the
    wage value — Ireland's CSO SES06 carries mean_paid_weekly_hours /
    median_paid_weekly_hours alongside mean_eur_hour / median_eur_hour,
    for the identical population (SOC major group 2, same year) — that
    matched figure is a strictly better match than the generic
    cross-country hours_worked.json (Eurostat lfsa_ewhun2, NACE J or
    TOTAL, ALL full-time employees regardless of occupation), which
    caused a real, measured 21.4% overstatement of Ireland's mean when
    used instead (33.6 CSO-matched hours vs 40.8 Eurostat all-employee
    hours). Still refuses (ok: False) if explicit_hours itself is
    incomplete — this parameter is an alternative SOURCE for the hours
    figure, not an exemption from rule 6's "must be real and sourced"."""
    if period == "year":
        return {"ok": True, "value_annual": value, "chain": [{"op": "identity", "detail": "already annual"}]}
    if period == "month":
        return {
            "ok": True,
            "value_annual": value * MONTHLY_MULTIPLIER,
            "chain": [{"op": "monthly_to_annual", "detail": f"{value} x {MONTHLY_MULTIPLIER} (fixed, "
                       "never any other multiplier — see module docstring rule 3)"}],
        }
    if period == "hour":
        if explicit_hours is not None:
            if not explicit_hours.get("hours_per_week") or not explicit_hours.get("source"):
                return {"ok": False, "reason": "explicit_hours given but incomplete (needs a real "
                         "hours_per_week and source) — not annualised, never assumed 2080"}
            hours = {**explicit_hours, "country": country,
                     "reliability_flag": explicit_hours.get("reliability_flag")}
        else:
            hours = hours_for(country, hours_year)
        if hours is None:
            return {"ok": False, "reason": f"no sourced usual-weekly-hours figure for {country} — "
                     "not annualised, never assumed 2080 (40h x 52wk)"}
        weekly = value * hours["hours_per_week"]
        annual = weekly * WEEKS_PER_YEAR
        return {
            "ok": True,
            "value_annual": annual,
            "chain": [
                {"op": "hourly_to_weekly", "detail": f"{value} x {hours['hours_per_week']} hours/week "
                 f"({hours['country']} {hours['year']}, {hours['source']}"
                 + (f", flagged {hours['reliability_flag']!r}" if hours["reliability_flag"] else "") + ")"},
                {"op": "weekly_to_annual", "detail": f"x {WEEKS_PER_YEAR} weeks/year"},
            ],
            "hours_per_week": hours["hours_per_week"], "hours_year": hours["year"],
            "hours_source": hours["source"], "hours_reliability_flag": hours["reliability_flag"],
        }
    return {"ok": False, "reason": f"unknown period {period!r} — expected 'hour', 'month' or 'year'"}


def subtract_component(value: float, source_id: str, component: str, component_value: float) -> dict:
    """Remove `component_value` from `value` — ONLY if pay_composition.json
    lists `component` (matched by substring, e.g. 'employer_social_contributions')
    as one of source_id's separately_published_components. Rule 2: this is
    the only subtraction path in this module, and there is no corresponding
    add_component() — a component the source never measured is never
    synthesised and added, under any name."""
    comp = _composition(source_id)
    if comp is None:
        return {"ok": False, "reason": f"no pay_composition.json entry for {source_id!r}"}
    published = comp.get("separately_published_components", [])
    if not any(component in p for p in published):
        return {"ok": False, "reason": f"{source_id!r}'s pay_composition entry does not list "
                 f"{component!r} as a separately_published_component ({published!r}) — refusing to "
                 "subtract a component the source does not itself publish separately"}
    return {
        "ok": True,
        "value_after_subtraction": value - component_value,
        "chain": [{"op": "subtract", "detail": f"{value} - {component_value} ({component}, sourced "
                   f"from {source_id}'s own separately-published figure — pay_composition.json entry "
                   f"cites the evidence)"}],
        "component_subtracted": component, "component_value": component_value,
    }


def comparison_basis(source_id_a: str, source_id_b: str) -> dict:
    """The pay-composition analogue of scripts/crosswalk.py's compare():
    can source_id_a and source_id_b be compared on the SAME basis —
    regular_pay (excludes irregular_bonus and employer_social_contributions)
    or total_earnings (includes irregular_bonus, excludes employer
    contributions)? Refuses, with a reason, rather than comparing two
    figures that mean different things — rule 4.

    Checks each source's RAW pay_composition.json entry, not a
    post-subtraction state — Denmark's own FORINKL includes employer
    pension by construction, so this reports 'neither' basis for
    salary_dk as shipped, even though subtract_component() can turn it
    into a real total_earnings figure. That subtraction is the caller's
    job (and its own, separate step with its own chain) — this function
    does not track "what basis does the value become after a specific
    subtraction", only what the source natively supports.

    FIX (package 9, tier 7, adversarial review finding F1): the first
    version of this function granted total_earnings to any source with
    employer_social_contributions == False, without checking
    irregular_bonus at all. total_earnings is DEFINED (work order
    §5.1.4) as "includes irregular bonuses, excludes employer
    contributions" — a source whose own figure EXCLUDES the bonus
    (Sweden, Netherlands, Finland, Ireland — all bonus=False) does not
    become a total_earnings figure just because it also has no employer
    contributions to exclude; it is a regular_pay figure, full stop.
    The old code let comparison_basis('salary_se', 'salary_es') report
    'total_earnings' as a shared basis — Sweden's bonus-excluded
    Manadslon compared as equivalent to Spain's bonus-included Ganancia
    bruta anual, exactly the "two different earnings concepts" mixing
    rule 4 exists to prevent. Fixed: total_earnings now requires
    irregular_bonus is True, symmetric with regular_pay's own
    irregular_bonus is False requirement.

    Two sources — US (bls_oews) and UK (salary_uk) — store irregular_bonus
    as a descriptive STRING, not a boolean, because their real-world
    composition doesn't collapse cleanly to one (BLS: "partial —
    production/incentive pay included, non-production bonuses excluded";
    ASHE: "true (annual) / false (weekly...)" — this pipeline's own
    _extract_uk() reads the ANNUAL field specifically). `is True`/`is
    False` identity checks never match a string, so without a specific
    rule these two would silently express NEITHER basis — safe (refusal,
    never a wrong comparison) but not what the work order's own §5.1.4
    table explicitly assigns: US under regular_pay ("closer to the
    regular-pay concept... production/incentive pay is closer to base
    pay than a discretionary bonus is"), UK under total_earnings ("annual
    ... yes, in full"). Both overrides below cite that table as their
    authority, not a guess made here."""
    a, b = _composition(source_id_a), _composition(source_id_b)
    if a is None or b is None:
        missing = source_id_a if a is None else source_id_b
        return {"comparable": False, "reason": f"no pay_composition.json entry for {missing!r}"}

    # Work order §5.1.4's own explicit basis table for the two sources whose
    # irregular_bonus field is prose, not a boolean — see docstring above.
    _STRING_BONUS_OVERRIDE = {"bls_oews": "regular_pay", "salary_uk": "total_earnings"}

    def bases(comp: dict) -> set[str]:
        b_set = set()
        bonus, contrib = comp.get("irregular_bonus"), comp.get("employer_social_contributions")
        if bonus is False and contrib is False:
            b_set.add("regular_pay")
        if bonus is True and contrib is False:
            b_set.add("total_earnings")
        override = _STRING_BONUS_OVERRIDE.get(comp.get("source_id"))
        if override and contrib is False:
            b_set.add(override)
        return b_set

    common = bases(a) & bases(b)
    if not common:
        return {"comparable": False,
                 "reason": f"{source_id_a} and {source_id_b} share no common basis — "
                 f"{source_id_a} can express {sorted(bases(a)) or ['neither']}, "
                 f"{source_id_b} can express {sorted(bases(b)) or ['neither']}"}
    return {"comparable": True, "common_bases": sorted(common)}
