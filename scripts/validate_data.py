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
            if doc.get("data"):
                err(f"processed/{path.name}: status is {status!r} but data is non-empty")
        else:
            ok += 1
            if not doc.get("data"):
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


def main() -> int:
    log("CS Migration Compass — data validation")
    log("")
    check_curated()
    check_staleness()
    check_processed()
    check_forecast_separation()
    check_odbl_isolation()
    check_survey_vs_advertised_pay()
    check_percentiles_not_seniority()
    check_crosswalk_comparison_depth()
    check_crosswalk_notes()
    check_no_series_records()
    check_percentile_absence_explicit()

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
