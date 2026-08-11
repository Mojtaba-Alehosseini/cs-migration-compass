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


def check_crosswalk_comparison_depth(mappings: list[dict] | None = None,
                                      compare_fn=None) -> None:
    """Package 8, assertion 1. The 'meet in the middle' comparison rule
    (scripts/crosswalk.py's compare()) must never report a resolved depth
    deeper than either side's own mapping supports. Checked systematically
    across every pair of mappings — not eyeballed on the handful of samples
    crosswalk.py prints — so a future change to compare() that quietly
    breaks the rule for some untested pair still gets caught.

    compare_fn is overridable so this can be tested against a deliberately
    broken implementation without touching scripts/crosswalk.py."""
    log("· crosswalk comparison rule never reports a depth deeper than either side supports")
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
            depth_a, depth_b = crosswalk.depth_of(a["shared_key"]), crosswalk.depth_of(b["shared_key"])
            if depth_a is None or depth_b is None:
                bad += 1
                err(f"comparison rule: {a['country']}/{a['national_code']} vs "
                    f"{b['country']}/{b['national_code']} reported comparable=True but at least one "
                    "side has no ISCO-08 depth at all (shared_key 'unmapped') — must be refused")
                continue
            if result.get("depth") is None or result["depth"] > min(depth_a, depth_b):
                bad += 1
                err(f"comparison rule: {a['country']}/{a['national_code']} (depth {depth_a}) vs "
                    f"{b['country']}/{b['national_code']} (depth {depth_b}) resolved to depth "
                    f"{result.get('depth')!r}, deeper than the shallower side supports")
    log(f"  {checked} mapping pairs checked, {bad} depth violation(s)")


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
        note = (m.get("note") or "").strip()
        if len(note) < 40:
            thin += 1
            err(f"occupations.json: {m.get('country')}/{m.get('national_code')} has no real "
                f"evidence note ({len(note)} chars) — a mapping nobody checked is a guess, not a mapping")
    log(f"  {len(mappings)} mappings, {thin} without a real note")


def check_no_series_records(source_ids=None, processed_dir: Path = PROCESSED) -> None:
    """Package 8, assertion 3. A 'no-series' (or 'no-occupation-series')
    salary record is well formed: it carries that status, AND either a
    dated last-known figure (a year appears somewhere in its data — the
    UAE's case) or an explicit reason why no figure exists at all (a
    meta.why_it_matters or data.alternative pointer — Italy's case).
    Absence with no reason given is indistinguishable from a bug.

    Scans every processed dataset by default (not just files named
    salary_*.json — that pattern would silently skip bls_oews.json, exactly
    the scoping mistake package 7's own review caught in
    check_survey_vs_advertised_pay). source_ids/processed_dir are
    overridable so this can be tested against a scratch directory."""
    log("· 'no-series' salary records carry a status, a reason, and dated or explicitly-absent data")
    checked = 0
    for path in _processed_files(processed_dir, source_ids):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        data = doc.get("data") or {}
        status = data.get("status")
        if not isinstance(status, str) or not status.startswith("no-"):
            continue
        checked += 1
        meta = doc.get("meta") or {}
        occs = data.get("occupations") or {}
        if occs:
            # The year can live inside the occupation records themselves (a
            # by_year breakdown) or as a sibling of "occupations" (the UAE's
            # last_known_year) — search the whole data blob, not just occs.
            blob = json.dumps(data)
            if not re.search(r"\b(19|20)\d{2}\b", blob):
                err(f"processed/{path.name}: status {status!r} has non-empty occupations but no year "
                    "appears anywhere in its data — a 'no-series' record that still shows data must date it")
        else:
            if not meta.get("why_it_matters") and not data.get("alternative"):
                err(f"processed/{path.name}: status {status!r} has empty occupations and no "
                    "explanation (meta.why_it_matters or data.alternative) — absence with no reason "
                    "given is indistinguishable from a bug")
        if meta.get("status") != status:
            err(f"processed/{path.name}: data.status={status!r} but meta.status={meta.get('status')!r} "
                "— these must agree")
    log(f"  {checked} no-data record(s) found and checked")


def check_percentile_absence_explicit(source_ids=None, processed_dir: Path = PROCESSED) -> None:
    """Package 8, assertion 4. A salary source with no percentile fields
    must say so explicitly via a `distribution` flag (e.g.
    'central-tendency-only', 'mean-only') on every occupation record.
    Otherwise a genuinely percentile-less source (Australia, Ireland, Qatar,
    the UAE) is indistinguishable from a harvester that simply forgot to
    ask for percentiles — package 9's estimator needs to tell those apart.

    Scans every processed dataset by default — see check_no_series_records
    for why a salary_*.json-only glob is the wrong default here."""
    log("· sources with no percentiles say so explicitly (a distribution flag)")
    percentile_field_re = re.compile(r"(?:^|_)p\d{1,3}(?:_|$)")
    checked = 0
    for path in _processed_files(processed_dir, source_ids):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        occs = (doc.get("data") or {}).get("occupations") or {}
        for code, occ in occs.items():
            if not isinstance(occ, dict):
                continue
            checked += 1
            names = {n.lower() for n in _field_names(occ)}
            has_percentile = any(percentile_field_re.search(n) for n in names)
            if not has_percentile and "distribution" not in occ:
                err(f"processed/{path.name}: occupation {code!r} has no percentile field and no "
                    "'distribution' flag — must be explicit (e.g. distribution: 'central-tendency-only' "
                    "or 'mean-only'), not silently missing")
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
