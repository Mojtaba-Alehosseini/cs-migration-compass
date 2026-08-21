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
HISTORY_DIR = DATA / "quality_history"
HISTORY_FILE = HISTORY_DIR / "snapshots.jsonl"

_POSTINGS_SOURCE_RE = re.compile(r"^postings")
DROP_THRESHOLD_PCT = 15.0     # any source: a drop past this is a finding
GROWTH_THRESHOLD_PCT = 50.0   # non-postings sources only: growth past this is ALSO a finding


def flag(msg: str) -> None:
    FLAGS.append(msg)


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Part 1 — snapshot
# ---------------------------------------------------------------------------

def compute_snapshot() -> dict:
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
            flag(f"drift: {source_id} dropped {abs(change):.1f}% ({old_count} -> {new_count} rows) "
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
        if rate_change is not None and abs(rate_change) > DROP_THRESHOLD_PCT:
            flag(f"drift: overall postings stated-pay rate moved {rate_change:+.1f}% since the previous "
                 f"snapshot ({old_overall['stated_pay']}/{old_overall['total']} -> "
                 f"{new_overall['stated_pay']}/{new_overall['total']})")

    log(f"  {len(current['record_counts'])} source(s) compared, {len(FLAGS)} material movement(s) flagged so far")


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
        p_rec = postings_by_country.get(iso.split("-")[0], {"total": 0, "stated_pay": 0})
        matrix[iso] = {
            "comparable": row.get("crosswalk", {}).get("comparable"),
            "occupation_depth": row.get("crosswalk", {}).get("depth"),
            "pay_basis": {k: v.get("ok", False) for k, v in combos.items()},
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
        bases = ", ".join(k for k, ok in m["pay_basis"].items() if ok) or "none"
        log(f"  {iso:9s} depth={m['occupation_depth']!s:4s} comparable={m['comparable']!s:5s} "
            f"bases=[{bases}] experience={m['experience_cross']} "
            f"postings={m['postings_count']} stated_pay={m['postings_stated_pay_rate_pct']}%")


# ---------------------------------------------------------------------------

def main() -> int:
    log("CS Migration Compass — drift and coverage snapshot (Tier 3)")
    log("")

    history = load_history()
    previous = history[-1] if history else None
    current = compute_snapshot()
    compare_against_previous(current, previous)
    append_snapshot(current)
    log(f"  snapshot appended to {HISTORY_FILE.relative_to(ROOT)} ({len(history) + 1} total)")

    log("")
    matrix = build_coverage_matrix()
    report_coverage_matrix(matrix)
    (HISTORY_DIR / "coverage_matrix.json").write_text(
        json.dumps({"generated_at": current["generated_at"], "matrix": matrix}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    log(f"  coverage matrix written to {(HISTORY_DIR / 'coverage_matrix.json').relative_to(ROOT)}")

    log("")
    if FLAGS:
        log(f"{len(FLAGS)} flag(s):")
        for f in FLAGS:
            log(f"  ! {f}")
    else:
        log("no material drift since the previous snapshot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
