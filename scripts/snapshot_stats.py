"""Package 13, Tier 3 — drift and coverage.

Part 1 (drift): a snapshot of key statistics after each run, appended to
data/quality_history/snapshots.jsonl (committed — "store history in the
repo," the work order's own words) and compared against the immediately
previous entry. Material movement is flagged, not silently accepted: the
work order's own example is a source dropping 40%, "a finding, not a
fact." Postings sources are expected to GROW between weekly refreshes (a
live crawl catching more companies over time) — only a drop is flagged
for them; curated/survey sources are expected to stay flat between runs,
so either direction is flagged.

Part 2 (coverage): a matrix per country — occupation depth, pay basis,
experience cross, postings count, stated-pay rate. Every cell is read
directly from what a resolver already computed and committed (wage_
distribution.json's own crosswalk.depth/combos.*.ok, experience_gradient
.json's own by_country keys, postings.json's own provider_summary/
country_counts) rather than independently recomputed here — so this
matrix can never disagree with, or overclaim past, what the site itself
would show (Tier 5's own gate 9).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, PROCESSED, PROVENANCE, ROOT, log  # noqa: E402

FLAGS: list[str] = []
# A DROP specifically (a source/provider/country materially shrinking) is
# split into its own list, checked by main()'s own return code -- adversarial
# review finding M6/M8: this module's main() returned 0 unconditionally, so
# wiring it into an unattended workflow (as Tier 4 now does) would have
# printed a warning nobody's automation actually stopped for. A brand-new
# source appearing, or unexpected growth in a normally-static one, stays a
# FLAG (worth a human noticing, not worth blocking a commit over); an actual
# drop is the one signal the work order's own "a source dropping 40% is a
# finding, not a fact" example is about, and now fails the build.
DROPS: list[str] = []
HISTORY_DIR = DATA / "quality_history"
HISTORY_FILE = HISTORY_DIR / "snapshots.jsonl"

_POSTINGS_SOURCE_RE = re.compile(r"^postings")
DROP_THRESHOLD_PCT = 15.0     # any source: a drop past this is a finding
GROWTH_THRESHOLD_PCT = 50.0   # non-postings sources only: growth past this is ALSO a finding


def flag(msg: str) -> None:
    FLAGS.append(msg)


def drop(msg: str) -> None:
    """A genuine drop, not just a movement worth a human's attention --
    blocks main()'s own return code. See DROPS' own module-level comment."""
    DROPS.append(msg)


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Part 1 — snapshot
# ---------------------------------------------------------------------------

def compute_snapshot(*, baseline_reset_note: str | None = None) -> dict:
    """`baseline_reset_note`, when given, is embedded in the snapshot
    verbatim as its own field — package 14, Tier 4.3: the drift detector
    reported "no material drift" while sitting on a dataset that had
    already lost 55% of its records, because its own baseline snapshot was
    captured AFTER that loss (see docs/REGRESSION-CATALOGUE.md and
    REPORT-P14.md gate 9). snapshots.jsonl is append-only, deliberately —
    "store history in the repo" (this module's own docstring) means the
    OLD, mid-degradation entries are never edited or deleted; this field
    marks the FIRST entry after recovery as the new, honest reference
    point, in the history itself, not a comment only a human reading the
    code would ever see."""
    prov = _load(PROVENANCE) or {"entries": []}
    record_counts = {e["source_id"]: e.get("rows") for e in prov.get("entries", []) if e.get("rows") is not None}

    postings_doc = (_load(PROCESSED / "postings.json") or {}).get("data", {})
    provider_summary = postings_doc.get("provider_summary", {})
    postings_list = postings_doc.get("postings", [])
    by_country: dict[str, dict] = {}
    for p in postings_list:
        c = p.get("country") or "unresolved"
        rec = by_country.setdefault(c, {"total": 0, "stated_pay": 0})
        rec["total"] += 1
        if p.get("compensation"):
            rec["stated_pay"] += 1
    for c, rec in by_country.items():
        rec["stated_pay_rate_pct"] = round(rec["stated_pay"] / rec["total"] * 100, 2) if rec["total"] else 0.0

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "baseline_reset_note": baseline_reset_note,
        "record_counts": record_counts,
        "postings_overall": {
            "total": len(postings_list),
            "stated_pay": sum(1 for p in postings_list if p.get("compensation")),
        },
        "postings_by_provider": {
            k: {"postings_count": v.get("postings_count"), "compensation_present_count": v.get("compensation_present_count")}
            for k, v in provider_summary.items()
        },
        "postings_by_country": by_country,
    }


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    return [json.loads(line) for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_snapshot(snapshot: dict) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, sort_keys=True) + "\n")


def _pct_change(old: float, new: float) -> float | None:
    if old == 0:
        return None  # 0 -> anything is a qualitative appearance, not a percentage
    return (new - old) / old * 100


def compare_against_previous(current: dict, previous: dict | None) -> None:
    log("· drift — comparing against the immediately previous snapshot")
    if previous is None:
        log("  no previous snapshot found — this run establishes the baseline")
        return

    for source_id, new_count in current["record_counts"].items():
        old_count = previous["record_counts"].get(source_id)
        if old_count is None:
            flag(f"drift: {source_id} is new since the previous snapshot ({new_count} rows) — not "
                 "necessarily wrong, but wasn't there last time")
            continue
        change = _pct_change(old_count, new_count)
        if change is None:
            continue
        is_postings_source = bool(_POSTINGS_SOURCE_RE.match(source_id))
        if change < -DROP_THRESHOLD_PCT:
            drop(f"drift: {source_id} dropped {abs(change):.1f}% ({old_count} -> {new_count} rows) "
                 "since the previous snapshot")
        elif not is_postings_source and change > GROWTH_THRESHOLD_PCT:
            flag(f"drift: {source_id} grew {change:.1f}% ({old_count} -> {new_count} rows) since the "
                 "previous snapshot — unexpected for a non-postings source between runs")

    old_overall = previous.get("postings_overall", {})
    new_overall = current["postings_overall"]
    if old_overall.get("total"):
        rate_change = _pct_change(
            old_overall["stated_pay"] / old_overall["total"],
            new_overall["stated_pay"] / new_overall["total"],
        )
        if rate_change is not None and rate_change < -DROP_THRESHOLD_PCT:
            drop(f"drift: overall postings stated-pay rate dropped {abs(rate_change):.1f}% since the "
                 f"previous snapshot ({old_overall['stated_pay']}/{old_overall['total']} -> "
                 f"{new_overall['stated_pay']}/{new_overall['total']})")
        elif rate_change is not None and abs(rate_change) > DROP_THRESHOLD_PCT:
            flag(f"drift: overall postings stated-pay rate moved {rate_change:+.1f}% since the previous "
                 f"snapshot ({old_overall['stated_pay']}/{old_overall['total']} -> "
                 f"{new_overall['stated_pay']}/{new_overall['total']})")

    # Per-provider and per-country counts were recorded in every snapshot
    # but never actually compared -- adversarial review finding M7: the
    # overall total and stated-pay rate can both stay flat while one
    # provider silently collapses (a partial harvester failure whose OTHER
    # providers backfill the total) or while a country_from_location()
    # regression (the exact bug class R14 already fixed once) moves postings
    # from a real country into "unresolved" with the overall total
    # unchanged. Same drop-only-for-postings-sources threshold as the
    # record_counts loop above, since both are postings-shaped counts that
    # are expected to grow, not shrink, between runs.
    for provider, new_p in current.get("postings_by_provider", {}).items():
        old_p = previous.get("postings_by_provider", {}).get(provider)
        new_count = new_p.get("postings_count")
        if old_p is None or new_count is None:
            continue
        change = _pct_change(old_p.get("postings_count"), new_count)
        if change is not None and change < -DROP_THRESHOLD_PCT:
            drop(f"drift: postings provider {provider!r} dropped {abs(change):.1f}% "
                 f"({old_p['postings_count']} -> {new_count} postings) since the previous snapshot")

    MIN_COUNTRY_COUNT_FOR_DROP = 20  # below this, a 15% swing is sample noise, not signal
    for country, new_c in current.get("postings_by_country", {}).items():
        old_c = previous.get("postings_by_country", {}).get(country)
        if old_c is None:
            continue
        change = _pct_change(old_c.get("total"), new_c.get("total"))
        if change is None or change >= -DROP_THRESHOLD_PCT:
            continue
        msg = (f"drift: postings country {country!r} dropped {abs(change):.1f}% "
               f"({old_c['total']} -> {new_c['total']} postings) since the previous snapshot — "
               "check for a country-resolution regression (docs/REGRESSION-CATALOGUE.md R14), "
               "not just a genuine drop in that country's own postings")
        if old_c["total"] >= MIN_COUNTRY_COUNT_FOR_DROP:
            drop(msg)
        else:
            flag(msg + f" (below the {MIN_COUNTRY_COUNT_FOR_DROP}-count floor for blocking — flagged, not failed)")

    log(f"  {len(current['record_counts'])} source(s), "
        f"{len(current.get('postings_by_provider', {}))} provider(s), "
        f"{len(current.get('postings_by_country', {}))} countries compared, "
        f"{len(FLAGS)} flag(s), {len(DROPS)} drop(s) so far")


# ---------------------------------------------------------------------------
# Part 2 — coverage matrix
# ---------------------------------------------------------------------------

def build_coverage_matrix() -> dict[str, dict]:
    wd = (_load(PROCESSED / "wage_distribution.json") or {}).get("data", {})
    countries = {row["country"]: row for row in wd.get("countries", [])}

    eg = (_load(PROCESSED / "experience_gradient.json") or {}).get("data", {})
    experience_countries = set(eg.get("by_country", {}).keys())

    postings_doc = (_load(PROCESSED / "postings.json") or {}).get("data", {})
    country_counts = postings_doc.get("country_counts", {})
    postings_by_country: dict[str, dict] = {}
    for p in postings_doc.get("postings", []):
        c = p.get("country")
        if not c:
            continue
        rec = postings_by_country.setdefault(c, {"total": 0, "stated_pay": 0})
        rec["total"] += 1
        if p.get("compensation"):
            rec["stated_pay"] += 1

    matrix: dict[str, dict] = {}
    for iso, row in countries.items():
        combos = row.get("combos", {})
        comparable = row.get("crosswalk", {}).get("comparable")
        p_rec = postings_by_country.get(iso.split("-")[0], {"total": 0, "stated_pay": 0})
        matrix[iso] = {
            "comparable": comparable,
            "occupation_depth": row.get("crosswalk", {}).get("depth"),
            # Gated on `comparable`, not just each combo's own `ok` flag --
            # R8's own finding is that computePosition()/computeEstimate()
            # check crosswalk.comparable FIRST and render nothing at all
            # when it's False, regardless of what combos.*.ok says. An
            # earlier version of this matrix reported the Netherlands'
            # combos.native_regular_pay.ok=true as though the site would
            # show a figure for it -- it never does (comparable=false,
            # "NL has no ISCO-08 correspondence at all for this
            # occupation"). Named pay_basis_if_comparable so a reader can't
            # miss the precondition even without reading this comment.
            # Adversarial review finding H4, reproduced against the real
            # committed data before this fix, not assumed.
            "pay_basis_if_comparable": {k: v.get("ok", False) for k, v in combos.items()} if comparable else {},
            "experience_cross": iso in experience_countries,
            "postings_count": country_counts.get(iso, p_rec["total"]),
            "postings_stated_pay_rate_pct": round(p_rec["stated_pay"] / p_rec["total"] * 100, 1) if p_rec["total"] else None,
        }
    return matrix


def report_coverage_matrix(matrix: dict[str, dict]) -> None:
    log("· coverage matrix — every cell read from the resolver's own committed output")
    log(f"  {len(matrix)} countries in wage_distribution.json; "
        f"{sum(1 for m in matrix.values() if m['experience_cross'])} personalise by experience "
        f"({sorted(iso for iso, m in matrix.items() if m['experience_cross'])})")
    for iso in sorted(matrix):
        m = matrix[iso]
        bases = ", ".join(k for k, ok in m["pay_basis_if_comparable"].items() if ok) or "none"
        log(f"  {iso:9s} depth={m['occupation_depth']!s:4s} comparable={m['comparable']!s:5s} "
            f"bases=[{bases}] experience={m['experience_cross']} "
            f"postings={m['postings_count']} stated_pay={m['postings_stated_pay_rate_pct']}%")


# ---------------------------------------------------------------------------

def main(*, append: bool = True, baseline_reset_note: str | None = None) -> int:
    """`append=False` (generate_data_quality_doc.py's own read-only report
    path) runs the same drift comparison and coverage build but writes
    NEITHER data/quality_history/snapshots.jsonl NOR coverage_matrix.json —
    regenerating the DOC must never itself add a real entry to drift
    history (package 13 finding L16). Package 14, Tier 4.1 (external audit
    Finding 4): this parameter was DESCRIBED as already added in package
    13's own report, but the live file never actually carried it — a real,
    reproduced TypeError (`main() got an unexpected keyword argument
    'append'`) when generate_data_quality_doc.py called it, which is
    exactly why DATA-QUALITY.md was reporting "Overall: PASSING" while its
    own Snapshot section silently said COULD NOT RUN. Every doc
    regeneration since (this package's own preflight included) appended a
    spurious real snapshot entry as a result — see Tier 4.3 for the
    baseline reset this caused."""
    log("CS Migration Compass — drift and coverage snapshot (Tier 3)")
    log("")

    history = load_history()
    previous = history[-1] if history else None
    current = compute_snapshot(baseline_reset_note=baseline_reset_note)
    compare_against_previous(current, previous)
    if baseline_reset_note:
        log(f"  BASELINE RESET: {baseline_reset_note}")
    if append:
        append_snapshot(current)
        log(f"  snapshot appended to {HISTORY_FILE.relative_to(ROOT)} ({len(history) + 1} total)")
    else:
        log("  read-only report (append=False) — no snapshot written")

    log("")
    matrix = build_coverage_matrix()
    report_coverage_matrix(matrix)
    if append:
        (HISTORY_DIR / "coverage_matrix.json").write_text(
            json.dumps({"generated_at": current["generated_at"], "matrix": matrix}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        log(f"  coverage matrix written to {(HISTORY_DIR / 'coverage_matrix.json').relative_to(ROOT)}")
    else:
        log("  read-only report (append=False) — coverage_matrix.json not written")

    log("")
    if FLAGS:
        log(f"{len(FLAGS)} flag(s):")
        for f in FLAGS:
            log(f"  ! {f}")
    if DROPS:
        log(f"{len(DROPS)} DROP(s) — a genuine decline, past the point of sample noise:")
        for d in DROPS:
            log(f"  x {d}")
        log("")
        log("FAILED")
        return 1
    if not FLAGS:
        log("no material drift since the previous snapshot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
