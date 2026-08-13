"""Tier 6's build-time resolver — the ONLY place crosswalk.compare() and
normalise.py's conversion functions run against real salary data to produce
what the UI actually renders. Per crosswalk.py's own docstring ("package 9
must call this function rather than re-deriving the rule in the UI") and
normalise.py's pure, side-effect-free design (no fetch, no I/O), no
equivalent logic exists client-side — the browser only ever displays
data/processed/wage_distribution.json, built here.

REFERENCE COUNTRY: Sweden, isco08:2512, "high" confidence — the same country
crosswalk.py's own gate-7 demonstration uses as mapping_a in every sample
pair (crosswalk.py:236-243). Every other country's occupation mapping is
compared() against Sweden's to get a real, reproducible depth/degradation
verdict, not a fresh judgement call made here.

WHY EACH SOURCE HAS ITS OWN EXTRACTOR: verified against the real, live
data/processed/*.json this session — thirteen genuinely different shapes
(monthly vs hourly vs annual native period; a "dispersion_by_year" dict vs a
flat "dispersion" vs no wrapper at all; UK and CA already-annual figures
sitting directly on the occupation record; BLS keyed by city with a
"_national" sibling; Ireland/Qatar/UAE with mean-only or gendered-split
figures). No universal schema exists at the harvester level anywhere in this
pipeline (see scripts/src_salary_*.py, each shaped by its own source), so
none is invented here either — a small, explicit adapter per source is more
honest than a generic parser that would silently misread the one shape it
wasn't built for.

BASIS AVAILABILITY, verified against data/pay_composition.json's actual
booleans (updated package 10, tier 0.3 — Norway moved buckets, see below):
Sweden/Netherlands/Ireland/Finland/Norway (bonus=False, contrib=False, or a
genuine dual-basis native split) express BOTH regular_pay and total_earnings
natively. UK/US/Spain/Australia (contrib=False, bonus=True or a non-boolean
caveat string) express only total_earnings. Canada/Qatar/UAE (both fields
"unknown") express NEITHER — an honest gap, not a bug: this pipeline does
not guess a boolean it hasn't verified. Denmark (bonus=True, contrib=True,
BOTH separately published as PENSST/UREGELST — package 10, tier 0.2,
switched from PENS/UREGEL, see _extract_dk) is the one source that needs
subtract_component() calls to reach either basis at all — matching the
smoke-test finding recorded in normalise.py's own commit history: Denmark's
raw STAND expresses neither basis unmodified. Norway (NEEDS-DECISION #18,
resolved) turned out to have the Finland shape, not the "flat-scalar
subtraction" shape a first read of the work order suggested: SSB's table
11418 publishes AvtaltManedslonn (regular_pay basis) at the same
measuring-method granularity as the total, so _extract_no() selects between
two real native fields exactly like _extract_fi() does — no subtraction,
no flat scalar, no distribution-distorting assumption to disclose.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, PROCESSED, log  # noqa: E402
import crosswalk  # noqa: E402
import normalise as nm  # noqa: E402

REFERENCE = ("SE", "2512")


# --------------------------------------------------------------------------
# Per-source extraction: each returns the LATEST year's observation as
# {"year": int, "period": "hour"|"month"|"year", "currency": "SEK", ...,
#  "mean"/"median"/"p10"/"p25"/"p75"/"p90": float|None, "n_employees": int|None}
# All percentile keys are always present (None where the source doesn't
# publish that one) so downstream code never has to guess a field exists.
# --------------------------------------------------------------------------

def _pick(d: dict, suffix: str) -> float | None:
    for k, v in d.items():
        if k.endswith(suffix) and v is not None:
            return float(v)
    return None


def _latest_year_row(by_year: dict) -> tuple[str, dict]:
    return max(by_year.items(), key=lambda kv: kv[0])


def _classify_distribution(obs: dict) -> str:
    """FIXED (tier 7, adversarial review finding F14): the original
    two-way check ("full" if p10 present, else "central-tendency-only")
    conflated two genuinely different shapes — Denmark/Norway/Netherlands
    publish p25/median/p75 (a real quartile spread) but not p10/p90, and
    were being labelled "central-tendency-only" (no spread at all), the
    same label Australia/Ireland correctly get for publishing only a
    mean/median with NOTHING else. WagePanel.tsx's own chart already drew
    the quartile box correctly regardless (it checks the actual p25/p75
    values present, not this label) — only this label, and the country-
    page prose built from it, were wrong."""
    if obs.get("p10") is not None and obs.get("p90") is not None:
        return "full"
    if obs.get("p25") is not None and obs.get("p75") is not None:
        return "quartile-only"
    if obs.get("median") is not None:
        return "central-tendency-only"
    return "mean-only"


def _base_obs(period: str, currency: str, year, row: dict, unit_suffix: str) -> dict:
    return {
        "year": int(year), "period": period, "currency": currency,
        "mean": _pick(row, f"mean_{unit_suffix}"), "median": _pick(row, f"median_{unit_suffix}"),
        "p10": _pick(row, f"p10_{unit_suffix}"), "p25": _pick(row, f"p25_{unit_suffix}"),
        "p75": _pick(row, f"p75_{unit_suffix}"), "p90": _pick(row, f"p90_{unit_suffix}"),
        "n_employees": row.get("n_employees"),
    }


def _extract_se(occ: dict) -> dict:
    year, row = _latest_year_row(occ["dispersion_by_year"])
    return _base_obs("month", "SEK", year, row, "sek_month")


DK_STANDARDISED_HOURS_PER_WEEK = 37.0  # matches src_salary_dk.py's own constant — see that module's
                                        # docstring for the empirical STAND<->MDRSNIT proof this rests on


def _extract_dk(occ: dict) -> dict:
    """Package 10, tier 0.2 (NEEDS-DECISION #17): switched from the FORINKL
    family (DKK per hour ACTUALLY WORKED) to the STAND family (DKK per DK's
    own STANDARDISED hour) as the primary DK figure. FORINKL x Eurostat's
    measured hours overstated DST's own MDRSNIT monthly headline by 23-25%
    every year checked — not a real disagreement between two DST statistics,
    but this pipeline comparing two different LØNMÅL concepts as if they were
    one. STAND x DK's own 160.33h/month standardisation constant reproduces
    MDRSNIT to <0.002% (src_salary_dk.py's mdrsnit_reconciliation, re-proven
    on every harvester run, not asserted once and trusted forever).

    explicit_hours_by_field carries DK_STANDARDISED_HOURS_PER_WEEK (37h) for
    every field STAND publishes — a fixed constant, not hours_worked.json's
    generic Eurostat lookup, because STAND is already expressed per
    standardised hour: annualising it with Eurostat's *measured* hours would
    reintroduce the exact mismatch this fix removes. Same explicit_hours
    mechanism as Ireland's F2 fix (package 9) — a source's own matched hours
    figure beats the generic cross-country lookup — just a fixed constant
    here rather than a per-year measurement, because DK's standardisation
    convention does not itself vary year to year the way measured hours do."""
    year, row = _latest_year_row(occ["dispersion_by_year"])
    obs = _base_obs("hour", "DKK", year, row, "std_dkk_hour")
    obs["employer_pension_dkk_hour"] = row.get("employer_pension_std_dkk_hour")
    obs["irregular_dkk_hour"] = row.get("irregular_std_dkk_hour")
    obs["also_published"] = {
        "concept": "FORINKL — DKK per hour actually worked (not standardised)",
        "mean": row.get("mean_dkk_hour"), "median": row.get("median_dkk_hour"),
        "p25": row.get("p25_dkk_hour"), "p75": row.get("p75_dkk_hour"),
        "note": "DST publishes this alongside STAND; kept for context, not used for any figure this "
                "site computes — it does not reconcile with DST's own MDRSNIT monthly headline the way "
                "STAND does. See scripts/src_salary_dk.py's module docstring.",
    }
    hours_note = {
        "hours_per_week": DK_STANDARDISED_HOURS_PER_WEEK, "year": int(year),
        "source": "Danmarks Statistik's own standardised full-time week (37h) — empirically verified "
                   "via the STAND x 160.33h/month = MDRSNIT identity, <0.002% residual across all "
                   "years/occupations in table LONS20 (src_salary_dk.py mdrsnit_reconciliation), not "
                   "the generic cross-country hours_worked.json Eurostat figure",
    }
    obs["explicit_hours_by_field"] = {f: hours_note for f in ("mean", "median", "p25", "p75")}
    row_check = occ.get("mdrsnit_reconciliation_by_year", {}).get(year)
    if row_check:
        obs["mdrsnit_check"] = row_check
    return obs


def _extract_no(occ: dict) -> dict:
    """Package 10, tier 0.3 (NEEDS-DECISION #18, resolved): SSB's table 11418
    publishes AvtaltManedslonn (basic salary, bonus/overtime/irregular
    allowances OUT) at the same measuring-method granularity as Manedslonn
    (total, bonus IN) — a genuine dual-basis native source, the same shape
    as Finland's total_*/regular_* split (_extract_fi), not a subtraction
    this pipeline performs. See src_salary_no.py's module docstring.

    Generic mean/median/p25/p75 keys are set explicitly from the UNPREFIXED
    (Manedslonn/total) fields here, NOT via _base_obs's suffix match — both
    "mean_nok_month" and "avtalt_mean_nok_month" end with "nok_month", so a
    generic suffix match would silently pick whichever key happens to
    iterate first in the source dict. This is the exact bug package 9 found
    and fixed for Finland's total_/regular_ split (adversarial review,
    tier 6) — the same fix, applied here before it could ship broken."""
    year, row = _latest_year_row(occ["dispersion_by_year"])
    obs = {
        "year": int(year), "period": "month", "currency": "NOK",
        "mean": row.get("mean_nok_month"), "median": row.get("median_nok_month"),
        "p10": None, "p25": row.get("p25_nok_month"), "p75": row.get("p75_nok_month"), "p90": None,
        "n_employees": row.get("n_employees"),
    }
    for basis, prefix in (("total_earnings", ""), ("regular_pay", "avtalt_")):
        obs[f"basis_{basis}"] = {
            "mean": row.get(f"{prefix}mean_nok_month"), "median": row.get(f"{prefix}median_nok_month"),
            "p10": None, "p25": row.get(f"{prefix}p25_nok_month"),
            "p75": row.get(f"{prefix}p75_nok_month"), "p90": None,
        }
    return obs


def _extract_fi(occ: dict) -> dict:
    """Finland already publishes two parallel series — total_* (total_earnings)
    and regular_* (regular_pay), see module docstring — so there is no single
    basis-neutral "native" figure the way DK/SE/etc. have one. The generic
    mean/median/p10/p90 keys (which every other extractor relies on for the
    "native" display block) are set explicitly from the regular_ prefix here,
    matching the panel's own stated default ("native and regular are the
    defaults") — NOT left to _base_obs's generic eur_month suffix match, which
    would silently return whichever of total_/regular_ happens to iterate
    first in the source dict (verified live: that was "total_", by accident
    of key insertion order, not by any deliberate choice — caught by
    inspecting the actual resolved native.value against the source's own
    total_median_eur_month before this fix)."""
    row = occ["dispersion"]
    obs = {
        "year": int(occ["year"]), "period": "month", "currency": "EUR",
        "mean": row.get("regular_mean_eur_month"), "median": row.get("regular_median_eur_month"),
        "p10": row.get("regular_p10_eur_month"), "p90": row.get("regular_p90_eur_month"),
        "p25": None, "p75": None,
    }
    for basis, prefix in (("total_earnings", "total"), ("regular_pay", "regular")):
        obs[f"basis_{basis}"] = {
            "mean": row.get(f"{prefix}_mean_eur_month"), "median": row.get(f"{prefix}_median_eur_month"),
            "p10": row.get(f"{prefix}_p10_eur_month"), "p90": row.get(f"{prefix}_p90_eur_month"),
            "p25": None, "p75": None,
        }
    obs["n_employees"] = row.get("n_employees")
    return obs


def _extract_de(occ: dict) -> dict:
    """Package 11, tier 2: Germany's own two GENESIS tables (62361-0030,
    excl. special payments = regular_pay; 62361-0034, incl. special
    payments = total_earnings) are a genuine dual-native-basis source, the
    same shape as Finland's total_*/regular_* split and Norway's
    Manedslonn/AvtaltManedslonn split above — not a subtraction.

    The one real difference from those two: Destatis publishes -0030
    monthly and -0034 annually — different NATIVE periods for the same
    occupation, where _figure_for_basis()'s own dual-basis branch (below)
    assumes one shared period across both bases (true for FI/NO, both
    monthly). Rather than extending that mechanism for one source,
    -0030's own monthly median/mean are annualised HERE (x12, this
    pipeline's own single fixed multiplier — normalise.py's own
    annualise() applies the identical x12 everywhere else, just at
    combo-resolution time instead of extraction time) so both bases share
    period="year" and the rest of the pipeline never has to know Germany's
    own tables disagree about period at the source."""
    row = occ["dispersion"]
    reg_median = row.get("regular_median_eur_month")
    reg_mean = row.get("regular_mean_eur_month")
    reg_median_year = round(reg_median * 12, 2) if reg_median is not None else None
    reg_mean_year = round(reg_mean * 12, 2) if reg_mean is not None else None
    return {
        "year": int(occ["year"]), "period": "year", "currency": "EUR",
        "mean": reg_mean_year, "median": reg_median_year,
        "p10": None, "p25": None, "p75": None, "p90": None,
        "n_employees": None,
        "basis_regular_pay": {
            "mean": reg_mean_year, "median": reg_median_year,
            "p10": None, "p25": None, "p75": None, "p90": None,
        },
        "basis_total_earnings": {
            "mean": row.get("total_mean_eur_year"), "median": row.get("total_median_eur_year"),
            "p10": None, "p25": None, "p75": None, "p90": None,
        },
    }


def _extract_es(occ: dict) -> dict:
    row = occ["dispersion"]
    return _base_obs("year", "EUR", occ["year"], row, "eur_year")


def _extract_uk(occ: dict) -> dict:
    return _base_obs("year", "GBP", 2025, occ, "gbp_year")  # ASHE 2025 provisional — flat on the record


def _extract_ca(occ: dict) -> dict:
    national = next(g for g in occ["geographies"] if g.get("is_national"))
    return {
        "year": 2024, "period": "hour", "currency": "CAD",  # reference_period "2023-2024"
        "mean": national.get("average_cad_hour"), "median": national.get("median_cad_hour"),
        "p10": national.get("p10_low_cad_hour"), "p25": national.get("p25_q1_cad_hour"),
        "p75": national.get("p75_q3_cad_hour"), "p90": national.get("p90_high_cad_hour"),
        "n_employees": None,
    }


def _extract_us(data: dict) -> dict:
    nat = data["_national"]

    def v(key: str) -> float | None:
        series = nat.get(key) or []
        return series[-1]["value"] if series else None

    return {
        "year": int((nat.get("annual_median_usd") or [{}])[-1].get("year", 2025)),
        "period": "year", "currency": "USD",
        "mean": v("annual_mean_usd"), "median": v("annual_median_usd"),
        "p10": v("annual_p10_usd"), "p25": v("annual_p25_usd"),
        "p75": v("annual_p75_usd"), "p90": v("annual_p90_usd"),
        "n_employees": v("employment"),
    }


def _extract_au(occ: dict) -> dict:
    row = occ["salary_or_wage_income"]  # closest to "wages" among the three concepts this source offers
    return {
        "year": 2024, "period": "year", "currency": "AUD",
        "mean": row.get("mean_aud_year"), "median": row.get("median_aud_year"),
        "p10": None, "p25": None, "p75": None, "p90": None,
        "n_employees": occ.get("n_individuals"),
        "distribution": occ.get("distribution"),
    }


def _extract_nl(occ: dict) -> dict:
    year, row = _latest_year_row(occ["dispersion_by_year"])
    obs = _base_obs("hour", "EUR", year, row, "eur_hour")
    obs["n_employees"] = (row.get("n_employees_thousands") or 0) * 1000 or None
    return obs


def _extract_ie(occ: dict) -> dict:
    """CSO SES06 publishes mean_paid_weekly_hours / median_paid_weekly_hours
    ALONGSIDE mean_eur_hour / median_eur_hour, in the same row, for the
    identical population (SOC major group 2, same year) — a strictly
    better hours match than the generic cross-country hours_worked.json
    (Eurostat lfsa_ewhun2), which measures ALL full-time employees
    regardless of occupation and, used here, overstated Ireland's mean by
    a measured 21.4% (33.6 CSO-matched hours vs 40.8 Eurostat all-employee
    hours) — adversarial review finding F2. Carried through per-field
    (mean's own hours for the mean value, median's own for the median) so
    resolve_country() can pass them to annualise()'s explicit_hours."""
    year, row = _latest_year_row(occ["by_year"])
    return {
        "year": int(year), "period": "hour", "currency": "EUR",
        "mean": row.get("mean_eur_hour"), "median": row.get("median_eur_hour"),
        "p10": None, "p25": None, "p75": None, "p90": None,
        "n_employees": None, "distribution": occ.get("distribution"),
        "explicit_hours_by_field": {
            "mean": {"hours_per_week": row.get("mean_paid_weekly_hours"), "year": int(year),
                     "source": "CSO SES06 (mean_paid_weekly_hours — matched to this same cell, not "
                               "the generic cross-country hours_worked.json)"},
            "median": {"hours_per_week": row.get("median_paid_weekly_hours"), "year": int(year),
                       "source": "CSO SES06 (median_paid_weekly_hours — matched to this same cell, not "
                                 "the generic cross-country hours_worked.json)"},
        },
    }


def _extract_qa(occ: dict) -> dict:
    """Qatar publishes Male/Female wages separately with no combined figure —
    a real, transparent weighted mean (weighted by each group's own published
    employee count) is computed here rather than either inventing a combined
    number some other way or silently picking one gender. The weighting is
    recorded in the observation so it is never mistaken for a native figure."""
    year, row = _latest_year_row(occ["by_year"])
    m, f = row.get("Males") or {}, row.get("Females") or {}
    m_n, f_n = m.get("paid_employment_workers") or 0, f.get("paid_employment_workers") or 0
    m_w, f_w = m.get("monthly_average_wage_qar"), f.get("monthly_average_wage_qar")
    weighted = None
    if m_w is not None and f_w is not None and (m_n + f_n) > 0:
        weighted = (m_w * m_n + f_w * f_n) / (m_n + f_n)
    return {
        "year": int(year), "period": "month", "currency": "QAR",
        "mean": weighted, "median": None, "p10": None, "p25": None, "p75": None, "p90": None,
        "n_employees": m_n + f_n, "distribution": occ.get("distribution"),
        "weighting_note": f"mean weighted by Qatar PSA's own published Male (n={m_n}, "
            f"{m_w} QAR/mo) and Female (n={f_n}, {f_w} QAR/mo) counts — not a native combined figure",
    }


def _extract_ae(occ: dict) -> dict:
    return {
        "year": 2009, "period": "month", "currency": "AED",
        "mean": occ.get("monthly_average_wage_aed"), "median": None,
        "p10": None, "p25": None, "p75": None, "p90": None,
        "n_employees": None, "distribution": occ.get("distribution"),
    }


# country -> (source_id, national_code, extractor, occ_lookup)
# occ_lookup 'occupations' pulls data.occupations[national_code]; 'root' passes data itself (bls_oews).
SOURCE_TABLE = {
    "SE": ("salary_se", "2512", _extract_se, "occupations"),
    "GB": ("salary_uk", "2134", _extract_uk, "occupations"),
    "US": ("bls_oews", "15-1252", _extract_us, "root"),
    "DK": ("salary_dk", "2512", _extract_dk, "occupations"),
    "NO": ("salary_no", "2512", _extract_no, "occupations"),
    "FI": ("salary_fi", "2512", _extract_fi, "occupations"),
    "AU": ("salary_au", "261313", _extract_au, "occupations"),
    "ES": ("salary_es", "it_professionals", _extract_es, "occupations"),
    "IE": ("salary_ie", "soc1:2", _extract_ie, "occupations"),
    "QA": ("salary_qa", "isco08_major:2", _extract_qa, "occupations"),
    "AE": ("salary_ae", "isco08_major:2", _extract_ae, "occupations"),
    # NL is real, sourced data with a real crosswalk verdict (comparable=False,
    # "no ISCO-08 correspondence") — it belongs in SOURCE_TABLE, not ABSENT,
    # because ABSENT means "nothing to plot anywhere", and NL's country page
    # has a real number to show even though the cross-country panel excludes
    # it. An earlier version of this file put NL in ABSENT with a comment
    # claiming its country page would still show real data — untrue at the
    # time, since ABSENT countries never reach wage_distribution.json at all;
    # caught by checking the actual rendered country page against that claim.
    "NL": ("salary_nl", "0811", _extract_nl, "occupations"),
    # Package 11, tier 2: unblocked. KldB 2010 group 434 is Destatis's own
    # 3-digit rollup ("Occup. in software development and programming") —
    # see src_salary_de.py's own module docstring for why this specific
    # code, and data/occupations.json for the crosswalk depth this maps at.
    "DE": ("salary_de", "434", _extract_de, "occupations"),
}
# Canada gets two rows — see NEEDS-DECISION.md #12, still open: shown side by
# side rather than combined or picking one, the least-invented of the three
# options the decision names, and reversible the moment #12 is actually
# resolved by the project owner.
CANADA_CODES = ["21231", "21232"]

ABSENT = {
    "IT": "no-series — ISTAT publishes no occupation-level (CP2011) earnings flow at all, per "
          "src_salary_it.py",
}


# --------------------------------------------------------------------------
# Basis resolution — native figure, or a subtraction chain, or a refusal
# --------------------------------------------------------------------------

_FIELDS = ("mean", "median", "p10", "p25", "p75", "p90")


def _repr_field(obs: dict) -> str:
    """The one field whose own trace becomes the displayed chain — every stage
    (subtract, annualise, to_usd) must pick the SAME field, or the chain shown
    to a reader mixes one field's subtraction with a different field's
    annualisation, producing numbers that don't actually chain into each
    other. (Caught by inspecting a real Denmark run: the annualise step's
    "420.85 x 38.4" didn't follow from the subtract step's own "= 402.12"
    directly above it, because the first pass captured the median's subtract
    trace but the mean's annualise trace — first-non-None-field, not a
    chosen, consistent field.) Prefers median; falls back to mean, since
    every source in this pipeline publishes at least one of the two."""
    return "median" if obs.get("median") is not None else "mean"


def _figure_for_basis(source_id: str, obs: dict, basis: str, repr_field: str) -> dict:
    """Returns {"ok": True, "value": {mean,median,p10,p25,p75,p90}, "chain": [...]}
    or {"ok": False, "reason": "..."} — calling normalise.py's real functions,
    never re-deriving their verdicts. `chain` is built from `repr_field` only —
    see _repr_field()."""
    if "basis_total_earnings" in obs:  # Finland — already-split native fields
        key = "basis_total_earnings" if basis == "total_earnings" else "basis_regular_pay"
        return {"ok": True, "value": obs[key],
                "chain": [{"op": "native_basis_select", "detail": f"{source_id} publishes "
                           f"{basis} as its own separate field — no subtraction needed"}]}

    check = nm.comparison_basis(source_id, source_id)
    native_ok = check.get("comparable") and basis in (check.get("common_bases") or [])
    if native_ok:
        value = {k: obs.get(k) for k in _FIELDS}
        return {"ok": True, "value": value, "chain": [{"op": "native", "detail": "published as-is; "
                 f"{source_id}'s composition already excludes what {basis} requires excluded"}]}

    if source_id == "salary_dk":
        # Denmark: raw STAND (standardised-hour earnings, package 10 tier 0.2 — see
        # src_salary_dk.py's module docstring) = base + PENSST (employer_social_contributions)
        # + UREGELST (irregular_bonus). regular_pay needs both subtracted; total_earnings needs
        # only PENSST subtracted (total_earnings still includes the irregular bonus).
        to_subtract = ["employer_social_contributions"] if basis == "total_earnings" \
            else ["employer_social_contributions", "irregular_bonus"]
        value, chain = {}, []
        mdrsnit_check = obs.get("mdrsnit_check")
        if mdrsnit_check:
            chain.append({"op": "concept_note", "detail": "published as DKK per DK's own standardised "
                          f"hour (STAND, table LONS20) — verified against Danmarks Statistik's own "
                          f"separately-published monthly headline (MDRSNIT): "
                          f"{mdrsnit_check['stand_dkk_hour']} x 160.33h/month = "
                          f"{mdrsnit_check['computed_monthly']:,.2f}, DST publishes "
                          f"{mdrsnit_check['published_mdrsnit']:,.2f} "
                          f"({mdrsnit_check['residual_pct']:+.3f}% residual)"})
        ok_all = True
        for field in _FIELDS:
            v = obs.get(field)
            if v is None:
                value[field] = None
                continue
            for component in to_subtract:
                comp_value = obs["employer_pension_dkk_hour"] if "employer_social" in component \
                    else obs["irregular_dkk_hour"]
                result = nm.subtract_component(v, source_id, component, comp_value)
                if not result.get("ok"):
                    ok_all = False
                    value[field] = None
                    break
                v = result["value_after_subtraction"]
                if field == repr_field:
                    chain.append(result["chain"][0])
            else:
                value[field] = v
        if ok_all:
            # Package 10, tier 0.2: state the flat-scalar assumption as its own
            # visible step, rather than let a mean-derived scalar silently reshape
            # a distribution (the work order's own words). DST publishes PENSST/
            # UREGELST only as one figure per occupation, not broken out by
            # percentile, so the SAME subtracted amount was just applied to every
            # one of p25/median/p75 above — this line is that assumption, named.
            chain.append({"op": "assumption", "detail": "the same PENSST/UREGELST rate is subtracted "
                          "at every percentile shown — Danmarks Statistik does not publish either "
                          "component broken out by percentile, only once for the whole occupation. "
                          "This assumes a flat per-hour krone amount rather than a constant share of "
                          "pay; if employer pension is negotiated as a percentage of salary (common "
                          "under Danish overenskomster), the true gap is understated at the top of the "
                          "distribution and overstated at the bottom. Unresolved — see NEEDS-DECISION.md."})
            return {"ok": True, "value": value, "chain": chain}
        return {"ok": False, "reason": f"{source_id}: subtract_component() refused one of {to_subtract}"}

    return {"ok": False, "reason": check.get("reason") or f"{source_id} does not publish enough to "
            f"express {basis} and has no separately-published component this pipeline can subtract "
            "to reach it (pay_composition.json's own fields say so — see its own note per source)"}


def _to_usd_all(value: dict, country: str, year: int, repr_field: str) -> dict:
    out, chain, ok_any = {}, None, False
    for field in _FIELDS:
        v = value.get(field)
        if v is None:
            out[field] = None
            continue
        r = nm.to_usd(v, country, year)
        if not r.get("ok"):
            out[field] = None
            continue
        ok_any = True
        out[field] = r["value_usd"]
        if field == repr_field:
            chain = r
    if not ok_any:
        return {"ok": False, "reason": nm.to_usd(next((v for v in value.values() if v is not None), 0),
                                                   country, year).get("reason")}
    if chain is None:  # repr_field itself was None for this row (e.g. AU has no p10) — fall back to any success
        chain = next(nm.to_usd(v, country, year) for v in value.values() if v is not None)
    return {"ok": True, "value": out, "fx_rate": chain["fx_rate"], "fx_year": chain["fx_year"],
            "fx_source": chain["fx_source"], "chain_step": chain["chain"][0]}


def _annualise_all(value: dict, period: str, country: str, hours_year: int | None, repr_field: str,
                    explicit_hours_by_field: dict | None = None) -> dict:
    """explicit_hours_by_field (finding F2): {field: {hours_per_week, year,
    source}}, when given, overrides hours_for() PER FIELD — Ireland's own
    mean/median each carry their own CSO-matched hours, not one shared
    country-level figure, so this cannot just be a single explicit_hours
    value threaded through every field the way a plain override would be."""
    if period == "year":
        return {"ok": True, "value": value, "chain": [{"op": "identity", "detail": "already annual"}]}
    ehf = explicit_hours_by_field or {}
    out, meta_chain, ok_any = {}, None, False
    for field in _FIELDS:
        v = value.get(field)
        if v is None:
            out[field] = None
            continue
        r = nm.annualise(v, period, country, hours_year, explicit_hours=ehf.get(field))
        if not r.get("ok"):
            out[field] = None
            continue
        ok_any = True
        out[field] = r["value_annual"]
        if field == repr_field:
            meta_chain = r
    if not ok_any:
        sample_field = next(f for f in _FIELDS if value.get(f) is not None)
        sample = nm.annualise(value[sample_field], period, country, hours_year, explicit_hours=ehf.get(sample_field))
        return {"ok": False, "reason": sample.get("reason")}
    if meta_chain is None:
        rf = next(f for f in _FIELDS if value.get(f) is not None)
        meta_chain = nm.annualise(value[rf], period, country, hours_year, explicit_hours=ehf.get(rf))
    return {"ok": True, "value": out, "chain": meta_chain["chain"]}


def resolve_country(cc: str, source_id: str, national_code: str, obs: dict, mapping: dict | None) -> dict:
    ref_mapping = crosswalk.load()[1].get(REFERENCE)
    cw = crosswalk.compare(ref_mapping, mapping) if mapping else \
        {"comparable": False, "reason": "no occupation crosswalk mapping exists for this country"}
    repr_field = _repr_field(obs)

    combos: dict[str, dict] = {}
    for currency_mode in ("native", "usd"):
        for basis in ("regular_pay", "total_earnings"):
            combo_key = f"{currency_mode}_{basis}"
            basis_result = _figure_for_basis(source_id, obs, basis, repr_field)
            if not basis_result["ok"]:
                combos[combo_key] = {"ok": False, "reason": basis_result["reason"]}
                continue
            value, chain = dict(basis_result["value"]), list(basis_result["chain"])
            this_repr_field = repr_field if value.get(repr_field) is not None else \
                next((f for f in _FIELDS if value.get(f) is not None), repr_field)

            ann = _annualise_all(value, obs["period"], cc, obs["year"], this_repr_field,
                                  explicit_hours_by_field=obs.get("explicit_hours_by_field"))
            if not ann["ok"]:
                combos[combo_key] = {"ok": False, "reason": ann["reason"]}
                continue
            value, chain = ann["value"], chain + ann["chain"]

            if currency_mode == "usd":
                usd = _to_usd_all(value, cc, obs["year"], this_repr_field)
                if not usd["ok"]:
                    combos[combo_key] = {"ok": False, "reason": usd["reason"]}
                    continue
                value = usd["value"]
                chain = chain + [usd["chain_step"]]

            combos[combo_key] = {"ok": True, "value": value, "chain": chain,
                                  "currency": "USD" if currency_mode == "usd" else obs["currency"],
                                  "chain_field": this_repr_field}

    return {
        "country": cc, "source_id": source_id, "national_code": national_code,
        "native": {"currency": obs["currency"], "period": obs["period"], "year": obs["year"],
                   "value": {k: obs.get(k) for k in ("mean", "median", "p10", "p25", "p75", "p90")},
                   "n_employees": obs.get("n_employees"),
                   "distribution": obs.get("distribution") or _classify_distribution(obs),
                   # FIXED (tier 7, adversarial review finding F15): Qatar's
                   # mean is this pipeline's OWN weighted average of PSA's
                   # separately-published Male/Female series (see
                   # _extract_qa's docstring) — a real derivation, not a
                   # value PSA itself published. weighting_note carries
                   # exactly how, so the UI can say so rather than
                   # presenting it as a plain sourced figure. None for
                   # every other country (nothing else in this file
                   # computes a native-currency value; conversions are a
                   # separate, already-disclosed step in combos.*.chain).
                   "weighting_note": obs.get("weighting_note"),
                   # Set only for Denmark (package 10, tier 0.2): proof that this
                   # native figure (DST's STAND concept) reconciles with DST's own
                   # separately-published monthly headline (MDRSNIT). None for
                   # every other country — see _extract_dk() and NEEDS-DECISION #17.
                   "mdrsnit_check": obs.get("mdrsnit_check")},
        "crosswalk": cw,
        "combos": combos,
    }


def build() -> dict:
    _, by_pair = crosswalk.load()
    results = []

    for cc, (source_id, national_code, extractor, lookup) in SOURCE_TABLE.items():
        doc = __import__("json").loads((PROCESSED / f"{source_id}.json").read_text(encoding="utf-8"))
        data = doc["data"]
        raw = data if lookup == "root" else data["occupations"][national_code]
        obs = extractor(raw)
        mapping = by_pair.get((cc, national_code))
        results.append(resolve_country(cc, source_id, national_code, obs, mapping))
        log(f"  {cc:3s} {source_id:12s} native {obs['period']:5s} {obs['currency']}: "
            f"median={obs.get('median')}  comparable={results[-1]['crosswalk'].get('comparable')}")

    for code in CANADA_CODES:
        doc = __import__("json").loads((PROCESSED / "salary_ca.json").read_text(encoding="utf-8"))
        raw = doc["data"]["occupations"][code]
        obs = _extract_ca(raw)
        mapping = by_pair.get(("CA", code))
        r = resolve_country("CA", "salary_ca", code, obs, mapping)
        r["country"] = f"CA-{code}"  # distinguish the two Canadian rows — see NEEDS-DECISION #12
        results.append(r)
        log(f"  CA  salary_ca ({code}) native {obs['period']:5s} {obs['currency']}: "
            f"median={obs.get('median')}  comparable={r['crosswalk'].get('comparable')}")

    for cc, reason in ABSENT.items():
        log(f"  {cc:3s} ABSENT — {reason}")

    return {
        "reference": {"country": REFERENCE[0], "national_code": REFERENCE[1],
                      "note": "every crosswalk comparability verdict below is this country's mapping "
                              "compared() against the row's own — see crosswalk.py"},
        "countries": results,
        "absent": [{"country": cc, "reason": reason} for cc, reason in ABSENT.items()],
    }


def run() -> None:
    log("── wage_distribution — Tier 6 resolver (crosswalk.compare() + normalise.py, exercised for real)")
    payload = build()
    from _common import record_provenance, write_processed
    write_processed("wage_distribution", payload, meta={
        "purpose": "Pre-resolved at build time — see module docstring. The browser never re-runs "
                   "crosswalk.compare() or any normalise.py function; it only displays this file.",
        "basis_default": "regular_pay", "currency_default": "native",
        "confidence": "derived",
    })
    log(f"  wrote data/processed/wage_distribution.json — {len(payload['countries'])} country rows, "
        f"{len(payload['absent'])} drawn absent")
    record_provenance(
        source_id="wage_distribution",
        name="Wage distribution panel — crosswalk.compare() + normalise.py resolved at build time",
        urls=[],  # derived from already-provenanced sources, not fetched from the network itself
        license_note="Inherits each underlying salary_*.json / bls_oews.json source's own licence — "
                      "this file adds no new licensing terms, only computation over already-committed "
                      "and already-licensed data.",
        redistribution="derived — nothing fetched; every input file's own provenance entry already "
                        "covers redistribution terms for the raw figures this derives from.",
        transforms=[
            "For each of the salary spine's primary-target (and next-best-available) occupation "
            "mappings, ran crosswalk.compare() against the Sweden/2512 reference to get a real "
            "comparability verdict, depth and degradation text — never re-derived in the UI.",
            "For each of the 4 (native/USD x regular_pay/total_earnings) combinations, called "
            "normalise.py's real to_usd()/annualise()/subtract_component()/comparison_basis() — "
            "never a client-side re-implementation.",
            "Qatar's mean is a transparent weighted average of PSA's own published Male/Female means, "
            "weighted by each group's own published employee count — the only figure in this file "
            "that is a genuine derivation rather than a pass-through of one source field.",
            "Countries whose pay-composition booleans are 'unknown' (Canada, Qatar, UAE) are refused "
            "on both basis combinations by normalise.comparison_basis() itself, not by a rule "
            "re-implemented here — an honest consequence of unverified composition, not a bug.",
        ],
        output="data/processed/wage_distribution.json",
        rows=len(payload["countries"]),
        coverage=f"{len(payload['countries'])} country rows ({len({c['country'].split('-')[0] for c in payload['countries']})} countries, Canada shown as two rows per NEEDS-DECISION #12), "
                 f"{len(payload['absent'])} drawn absent ({', '.join(a['country'] for a in payload['absent'])})",
        notes="Every number in this file traces back through its own chain to a value already "
              "committed and provenanced elsewhere — this file adds derivation, not new source data.",
    )


if __name__ == "__main__":
    run()
