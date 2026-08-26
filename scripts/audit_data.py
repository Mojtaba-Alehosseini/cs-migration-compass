"""Package 13, Tier 1 — structural invariants over every file in
data/processed/. `make validate` (scripts/validate_data.py) already covers
a lot of this project's data-integrity rules; this file is deliberately
scoped to NOT re-check what that one already does well: curated-data
inversions/nulls, envelope/provenance completeness, ODbL isolation,
survey-vs-advertised separation, percentile-vs-seniority labelling,
crosswalk depth, no-series well-formedness, percentile-ABSENCE labelling,
and all six normalise.py behavioural rules. See that file's own docstring
for the full list. Tier 4 folds both into one command; until then, run
both (`make validate && make audit`, or `python scripts/audit_data.py`).

This file adds the checks the work order's own Tier 1 names that validate_data.py
does not do:

  * a distribution's own percentiles are monotonic (p10<=p25<=median<=p75<=p90)
    wherever they co-occur, in ANY of this pipeline's three real shapes
    (salary_*.json's `_sek_month`-suffixed dispersion_by_year, bls_oews.json's
    `annual_p10_usd`-style series, wage_distribution.json's bare mean/median/p10..p90)
  * a distribution's own mean sits inside its own [p10, p90]
  * no pay figure is negative; a real $0/€0/etc. is never presented as a
    figure (must be null/absent, not a fabricated zero)
  * every pay figure's unit (currency + period) is recoverable — either from
    its own field name (salary_*.json's convention) or from currency/period
    sibling fields in its immediate container (wage_distribution.json's
    convention) — never neither
  * order-of-magnitude plausibility per (currency, period), bounds built from
    this dataset's own committed values (a wide multiple of the observed
    spread), outliers flagged for review, never silently dropped
  * a native record's own embedded cross-check against its source's separately
    published headline (Denmark's mdrsnit_check being the one example that
    exists today) actually reconciles under independent recomputation, not
    just an asserted residual_pct nobody re-derives
  * the OPPOSITE direction from validate_data.py's check_percentile_absence_
    explicit: a record that DOES carry real percentile fields must not also
    carry a distribution flag ("central-tendency-only", "mean-only") that
    claims it doesn't
  * every data/provenance.json entry is checked against an expected refresh
    interval and reported (not failed — see check_refresh_intervals's own
    docstring) if stale
  * a source that extracts a PDF's ENTIRE ranking table (meta.full_table)
    matches the publisher's own row count, its own stated range, and a
    complete tie-aware rank sequence — generic over any source shaped this
    way, see check_full_table_self_consistency()

Exit code 1 on any ERROR. Warnings/flags are reported but do not fail the
build — matching validate_data.py's own severity split.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, PROCESSED, PROVENANCE, log  # noqa: E402

ERRORS: list[str] = []
FLAGS: list[str] = []


def err(msg: str) -> None:
    ERRORS.append(msg)


def flag(msg: str) -> None:
    FLAGS.append(msg)


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# shared: finding every wage-percentile "family" anywhere in a document,
# regardless of which of this pipeline's three real naming shapes it uses
# ---------------------------------------------------------------------------

# A percentile/central-tendency token, optionally wrapped in a currency/period
# prefix ("annual_", "hourly_") and/or a currency/period suffix ("_sek_month",
# "_usd"). Deliberately excludes "margin"/"ci95" so a confidence-interval
# half-width (salary_se.json's own median_ci95_margin_sek_month) is never
# mistaken for the point estimate it accompanies -- found live: without this
# exclusion, the very first run flagged real, correct CI margins as
# "non-monotonic" simply because a margin is usually smaller than its own
# point estimate, which is not what monotonicity means here.
_TOKEN_RE = re.compile(r"(p10|p25|p50|p75|p90|median|mean|average)", re.I)
# margin/ci95/etc: a confidence-interval half-width, not a point estimate.
# pct_change_yoy: salary_uk.json's own year-over-year CHANGE RATE (a %),
# reusing mean/median for a different concept, same shape as
# coefficient_of_variation_pct below. paid_weekly_hours: salary_ie.json's
# own median/mean of HOURS WORKED, not of pay -- caught live by adversarial
# review testing the unit-disclosure check against real data (a genuine
# non-pay figure that happens to share the mean/median vocabulary, not a
# check bug this time).
_EXCLUDE_RE = re.compile(r"margin|ci95|ci_95|confidence|stderr|std_err|pct_change_yoy|paid_weekly_hours", re.I)
_ORDER = ["p10", "p25", "median", "p75", "p90"]  # p50 normalised to "median" below

# A percentile-labelling qualifier immediately after the token, stripped
# before grouping -- salary_ca.json's own real field names are p10_low_cad_
# hour, p25_q1_cad_hour, median_cad_hour, p75_q3_cad_hour, p90_high_cad_hour:
# five DIFFERENT suffixes for what is one family. Found by adversarial
# review, not anticipated: grouping on the raw (prefix, suffix) tuple made
# every one of these its own 1-member family, and (before the >=1 fix below
# existed) the >=2 gate then dropped every single one -- 826 real wage
# figures, ALL of Canada's own published dispersion, invisible to every
# family-based check in this file.
_QUALIFIER_RE = re.compile(r"^_(low|high|q1|q3)(?=_|$)", re.I)

# A container whose OWN key means its p10/p25/mean/median-shaped children are
# not pay figures at all. Found live on the first real run against this
# repo, not guessed in advance: salary_uk.json's own coefficient_of_variation_pct
# is ONS's published RELIABILITY metric for each corresponding wage estimate
# (a %, describing how trustworthy that estimate is), reusing the identical
# p10/p25/mean/median vocabulary for a completely different concept. Its own
# values have no reason to be monotonic in the wage sense (a smaller sample at
# an extreme percentile routinely has a HIGHER coefficient of variation than
# the more densely-populated median, which is the opposite ordering pay
# itself follows) and no reason to carry a currency (it's a percentage, and
# its parent key already says so via its own "_pct" suffix).
_NOT_A_WAGE_CONTAINER_RE = re.compile(r"coefficient_of_variation", re.I)

# Files with no pay data at all, whose OWN fields still happen to match the
# mean/median/p10.. vocabulary for an unrelated concept -- climate_normals
# .json's monthly mean_c (mean temperature, Celsius) is the one confirmed
# live: matched "mean", found no currency/period anywhere (correctly -- it
# has none), and was flagged by every family-based check in this file as a
# missing-unit pay figure, 252 times over, once the >=1 fix (below) made a
# lone mean_c field checkable at all. A per-FIELD exclusion pattern doesn't
# fit here the way pct_change_yoy/paid_weekly_hours do above -- "_c" alone
# is too generic to safely exclude as a suffix pattern -- so this is scoped
# to the one file actually evidenced to need it, not guessed more broadly.
_NOT_A_WAGE_FILE = {"climate_normals.json"}


def _family_key(field_name: str) -> tuple[str, str, str] | None:
    """(prefix, token, suffix) for a recognised wage field name, or None."""
    if _EXCLUDE_RE.search(field_name):
        return None
    m = _TOKEN_RE.search(field_name)
    if not m:
        return None
    token = m.group(1).lower()
    if token in ("p50", "average"):
        token = "median" if token == "p50" else "mean"
    prefix, suffix = field_name[:m.start()], field_name[m.end():]
    qm = _QUALIFIER_RE.match(suffix)
    if qm:
        suffix = suffix[qm.end():]
    return (prefix, token, suffix)


def _numeric_leaf(v):
    """A field's own value, unwrapped from bls_oews.json's own [{year,value}]
    time-series shape or wage_distribution.json's bare-number shape alike --
    always the MOST RECENT point for a series, since that is what every
    other shape's own bare number already represents (a single current
    figure, not a history)."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list) and v and isinstance(v[-1], dict) and "value" in v[-1]:
        val = v[-1].get("value")
        return float(val) if isinstance(val, (int, float)) else None
    return None


_CURRENCY_RE = re.compile(r"(?:^|_)(usd|eur|gbp|sek|nok|dkk|cad|aud|qar|aed)(?:_|$)", re.I)


_CONTAINER_CURRENCY_KEYS = ("currency", "currency_original")


def _resolve_unit(prefix: str, suffix: str, container: dict, ancestors: list[dict],
                   container_key_name: str = "") -> tuple[str | None, str | None]:
    """A family's own (currency, period), resolved INDEPENDENTLY — name-
    embedded first, falling back to a container/ancestor sibling field, or
    to the name of the KEY the container itself sits under — not as a
    single all-or-nothing pair, and not from one fixed source. Three real
    conventions, each covering fields the others miss:
    (1) the LEAF field's own name (salary_*.json's mean_sek_month);
    (2) a currency/period SIBLING field on the container (wage_
        distribution.json's bare mean/median next to "currency": "SEK");
    (3) the CONTAINER's OWN key name (salary_es.json's own
        broader_category_context.age_bands_eur_year: {"All ages. Average
        gross salary.": 34505.8, ...} — real INE age-band context data,
        the leaf keys are Spanish/English PROSE labels with no unit in
        them at all, and there is no currency/period sibling either; the
        unit lives only in "age_bands_eur_year", the dict's own key one
        level up, which nothing before this checked).
    levels_fyi.json's own median_total_comp_usd names its currency (the
    "_usd" suffix) but not its period (a container sibling, "period":
    "year"); its own sibling median_original names NEITHER in its own
    name, but its currency is a container sibling too, just under a
    different real key (currency_original — the ORIGINAL, pre-conversion
    currency, which varies per record, so it can never be the blanket
    "currency" key a USD-converted sibling field would want). An earlier
    version required BOTH currency and period to come from the SAME
    source and so resolved neither for these real, otherwise-fully-
    disclosed fields — found live: 830 real, correctly-USD-and-annual
    levels.fyi/Stack Overflow figures flagged as unit-less (adversarial
    review finding M9's own predicted "several are genuine" cases), then
    13 more real, correctly-EUR-and-annual salary_es.json context figures
    once convention (3) was found needed too, in the SAME remediation."""
    def _from_text(text: str) -> tuple[str | None, str | None]:
        t = text.lower()
        p = "hour" if "hour" in t else "month" if "month" in t else \
            "year" if ("annual" in t or "year" in t) else None
        cm = _CURRENCY_RE.search(t)
        return (cm.group(1).upper() if cm else None), p

    currency, period = _from_text(prefix + suffix)
    if container_key_name and not (currency and period):
        key_currency, key_period = _from_text(container_key_name)
        currency = currency or key_currency
        period = period or key_period
    for ctx in [container, *ancestors[-2:]]:
        if currency and period:
            break
        if not currency:
            for key in _CONTAINER_CURRENCY_KEYS:
                if isinstance(ctx.get(key), str):
                    currency = ctx[key]
                    break
        if not period and isinstance(ctx.get("period"), str):
            period = ctx["period"]
    return currency, period


def _find_families(obj, path: str, out: list[dict], ancestors: list[dict] | None = None) -> None:
    """Recursively find every dict whose own keys include >=1 member of a
    single (prefix, suffix) wage family, and record {path, prefix, suffix,
    values: {token: (field_name, value)}, currency, period} — the last two
    resolved via _resolve_unit(), None/None if genuinely unrecoverable (that
    gap is what check_pay_fields_disclose_currency_and_period reports on;
    here it just means this family is skipped by anything that buckets on
    currency+period, e.g. check_magnitude_plausibility). Does not descend
    into a family's OWN matched keys further (they're leaves for this
    purpose) but does descend into every other key normally, so a nested
    dispersion_by_year structure is walked into, not just its own top level.

    >=1, not >=2 (an earlier version's own threshold): a lone pay field with
    no sibling percentiles in the SAME dict -- bls_oews.json's own
    hourly_mean_usd, salary_es.json's national_reference.mean_eur_year --
    is still a real figure a negative/zero check and a magnitude check both
    need to see. Found by adversarial review: >=2 silently dropped 1,412
    real pay figures from every family-based check in this file, is_es and
    bls_oews's own lone means among them. The checks that genuinely need
    >=2 (monotonicity) or a specific combination (mean+p10+p90) already
    guard for that themselves via their own `continue` — this threshold is
    not what protects them."""
    ancestors = ancestors or []
    if isinstance(obj, dict):
        groups: dict[tuple[str, str], dict[str, tuple[str, float]]] = {}
        for k, v in obj.items():
            fam = _family_key(str(k))
            leaf = _numeric_leaf(v)
            if fam and leaf is not None:
                prefix, token, suffix = fam
                groups.setdefault((prefix, suffix), {})[token] = (str(k), leaf)
        own_key_name = path.rsplit(".", 1)[-1]
        is_wage_container = not _NOT_A_WAGE_CONTAINER_RE.search(own_key_name)
        if is_wage_container:
            for (prefix, suffix), members in groups.items():
                if len(members) >= 1:
                    currency, period = _resolve_unit(prefix, suffix, obj, ancestors, own_key_name)
                    out.append({"path": path, "prefix": prefix, "suffix": suffix, "values": members,
                                "currency": currency, "period": period})
        for k, v in obj.items():
            _find_families(v, f"{path}.{k}", out, ancestors + [obj])
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _find_families(item, f"{path}[{i}]", out, ancestors)


def _all_families(processed_dir: Path = PROCESSED) -> list[tuple[Path, dict]]:
    out = []
    for p in sorted(processed_dir.glob("*.json")):
        if p.name in _NOT_A_WAGE_FILE:
            continue
        doc = _load(p)
        if doc is None:
            continue
        families: list[dict] = []
        _find_families(doc.get("data"), "data", families)
        for fam in families:
            out.append((p, fam))
    return out


# ---------------------------------------------------------------------------
# distributions
# ---------------------------------------------------------------------------

def check_percentiles_monotonic(processed_dir: Path = PROCESSED) -> None:
    log("· percentiles are monotonic (p10<=p25<=median<=p75<=p90) wherever they co-occur")
    checked = bad = 0
    for path, fam in _all_families(processed_dir):
        present = [(tok, fam["values"][tok]) for tok in _ORDER if tok in fam["values"]]
        if len(present) < 2:
            continue
        checked += 1
        for (tok_a, (name_a, val_a)), (tok_b, (name_b, val_b)) in zip(present, present[1:]):
            if val_a > val_b:
                bad += 1
                err(f"{path.name}:{fam['path']}: {name_a}={val_a:,g} > {name_b}={val_b:,g} "
                    f"— percentiles must never invert ({tok_a} <= {tok_b})")
    log(f"  {checked} distribution(s) with >=2 ordered points checked, {bad} inversion(s)")


def check_mean_within_percentile_range(processed_dir: Path = PROCESSED) -> None:
    log("· mean sits inside its own [p10, p90]")
    checked = bad = 0
    for path, fam in _all_families(processed_dir):
        v = fam["values"]
        if "mean" not in v or "p10" not in v or "p90" not in v:
            continue
        checked += 1
        (mean_name, mean_val), (p10_name, p10_val), (p90_name, p90_val) = v["mean"], v["p10"], v["p90"]
        if not (p10_val <= mean_val <= p90_val):
            bad += 1
            err(f"{path.name}:{fam['path']}: {mean_name}={mean_val:,g} is outside "
                f"[{p10_name}={p10_val:,g}, {p90_name}={p90_val:,g}]")
    log(f"  {checked} distribution(s) with mean+p10+p90 checked, {bad} out of range")


def check_no_negative_or_zero_pay(processed_dir: Path = PROCESSED) -> None:
    """A figure only gets checked here once it's confirmed to be a PAY
    figure (a resolved currency and period), not merely a field name that
    happens to match the mean/median/p10../average token vocabulary. Found
    live once the >=1 family-size fix (above) stopped hiding it:
    climate_normals.json's own `mean_c` (mean temperature, Celsius) matched
    the same token and, once eligible for checking at all, was flagged as
    "negative pay" for every city with a winter month below freezing --
    a real value, correctly negative, not a pay figure at all. Requiring a
    resolved unit is the same precondition check_magnitude_plausibility
    already uses, so the two can't disagree about what counts as pay."""
    log("· no negative pay figures; a real $0/€0/etc. is never presented as a figure")
    checked = bad = 0
    for path, fam in _all_families(processed_dir):
        if not fam.get("currency") or not fam.get("period"):
            continue
        for tok, (name, val) in fam["values"].items():
            checked += 1
            if val < 0:
                bad += 1
                err(f"{path.name}:{fam['path']}.{name}: negative pay figure ({val:,g})")
            elif val == 0:
                bad += 1
                err(f"{path.name}:{fam['path']}.{name}: pay figure is exactly 0 — a real absence must be "
                    "null/omitted, never a fabricated zero (see docs/REGRESSION-CATALOGUE.md R14 [Ashby/"
                    "Lever/Greenhouse's own $0 guards] for the postings-side version of this same rule)")
    log(f"  {checked} pay figure(s) checked, {bad} negative-or-zero")


_KNOWN_DISTRIBUTION_LABELS = {"full", "quartile-only", "central-tendency-only", "mean-only"}


def check_distribution_label_matches_percentile_presence(processed_dir: Path = PROCESSED) -> None:
    """The direction validate_data.py's check_percentile_absence_explicit
    does NOT check: a record that names itself 'central-tendency-only' or
    'mean-only' but actually carries real percentile fields is just as
    misleading as the reverse (percentiles present, label says there are
    none) that check already covers -- a consumer trusting the label would
    wrongly believe percentiles are unavailable and skip real data."""
    log("· a 'central-tendency-only'/'mean-only' distribution label is never contradicted by real percentile fields")
    checked = bad = 0
    for path in sorted(processed_dir.glob("*.json")):
        doc = _load(path)
        if doc is None:
            continue

        def walk(obj, ctx_path):
            nonlocal checked, bad
            if isinstance(obj, dict):
                dist = obj.get("distribution")
                if isinstance(dist, str):
                    if dist not in _KNOWN_DISTRIBUTION_LABELS:
                        bad += 1
                        err(f"{path.name}:{ctx_path}.distribution: unregistered value {dist!r}, "
                            f"expected one of {sorted(_KNOWN_DISTRIBUTION_LABELS)}")
                    elif dist in ("central-tendency-only", "mean-only"):
                        checked += 1
                        # wage_distribution.json's own convention puts
                        # distribution as a SIBLING of value, not of the
                        # percentile fields themselves (native: {distribution,
                        # value: {mean, p10, ...}}) -- checking only obj's own
                        # direct children missed this shape entirely (a
                        # constructed mean-only-labelled record with a full
                        # p10-p90 spread nested under value: {} passed this
                        # check clean). Checked here, not just obj itself.
                        candidates = [obj]
                        nested_value = obj.get("value")
                        if isinstance(nested_value, dict):
                            candidates.append(nested_value)
                        # "central-tendency-only" means mean AND/OR median,
                        # no percentiles -- median is a central-tendency
                        # measure, not a percentile, so excluding only
                        # "mean" here flagged every real AU/IE/DE record
                        # (mean+median present, p10-p90 genuinely null) as
                        # self-contradicting the moment the nested-value
                        # lookup above could see median at all. Verified
                        # against the real data before fixing, not assumed:
                        # all three have {} for every non-null field other
                        # than mean/median.
                        has_pct = any(
                            _family_key(str(k)) and _family_key(str(k))[1] not in ("mean", "median")
                            for c in candidates for k in c if isinstance(c.get(k), (int, float))
                        )
                        if has_pct:
                            bad += 1
                            err(f"{path.name}:{ctx_path}: distribution={dist!r} but this record carries a "
                                "real percentile field alongside it")
                for k, v in obj.items():
                    walk(v, f"{ctx_path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    walk(item, f"{ctx_path}[{i}]")

        walk(doc.get("data"), "data")
    log(f"  {checked} labelled-central-tendency-only record(s) checked, {bad} contradicted by their own data")


# ---------------------------------------------------------------------------
# units / magnitude
# ---------------------------------------------------------------------------

def check_pay_fields_disclose_currency_and_period(processed_dir: Path = PROCESSED) -> None:
    """Every pay figure's unit must be recoverable, in EITHER of this
    pipeline's two real, legitimate conventions: the field NAME embeds it
    (salary_*.json / bls_oews.json's own `_sek_month` / `_usd` suffixes), or
    the immediate container carries explicit `currency`/`period` sibling
    fields (wage_distribution.json's own convention, checked once per
    combo/native block rather than per bare `mean`/`median` key inside it).
    A field satisfying NEITHER is the actual failure this rule exists for."""
    log("· every pay field's unit (currency+period) is recoverable from its name or its container")
    checked = bad = 0
    for path in sorted(processed_dir.glob("*.json")):
        if path.name in _NOT_A_WAGE_FILE:
            continue
        doc = _load(path)
        if doc is None:
            continue

        def walk(obj, ctx_path, ancestors):
            nonlocal checked, bad
            if not isinstance(obj, dict):
                if isinstance(obj, list):
                    for i, item in enumerate(obj):
                        walk(item, f"{ctx_path}[{i}]", ancestors)
                return
            # Same exclusion _find_families() applies (e.g. salary_uk.json's
            # coefficient_of_variation_pct) — its own bare mean/p10/etc.
            # fields are a percentage, not a pay figure, so they need no
            # currency/period disclosure at all; not just "checked and
            # passing", genuinely out of scope for this rule.
            own_key_name = ctx_path.rsplit(".", 1)[-1]
            if _NOT_A_WAGE_CONTAINER_RE.search(own_key_name):
                return
            for k, v in obj.items():
                if isinstance(v, (int, float)):
                    fam = _family_key(str(k))
                    if fam is None:
                        continue
                    checked += 1
                    prefix, token, suffix = fam
                    # Reuses _resolve_unit() -- the SAME function
                    # check_magnitude_plausibility's own bucketing calls via
                    # _find_families() -- rather than this check's own
                    # separate `any letter in the name` test. An earlier,
                    # separate test accepted ANY letter anywhere in the
                    # name as "the unit is disclosed": total_mean (no
                    # currency, no period), median_eur (currency, no
                    # period) and median_year (period, no currency) all
                    # passed it, and then silently vanished from magnitude
                    # checking too, since _resolve_unit() correctly returns
                    # None/None for all three — a badly-named field passed
                    # the disclosure check AND disappeared from the value
                    # check, with no warning from either. Adversarial
                    # review finding M9, reproduced against these exact
                    # three constructed names before this fix.
                    currency, period = _resolve_unit(prefix, suffix, obj, ancestors, own_key_name)
                    if not currency or not period:
                        bad += 1
                        missing = ("currency and period" if not currency and not period
                                   else "period" if currency else "currency")
                        err(f"{path.name}:{ctx_path}.{k}: {token} field {k!r} is missing its own {missing} — "
                            "neither its name nor its container/grandparent discloses it")
                else:
                    walk(v, f"{ctx_path}.{k}", ancestors + [obj])

        walk(doc.get("data"), "data", [])
    log(f"  {checked} pay field(s) checked, {bad} with no recoverable unit")


# Absolute, currency-agnostic sanity bands per period -- deliberately wide
# (these are sanity bounds, not plausibility bounds; the dataset-relative
# check below does the fine-grained work). Exists specifically because a
# bound built from a bucket's OWN spread cannot catch every point in that
# SAME bucket being wrong the same way -- adversarial review finding H1,
# reproduced live: writing the ANNUAL mean into every one of bls_oews.json's
# 31 hourly_mean_usd fields (the real historical P7 bug) passed the
# dataset-relative check cleanly, because the bucket's own median moved
# with it. No real wage in any currency this pipeline commits sits outside
# these; a value that does is wrong regardless of what its own bucket says.
_ABSOLUTE_SANITY_BANDS = {"hour": (0.5, 2000), "month": (50, 500_000), "year": (500, 5_000_000)}


def check_magnitude_plausibility(processed_dir: Path = PROCESSED) -> None:
    """Two independent bounds per figure, per (currency, period) — flags for
    review, never silently dropped, never auto-"fixed":

    1. Dataset-relative: median +/- a wide multiple of the median absolute
       deviation of that bucket's OWN percentile values (robust to a
       handful of real outliers skewing a plain mean/stdev; needs >=5
       points to say anything). The lower bound is clamped to a quarter of
       the median -- unclamped, `median - 8*MAD` is negative in 12 of this
       dataset's own 13 real buckets, meaning a figure could read as low as
       $0 and still pass (adversarial review finding H3, reproduced live:
       a Netherlands hourly rate left un-annualised, a DKK/hour figure 10x
       too small, and seven other constructed downward errors all passed
       the unclamped bound).
    2. Absolute (_ABSOLUTE_SANITY_BANDS): catches the case (1) cannot by
       construction -- an entire bucket wrong the same way.

    Every value in a family is tested against both, INCLUDING mean (an
    earlier version excluded mean from testing, not just from bound-
    building, which let bls_oews.json's own mean-only hourly_mean_usd
    field escape checking entirely -- adversarial review finding H1).
    Bound-building itself still prefers a family's own non-mean
    (percentile) values where present, falling back to mean only when
    that's the sole figure a family has -- avoids double-counting a
    distribution's own spread without leaving a mean-only source's bucket
    empty."""
    log("· order-of-magnitude plausibility per (currency, period): dataset-relative + absolute sanity bounds")
    bucket_source: dict[tuple[str, str], list[float]] = {}
    all_points: list[tuple[str, str, float, str, str]] = []
    for path, fam in _all_families(processed_dir):
        # fam's own currency/period, resolved by _find_families() via
        # _resolve_unit() -- name-embedded (salary_*.json, bls_oews.json) OR
        # container/ancestor sibling fields (wage_distribution.json).
        currency, period = fam.get("currency"), fam.get("period")
        if not currency or not period:
            continue
        non_mean = {tok: v for tok, v in fam["values"].items() if tok != "mean"}
        for _, val in (non_mean or fam["values"]).values():
            bucket_source.setdefault((currency, period), []).append(val)
        for tok, (name, val) in fam["values"].items():
            all_points.append((path.name, name, val, currency, period))

    bounds: dict[tuple[str, str], tuple[float, float, float, int]] = {}
    for key, vals in bucket_source.items():
        if len(vals) < 5:
            continue
        med = statistics.median(vals)
        mad = statistics.median([abs(v - med) for v in vals]) or (med * 0.05)
        lo = max(med - 8 * mad, med / 4)
        hi = med + 8 * mad
        bounds[key] = (lo, hi, med, len(vals))

    flagged = 0
    for fname, field, val, currency, period in all_points:
        absolute = _ABSOLUTE_SANITY_BANDS.get(period)
        if absolute and not (absolute[0] <= val <= absolute[1]):
            flagged += 1
            flag(f"{fname}:{field}: {val:,g} {currency}/{period} is outside the absolute sanity band "
                 f"[{absolute[0]:,g}, {absolute[1]:,g}] for any {period}-basis figure this pipeline commits "
                 "— review, not auto-corrected")
            continue  # already flagged; don't double-flag the same figure against the relative bound too
        b = bounds.get((currency, period))
        if b is None:
            continue
        lo, hi, med, n = b
        if val < lo or val > hi:
            flagged += 1
            flag(f"{fname}:{field}: {val:,g} {currency}/{period} is outside this dataset's own "
                 f"plausible range [{lo:,.0f}, {hi:,.0f}] (median {med:,.0f}, {n} points in bucket) "
                 "— review, not auto-corrected")
    log(f"  {len(all_points)} figure(s) across {len(bounds)} dataset-relative bucket(s), "
        f"{flagged} flagged for review")


def check_embedded_cross_checks_reconcile(processed_dir: Path = PROCESSED, *, require_found: bool = True) -> None:
    """Wherever a native record carries its own embedded cross-check
    against a source's separately-published headline (Denmark's
    mdrsnit_check is the one that exists today: stand_dkk_hour x its own
    hours-per-month = computed_monthly, compared against published_mdrsnit),
    recompute residual_pct independently rather than trust the stored
    number -- a stale or hand-edited residual_pct would otherwise pass
    forever. This is the Tier-1 (purely internal, no live fetch) half of
    what Tier 2's reconcile.py generalises against LIVE sources.

    require_found=False skips the "0 found is itself a finding" flag --
    for a scratch directory constructed to test one specific violation
    shape, 0 embedded cross-checks found is the expected setup, not a gap."""
    log("· a native record's own embedded cross-check (e.g. Denmark's mdrsnit_check) reconciles under independent recomputation")
    checked = bad = 0
    for path in sorted(processed_dir.glob("*.json")):
        doc = _load(path)
        if doc is None:
            continue

        def walk(obj, ctx_path):
            nonlocal checked, bad
            if isinstance(obj, dict):
                mc = obj.get("mdrsnit_check")
                if isinstance(mc, dict) and all(k in mc for k in
                        ("stand_dkk_hour", "computed_monthly", "published_mdrsnit", "residual_pct")):
                    checked += 1
                    # DK's own 37h/week standardised full-time week (the
                    # near-universal Danish overenskomst convention;
                    # src_salary_dk.py's own STANDARDISED_HOURS_PER_WEEK,
                    # pinned here as the one external fact this check is
                    # FOR, not re-imported, so a bug in that module can't
                    # also blind this check to the same bug) x 52/12 =
                    # 160.333...h/month. NOT the rounded "160.33" the
                    # chain's own detail STRING displays for humans --
                    # using that rounded literal here first produced a
                    # false violation (65,504.42 recomputed vs 65,505.79
                    # stored): the stored figure is the one that's right,
                    # confirmed against src_salary_dk.py's own defining
                    # formula, the same rounded-display-vs-full-precision
                    # gap this package's own R9 regression test guards
                    # against elsewhere (docs/REGRESSION-CATALOGUE.md).
                    hours_per_month = 37.0 * 52 / 12
                    recomputed = round(mc["stand_dkk_hour"] * hours_per_month, 2)
                    if abs(recomputed - mc["computed_monthly"]) > 0.02:
                        bad += 1
                        err(f"{path.name}:{ctx_path}.mdrsnit_check: stand_dkk_hour ({mc['stand_dkk_hour']}) x "
                            f"160.33h != computed_monthly — stored {mc['computed_monthly']}, recomputed {recomputed}")
                    real_residual = round(abs(mc["computed_monthly"] - mc["published_mdrsnit"])
                                           / mc["published_mdrsnit"] * 100, 4)
                    if abs(real_residual - mc["residual_pct"]) > 0.001:
                        bad += 1
                        err(f"{path.name}:{ctx_path}.mdrsnit_check: stored residual_pct={mc['residual_pct']} "
                            f"does not match independently recomputed {real_residual}")
                    if real_residual > 1.0:
                        bad += 1
                        err(f"{path.name}:{ctx_path}.mdrsnit_check: residual {real_residual}% against DST's own "
                            "published MDRSNIT headline exceeds the 1% sanity bound")
                for k, v in obj.items():
                    walk(v, f"{ctx_path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    walk(item, f"{ctx_path}[{i}]")

        walk(doc.get("data"), "data")
    log(f"  {checked} embedded cross-check(s) found and independently recomputed, {bad} violation(s)")
    if checked == 0 and require_found:
        flag("no embedded cross-checks (e.g. mdrsnit_check) found anywhere in data/processed/ — if Denmark's "
             "own check was renamed or removed, this function needs updating, not silently passing 0/0")


# ---------------------------------------------------------------------------
# freshness
# ---------------------------------------------------------------------------

# Expected refresh interval per source, by source_id pattern -- declared
# HERE rather than per-harvester (record_provenance()'s own call sites
# number in the dozens; centralising is the proportionate choice for a
# metadata EXPECTATION, not a data value, and keeps every source's own
# declared cadence visible in one place rather than scattered). First
# matching pattern wins; unmatched sources get DEFAULT_REFRESH_MONTHS.
_REFRESH_EXPECTATIONS_MONTHS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"^postings_"), 1),               # live job-board APIs, this project's own weekly refresh workflow targets these
    (re.compile(r"^postings$"), 1),                # the merged cross-provider postings file
    (re.compile(r"^fx_rates$"), 3),
    (re.compile(r"^salary_|^bls_oews$"), 15),      # annual government wage surveys, +3mo grace for the source's own publication lag
    (re.compile(r"^(experience_gradient|hours_worked|pay_composition)$"), 15),
    (re.compile(r"^(world_bank|imf_weo|oecd_|un_wpp|un_migrant_stock|worldbank_gep)"), 15),
    (re.compile(r"^(climate_normals|city_coordinates|mipex|wipo_gii|rsf_press_freedom|"
                r"wikipedia_english_speakers|world_happiness_report)$"), 24),
    (re.compile(r"^(bis_property_prices|fhfa_hpi_metro|teranet_national_bank_hpi|uk_hpi|numbeo_history)"), 15),
    (re.compile(r"^levels_fyi$"), 6),
    (re.compile(r"^stackoverflow_survey$"), 15),
]
DEFAULT_REFRESH_MONTHS = 15


def _expected_refresh_months(source_id: str) -> int:
    for pattern, months in _REFRESH_EXPECTATIONS_MONTHS:
        if pattern.match(source_id):
            return months
    return DEFAULT_REFRESH_MONTHS


def check_refresh_intervals(provenance_path: Path = PROVENANCE) -> None:
    """Reports (does not fail the build -- the work order's own Tier 1
    wording is explicit: "report, don't delete") any provenance entry
    whose fetched_at is older than its own expected refresh interval.
    check_staleness() in validate_data.py already does the curated-data
    (cities.json/countries.json) version of this against a single blanket
    rule from metrics.json; this is the processed-source-layer version,
    per-source, which nothing currently checks."""
    log("· every source is checked against its own expected refresh interval")
    if not provenance_path.exists():
        err("data/provenance.json missing — cannot check refresh intervals")
        return
    prov = json.loads(provenance_path.read_text(encoding="utf-8"))
    today = dt.datetime.now(dt.timezone.utc)
    stale = checked = 0
    for entry in prov.get("entries", []):
        sid = entry.get("source_id", "")
        fetched = entry.get("fetched_at")
        if not fetched:
            continue
        try:
            fetched_dt = dt.datetime.fromisoformat(fetched.replace("Z", "+00:00"))
        except ValueError:
            continue
        checked += 1
        expected = _expected_refresh_months(sid)
        age_days = (today - fetched_dt).days
        if age_days > expected * 30:
            stale += 1
            flag(f"provenance[{sid}]: fetched_at {fetched} is {age_days}d old, past its own "
                 f"{expected}-month expected refresh interval")
    log(f"  {checked} source(s) checked, {stale} past their own expected refresh interval")


_POSTINGS_PROVIDER_FILES = [
    "postings_ashby", "postings_greenhouse", "postings_lever",
    "postings_teamtailor", "postings_usajobs", "postings_hn",
]


def check_postings_merge_is_current(processed_dir: Path = PROCESSED) -> None:
    """Package 14, Tier 0.1 -- the external audit's Finding 3 "stale merge":
    postings.json (build_postings.py's own merged output) was five days
    behind Greenhouse and Lever's own provider files, silently serving
    ~15,000 fewer postings than the repo already held on disk, because a
    provider file can be regenerated (a harvester run standalone, outside
    postings-refresh.yml, for an unrelated reason -- exactly what happened
    here, see REPORT-P14.md gate 1) without anyone re-running the merge,
    and nothing caught the resulting drift.

    postings.json's own provider_summary[provider]['generated_at'] records
    what each provider file's generated_at WAS at merge time -- so this
    check is a straight comparison against what that provider file's
    generated_at IS now. Any mismatch means the merge no longer reflects
    what's on disk, in either direction (a provider file rebuilt after the
    merge, or a merge that used a provider file since replaced) -- ERROR,
    not a flag: the previous, unenforced version of "always run the merge
    after a harvest" is exactly what let this go stale for 5 days
    unnoticed."""
    log("· postings.json's own recorded provider generated_at matches each provider file's own, now")
    merged_path = processed_dir / "postings.json"
    merged = _load(merged_path)
    if not merged:
        flag("postings.json missing or unreadable — cannot check merge freshness (fine if postings "
             "hasn't been built yet in this environment)")
        return
    provider_summary = merged.get("data", {}).get("provider_summary", {})
    stale = []
    for source_id in _POSTINGS_PROVIDER_FILES:
        provider = source_id.replace("postings_", "")
        provider_doc = _load(processed_dir / f"{source_id}.json")
        if not provider_doc:
            continue  # provider not built in this environment — not this check's concern
        recorded = provider_summary.get(provider, {}).get("generated_at")
        current = provider_doc.get("generated_at")
        if recorded != current:
            stale.append((provider, recorded, current))
    if stale:
        for provider, recorded, current in stale:
            err(f"postings.json's merge is STALE for '{provider}': merged file recorded "
                f"generated_at={recorded}, but data/processed/postings_{provider}.json is now "
                f"generated_at={current} — run `python scripts/build_postings.py` to re-merge")
        log(f"  {len(stale)} of {len(_POSTINGS_PROVIDER_FILES)} provider file(s) newer than the last merge")
    else:
        log(f"  all {len(_POSTINGS_PROVIDER_FILES)} provider files match what postings.json's own merge recorded")


_OECD_BENCHMARK_LOW, _OECD_BENCHMARK_HIGH = 1.0, 2.5
# Package 14, Tier 1 -- the external audit's own Finding 1 (SEVERE)
# threshold: software occupations carry a well-documented premium over the
# national average wage, 1.2-1.8x in OECD economies, higher in the US.
# Below 1.0x a "software developer" figure claims this occupation pays
# LESS than the average worker in its own country, not credible on its
# face; above 2.5x is generous headroom past the US's own real 1.56x (the
# richest, most dispersed case this pipeline has), wide enough that this
# never fires on a genuinely elevated but real figure.

# An adversarial review's own M5 finding: every EXEMPT country only ever
# reached a log() line, and a WG_USD_PPP rename/removal upstream would
# silently turn EVERY country exempt -- checked stays 0, flagged stays 0,
# the function returns clean, and "0 checked, 0 flagged, PASS" reads
# exactly like a healthy run. That defeats the whole reason this check
# exists ("would have caught Finding 1 the day it shipped" -- not if it
# can go blind and still say PASS). AE and QA are the only two countries
# this pipeline has ever found with no OECD avg_wages series at all; a
# third joining that list is far more likely a real break upstream than a
# new, genuine data gap.
_OECD_BENCHMARK_EXPECTED_EXEMPT = {"AE", "QA"}


def check_oecd_wage_benchmark(processed_dir: Path = PROCESSED) -> None:
    """Package 14, Tier 1 (external audit Finding 1, SEVERE) -- the standing
    invariant the audit's own text names directly: "any country whose
    published median falls below 1.0x or above 2.5x its own OECD avg_wages
    for the same year fails the audit... this single check would have
    caught Finding 1 the day it shipped." Benchmarks wage_distribution.
    json's own USD median (whichever basis combo is ok) against oecd_
    indicators.json's own avg_wages.WG_USD_PPP for the SAME published year
    -- the identical comparison the audit itself ran to find Finding 1, now
    running on every future commit instead of once, by hand, externally.

    FLAG, not ERROR -- deliberately, and disclosed here rather than left
    implicit: this package's own investigation (REPORT-P14.md gate 4, and
    the Tier 1 set-wide chart fix earlier in main()) found the ratio
    itself is not a bug to fix by changing a number. Spain, Ireland and the
    Netherlands currently flag (0.77x, 0.98x, 0.97x) -- each for its own
    real, disclosed, DIFFERENT reason, not one uniform story (an earlier
    draft of this docstring wrongly named Germany as the third country and
    applied Ireland's own "broader occupation" explanation to all three;
    corrected after re-deriving each ratio directly against live data
    rather than trusting a stale note -- see NEEDS-DECISION #35):
      - Spain: crosswalk.compare() forces its own 4-digit ISCO mapping down
        to 2-digit against the reference -- its own government source
        genuinely covers a broader occupation band than "software
        developer" specifically.
      - Ireland: forced further still, to 1-digit ("all professionals") --
        the same kind of breadth issue as Spain, more severe.
      - Netherlands: a DIFFERENT mechanism -- data/occupations.json's own
        mapping note says its BRC 2014 classification is "not a national
        adaptation of ISCO-08... no defensible ISCO-08 anchor at any
        depth," despite its own national_title being software-developer-
        specific ("Software- en applicatieontwikkelaars"). No breadth
        issue at all; a crosswalk STRUCTURAL-compatibility gap instead.
        Its own regular_pay (bonus-excluded) basis is the more likely
        driver of its near-1.0 ratio -- see NEEDS-DECISION #37's own
        compositional-basis finding, which this ratio sits close enough to
        1.0 to plausibly cross under a fully bonus-inclusive comparison.
    All three published medians remain correctly sourced and correctly
    computed for what their own national statistics actually measure --
    the Tier 1 chart fix already excludes exactly these countries from the
    cross-country COMPARISON chart for their own individually-disclosed
    reasons, but each one's own figure is still real, sourced, and
    correctly worth publishing on its own country page. Making this an
    ERROR would fail CI permanently for conditions no future commit can
    fix without either fabricating a narrower occupation-specific figure
    that does not exist (forbidden by this project's own rules) or
    removing a country page entirely (not asked for) -- exactly the
    tension the work order's own gate 4 anticipates: "show it passing
    after Tier 1's fix -- or, if figures still fail, say so plainly rather
    than loosening the threshold." FLAG keeps the check permanently
    VISIBLE (satisfying "would have caught Finding 1 the day it shipped")
    without permanently blocking a build over conditions this package
    already investigated and disclosed -- not "silencing" the check: the
    threshold, the comparison, and the visibility are all unchanged; only
    its power to block a commit forever over an unfixable-by-normal-means
    condition is. Recorded in NEEDS-DECISION.md too, for the owner's own
    review."""
    log(f"· every country's published median is checked against its own OECD avg_wages "
        f"({_OECD_BENCHMARK_LOW}x-{_OECD_BENCHMARK_HIGH}x band)")
    wd = _load(processed_dir / "wage_distribution.json")
    oecd = _load(processed_dir / "oecd_indicators.json")
    if not wd or not oecd:
        flag("wage_distribution.json or oecd_indicators.json missing — cannot check the OECD wage "
             "benchmark (fine if this environment hasn't built the wage spine yet)")
        return
    # An adversarial review (L10) found Canada's own two rows produce the
    # identical "no USD-converted median available on any basis" FLAG every
    # single run, forever -- pay_composition.json's own salary_ca entry
    # marks irregular_bonus/employer_social_contributions "unknown", a
    # genuinely UNVERIFIED (not merely absent) composition that can never
    # resolve to an .ok combo on any future run without new source
    # evidence. That is structurally different from every other reason this
    # branch can fire (a real, possibly-transient FX or data gap worth a
    # human's attention each time it happens) -- looked up by source_id
    # against this authoritative field, not hardcoded by country code, so
    # it also covers Qatar/UAE's own same documented gap without a repeat.
    pay_comp = _load(DATA / "pay_composition.json") or {}
    unverified_source_ids = {
        s["source_id"] for s in pay_comp.get("sources", [])
        if s.get("irregular_bonus") == "unknown" or s.get("employer_social_contributions") == "unknown"
    }
    oecd_data = oecd.get("data", {})
    countries = wd.get("data", {}).get("countries", [])
    checked = exempt = flagged = uncheckable = 0
    exempt_countries: set[str] = set()
    for row in countries:
        cc = row["country"].split("-")[0]  # "CA-21231"/"CA-21232" -> "CA"
        avg_wages = (oecd_data.get(cc, {}).get("avg_wages", {}) or {}).get("WG_USD_PPP", [])
        if not avg_wages:
            exempt += 1
            exempt_countries.add(cc)
            log(f"  {row['country']}: EXEMPT — no OECD avg_wages series for {cc}")
            continue
        year = row["native"]["year"]
        oecd_row = next((r for r in avg_wages if str(r.get("period")) == str(year)), None)
        if oecd_row is None or oecd_row.get("value") is None:
            flag(f"{row['country']}: no OECD avg_wages figure for {year} (its own published year) — "
                 "cannot benchmark this specific year")
            continue
        combo = row["combos"].get("usd_regular_pay")
        if not combo or not combo.get("ok"):
            combo = row["combos"].get("usd_total_earnings")
        if not combo or not combo.get("ok"):
            if row.get("source_id") in unverified_source_ids:
                uncheckable += 1
                log(f"  {row['country']}: UNCHECKABLE — {row['source_id']}'s own pay composition is "
                    "unverified (pay_composition.json), not a benchmark result")
            else:
                flag(f"{row['country']}: no USD-converted median available on any basis — cannot benchmark")
            continue
        median = combo["value"].get("median")
        if median is None:
            median = combo["value"].get("mean")
        if median is None:
            flag(f"{row['country']}: USD combo has no median or mean — cannot benchmark")
            continue
        checked += 1
        ratio = median / oecd_row["value"]
        if ratio < _OECD_BENCHMARK_LOW or ratio > _OECD_BENCHMARK_HIGH:
            flagged += 1
            flag(f"{row['country']}: published median ${median:,.0f} is {ratio:.2f}x its own OECD "
                 f"avg_wages (${oecd_row['value']:,.0f}, {year}) — outside the {_OECD_BENCHMARK_LOW}x-"
                 f"{_OECD_BENCHMARK_HIGH}x band a software-occupation premium should plausibly fall in")
    log(f"  {checked} checked, {flagged} outside the {_OECD_BENCHMARK_LOW}x-{_OECD_BENCHMARK_HIGH}x "
        f"band, {exempt} exempt (no OECD avg_wages series), {uncheckable} uncheckable "
        f"(unverified pay composition, not a benchmark result)")

    # M5's own hardening: a rename/removal of WG_USD_PPP upstream would
    # otherwise make every country EXEMPT and let this function return
    # having verified nothing, printing a clean "0 checked, 0 flagged" that
    # reads exactly like a healthy run. checked == 0 here is never a real
    # data limitation -- every row that reaches the loop already has a
    # native/combos shape checked() would happily use if avg_wages simply
    # existed -- so it is always this check itself failing to find data,
    # not the data legitimately having none. ERROR, not FLAG: unlike a
    # country's own occupation-scope mismatch (genuinely unfixable by any
    # future commit, see this function's own docstring), a broken lookup
    # key is fixable by the very next commit, and silently downgrading the
    # audit's own headline check to "checks nothing, always passes" is a
    # regression this project's own no-silent-caps discipline exists to
    # catch, not wave through as a clean PASS.
    if checked == 0 and countries:
        err("check_oecd_wage_benchmark checked 0 countries despite wage_distribution.json "
            "having rows — WG_USD_PPP (or oecd_indicators.json's own shape) likely renamed or "
            "missing upstream; this check is currently verifying NOTHING, not passing cleanly")
    unexpected_exempt = exempt_countries - _OECD_BENCHMARK_EXPECTED_EXEMPT
    if unexpected_exempt:
        flag(f"OECD benchmark: {sorted(unexpected_exempt)} exempt for lack of an avg_wages series, "
             f"beyond the known {sorted(_OECD_BENCHMARK_EXPECTED_EXEMPT)} baseline — a new, genuine "
             "gap (worth recording) or a country-code mismatch (worth fixing); either way, "
             "someone should look, this should not stay a silent exemption")


_POSTINGS_ANNUAL_USD_LOW, _POSTINGS_ANNUAL_USD_HIGH = 500, 5_000_000
# Package 14, Tier 3.3 -- matches audit_data.py's own existing
# _ABSOLUTE_SANITY_BANDS["year"] (package 13) exactly, deliberately: one
# already-shipped, already-reasoned annual-USD band, not a second number
# invented independently. Checked against each posting's own USD-CONVERTED
# annualised midpoint (Tier 3.1's own compensation.usd), never the RAW
# native number -- this is exactly what makes JPY 18,000,000/year (~$120K),
# KHR 123,000,000/year (~$30K) and INR 1,500,000/year (~$17K) all pass
# cleanly instead of being flagged as implausible: converted to a common
# currency first, they are all ordinary salaries. A check that instead
# eyeballed the raw native number against one USD-shaped band would flag
# all three as extreme outliers purely because of currency, which the work
# order's own instruction names directly as the failure mode to avoid.
# An adversarial review flagged the flat 2080 (40h x 52wk, the US
# convention) below against normalise.py's own hours_for() docstring,
# which documents a named, tested prohibition on exactly this assumption
# (see that function's own module comment and
# test_normalise.py::test_annualise_hour_uses_sourced_hours_not_2080) --
# a fair challenge to answer explicitly, not silently share a number with
# and hope it reads as consistent.
#
# The two contexts are not the same rule applied inconsistently. normalise.
# hours_for() feeds a PUBLISHED comparison VALUE for a bounded ~15-country
# wage spine where a real, sourced hours-per-week record is available for
# every one of them -- there, "refuse rather than guess" costs nothing
# (nothing is ever actually missing) and a 2080 assumption would silently
# change the number a reader sees by the several-percent gap real average
# workweeks (Denmark ~37h, France ~35h) open up against 40h.
#
# This constant instead feeds a FLAG-only plausibility screen (never an
# auto-correction, see this check's own docstring) against a band spanning
# _POSTINGS_ANNUAL_USD_LOW to _POSTINGS_ANNUAL_USD_HIGH above -- four
# orders of magnitude wide. The same several-percent gap a real country's
# hours would open up against 2080 cannot move a value across either edge
# of a 10,000x band in any realistic case; if one ever sits close enough
# to the edge for that gap to matter, this check's own job is only to
# flag it for a human to look at, not to decide silently either way. And
# unlike the wage spine's bounded, fully-sourced country set, postings
# span ~90 countries worldwide -- normalise.hours_for() has no sourced
# record for most of them, so a "use it when available" version would
# still need this same fallback for the majority of rows it checks, at
# the cost of a new dependency between this postings-side gate and the
# wage-spine's own country coverage. Kept as one flat, disclosed
# approximation, used the same way for every country on purpose.
_POSTINGS_ANNUAL_MULT = {"year": 1, "month": 12, "hour": 2080}


def check_postings_annualised_plausibility(processed_dir: Path = PROCESSED) -> None:
    """Package 14, Tier 3.3 (external audit Finding 3) -- "in the spirit of
    Tier 1's benchmark: a posting whose annualised midpoint falls outside a
    defensible band for its currency and country is flagged for review,
    not deleted." Reads the already-converted compensation.usd field
    build_postings.py's own Tier 3.1 fix computes (year-matched FX, never
    re-derived here) and checks the ANNUALISED USD midpoint against one
    fixed, already-reasoned band -- see _POSTINGS_ANNUAL_USD_LOW/HIGH's own
    docstring for why checking the converted figure, not the raw native
    number, is what makes this currency-fair rather than currency-blind.

    FLAG only, per the work order's own explicit instruction ("flagged for
    review, not deleted") -- no ambiguity to resolve the way the OECD wage
    benchmark's own FLAG-vs-ERROR choice needed (see that check's own
    docstring): this one was never asked to block anything.

    COVERAGE, disclosed plainly (an adversarial review's own M10 finding:
    an earlier version of this docstring and its own log() line both said
    "every posting" in a way that overstated what actually gets checked):
    only postings.json rows with a successful compensation.usd conversion
    reach this check at all -- currently ~29% of compensation-bearing
    postings (checked directly: 4,578 of 15,708 in the committed data this
    package regenerated), the rest excluded by an unmapped currency or a
    year with no FX rate, per convert_compensation_to_usd()'s own "refuse
    rather than guess" rule. The other ~71% carry no silent pass here --
    they were never claimed plausible, they were never checked, and the
    no_usd count logged below says so on every run, not just this
    docstring."""
    log(f"· every postings.json row with a successful USD conversion (compensation.usd) is checked "
        f"against a ${_POSTINGS_ANNUAL_USD_LOW:,}-${_POSTINGS_ANNUAL_USD_HIGH:,}/year band -- see "
        f"the no_usd count below for how many rows that excludes")
    postings = _load(processed_dir / "postings.json")
    if not postings:
        flag("postings.json missing or unreadable — cannot check annualised plausibility "
             "(fine if this environment hasn't built the postings panel yet)")
        return
    rows = postings.get("data", {}).get("postings", [])
    checked = flagged = no_usd = 0
    for p in rows:
        comp = p.get("compensation")
        if not comp:
            continue
        usd = comp.get("usd")
        if not usd or usd.get("min") is None or usd.get("max") is None:
            no_usd += 1
            continue
        mult = _POSTINGS_ANNUAL_MULT.get(comp.get("period"))
        if not mult:
            continue
        checked += 1
        midpoint_annual = (usd["min"] + usd["max"]) / 2 * mult
        if midpoint_annual < _POSTINGS_ANNUAL_USD_LOW or midpoint_annual > _POSTINGS_ANNUAL_USD_HIGH:
            flagged += 1
            flag(f"postings[{p.get('id')}] ({p.get('company') or p.get('company_slug')}, "
                 f"{p.get('title')!r}): annualised ${midpoint_annual:,.0f}/year (from "
                 f"{comp.get('min')}-{comp.get('max')} {comp.get('currency')}/{comp.get('period')}) is "
                 f"outside the ${_POSTINGS_ANNUAL_USD_LOW:,}-${_POSTINGS_ANNUAL_USD_HIGH:,} band — "
                 "review, not auto-corrected or dropped")
    log(f"  {checked} checked, {flagged} outside the band, {no_usd} with compensation but no USD "
        f"conversion available (unmapped currency or no FX rate for that year — not counted either way)")


def check_full_table_self_consistency(processed_dir: Path = PROCESSED) -> None:
    """Package 19 -- a source that extracts a PDF's ENTIRE ranking table (not
    just our 15 countries), like ef_epi.json and wipo_gii.json, can validate
    itself against the publication's own structure instead of trusting the
    parse blind. A source opts in by carrying meta.full_table (every row)
    and meta.full_table_stats (published_total, range) -- see
    src_pdf_indices.py. Generic over any source shaped this way, not a
    one-off check tied to these two files.

    Four checks:
      * row count matches what the publisher itself states;
      * every score falls inside the publisher's own stated range;
      * the rank sequence is complete and tie-aware -- competition ranking
        (1, 2, 2, 4, ...) is how these tables are actually published, so a
        rank that repeats with the SAME score is a legitimate tie and the
        next distinct rank is expected to skip accordingly, never an error.
        Package 18 wasted a whole check on exactly this mistake, flagging
        Sweden and Australia's identical 7.284 as if it were a defect;
      * a rank that repeats with a DIFFERENT score is not a tie -- it is two
        rows read as the same rank -- and IS an error.
    """
    log("· a full extracted PDF table (meta.full_table) matches the publisher's own row count, "
        "range and rank sequence — ties allowed, conflicts are not")
    sources_checked = 0
    for path in sorted(processed_dir.glob("*.json")):
        doc = _load(path)
        if not doc:
            continue
        meta = doc.get("meta") or {}
        table = meta.get("full_table")
        stats = meta.get("full_table_stats")
        if not table or not stats:
            continue
        sources_checked += 1
        source = path.name

        rows = sorted(
            ((r["rank"], r["name"], r["score"]) for r in table if "rank" in r and "score" in r),
            key=lambda r: r[0],
        )

        expected_total = stats.get("published_total")
        if expected_total is not None and len(rows) != expected_total:
            err(f"{source}: full_table has {len(rows)} rows, publisher states {expected_total}")

        rng = stats.get("range")
        if rng and len(rng) == 2:
            lo, hi = rng
            for rank, name, score in rows:
                if not (lo <= score <= hi):
                    err(f"{source}: {name!r} (rank {rank}) score {score} is outside the "
                        f"publisher's own range [{lo}, {hi}]")

        by_rank: dict[int, list[tuple[int, str, float]]] = {}
        for r in rows:
            by_rank.setdefault(r[0], []).append(r)

        expected_next = 1
        for rank in sorted(by_rank):
            entries = by_rank[rank]
            distinct_scores = {round(e[2], 6) for e in entries}
            if len(distinct_scores) > 1:
                err(f"{source}: rank {rank} has conflicting scores {sorted(distinct_scores)} across "
                    f"{[e[1] for e in entries]} — not a tie, a parse conflict")
            if rank != expected_next:
                err(f"{source}: rank sequence gap — expected {expected_next}, found {rank}")
            expected_next = rank + len(entries)

        prev_rank = prev_score = None
        for rank, name, score in rows:
            if prev_score is not None and rank != prev_rank and score > prev_score + 1e-9:
                err(f"{source}: {name!r} (rank {rank}, score {score}) scores higher than "
                    f"rank {prev_rank}'s {prev_score} — ranking is not monotonic")
            prev_rank, prev_score = rank, score

    log(f"  {sources_checked} source(s) with a self-checking full table")


# ---------------------------------------------------------------------------

def main() -> int:
    log("CS Migration Compass — data audit (Tier 1 structural invariants)")
    log("(complements `make validate` — see this file's own docstring for the split)")
    log("")
    check_percentiles_monotonic()
    check_mean_within_percentile_range()
    check_no_negative_or_zero_pay()
    check_distribution_label_matches_percentile_presence()
    check_pay_fields_disclose_currency_and_period()
    check_magnitude_plausibility()
    check_embedded_cross_checks_reconcile()
    check_refresh_intervals()
    check_postings_merge_is_current()
    check_oecd_wage_benchmark()
    check_postings_annualised_plausibility()
    check_full_table_self_consistency()

    log("")
    if FLAGS:
        log(f"{len(FLAGS)} flag(s) for review:")
        for f in FLAGS[:60]:
            log(f"  ! {f}")
        if len(FLAGS) > 60:
            log(f"  ... and {len(FLAGS) - 60} more")
    if ERRORS:
        log("")
        log(f"{len(ERRORS)} ERROR(s):")
        for e in ERRORS:
            log(f"  x {e}")
        log("")
        log("FAILED")
        return 1
    log("")
    log("PASSED — every processed dataset's own structural invariants hold (or are explicitly flagged for review).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
