"""Audits data/occupations.json — the national-code -> ISCO-08 crosswalk — and
implements the cross-country comparison rule package 8 adds on top of it.

This is not a fetcher: the crosswalk is a curated, evidenced judgement call
(there is no single API that hands you "is SSYK 2514 the same job as ISCO-08
2514"), the same way cities.json and countries.json are curated rather than
derived. What this script checks is that the table is internally honest:

  * every mapping carries a confidence level from the table's own vocabulary,
    consistent with its shared_key's DEPTH — 4-digit (high/moderate), 2-digit
    ('2-digit-only'), 1-digit major-group ('major-group-only'), or no
    correspondence at all ('no-isco-correspondence', shared_key "unmapped")
  * every mapping carries a non-trivial note (evidence, not a placeholder)
  * no (country, national_code) pair is silently duplicated or contradicted
  * every real shared_key is well-formed AND appears in the shared_keys
    registry (a well-formed-but-unregistered key such as a typo'd
    isco08:2599 is caught, not just checked for shape)
  * every national_code, AND its national_title, actually match the source
    file it claims to — catching drift if a harvester's occupation codes or
    titles ever change, not just the code

`python scripts/crosswalk.py` prints the full table plus a sample of resolved
country-pair comparisons (gate 8's evidence) and exits non-zero on any
structural problem. `make validate` does not currently call this — it is a
standalone audit, run and its output pasted into the package report, the
same way the chart-integrity audits were in package 6.

THE COMPARISON RULE (package 8, "meet in the middle"): a cross-country
comparison happens at the DEEPEST level BOTH sides support. If one side is
2-digit-only, both sides degrade to 2-digit and the result states which
country forced the degradation. A 4-digit figure must never sit opposite a
2-digit figure as though they were equivalent. See compare() below — package
9 must call this function rather than re-deriving the rule in the UI.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, PROCESSED, log  # noqa: E402

OCC_FILE = DATA / "occupations.json"

# A real key is "isco08:" + 1, 2 or 4 digits (1 = major group, 2 = sub-major
# group, 4 = unit group — ISCO-08 has no 3-digit terminal level relevant
# here). The literal sentinel "unmapped" is the only other legal value,
# reserved for confidence == "no-isco-correspondence".
SHARED_KEY_RE = re.compile(r"^isco08:(\d{1}|\d{2}|\d{4})$")
UNMAPPED = "unmapped"

DEPTH_CONFIDENCE = {
    4: {"high", "moderate"},
    2: {"2-digit-only"},
    1: {"major-group-only"},
}

ERRORS: list[str] = []


def err(msg: str) -> None:
    ERRORS.append(msg)


def depth_of(shared_key: str) -> int | None:
    """4/2/1-digit depth, or None for 'unmapped' (no ISCO-08 correspondence)."""
    if shared_key == UNMAPPED:
        return None
    m = SHARED_KEY_RE.match(shared_key or "")
    return len(m.group(1)) if m else None


def compare(mapping_a: dict, mapping_b: dict) -> dict:
    """The meet-in-the-middle comparison rule. Each argument is one mapping
    dict from data/occupations.json's 'mappings' list (as returned by
    load()'s by_pair index). Returns:
      {"comparable": False, "reason": "..."}                          or
      {"comparable": True, "depth": N, "shared_key": "isco08:...",
       "degraded_by": "<country> forced N->M digits" | None}
    """
    key_a, key_b = mapping_a["shared_key"], mapping_b["shared_key"]
    depth_a, depth_b = depth_of(key_a), depth_of(key_b)
    if depth_a is None or depth_b is None:
        blamed = mapping_a["country"] if depth_a is None else mapping_b["country"]
        return {"comparable": False,
                "reason": f"{blamed} has no ISCO-08 correspondence at all for this occupation"}

    depth = min(depth_a, depth_b)
    truncated_a = key_a.split(":")[1][:depth]
    truncated_b = key_b.split(":")[1][:depth]
    if truncated_a != truncated_b:
        return {"comparable": False,
                "reason": f"even truncated to {depth}-digit the codes disagree: "
                          f"isco08:{truncated_a} (from {mapping_a['country']}'s {key_a}) vs "
                          f"isco08:{truncated_b} (from {mapping_b['country']}'s {key_b})"}

    degraded_by = None
    if depth_a != depth_b:
        deeper_depth = max(depth_a, depth_b)
        forcing_country = mapping_a["country"] if depth_a < depth_b else mapping_b["country"]
        degraded_by = f"{forcing_country} forced {deeper_depth}-digit down to {depth}-digit"

    return {"comparable": True, "depth": depth, "shared_key": f"isco08:{truncated_a}", "degraded_by": degraded_by}


def load() -> tuple[dict, dict[tuple[str, str], dict]]:
    doc = json.loads(OCC_FILE.read_text(encoding="utf-8"))
    by_pair = {(m["country"], m["national_code"]): m for m in doc.get("mappings", [])}
    return doc, by_pair


def main() -> int:
    log("CS Migration Compass — occupation crosswalk audit")
    log("")

    if not OCC_FILE.exists():
        err("data/occupations.json is missing")
        log(f"{len(ERRORS)} ERROR(s)"); log("  x " + ERRORS[0])
        return 1

    doc, by_pair = load()
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

    header = f"{'country':7s} {'code':10s} {'shared_key':14s} {'conf':21s}  title"
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
        depth = depth_of(key)
        if key != UNMAPPED and not SHARED_KEY_RE.match(key):
            err(f"{pair}: shared_key {key!r} is not a well-formed isco08:N / NN / NNNN key or "
                f"the {UNMAPPED!r} sentinel")
        elif key == UNMAPPED:
            if conf != "no-isco-correspondence":
                err(f"{pair}: shared_key is the {UNMAPPED!r} sentinel but confidence is {conf!r}, "
                    "not 'no-isco-correspondence'")
        else:
            if key not in registry:
                err(f"{pair}: shared_key {key!r} is not in the shared_keys registry — a key that "
                    "is well-formed but unregistered is a typo, not a deliberate mapping")
            if depth == 4:
                four_digit_targets.add(key)
            expected_confs = DEPTH_CONFIDENCE.get(depth, set())
            if conf not in expected_confs:
                err(f"{pair}: shared_key {key!r} is {depth}-digit but confidence is {conf!r}, "
                    f"expected one of {sorted(expected_confs)}")

        # Cross-check the code AND its title actually exist in the source file
        # it claims to. salary_se/salary_uk/salary_ca/... key their output by
        # occupation code ({"occupations": {code: {"title": ..., ...}}});
        # bls_oews predates this package and tracks exactly one occupation
        # (SOC 15-1252) keyed by city instead, so both its code and title
        # checks fall back to substring-matching meta.occupation. Sources
        # with no live occupation data (salary_de does not exist; salary_it
        # has an empty occupations dict) are skipped rather than failed —
        # there is nothing for a "no-series" mapping to drift from.
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

        log(f"{country:7s} {code:10s} {key:14s} {conf:21s}  {m.get('national_title')}")
        log(f"          note: {note}")

    log("")
    log(f"distinct 4-digit ISCO-08 targets referenced: {sorted(four_digit_targets)}")
    primary = [m for m in mappings if m.get("is_primary_target")]
    log(f"primary-target mappings (isco08:2512, the cross-country comparison set): "
        f"{[(m['country'], m['national_code']) for m in primary]}")
    for tier in ("2-digit-only", "major-group-only", "no-isco-correspondence"):
        hits = [m for m in mappings if m.get("confidence") == tier]
        log(f"mappings at {tier!r}: {len(hits)} of {len(mappings)} "
            f"({[(m['country'], m['national_code']) for m in hits]})")

    # ---- gate 7 evidence: the comparison rule, exercised on real pairs ----
    log("")
    log("=== comparison rule ('meet in the middle') on sample country pairs ===")
    sample_pairs = [
        (("SE", "2512"), ("GB", "2134")),          # 4-digit vs 4-digit, exact
        (("SE", "2512"), ("DK", "2512")),          # 4-digit vs 4-digit, exact
        (("SE", "2512"), ("US", "15-1252")),       # 4-digit vs 4-digit, exact
        (("SE", "2512"), ("CA", "21232")),         # 4-digit(high) vs 4-digit(moderate, split)
        (("SE", "2512"), ("ES", "it_professionals")),  # 4-digit vs 2-digit -> degrades to 2
        (("SE", "2512"), ("IE", "soc1:2")),        # 4-digit vs 1-digit -> degrades to 1
        (("SE", "2512"), ("NL", "0811")),          # 4-digit vs unmapped -> refused
        (("GB", "2137"), ("NO", "2515")) if ("NO", "2515") in by_pair else (("GB", "2137"), ("SE", "2515")),
    ]
    for (ca, na), (cb, nb) in sample_pairs:
        ma, mb = by_pair.get((ca, na)), by_pair.get((cb, nb))
        if ma is None or mb is None:
            log(f"  {ca} {na}  vs  {cb} {nb}: SKIPPED (mapping not found — check the sample list)")
            continue
        result = compare(ma, mb)
        if result["comparable"]:
            log(f"  {ca} {na} ({ma['shared_key']})  vs  {cb} {nb} ({mb['shared_key']}): "
                f"comparable at {result['depth']}-digit ({result['shared_key']})"
                + (f" — {result['degraded_by']}" if result["degraded_by"] else ""))
        else:
            log(f"  {ca} {na} ({ma['shared_key']})  vs  {cb} {nb} ({mb['shared_key']}): "
                f"NOT COMPARABLE — {result['reason']}")

    log("")
    if ERRORS:
        log(f"{len(ERRORS)} ERROR(s):")
        for e in ERRORS:
            log(f"  x {e}")
        log("")
        log("FAILED")
        return 1
    log("PASSED — every mapping carries a valid confidence level, a real note, a well-formed shared "
        "key consistent with its own confidence/depth, and a national_code confirmed present in its "
        "source file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
