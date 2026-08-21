"""Data validation — `make validate`, and the gate CI runs on every push.

This encodes the project's non-negotiable data rules as executable checks, so a
violation fails the build instead of quietly shipping:

  * every city belongs to a known country; ids are unique
  * salary bands never invert (new_grad <= mid <= senior)
  * missing values are explicit null — never 0, "", "n/a" or "unknown"
  * every record carries as_of and at least one source
  * FX rates and confidence tiers exist in metrics.json
  * every processed dataset parses, matches the envelope, and has provenance
  * provenance entries declare a licence and their transforms
  * as_of dates are checked against the staleness rules in metrics.json
  * the ODbL Stack Overflow survey never reaches core.json (share-alike risk)
  * survey earnings and advertised pay never occupy the same field
  * a percentile is never labelled a seniority band, in a field name or in prose
  * the crosswalk's comparison rule never reports a depth deeper than either
    side's own mapping supports
  * every crosswalk mapping carries a real, checked-against evidence note
  * a "no-series" salary record is well formed: a status, a reason, and
    either a dated last-known figure or an explicit statement that none exists
  * a source with no percentiles says so explicitly (a `distribution` flag),
    rather than a silently missing field that looks like a fetch omission
  * scripts/normalise.py never substitutes a different year's FX rate than
    the one requested
  * scripts/normalise.py never annualises an hourly figure without a real,
    sourced hours-per-week record (never a flat 2080)
  * scripts/normalise.py's monthly->annual multiplier is exactly 12,
    everywhere, and no other multiplier or additive bonus uplift exists
    anywhere in the codebase
  * scripts/normalise.py's comparison_basis() never reports two sources
    comparable when they cannot express the same pay-composition basis
  * scripts/normalise.py performs no file writes at all — it is a pure
    conversion module; native processed data is never overwritten by it
  * every successful scripts/normalise.py conversion names its own rate,
    year and source in its return value, not just a bare number

Exit code 1 on any ERROR. Warnings are reported but do not fail the build.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA, PROCESSED, PROVENANCE, ROOT, load_cities, load_countries, log,
)

ERRORS: list[str] = []
WARNINGS: list[str] = []

FAKE_NULLS = {"", "n/a", "N/A", "na", "none", "None", "unknown", "-", "--", "?"}


def err(msg: str) -> None:
    ERRORS.append(msg)


def warn(msg: str) -> None:
    WARNINGS.append(msg)


def _is_effectively_empty(obj) -> bool:
    """True if obj holds no real content anywhere inside it -- None, a bare
    {}/[], or a dict/list whose every value is ALSO effectively empty
    (recursively). A plain `if doc.get("data")` truthiness check (this
    function's own first version) treats {"classifications": {}} as
    non-empty, because the outer dict has one key -- found live, not
    theoretical: postings_classifications.json's own blocked/0-rows state
    (GEMINI_API_KEY absent) is EXACTLY this shape, {"classifications": {}},
    and failed `make validate` (the gate CI runs on every push) for a
    correctly-empty result. A scalar (a number, a non-empty string, True/
    False) is never effectively empty -- only containers can be, and only
    when every one of their own values is too."""
    if obj is None:
        return True
    if isinstance(obj, dict):
        return all(_is_effectively_empty(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_is_effectively_empty(v) for v in obj)
    return False


def check_curated() -> None:
    log("· curated data")
    countries = load_countries()
    cities = load_cities()
    metrics = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))

    ids = [c["id"] for c in countries]
    if len(ids) != len(set(ids)):
        err(f"countries.json: duplicate ids {[i for i in ids if ids.count(i) > 1]}")
    known = set(ids)
    log(f"  {len(countries)} countries, {len(cities)} cities")

    city_ids = [c["id"] for c in cities]
    if len(city_ids) != len(set(city_ids)):
        err(f"cities.json: duplicate ids {sorted({i for i in city_ids if city_ids.count(i) > 1})}")

    inversions = 0
    nulls_found = 0
    for c in cities:
        if c.get("country") not in known:
            err(f"cities.json: {c['id']} has unknown country {c.get('country')!r}")
        if not c.get("as_of"):
            err(f"cities.json: {c['id']} missing as_of")
        if not c.get("sources"):
            err(f"cities.json: {c['id']} has no sources")

        sal = c.get("salary_usd_year") or {}
        bands = [sal.get("new_grad"), sal.get("mid"), sal.get("senior")]
        present = [b for b in bands if isinstance(b, (int, float))]
        if len(present) == 3 and not (present[0] <= present[1] <= present[2]):
            err(f"cities.json: {c['id']} salary bands invert: {present}")
            inversions += 1

        # explicit nulls only — a fabricated 0 would silently become a real value
        for k, v in c.items():
            if isinstance(v, str) and v.strip() in FAKE_NULLS:
                err(f"cities.json: {c['id']}.{k} uses a placeholder string {v!r} instead of null")
            if v is None:
                nulls_found += 1
        for k, v in (c.get("climate") or {}).items():
            if v is None:
                nulls_found += 1

    for c in countries:
        if not c.get("as_of"):
            err(f"countries.json: {c['id']} missing as_of")
        if not c.get("sources"):
            err(f"countries.json: {c['id']} has no sources")
        tax = (c.get("tax") or {}).get("net_pct_single_mid_dev")
        if tax is not None and not (30 <= tax <= 100):
            err(f"countries.json: {c['id']} implausible net_pct_single_mid_dev {tax}")

    log(f"  {inversions} salary inversions, {nulls_found} explicit nulls (nulls are expected and fine)")

    meta = metrics.get("meta", {})
    if not meta.get("fx_rates_usd_base"):
        err("metrics.json: missing fx_rates_usd_base")
    tiers = set(meta.get("confidence_tiers", {}))
    if tiers != {"official", "index", "crowd"}:
        err(f"metrics.json: confidence tiers should be official/index/crowd, got {sorted(tiers)}")
    if not meta.get("staleness_rules_months"):
        err("metrics.json: missing staleness_rules_months")


def check_staleness() -> None:
    log("· staleness")
    metrics = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))
    rules = metrics["meta"]["staleness_rules_months"]
    today = dt.date.today()

    def months_old(as_of: str) -> float | None:
        try:
            parts = as_of.split("-")
            y, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 1
        except (ValueError, IndexError):
            return None
        return (today.year - y) * 12 + (today.month - m)

    stale = 0
    for rec in load_cities() + load_countries():
        age = months_old(str(rec.get("as_of", "")))
        if age is None:
            warn(f"{rec['id']}: unparseable as_of {rec.get('as_of')!r}")
            continue
        if age > rules.get("prices_salaries", 12):
            warn(f"{rec['id']}: as_of {rec['as_of']} is {age} months old "
                 f"(> {rules['prices_salaries']}m rule) — the UI must show a staleness warning")
            stale += 1
    log(f"  {stale} record(s) past the prices/salaries staleness rule")


def check_processed() -> None:
    log("· processed datasets + provenance")
    if not PROVENANCE.exists():
        err("data/provenance.json missing — run `make pipeline` first")
        return
    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    entries = {e["source_id"]: e for e in prov.get("entries", [])}

    files = sorted(PROCESSED.glob("*.json"))
    if not files:
        err("data/processed/ is empty — run `make pipeline` first")
        return

    ok = blocked = 0
    for path in files:
        sid = path.stem
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            err(f"processed/{path.name}: invalid JSON ({exc})")
            continue
        for key in ("source_id", "generated_at", "meta", "data"):
            if key not in doc:
                err(f"processed/{path.name}: missing envelope key {key!r}")
        entry = entries.get(sid)
        if entry is None:
            err(f"processed/{path.name}: no provenance entry for source_id {sid!r}")
            continue
        if not entry.get("license"):
            err(f"provenance[{sid}]: missing license")
        if not entry.get("transforms"):
            err(f"provenance[{sid}]: missing transforms — every dataset must say what was done to it")
        if not entry.get("fetched_at"):
            err(f"provenance[{sid}]: missing fetched_at")

        status = entry.get("status", "ok")
        if status in ("blocked", "unavailable", "failed"):
            blocked += 1
            if not entry.get("notes"):
                err(f"provenance[{sid}]: status {status!r} must carry notes explaining why")
            if not _is_effectively_empty(doc.get("data")):
                err(f"processed/{path.name}: status is {status!r} but data is non-empty")
        else:
            ok += 1
            if _is_effectively_empty(doc.get("data")):
                warn(f"processed/{path.name}: status ok but data is empty")

    # Most sources land in data/processed/. A few do not — a source whose output
    # is a committed derived asset elsewhere in the repo still needs provenance
    # and a citation line, so check what the entry actually claims rather than
    # assuming where it claims it.
    orphans = set(entries) - {p.stem for p in files}
    for o in orphans:
        output = (entries[o].get("output") or "").replace("\\", "/")
        if not output:
            warn(f"provenance[{o}] records no output at all")
        elif output.startswith("data/processed/"):
            warn(f"provenance[{o}] claims {output} but no such file exists")
        elif not (ROOT / output).exists():
            err(f"provenance[{o}] claims {output}, which is not in the repo")
    log(f"  {len(files)} datasets — {ok} with data, {blocked} recorded as blocked/unavailable")


def check_forecast_separation() -> None:
    """Institutional forecasts must be labelled as such and never pre-blended."""
    log("· forecast integrity")
    found = 0
    for path in sorted(PROCESSED.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        meta = doc.get("meta", {})
        if meta.get("kind") != "institutional_forecast":
            continue
        found += 1
        if not meta.get("institution"):
            err(f"processed/{path.name}: institutional forecast without an institution")
        if not meta.get("attribution_chip") and meta.get("status") not in ("blocked", "unavailable"):
            err(f"processed/{path.name}: institutional forecast without an attribution_chip")
        if not meta.get("render_rule"):
            warn(f"processed/{path.name}: no render_rule recorded")
    if found == 0:
        err("no institutional forecast datasets found — the forecast overlay would be empty")
    log(f"  {found} institutional forecast dataset(s)")


def _field_names(obj, out: set[str] | None = None) -> set[str]:
    """Every dict key anywhere inside a JSON-shaped value, recursively."""
    if out is None:
        out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(str(k))
            _field_names(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _field_names(v, out)
    return out


def _find_matching_brace(src: str, open_idx: int) -> int:
    """Given the index of a '{', return the index just past its matching '}'."""
    depth = 0
    for i in range(open_idx, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(src)


def check_odbl_isolation(build_site_data_path: Path | None = None) -> None:
    """Integrity rule 1 (package 7). The Stack Overflow survey is ODbL — a
    share-alike licence. Merging it into the same derived database as the
    CC-BY/public-domain sources that make up core.json risks pulling the whole
    bundle under ODbL. Today it ships only as its own lazy history file, via
    the HISTORY_SETS registration in build_site_data.py.

    This checks the WHOLE file, not just build_core() (a first version scoped
    to build_core() only and missed a reference planted in main(), which is
    what actually writes core.json — caught by this package's own adversarial
    review, not shipped). Every mention of 'stackoverflow' anywhere in the
    file must fall inside the HISTORY_SETS dict literal, the one sanctioned
    lazy-load registration; a mention anywhere else — in build_core(), in
    main(), in a helper, behind an alias — fails.

    build_site_data_path is overridable so this can be tested against a
    scratch file without touching the real pipeline script."""
    log("· ODbL isolation — the Stack Overflow survey must never reach core.json")
    path = build_site_data_path or (ROOT / "scripts" / "build_site_data.py")
    if not path.exists():
        err("scripts/build_site_data.py is missing — cannot check ODbL isolation")
        return
    src = path.read_text(encoding="utf-8")

    hs_start = src.find("HISTORY_SETS = {")
    if hs_start == -1:
        err("scripts/build_site_data.py: HISTORY_SETS not found — ODbL isolation cannot be checked "
            "(if it was renamed, this check needs updating, not skipping)")
        return
    hs_end = _find_matching_brace(src, src.find("{", hs_start))

    lower = src.lower()
    idx = 0
    while True:
        idx = lower.find("stackoverflow", idx)
        if idx == -1:
            break
        if not (hs_start <= idx < hs_end):
            line_no = src.count("\n", 0, idx) + 1
            err(f"scripts/build_site_data.py:{line_no}: 'stackoverflow' appears outside the "
                "HISTORY_SETS dict — the ODbL survey must reach core.json only through the "
                "sanctioned lazy-load path, never elsewhere in this file.")
        idx += len("stackoverflow")


def _processed_files(processed_dir: Path, source_ids) -> list[Path]:
    if source_ids is not None:
        return [processed_dir / f"{sid}.json" for sid in source_ids if (processed_dir / f"{sid}.json").exists()]
    return sorted(processed_dir.glob("*.json"))


def check_survey_vs_advertised_pay(source_ids=None, processed_dir: Path = PROCESSED) -> None:
    """Integrity rule 2 (package 7). Survey earnings (this package: SCB/ONS/Job
    Bank/BLS) and advertised pay (a future package: job postings) must never
    occupy the same field. Nothing ingests advertised pay yet, so this holds
    today by construction — the point is that it keeps holding once that
    package exists.

    Scans EVERY processed dataset by default, not a hardcoded list of today's
    four wage sources (a first version scoped to just those four and so could
    never see a brand-new file a later package adds — caught by this
    package's own adversarial review, not shipped). source_ids/processed_dir
    are overridable so this can be tested against a scratch directory."""
    log("· survey pay and advertised pay never share a field")
    survey_hints = ("median", "mean", "average", "p10", "p25", "p75", "p90", "jobs_thousand")
    advertised_markers = ("advertised", "posting_wage", "posted_pay", "offer_range", "offer_wage",
                           "listed_wage", "listing_wage", "jd_wage", "job_ad", "ad_salary", "ad_wage")
    for path in _processed_files(processed_dir, source_ids):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        names = {n.lower() for n in _field_names(doc.get("data"))}
        has_survey = any(any(h in n for h in survey_hints) for n in names)
        advertised_hits = [n for n in names if any(m in n for m in advertised_markers)]
        if has_survey and advertised_hits:
            err(f"processed/{path.name}: has both survey-wage field names and advertised-pay-shaped "
                f"field name(s) {advertised_hits} — these must never occupy the same field")


def check_postings_wage_spine_boundary(processed_dir: Path = PROCESSED) -> None:
    """Integrity rule (package 12). A genuine, additive cross-FILE check —
    postings.json literally never carries the wage spine's own distinctive
    field names, and wage_distribution.json literally never carries
    postings.json's own. Added alongside check_survey_vs_advertised_pay
    above, not folded into it: that check scans WITHIN one file for
    co-occurring hint words, which is a different (and already useful)
    thing, not a comparison between the two files at all — package 12's own
    first report claimed this file's existing assertion already covered
    the cross-file case, which this package's own adversarial review found
    was not true. Deliberately narrow: `country`/`currency`/`period` are
    real, ordinary field names both files use for their own unrelated
    reasons, and are excluded here rather than flagged, so this only fires
    on a genuine leak, not a coincidental shared word."""
    log("· postings.json and wage_distribution.json share no distinctive field")
    postings_path = processed_dir / "postings.json"
    spine_path = processed_dir / "wage_distribution.json"
    if not postings_path.exists() or not spine_path.exists():
        return
    postings_only = {
        "raw_text", "confidence", "company_slug", "location_raw", "seed_companies",
        "provider_summary", "country_counts",
    }
    spine_only = {
        "p10", "p25", "p75", "p90", "combos", "crosswalk", "native_regular_pay",
        "native_total_earnings", "usd_regular_pay", "usd_total_earnings", "dispersion_by_year",
    }
    postings_fields = _field_names(json.loads(postings_path.read_text(encoding="utf-8")).get("data"))
    spine_fields = _field_names(json.loads(spine_path.read_text(encoding="utf-8")).get("data"))
    leaked_into_spine = postings_only & spine_fields
    leaked_into_postings = spine_only & postings_fields
    if leaked_into_spine:
        err(f"processed/wage_distribution.json: carries postings-only field name(s) "
            f"{sorted(leaked_into_spine)} — advertised pay must never reach the survey-wage file")
    if leaked_into_postings:
        err(f"processed/postings.json: carries wage-spine-only field name(s) "
            f"{sorted(leaked_into_postings)} — survey wage data must never reach the postings file")


def check_percentiles_not_seniority(source_ids=None, processed_dir: Path = PROCESSED,
                                     docs_dir: Path | None = None) -> None:
    """Integrity rule 4 (package 7). A percentile is total dispersion — it
    conflates firm effects, region, part-time status, the sex pay gap,
    enterprise size and collective-agreement coverage, which is exactly why
    Eurostat publishes each of those as a separate breakdown. It is not a
    seniority signal and must never be labelled as one, in a field name or in
    the methodology prose. Sweden's age x occupation table is the one real
    seniority signal in this package; it is exempt because it is genuinely
    age-banded, not because it is close enough.

    Scans every processed dataset (field names are only flagged when the same
    file also looks percentile-shaped, so an unrelated file's legitimate use
    of 'senior' elsewhere is not a false positive). The prose check matches
    ANY P-plus-digits token (P10..P99), not a fixed list — a first version
    only matched P10/25/50/75/90 and missed the UK source's own P20/P30/P40/
    P60/P70/P80 fields, and only matched junior/senior/mid-career and missed
    'experienced'/'entry-level' phrasing — both caught by this package's own
    adversarial review, not shipped. source_ids/processed_dir/docs_dir are
    overridable so this can be tested against scratch files."""
    log("· percentile fields and prose are never labelled as seniority bands")
    seniority_words = ("junior", "senior", "mid-career", "mid_career", "midcareer",
                        "entry-level", "entry_level", "entry level", "experienced")
    # Matches a p10/p25/.../p90-style token anywhere in a field name, whether
    # it's the whole name ("p10"), a suffix ("p10_low"), or embedded between
    # words ("annual_p10_usd") — not just names that start with it.
    percentile_field_re = re.compile(r"(?:^|_)p\d{1,3}(?:_|$)")
    for path in _processed_files(processed_dir, source_ids):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        names = {n.lower() for n in _field_names(doc.get("data"))}
        # A single field name must match BOTH patterns to count — not "this
        # file has a percentile field somewhere and a seniority word
        # somewhere else". The first version flagged the file-wide
        # co-occurrence and caught stackoverflow_survey.json's legitimate,
        # unrelated "senior"/"senior executive (c-suite, vp, etc.)" experience
        # CATEGORY labels purely because that file also has percentile
        # compensation fields elsewhere — a false positive, caught by this
        # package's own adversarial review, not shipped. The work order's own
        # wording is about a percentile's OWN field name ("the field names
        # ... must not call them junior/mid/senior"), which this now matches.
        hit = [n for n in names if percentile_field_re.search(n) and any(w in n for w in seniority_words)]
        if hit:
            err(f"processed/{path.name}: percentile field name(s) {hit} use a seniority word — "
                "percentiles are dispersion, not seniority")

    perc_re = re.compile(r"\bP\d{1,3}\b|\bpercentiles?\b", re.IGNORECASE)
    sen_re = re.compile("|".join(rf"\b{re.escape(w)}\b" for w in seniority_words), re.IGNORECASE)
    for doc_name in ("METHODOLOGY.md", "LIMITATIONS.md"):
        path = (docs_dir or (ROOT / "docs")) / doc_name
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if perc_re.search(line) and sen_re.search(line):
                err(f"docs/{doc_name}:{i}: a percentile and a seniority word appear on the same line "
                    f"— check this is not labelling a percentile as a seniority band: {line.strip()!r}")


def _load_mappings(occ_file: Path | None = None) -> list[dict] | None:
    path = occ_file or (DATA / "occupations.json")
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("mappings", [])


def _key_depth_and_digits(shared_key: str) -> tuple[int | None, str | None]:
    """Ground truth for a shared_key's depth and digit string, computed by
    a fresh regex match rather than by calling crosswalk.depth_of() — so a
    bug in that function cannot also blind this check to the same bug (an
    adversarial review found the first version of this check derived its
    'expected' answer from the same function it was meant to be checking)."""
    if shared_key == "unmapped":
        return None, None
    m = re.match(r"^isco08:(\d{1}|\d{2}|\d{4})$", shared_key or "")
    return (len(m.group(1)), m.group(1)) if m else (None, None)


def check_crosswalk_comparison_depth(mappings: list[dict] | None = None,
                                      compare_fn=None) -> None:
    """Package 8, assertion 1. The 'meet in the middle' comparison rule
    (scripts/crosswalk.py's compare()) must never report a resolved depth
    deeper than either side's own mapping supports, and — checked
    independently, not just via depth — the resolved shared_key it reports
    must be the actual truncated digits BOTH sides agree on, not merely a
    plausible-looking depth. Checked systematically across every pair of
    mappings — not eyeballed on the handful of samples crosswalk.py prints
    — so a future change to compare() that quietly breaks the rule for some
    untested pair still gets caught.

    An earlier version of this check only compared result['depth'] against
    min(depth_a, depth_b) and never looked at result['shared_key'] at all —
    an adversarial review showed that lets compare() report two DIFFERENT
    4-digit codes as comparable at depth 4 (4 > 4 is False, so the old check
    stayed silent) as long as it didn't report a deeper number than either
    side's own depth. This version independently truncates both sides' own
    shared_key to min(depth_a, depth_b) digits and requires the two
    truncations to be equal to each other AND to match what compare()
    reported — closing that gap.

    compare_fn is overridable so this can be tested against a deliberately
    broken implementation without touching scripts/crosswalk.py."""
    log("· crosswalk comparison rule never reports a depth deeper than either side supports, "
        "and its resolved shared_key is the real agreed-upon truncation")
    if mappings is None:
        mappings = _load_mappings()
        if mappings is None:
            err("data/occupations.json is missing — cannot check the comparison rule")
            return
    import crosswalk
    compare = compare_fn or crosswalk.compare
    checked = bad = 0
    for i, a in enumerate(mappings):
        for b in mappings[i + 1:]:
            checked += 1
            result = compare(a, b)
            if not result.get("comparable"):
                continue
            depth_a, digits_a = _key_depth_and_digits(a["shared_key"])
            depth_b, digits_b = _key_depth_and_digits(b["shared_key"])
            if depth_a is None or depth_b is None:
                bad += 1
                err(f"comparison rule: {a['country']}/{a['national_code']} vs "
                    f"{b['country']}/{b['national_code']} reported comparable=True but at least one "
                    "side has no ISCO-08 depth at all (shared_key 'unmapped' or malformed) — must be refused")
                continue
            expected_depth = min(depth_a, depth_b)
            expected_digits = digits_a[:expected_depth]
            if digits_b[:expected_depth] != expected_digits:
                bad += 1
                err(f"comparison rule: {a['country']}/{a['national_code']} ({a['shared_key']}) vs "
                    f"{b['country']}/{b['national_code']} ({b['shared_key']}) reported comparable=True "
                    f"but the codes do NOT actually agree when independently truncated to "
                    f"{expected_depth} digits: {expected_digits!r} vs {digits_b[:expected_depth]!r} — "
                    "this compares two different occupations as if they were the same one")
                continue
            if result.get("depth") != expected_depth:
                bad += 1
                err(f"comparison rule: {a['country']}/{a['national_code']} (depth {depth_a}) vs "
                    f"{b['country']}/{b['national_code']} (depth {depth_b}) resolved to depth "
                    f"{result.get('depth')!r}, not the shallower side's own depth {expected_depth}")
                continue
            expected_key = f"isco08:{expected_digits}"
            if result.get("shared_key") != expected_key:
                bad += 1
                err(f"comparison rule: {a['country']}/{a['national_code']} vs "
                    f"{b['country']}/{b['national_code']} resolved shared_key "
                    f"{result.get('shared_key')!r}, not the expected truncation {expected_key!r} — "
                    "package 9 reads shared_key, not just depth, so this field must be right too")
    log(f"  {checked} mapping pairs checked, {bad} violation(s)")


_NOTE_PLACEHOLDER_MARKERS = ("todo", "fixme", "tbd", "xxx", "placeholder", "n/a",
                             "not sure", "probably fine", "checked ok", "looks fine")


def _note_defect(note: str) -> str | None:
    """Returns why a crosswalk note fails to count as real evidence, or
    None if it passes. A bare length check (the first version of this
    function) accepts forty dots or a chatty TODO as 'real evidence' — an
    adversarial review constructed both and got 0 errors. This also rejects
    low-character-variety strings (a repeated placeholder character) and a
    short list of placeholder phrases actually seen in the wild."""
    s = note.strip()
    if len(s) < 40:
        return f"too short ({len(s)} chars) to count as evidence"
    if len(set(s.lower()) - {" ", "."}) < 8:
        return "too low-variety to be real prose (looks like a repeated placeholder character)"
    low = s.lower()
    hit = next((m for m in _NOTE_PLACEHOLDER_MARKERS if m in low), None)
    if hit:
        return f"contains a placeholder phrase ({hit!r}), not evidence"
    return None


def check_crosswalk_notes(mappings: list[dict] | None = None) -> None:
    """Package 8, assertion 2. Every crosswalk mapping must carry a real,
    non-trivial note — the same bar scripts/crosswalk.py's own audit holds
    mappings to, checked here too so `make validate` (the gate CI actually
    runs) catches a thin note even if the crosswalk audit is not run."""
    log("· every crosswalk mapping carries a real, checked-against note")
    if mappings is None:
        mappings = _load_mappings()
        if mappings is None:
            err("data/occupations.json is missing — cannot check crosswalk notes")
            return
    thin = 0
    for m in mappings:
        defect = _note_defect(m.get("note") or "")
        if defect:
            thin += 1
            err(f"occupations.json: {m.get('country')}/{m.get('national_code')} has no real "
                f"evidence note — {defect} — a mapping nobody checked is a guess, not a mapping")
    log(f"  {len(mappings)} mappings, {thin} without a real note")


_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def _has_dated_evidence(obj) -> bool:
    """True if a year appears as a dict key (a by_year-style breakdown) or
    as a value under a key whose own name contains 'year' (last_known_year,
    years_stale, etc.) — anywhere in obj, recursively. Deliberately NARROWER
    than 'any 4-digit-shaped number anywhere in the JSON', which a plain
    salary figure like {"mean_eur_month": 2019.5} would satisfy by sheer
    coincidence — an adversarial review constructed exactly that and got a
    false 'well dated' pass from the first version of this function."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            ks = str(k)
            if _YEAR_RE.match(ks):
                return True
            if "year" in ks.lower():
                if isinstance(v, (int, float)) and 1900 <= v <= 2100:
                    return True
                if isinstance(v, str) and _YEAR_RE.match(v.strip()):
                    return True
                if isinstance(v, list) and any(
                        isinstance(x, (int, float, str)) and _YEAR_RE.match(str(x).strip()) for x in v):
                    return True
            if _has_dated_evidence(v):
                return True
        return False
    if isinstance(obj, list):
        return any(_has_dated_evidence(item) for item in obj)
    return False


def check_no_series_records(source_ids=None, processed_dir: Path = PROCESSED) -> None:
    """Package 8, assertion 3. A 'no-series' (or 'no-occupation-series')
    salary record is well formed: it carries that status, AND either a
    dated last-known figure (a year appears somewhere in its data — the
    UAE's case) or an explicit reason why no figure exists at all (a
    meta.why_it_matters or data.alternative pointer — Italy's case).
    Absence with no reason given is indistinguishable from a bug. meta and
    data must agree on the status.

    Scans every processed dataset by default (not just files named
    salary_*.json — that pattern would silently skip bls_oews.json, exactly
    the scoping mistake package 7's own review caught in
    check_survey_vs_advertised_pay). source_ids/processed_dir are
    overridable so this can be tested against a scratch directory.

    Checks meta.status and data.status for agreement even when only ONE of
    them claims a 'no-*' status — an earlier version keyed entirely off
    data.status, so a file with data.status missing entirely but
    meta.status='no-series' was skipped before the agreement check ever
    ran; an adversarial review constructed exactly that file and got 0
    errors."""
    log("· 'no-series' salary records carry a status, a reason, and dated or explicitly-absent data; "
        "meta and data agree on it")
    checked = 0
    for path in _processed_files(processed_dir, source_ids):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        data = doc.get("data") or {}
        meta = doc.get("meta") or {}
        data_status = data.get("status")
        meta_status = meta.get("status")
        data_is_noseries = isinstance(data_status, str) and data_status.startswith("no-")
        meta_is_noseries = isinstance(meta_status, str) and meta_status.startswith("no-")
        if not data_is_noseries and not meta_is_noseries:
            continue
        checked += 1
        if data_status != meta_status:
            err(f"processed/{path.name}: data.status={data_status!r} but meta.status={meta_status!r} "
                "— these must agree")
        if not data_is_noseries:
            continue  # meta claims no-series but data itself doesn't — nothing further to check
        occs = data.get("occupations") or {}
        if occs:
            if not _has_dated_evidence(data):
                err(f"processed/{path.name}: status {data_status!r} has non-empty occupations but no "
                    "year appears anywhere in its data — a 'no-series' record that still shows data "
                    "must date it")
        else:
            if not meta.get("why_it_matters") and not data.get("alternative"):
                err(f"processed/{path.name}: status {data_status!r} has empty occupations and no "
                    "explanation (meta.why_it_matters or data.alternative) — absence with no reason "
                    "given is indistinguishable from a bug")
    log(f"  {checked} no-data record(s) found and checked")


_WAGE_FIELD_HINTS = ("mean", "median", "average", "p10", "p25", "p75", "p90", "wage", "salary", "income")


def _occupation_like_records(data: dict) -> dict[str, dict]:
    """Find every {code: record} group that looks like occupation-level
    wage data. Prefers data['occupations'] (the standard shape every
    salary_*.json source uses); falls back to treating `data` ITSELF as a
    code-keyed group when there is no 'occupations' wrapper at all and a
    sibling value has at least THREE distinct wage-shaped field names —
    bls_oews.json's shape (city keys directly under data, e.g.
    data['new_york'], each with mean/median/p10-p90 fields). Without this
    fallback, a percentile-absence check that only ever looks inside
    data['occupations'] silently contributes zero checked records for
    bls_oews.json — an adversarial review confirmed this: the check's own
    docstring claimed a whole-directory scan closes exactly this kind of
    gap, but the actual field lookup still missed this file's shape.

    The 3-field threshold (not >=1) matters: a first version flagged ANY
    single wage-hint match, which swept in oecd_indicators.json's per-
    country records (house_prices/avg_wages/hours_worked/tax_wedge — one
    incidental 'wage' hit among four unrelated macro indicators, not an
    occupation-level wage record at all) and produced 13 false-positive
    errors against real, correct data on the first run against this repo."""
    occs = data.get("occupations")
    if isinstance(occs, dict):
        return {code: rec for code, rec in occs.items() if isinstance(rec, dict)}
    found = {}
    for k, v in data.items():
        if not isinstance(v, dict):
            continue
        matches = [fk for fk in v if any(h in str(fk).lower() for h in _WAGE_FIELD_HINTS)]
        if len(matches) >= 3:
            found[k] = v
    return found


def check_percentile_absence_explicit(source_ids=None, processed_dir: Path = PROCESSED) -> None:
    """Package 8, assertion 4. A salary source with no percentile fields
    must say so explicitly via a `distribution` flag drawn from a known,
    registered vocabulary (`central-tendency-only`, `mean-only`) on every
    occupation record. Otherwise a genuinely percentile-less source
    (Australia, Ireland, Qatar, the UAE) is indistinguishable from a
    harvester that simply forgot to ask for percentiles — package 9's
    estimator needs to tell those apart.

    Scans every processed dataset by default — see check_no_series_records
    for why a salary_*.json-only glob is the wrong default here — using
    _occupation_like_records() so a file without an 'occupations' wrapper
    (bls_oews.json) is actually scanned, not silently skipped.

    Requires `distribution`'s VALUE to be a real, registered value, not
    just present: an earlier version only checked `"distribution" not in
    occ`, so `"distribution": None`, `""`, or any made-up string all
    passed — an adversarial review constructed all three and got 0 errors."""
    log("· sources with no percentiles say so explicitly (a distribution flag from a known vocabulary)")
    percentile_field_re = re.compile(r"(?:^|_)p\d{1,3}(?:_|$)")
    known_distributions = {"central-tendency-only", "mean-only"}
    checked = 0
    for path in _processed_files(processed_dir, source_ids):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        records = _occupation_like_records((doc.get("data") or {}))
        for code, occ in records.items():
            checked += 1
            names = {n.lower() for n in _field_names(occ)}
            has_percentile = any(percentile_field_re.search(n) for n in names)
            if has_percentile:
                continue
            dist = occ.get("distribution")
            if dist not in known_distributions:
                err(f"processed/{path.name}: occupation {code!r} has no percentile field and no valid "
                    f"'distribution' flag (got {dist!r}) — must be one of {sorted(known_distributions)}, "
                    "not silently missing or an unregistered value")
    log(f"  {checked} occupation record(s) checked")


def check_normalise_fx_year_matching() -> None:
    """Package 9, assertion 1. scripts/normalise.py's fx_rate() must return
    the rate for EXACTLY the year requested, never a nearby year — and
    to_usd() must refuse (ok: False) rather than silently substitute a
    different year when the exact one is unavailable. Calls the real
    functions; does not scan a file (there is nothing on disk yet to
    scan — normalise.py is pure and writes nothing, see the next check).

    EXTENDED (tier 7, adversarial review finding F5): the original version
    only tested the REFUSAL path for to_usd() (a year with no rate). A
    to_usd() broken to refuse EVERY year, valid or not, would pass this
    check AND assertion 6 (whose self-describe check is itself gated on
    `usd.get("ok")`, so an always-False to_usd() short-circuits it too) —
    a real conversion that stopped working entirely, invisible to either
    assertion. Added: a KNOWN-GOOD year must actually succeed.

    ALSO EXTENDED (finding F10): the five assertions above test the pure
    FUNCTIONS; none of them ever open data/processed/wage_distribution.json
    and check the ARTEFACT the site actually ships. A hardcoded wrong year
    in one of build_wage_distribution.py's per-country extractors (several
    are hardcoded — UK 2025, AU/CA 2024, AE 2009) would reach the site
    undetected by every function-level check above. Added: scan the real,
    committed artefact for any usd-mode combo whose FX year doesn't match
    its own native.year."""
    log("· normalise.py never substitutes a different year's FX rate than the one requested")
    import normalise as nm
    bad = 0
    real = nm.fx_rate("DK", 2024)
    if real is None or real["year"] != 2024:
        bad += 1
        err(f"normalise.fx_rate('DK', 2024) returned {real!r} — expected year=2024 exactly")
    missing_year = nm.fx_rate("DK", 1500)  # centuries before any FX series exists
    if missing_year is not None:
        bad += 1
        err(f"normalise.fx_rate('DK', 1500) returned {missing_year!r} instead of None — "
            "a missing year must never resolve to a substitute year's rate")
    conv = nm.to_usd(100.0, "DK", 1500)
    if conv.get("ok") is not False:
        bad += 1
        err(f"normalise.to_usd(100.0, 'DK', 1500) returned {conv!r} — must refuse (ok: False) "
            "for a year with no FX rate, not convert at a substitute rate")
    # A to_usd() that refuses EVERY year (not just invalid ones) would pass
    # every check above — confirm a real, valid year actually succeeds.
    good = nm.to_usd(100.0, "DK", 2024)
    if good.get("ok") is not True or good.get("fx_year") != 2024:
        bad += 1
        err(f"normalise.to_usd(100.0, 'DK', 2024) — a year with a real, known FX rate — returned "
            f"{good!r}; expected ok:True, fx_year:2024. A to_usd() broken to refuse everything would "
            "pass this assertion's own refusal checks above and would also slip past assertion 6, "
            "whose self-describe check only runs when ok is already True")

    wd_path = PROCESSED / "wage_distribution.json"
    if wd_path.exists():
        doc = json.loads(wd_path.read_text(encoding="utf-8"))
        year_mismatches = 0
        for row in doc.get("data", {}).get("countries", []):
            native_year = row.get("native", {}).get("year")
            for combo_key, combo in row.get("combos", {}).items():
                if not combo_key.startswith("usd_") or not combo.get("ok"):
                    continue
                for step in combo.get("chain", []):
                    m = re.search(r"\((\w{2,3}) (\d{4}) period-average rate", step.get("detail", ""))
                    if m and int(m.group(2)) != native_year:
                        year_mismatches += 1
                        err(f"wage_distribution.json: {row['country']} {combo_key} converts at "
                            f"FX year {m.group(2)} but its own native.year is {native_year}")
        bad += year_mismatches
        log(f"  ({len(doc.get('data', {}).get('countries', []))} committed wage_distribution.json rows "
            f"scanned for FX-year mismatch: {year_mismatches} found)")
    log(f"  {bad} violation(s)")


def check_normalise_hours_required() -> None:
    """Package 9, assertion 2. scripts/normalise.py's annualise() must
    refuse (ok: False) to convert an hourly figure to annual for a country
    with no sourced hours-worked record — never assume the US 2080
    (40h x 52wk) convention, which would overstate Denmark's own ~38.2-38.4
    usual weekly hours by a measured 4.2-4.7% (year-dependent — see
    normalise.py's own docstring for the exact figures; tier 7's
    adversarial review caught an uncorrected "~7%" here)."""
    log("· normalise.py never annualises an hourly figure without a real, sourced hours record")
    import normalise as nm
    bad = 0
    fake_country = "ZZ"  # not in hours_worked.json by construction
    result = nm.annualise(100.0, "hour", fake_country)
    if result.get("ok") is not False or "value_annual" in result:
        bad += 1
        err(f"normalise.annualise(100.0, 'hour', 'ZZ') returned {result!r} — a country with no "
            "sourced hours record must refuse (ok: False, no value_annual key at all), not silently "
            "assume 2080 hours/year")
    real = nm.annualise(100.0, "hour", "DK")
    if real.get("ok") is not True or "hours_per_week" not in real or "hours_source" not in real:
        bad += 1
        err(f"normalise.annualise(100.0, 'hour', 'DK') (a country WITH a sourced hours record) "
            f"returned {real!r} — expected ok:True with hours_per_week and hours_source present")
    log(f"  {bad} violation(s)")


_SUSPICIOUS_MULTIPLIER_RE = re.compile(r"\*\s*1[134]\b|\*\s*13\.\d|value\s*\*\s*(?!12\b)\d+\s*#.*(?:month|annual)", re.I)
_UPLIFT_FUNCTION_RE = re.compile(r"^def \w*(?:uplift|add_component)\w*\(", re.M | re.I)


def check_normalise_multiplier_is_twelve() -> None:
    """Package 9, assertion 3. The monthly->annual multiplier is exactly
    12, everywhere — both behaviourally (calling the function) and
    structurally: no OTHER numeric multiplier or additive/multiplicative
    bonus uplift exists anywhere the work order's own rule 3 covers —
    "no x13 and no x14 anywhere in this codebase" (§5.2.3), not just in
    normalise.py.

    WIDENED (tier 7, adversarial review finding F8): the original version
    scanned only scripts/normalise.py. A x13.3 multiplier or an uplift
    function placed in scripts/build_wage_distribution.py — which also
    calls subtract_component() and does real arithmetic on wage values —
    was invisible to this check. Now scans every scripts/*.py file.
    Structural regex scanning cannot catch an arbitrarily-disguised
    equivalent expression (e.g. `40.0 / 3.0` instead of `13.33`) — that
    is an accepted, bounded limitation of pattern matching, not something
    this fix claims to close; the BEHAVIOURAL check above (a real
    annualise() call must return exactly x12) is what catches a change to
    the sanctioned path itself, and gate 10's hand-verified figures are
    the check of last resort for anything a pattern can't name."""
    log("· normalise.py's monthly->annual multiplier is exactly 12, nowhere else in the codebase")
    import normalise as nm
    bad = 0
    if nm.MONTHLY_MULTIPLIER != 12:
        bad += 1
        err(f"normalise.MONTHLY_MULTIPLIER is {nm.MONTHLY_MULTIPLIER!r}, not 12")
    r = nm.annualise(1000.0, "month", "SE")
    if r.get("value_annual") != 12000.0:
        bad += 1
        err(f"normalise.annualise(1000.0, 'month', 'SE') gave {r.get('value_annual')!r}, expected "
            "12000.0 (x12 exactly)")
    for py in sorted((ROOT / "scripts").glob("*.py")):
        src = py.read_text(encoding="utf-8")
        # validate_data.py itself legitimately contains the pattern's own
        # regex literal (_SUSPICIOUS_MULTIPLIER_RE's definition, right here
        # in this file) — the same self-match gate 9's evidence documented.
        # Skipped only for THIS pattern, on THIS one file; the uplift and
        # additive-bonus scans below have no equivalent self-reference and
        # still cover validate_data.py like every other file.
        hit = None if py.name == "validate_data.py" else _SUSPICIOUS_MULTIPLIER_RE.search(src)
        if hit:
            bad += 1
            err(f"scripts/{py.name} contains a suspicious multiplier pattern: {hit.group(0)!r} — "
                "the only sanctioned monthly->annual multiplier anywhere in this codebase is 12 "
                "(normalise.MONTHLY_MULTIPLIER)")
        uplift_hit = _UPLIFT_FUNCTION_RE.search(src)
        if uplift_hit:
            bad += 1
            err(f"scripts/{py.name} defines {uplift_hit.group(0)!r} — a function named like it adds "
                "or uplifts a bonus/component to a value; this codebase may only ever SUBTRACT a "
                "component the source publishes separately (normalise.subtract_component()), never "
                "add or scale one up")
        if re.search(r"value\s*\+=?\s*\w*bonus", src, re.I):
            bad += 1
            err(f"scripts/{py.name} contains an additive-bonus pattern (value + ...bonus) — this "
                "codebase may only ever subtract a component the source publishes separately")
    log(f"  {bad} violation(s)")


def check_normalise_comparison_basis() -> None:
    """Package 9, assertion 4. scripts/normalise.py's comparison_basis()
    must never report two sources 'comparable' when their pay_composition
    entries cannot express a shared basis — the composition analogue of
    scripts/crosswalk.py's compare(), held to the same standard package 8
    held that function to: construct a case where a naive check would get
    this wrong and confirm the real function still gets it right."""
    log("· normalise.py's comparison_basis() never compares sources on incompatible bases")
    import normalise as nm
    bad = 0
    # salary_dk's RAW pay_composition entry includes employer contributions
    # (PENS baked into FORINKL) — it cannot express EITHER basis as shipped.
    dk_vs_anything = nm.comparison_basis("salary_dk", "salary_se")
    if dk_vs_anything.get("comparable") is not False:
        bad += 1
        err(f"comparison_basis('salary_dk', 'salary_se') returned {dk_vs_anything!r} — Denmark's raw "
            "FORINKL includes employer pension contributions and cannot express either basis until "
            "subtract_component() is applied; this must be refused, not compared")
    # A genuinely unknown source (no pay_composition.json entry at all) must
    # also refuse, not silently treat "unknown" fields as compatible.
    unknown = nm.comparison_basis("salary_se", "salary_does_not_exist")
    if unknown.get("comparable") is not False:
        bad += 1
        err(f"comparison_basis('salary_se', 'salary_does_not_exist') returned {unknown!r} — a source "
            "with no pay_composition.json entry at all must refuse, not compare")
    # A real, known-compatible pair must still succeed — this check must not
    # be so strict it refuses everything. FIXED (tier 7, adversarial review
    # finding F7): the first version of this test required BOTH bases —
    # itself wrong, and it would have failed the moment the F1 fix (below)
    # made total_earnings require irregular_bonus is True, not just
    # employer_social_contributions is False. Sweden and the Netherlands
    # both have irregular_bonus=False — their own figures EXCLUDE the
    # bonus, so calling that pairing "total_earnings-comparable" repeats
    # exactly the bug F1 fixes: two bonus-excluded figures are not made
    # into a bonus-included ("total earnings") comparison by both also
    # lacking employer contributions. regular_pay is the one real shared
    # basis, and is what this test now requires.
    compatible = nm.comparison_basis("salary_se", "salary_nl")
    if compatible.get("comparable") is not True or "regular_pay" not in (compatible.get("common_bases") or []):
        bad += 1
        err(f"comparison_basis('salary_se', 'salary_nl') returned {compatible!r} — both sources "
            "carry irregular_bonus=False and employer_social_contributions=False in pay_composition.json "
            "and should be comparable on regular_pay")
    # The bug this whole assertion exists to catch, reproduced directly:
    # total_earnings must NEVER be granted to a source whose own figure
    # excludes the bonus, even if the other basis condition (no employer
    # contributions) is met.
    wrong_total = nm.comparison_basis("salary_se", "salary_es")
    if wrong_total.get("comparable") is True and "total_earnings" in (wrong_total.get("common_bases") or []):
        bad += 1
        err(f"comparison_basis('salary_se', 'salary_es') returned {wrong_total!r} — Sweden's own "
            "figure EXCLUDES the irregular bonus (irregular_bonus=False in pay_composition.json); "
            "comparing it to Spain's bonus-INCLUDED figure as 'total_earnings'-equivalent mixes two "
            "different earnings concepts, exactly what rule 4 exists to prevent")
    log(f"  {bad} violation(s)")


def check_normalise_no_file_writes() -> None:
    """Package 9, assertion 5. scripts/normalise.py performs NO file
    writes at all — rule 5, "native is the source of truth", enforced
    structurally: every function in that module is pure (takes values in,
    returns a new dict), so there is no code path anywhere in it that
    could overwrite a native data/processed/salary_*.json value. Checked
    by scanning the module's own source for any write-capable call, not
    by asserting the JSON files are unchanged after running it (weaker —
    a write that happened to write the same bytes back would pass a
    diff-based check and still be a rule violation in spirit).

    WIDENED (tier 7, adversarial review finding F9): the write-pattern
    list only matched `open(..., 'w'` — append mode (`open(path, 'a')` or
    `mode="a"`) and an atomic write-then-rename (`os.replace`/`os.rename`
    onto a native path, or `shutil.move`/`shutil.copy`) are equally real
    ways to overwrite a file and were invisible to it. Widened the pattern
    list to cover all of these.

    ALSO ADDED (same finding): normalise.py isn't the only module in this
    pipeline that writes files — scripts/build_wage_distribution.py
    legitimately does, every run, via write_processed(). Rule 5 is really
    "no NATIVE salary_*.json/bls_oews.json file is ever overwritten by
    anything this package added", which is a narrower and more precise
    claim than "this one file writes nothing" — checked directly by
    confirming build_wage_distribution.py's own write_processed() call
    always targets the literal string "wage_distribution", never a
    variable that could resolve to a native source's id."""
    log("· normalise.py performs no file writes — native processed data is never overwritten by it")
    src = (ROOT / "scripts" / "normalise.py").read_text(encoding="utf-8")
    bad = 0
    write_patterns = [
        (r"\.write_text\(", "write_text("), (r"\.write_bytes\(", "write_bytes("),
        (r"write_processed\(", "write_processed("), (r"open\([^)]*['\"]w", "open(..., 'w'"),
        (r"open\([^)]*mode\s*=\s*['\"]a", "open(..., mode='a'"), (r"open\([^)]*['\"]a['\"]\s*\)", "open(..., 'a')"),
        (r"os\.replace\(", "os.replace("), (r"os\.rename\(", "os.rename("),
        (r"shutil\.(move|copy)\(", "shutil.move/copy("),
    ]
    for pattern, label in write_patterns:
        if re.search(pattern, src):
            bad += 1
            err(f"scripts/normalise.py contains {label} — this module must perform no file writes "
                "at all (rule 5: native is the source of truth)")

    orchestrator = ROOT / "scripts" / "build_wage_distribution.py"
    if orchestrator.exists():
        osrc = orchestrator.read_text(encoding="utf-8")
        calls = re.findall(r"write_processed\(\s*([^,\)]+)", osrc)
        bad_calls = [c for c in calls if c.strip() not in ('"wage_distribution"', "'wage_distribution'")]
        if bad_calls:
            bad += 1
            err(f"scripts/build_wage_distribution.py calls write_processed() with {bad_calls!r} — "
                "this orchestrator may only ever write its own derived 'wage_distribution' output, "
                "never a variable source_id that could resolve to a native salary_*.json file")
        elif not calls:
            bad += 1
            err("scripts/build_wage_distribution.py has no write_processed() call at all — expected "
                "exactly one, writing 'wage_distribution'")
    log(f"  {bad} violation(s)")


def _missing_provenance_keys(result: dict, required: set[str]) -> set[str]:
    """The actual self-describe rule, factored out so the real check below
    and its own negative test run the SAME logic — see finding F6: an
    earlier version's 'negative case' did set arithmetic on two literals
    and never called this logic at all, so it could not fail regardless of
    what the real functions did. ok:False is never a violation (a refused
    conversion has nothing to self-describe); ok:True with missing keys is."""
    if not result.get("ok"):
        return set()
    return required - set(result)


def check_normalise_conversions_self_describe() -> None:
    """Package 9, assertion 6. Every successful conversion from
    scripts/normalise.py names its own rate, year and source in its
    return value — never a bare converted number with the evidence left
    implicit. Checked against real calls, and against a constructed
    'stripped' result to confirm the check itself can fail.

    FIXED (tier 7, adversarial review finding F6): the original negative
    case computed `required_usd - set(stripped)` directly and branched on
    THAT — pure set arithmetic on two hardcoded literals, never calling
    _missing_provenance_keys() (nor the inline logic it replaces) at all.
    It could not fail no matter how badly the real functions broke,
    because it never exercised them. Fixed to call the same helper the
    real checks below use, against the same stripped dict — now a real
    behavioural test, not a tautology.

    ALSO FIXED (finding F5, other half): to_usd()/annualise() broken to
    return ok:False unconditionally would make BOTH the real checks below
    silently skip (nothing to check on a refusal) — invisible here. That
    specific bypass is caught by assertion 1's added known-good-year check
    instead, which is a more precise place to catch it (a conversion that
    stopped succeeding at all vs. one that succeeds without describing
    itself are different failures) — noted here so the two assertions'
    coverage is legible together, not because this function re-tests it."""
    log("· every normalise.py conversion names its own rate, year and source")
    import normalise as nm
    bad = 0
    usd = nm.to_usd(100.0, "DK", 2024)
    required_usd = {"fx_rate", "fx_year", "fx_source", "chain"}
    missing = _missing_provenance_keys(usd, required_usd)
    if missing:
        bad += 1
        err(f"normalise.to_usd(...) result is missing {missing} — every conversion must self-describe "
            "its rate, year and source, not just return a bare value_usd")
    hourly = nm.annualise(100.0, "hour", "DK")
    required_hourly = {"hours_per_week", "hours_year", "hours_source", "chain"}
    missing_h = _missing_provenance_keys(hourly, required_hourly)
    if missing_h:
        bad += 1
        err(f"normalise.annualise(..., 'hour', ...) result is missing {missing_h}")
    # The check's own negative case: a stripped-down but ok:True result
    # MUST be flagged by the exact same helper used above, not by
    # re-deriving the expectation from scratch.
    stripped = {"ok": True, "value_usd": 70.96}
    stripped_missing = _missing_provenance_keys(stripped, required_usd)
    if not stripped_missing:
        bad += 1
        err("check_normalise_conversions_self_describe's own negative case (a stripped ok:True result "
            "with no fx_rate/fx_year/fx_source/chain) was NOT flagged by _missing_provenance_keys() — "
            "the check cannot actually fail, which means it cannot actually pass meaningfully either")
    log(f"  {bad} violation(s)")


def main() -> int:
    log("CS Migration Compass — data validation")
    log("")
    check_curated()
    check_staleness()
    check_processed()
    check_forecast_separation()
    check_odbl_isolation()
    check_survey_vs_advertised_pay()
    check_postings_wage_spine_boundary()
    check_percentiles_not_seniority()
    check_crosswalk_comparison_depth()
    check_crosswalk_notes()
    check_no_series_records()
    check_percentile_absence_explicit()
    check_normalise_fx_year_matching()
    check_normalise_hours_required()
    check_normalise_multiplier_is_twelve()
    check_normalise_comparison_basis()
    check_normalise_no_file_writes()
    check_normalise_conversions_self_describe()

    log("")
    if WARNINGS:
        log(f"{len(WARNINGS)} warning(s):")
        for w in WARNINGS[:40]:
            log(f"  ! {w}")
        if len(WARNINGS) > 40:
            log(f"  ... and {len(WARNINGS) - 40} more")
    if ERRORS:
        log("")
        log(f"{len(ERRORS)} ERROR(s):")
        for e in ERRORS:
            log(f"  x {e}")
        log("")
        log("FAILED")
        return 1
    log("")
    log("PASSED — curated data, processed datasets and provenance are consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
