"""Audits data/occupations.json — the national-code -> ISCO-08 crosswalk.

This is not a fetcher: the crosswalk is a curated, evidenced judgement call
(there is no single API that hands you "is SSYK 2514 the same job as ISCO-08
2514"), the same way cities.json and countries.json are curated rather than
derived. What this script checks is that the table is internally honest:

  * every mapping carries a confidence level from the table's own vocabulary,
    consistent with whether its shared_key is 4-digit or 2-digit
  * every mapping carries a non-trivial note (evidence, not a placeholder)
  * no (country, national_code) pair is silently duplicated or contradicted
  * every shared_key is well-formed AND appears in the shared_keys registry
    (a well-formed-but-unregistered key such as a typo'd isco08:2599 is
    caught, not just checked for shape)
  * every national_code, AND its national_title, actually match the source
    file it claims to — catching drift if a harvester's occupation codes or
    titles ever change, not just the code

`python scripts/crosswalk.py` prints the full table (gate 8's evidence) and
exits non-zero on any structural problem. `make validate` does not currently
call this — it is a standalone audit, run and its output pasted into the
package report, the same way the chart-integrity audits were in package 6.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, PROCESSED, log  # noqa: E402

OCC_FILE = DATA / "occupations.json"
SHARED_KEY_RE = re.compile(r"^isco08:(\d{2}|\d{4})$")

ERRORS: list[str] = []


def err(msg: str) -> None:
    ERRORS.append(msg)


def main() -> int:
    log("CS Migration Compass — occupation crosswalk audit")
    log("")

    if not OCC_FILE.exists():
        err("data/occupations.json is missing")
        log(f"{len(ERRORS)} ERROR(s)"); log("  x " + ERRORS[0])
        return 1

    doc = json.loads(OCC_FILE.read_text(encoding="utf-8"))
    levels = set(doc.get("confidence_levels", {}))
    registry = doc.get("shared_keys", {})
    mappings = doc.get("mappings", [])
    if not registry:
        err("data/occupations.json: no 'shared_keys' registry — every shared_key would pass on "
            "shape alone, with no check that it is a real, deliberately-registered ISCO-08 unit")
    log(f"confidence levels: {sorted(levels)}")
    log(f"{len(mappings)} mappings across {len({m['country'] for m in mappings})} countries")
    log("")

    seen_pairs: set[tuple[str, str]] = set()
    four_digit_targets: set[str] = set()
    source_cache: dict[str, dict] = {}

    header = f"{'country':7s} {'code':10s} {'shared_key':14s} {'conf':13s}  title"
    log(header)
    log("-" * len(header))

    for m in mappings:
        country, code = m.get("country"), m.get("national_code")
        pair = (country, code)
        if pair in seen_pairs:
            err(f"duplicate mapping for {pair}")
        seen_pairs.add(pair)

        conf = m.get("confidence")
        if conf not in levels:
            err(f"{pair}: confidence {conf!r} is not one of {sorted(levels)}")

        note = (m.get("note") or "").strip()
        if len(note) < 40:
            err(f"{pair}: note is missing or too thin ({len(note)} chars) to count as evidence")

        key = m.get("shared_key", "")
        if not SHARED_KEY_RE.match(key):
            err(f"{pair}: shared_key {key!r} is not a well-formed isco08:NN or isco08:NNNN key")
        else:
            if key not in registry:
                err(f"{pair}: shared_key {key!r} is not in the shared_keys registry — a key that "
                    "is well-formed but unregistered is a typo, not a deliberate mapping")
            if len(key.split(":")[1]) == 4:
                four_digit_targets.add(key)
                if conf == "2-digit-only":
                    err(f"{pair}: shared_key {key!r} is 4-digit but confidence is '2-digit-only' — "
                        "these must not disagree")
            elif conf != "2-digit-only":
                err(f"{pair}: shared_key {key!r} is 2-digit but confidence is {conf!r}, not '2-digit-only'")

        # Cross-check the code AND its title actually exist in the source file
        # it claims to. salary_se/salary_uk/salary_ca key their output by
        # occupation code ({"occupations": {code: {"title": ..., ...}}});
        # bls_oews predates this package and tracks exactly one occupation
        # (SOC 15-1252) keyed by city instead, so both its code and title
        # checks fall back to substring-matching meta.occupation.
        sid = m.get("source_id")
        national_title = (m.get("national_title") or "").strip()
        if sid:
            if sid not in source_cache:
                path = PROCESSED / f"{sid}.json"
                source_cache[sid] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            src = source_cache[sid]
            occs = (src.get("data") or {}).get("occupations")
            if occs is not None:
                if code not in occs:
                    err(f"{pair}: source_id {sid!r} has no occupation {code!r} in its processed output "
                        "(mapping has drifted from the harvester)")
                else:
                    live_title = str(occs[code].get("title", "")).strip()
                    if live_title and live_title != national_title:
                        err(f"{pair}: national_title {national_title!r} does not match the live "
                            f"title {live_title!r} from {sid!r} — the mapping's evidence rests on "
                            "this title; a mismatch means it was checked against stale text")
            else:
                meta_occ = str((src.get("meta") or {}).get("occupation", ""))
                if code not in meta_occ:
                    err(f"{pair}: source_id {sid!r} has no 'occupations' dict, and its meta.occupation "
                        f"({meta_occ!r}) does not mention {code!r} either — cannot confirm this code "
                        "is what the harvester actually fetched")
                if national_title and national_title not in meta_occ:
                    err(f"{pair}: national_title {national_title!r} does not appear in {sid!r}'s "
                        f"meta.occupation ({meta_occ!r})")

        log(f"{country:7s} {code:10s} {key:14s} {conf:13s}  {m.get('national_title')}")
        log(f"          note: {note}")

    log("")
    log(f"distinct 4-digit ISCO-08 targets referenced: {sorted(four_digit_targets)}")
    primary = [m for m in mappings if m.get("is_primary_target")]
    log(f"primary-target mappings (isco08:2512, the cross-country comparison set): "
        f"{[(m['country'], m['national_code']) for m in primary]}")
    markdowns = [m for m in mappings if m.get("confidence") == "2-digit-only"]
    log(f"mappings marked down to 2-digit-only: {len(markdowns)} of {len(mappings)} "
        f"({[(m['country'], m['national_code']) for m in markdowns]})")

    log("")
    if ERRORS:
        log(f"{len(ERRORS)} ERROR(s):")
        for e in ERRORS:
            log(f"  x {e}")
        log("")
        log("FAILED")
        return 1
    log("PASSED — every mapping carries a valid confidence level, a real note, a well-formed shared "
        "key consistent with its own confidence, and a national_code confirmed present in its source file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
