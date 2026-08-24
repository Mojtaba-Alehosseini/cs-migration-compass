"""Package 18, Tier 1 — re-key the de-duplication ground truth to a stable identity.

WHY. `dedupe_postings.py` verifies its 120 labelled pairs against the corpus before
it trusts any threshold, and that guard is right: the de-duplicator removes rows, and
package 15 measured its precision precisely so it could not do so unmeasured. But the
labels are keyed by ARRAY INDEX (`"i": 15125`), so a harvest that adds, removes or
reorders one row invalidates all 240 endpoints at once. Verified live on workflow run
32751240590 against a fresh 48,708-row corpus: 240 of 240 mismatched, and the weekly
refresh has not shipped since. The guard did not detect drift; it made the
de-duplicator unrunnable in the pipeline it belongs to.

WHAT THE KEY IS, and why it is not just the id. Posting `id` is nearly unique --
48,264 distinct ids across 48,267 rows -- but three ids are carried by two rows each,
and ONE LABELLED PAIR SITS ON EXACTLY THAT CASE. Pair 115 is rows 45826 and 46057,
both `usajobs:464770500`, byte-identical down to the URL and posted_at, labelled
`same_job: true` at cosine 1.0. The collision IS the duplicate the label describes.
Keying on the id alone would resolve both endpoints to the same row, turning a
labelled pair into a self-pair that is trivially "clustered together" at every
threshold -- a false true-positive that no threshold could ever fail. So the key is
(id, occurrence), where occurrence is the 0-based ordinal of the row among rows
sharing that id, in corpus order. For 239 of 240 endpoints the occurrence is 0.

WHAT THE DISPLAY STRING IS FOR. It stays, and it is NOT a key: the 240 endpoints use
219 distinct display strings and 43 of those match more than one row, because
near-duplicates share text -- which is the very thing these labels describe. It is
corroboration. An id that resolves to a row whose text has changed is a different
posting reusing an id, and the runtime guard treats that as fatal.

    python scripts/rekey_dedupe_labels.py           # write the re-keyed file
    python scripts/rekey_dedupe_labels.py --check   # resolve and report, write nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, log  # noqa: E402

LABELS = ROOT / "data" / "labels" / "dedupe_pair_ground_truth.json"
SCHEMA_V2 = "package-18 dedupe pair ground truth v2 (keyed by (id, occurrence))"


def display_of(r: dict) -> str:
    """The string the labels were built from. Company first, then the slug --
    reversing that order makes 118 of 240 endpoints look wrong while nothing is,
    which is how the original check was first written."""
    return (f"{r.get('title')} @ {r.get('company') or r.get('company_slug')} "
            f"/ {r.get('location_raw')}")


def occurrence_map(post: list[dict]) -> dict[str, list[int]]:
    """id -> the corpus indices carrying it, in corpus order."""
    m: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(post):
        pid = row.get("id")
        if pid is not None:
            m[pid].append(idx)
    return m


def rekey(post: list[dict], gt: dict) -> tuple[list[dict], list[dict], dict]:
    """Resolve every labelled endpoint to (id, occurrence). Returns
    (pairs_kept, pairs_dropped, stats). Nothing is written here."""
    by_id = occurrence_map(post)
    where = {}                                   # corpus index -> (id, occurrence)
    for pid, idxs in by_id.items():
        for occ, idx in enumerate(idxs):
            where[idx] = (pid, occ)

    kept, dropped = [], []
    n_on_collision = 0
    for r in gt["pairs"]:
        out = dict(r)
        problems = []
        for side, idx, stored in (("a", r["i"], r.get("a")), ("b", r["j"], r.get("b"))):
            if not (0 <= idx < len(post)):
                problems.append(f"{side}: index {idx} out of range"); continue
            row = post[idx]
            if idx not in where:
                problems.append(f"{side}: row {idx} has no id"); continue
            pid, occ = where[idx]
            if len(by_id[pid]) > 1:
                n_on_collision += 1
            if stored is not None and display_of(row) != stored:
                problems.append(f"{side}: text changed at index {idx} "
                                f"({stored!r} -> {display_of(row)!r})")
                continue
            out[f"id_{side}"] = pid
            out[f"occ_{side}"] = occ
        if problems or "id_a" not in out or "id_b" not in out:
            out["_why_dropped"] = problems or ["one endpoint did not resolve"]
            dropped.append(out)
        else:
            kept.append(out)

    stats = {
        "corpus_rows": len(post),
        "distinct_ids": len(by_id),
        "ids_carried_by_more_than_one_row": sum(1 for v in by_id.values() if len(v) > 1),
        "pairs_in": len(gt["pairs"]),
        "pairs_rekeyed": len(kept),
        "pairs_dropped": len(dropped),
        "endpoints_on_a_colliding_id": n_on_collision,
    }
    return kept, dropped, stats


def run(check_only: bool) -> int:
    post = json.loads((PROCESSED / "postings.json").read_text(encoding="utf-8"))["data"]["postings"]
    gt = json.loads(LABELS.read_text(encoding="utf-8"))
    kept, dropped, stats = rekey(post, gt)

    log(f"re-keying {stats['pairs_in']} labelled pairs against {stats['corpus_rows']:,} rows")
    log(f"  distinct ids {stats['distinct_ids']:,}; "
        f"{stats['ids_carried_by_more_than_one_row']} id(s) carried by more than one row")
    log(f"  labelled endpoints landing on a colliding id: "
        f"{stats['endpoints_on_a_colliding_id']}"
        + ("  (disambiguated by occurrence ordinal)" if stats["endpoints_on_a_colliding_id"]
           else "  (none -- checked, not assumed)"))
    for d in dropped:
        log(f"  DROPPED pair k={d['k']}: {'; '.join(d['_why_dropped'])}")
    log(f"  re-keyed {stats['pairs_rekeyed']} of {stats['pairs_in']}")

    # A partial file is worse than none: the tuning would silently measure a
    # different sample than the one the threshold was chosen on.
    if stats["pairs_rekeyed"] != stats["pairs_in"]:
        log(f"  REFUSING to write: {stats['pairs_dropped']} pair(s) did not resolve. "
            f"Re-key from a corpus where every label is still valid, or re-label.")
        return 2

    if check_only:
        log("  --check: resolved cleanly, nothing written")
        return 0

    out = dict(gt)
    out["schema"] = SCHEMA_V2
    out["key"] = (
        "Each endpoint is identified by (id_a, occ_a) and (id_b, occ_b): the posting's own id, "
        "and the 0-based ordinal of the row among rows sharing that id, in corpus order. `i`/`j` "
        "are the ARRAY INDICES the pair was originally labelled at and are kept as provenance "
        "only -- they are not resolved against and go stale the moment the corpus changes, which "
        "is the defect this re-key exists to fix. `a`/`b` are the display strings the labels were "
        "made from; they are corroboration, never a key (219 distinct strings across 240 "
        "endpoints, 43 of them matching more than one row -- near-duplicates share text, which is "
        "what these labels are about).")
    out["rekeyed"] = {
        "by": "scripts/rekey_dedupe_labels.py",
        "against_corpus_rows": stats["corpus_rows"],
        "endpoints_resolved": 2 * stats["pairs_rekeyed"],
        "endpoints_on_a_colliding_id": stats["endpoints_on_a_colliding_id"],
        "collision_note": (
            "pair 115 is rows 45826 and 46057, both id usajobs:464770500, byte-identical and "
            "labelled same_job=true at cosine 1.0 -- the id collision IS the duplicate the label "
            "describes, so the two endpoints are occurrence 0 and occurrence 1 of that id rather "
            "than one row twice."),
    }
    out["pairs"] = kept
    LABELS.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"  wrote {LABELS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="resolve and report without writing")
    a = ap.parse_args()
    raise SystemExit(run(a.check))
