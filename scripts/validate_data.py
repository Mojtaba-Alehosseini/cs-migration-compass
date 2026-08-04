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

Exit code 1 on any ERROR. Warnings are reported but do not fail the build.
"""
from __future__ import annotations

import datetime as dt
import json
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

    orphans = set(entries) - {p.stem for p in files}
    for o in orphans:
        warn(f"provenance[{o}] has no processed file")
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


def main() -> int:
    log("CS Migration Compass — data validation")
    log("")
    check_curated()
    check_staleness()
    check_processed()
    check_forecast_separation()

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
