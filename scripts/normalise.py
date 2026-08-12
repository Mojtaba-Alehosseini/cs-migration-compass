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
  6. Hourly->annual requires a sourced hours figure. annualise() raises
     rather than falling back to a flat 2080 (the US 40x52 convention) —
     see hours_for()'s own docstring for why that convention would
     specifically overstate Denmark.
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


def to_usd(value: float, country: str, year: int) -> dict:
    """Convert a native-currency value to USD at the rate from ITS OWN year.
    Returns {"ok": False, "reason": ...} rather than a number if that
    year's rate is unavailable — never substitutes a different year."""
    rate = fx_rate(country, year)
    if rate is None:
        return {"ok": False, "reason": f"no FX rate for {country} in {year} — "
                 "not converted, never substituted from a different year"}
    return {
        "ok": True,
        "value_usd": value / rate["rate"],
        "chain": [
            {"op": "fx_convert", "detail": f"{value} / {rate['rate']} ({country} {year} period-average "
             f"rate, {rate['source']})"},
        ],
        "fx_rate": rate["rate"], "fx_year": year, "fx_source": rate["source"],
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
    full-time hours (~38.2/week, verified live in scripts/src_hours_worked.py)
    would be overstated by roughly 7% under that assumption. A country
    with no entry in hours_worked.json gets None here, and annualise()
    refuses to guess past that."""
    series = _hours_series(country)
    if not series:
        return None
    use_year = str(year) if year is not None and str(year) in series else max(series, key=int)
    row = series[use_year]
    return {"hours_per_week": row["usual_weekly_hours"], "year": int(use_year), "country": country,
            "reliability_flag": row.get("reliability_flag"),
            "source": "hours_worked (Eurostat lfsa_ewhun2 / Statistics Canada WDS)"}


def annualise(value: float, period: str, country: str, hours_year: int | None = None) -> dict:
    """period is 'hour', 'month' or 'year'. 'year' returns the value
    unchanged (already annual). 'month' multiplies by MONTHLY_MULTIPLIER
    (12) — rule 3, the only multiplier this module uses for that
    conversion, anywhere. 'hour' requires hours_for(country) to return a
    real, sourced figure; if it does not, this returns {"ok": False, ...}
    rather than assuming 2080 — rule 6."""
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
    subtraction", only what the source natively supports."""
    a, b = _composition(source_id_a), _composition(source_id_b)
    if a is None or b is None:
        missing = source_id_a if a is None else source_id_b
        return {"comparable": False, "reason": f"no pay_composition.json entry for {missing!r}"}

    def bases(comp: dict) -> set[str]:
        b_set = set()
        bonus, contrib = comp.get("irregular_bonus"), comp.get("employer_social_contributions")
        if bonus is False and contrib is False:
            b_set.add("regular_pay")
        if contrib is False:
            b_set.add("total_earnings")
        return b_set

    common = bases(a) & bases(b)
    if not common:
        return {"comparable": False,
                 "reason": f"{source_id_a} and {source_id_b} share no common basis — "
                 f"{source_id_a} can express {sorted(bases(a)) or ['neither']}, "
                 f"{source_id_b} can express {sorted(bases(b)) or ['neither']}"}
    return {"comparable": True, "common_bases": sorted(common)}
