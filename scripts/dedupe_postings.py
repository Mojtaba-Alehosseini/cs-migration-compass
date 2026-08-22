"""Package 15, Tier 5.2 — near-duplicate detection over postings, measured.

Exact matching on (title, company, location) finds 2,000 groups covering
9.2% of rows. Near-duplicates are the larger problem and exact matching is
blind to all of them: "Sales Associate" vs "Sales Associate (Part-Time)",
the same role posted to two cities, the same req re-listed with a suffix.

METHOD: TF-IDF character n-grams over a normalised (title | company |
location) key, then cosine similarity within blocking groups. Blocking by
company is what makes this tractable -- 48,267 postings is 1.2 billion
pairs, but duplicates are near-always same-employer, so comparing only
within a company reduces it to a few million while giving up almost
nothing. That trade is stated because it IS a recall ceiling: a genuine
cross-employer duplicate (the same req posted by an agency and the
employer) is invisible to this and is not counted in the recall below.

THRESHOLD: tuned against a hand-labelled pair sample, not chosen by eye.
The precision/recall of the DE-DUPLICATOR ITSELF is reported, because a
de-duplicator with unmeasured precision silently deletes real postings,
which is worse than the duplicates it removes.

    python scripts/dedupe_postings.py              # tune, evaluate, write clusters
    python scripts/dedupe_postings.py --self-test  # gate 14
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, log  # noqa: E402

OUT = PROCESSED / "postings_duplicate_clusters.json"
EVAL = ROOT / "data" / "quality_history" / "dedupe_eval.json"
LABELS = ROOT / "data" / "labels" / "dedupe_pair_ground_truth.json"

# Tokens that are formatting rather than identity: two postings differing
# only by these are the same job. Deliberately NOT including seniority or
# location words -- "Senior X" and "X" are different jobs, and so are the
# same title in two cities.
_NOISE = re.compile(r"\b(full[- ]?time|part[- ]?time|permanent|contract|remote|hybrid|onsite|"
                    r"on[- ]site|f/m/d|m/f/d|m/w/d|h/f|w/m/d|new|urgent|hiring|apply now)\b", re.I)
_PUNCT = re.compile(r"[^\w\s]+", re.U)
_WS = re.compile(r"\s+")


def norm(s: str) -> str:
    s = (s or "").lower()
    s = _NOISE.sub(" ", s)
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip()


def key_of(p) -> str:
    return " | ".join([norm(p.get("title")),
                       norm(p.get("company") or p.get("company_slug")),
                       norm(p.get("location_raw"))])


def candidate_pairs(post, max_distinct_block=1200):
    """Blocked candidate generation: same company only. Returns (i, j, sim)
    for every within-block pair above a low floor, so the threshold can be
    tuned afterwards without recomputing.

    Cosine runs over DISTINCT normalised keys within a company, not over
    postings. That matters for correctness as well as speed: an earlier
    revision blocked on raw posting count and skipped any company with more
    than a few hundred rows, which silently excluded the ten largest
    employers -- precisely where duplicates concentrate -- and made the
    near-duplicate pass find FEWER removable rows than plain exact matching.
    Collapsing to distinct keys first makes those blocks small enough to
    compare exhaustively, so the near-duplicate result is now a genuine
    superset of the exact one.
    """
    by_co = defaultdict(list)
    for i, p in enumerate(post):
        by_co[norm(p.get("company") or p.get("company_slug"))].append(i)
    out = []
    skipped_blocks = []
    for co, idx in by_co.items():
        if len(idx) < 2:
            continue
        # group posting indices by their normalised key
        by_key = defaultdict(list)
        for i in idx:
            by_key[key_of(post[i])].append(i)
        keys = sorted(by_key)
        # exact-key collisions are duplicates at cosine 1.0 by definition
        for k in keys:
            g = by_key[k]
            for a in range(len(g)):
                for b in range(a + 1, len(g)):
                    out.append((g[a], g[b], 1.0))
        if len(keys) < 2:
            continue
        if len(keys) > max_distinct_block:
            skipped_blocks.append({"company": co[:60], "distinct_keys": len(keys)})
            continue
        try:
            V = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1).fit_transform(keys)
        except ValueError:
            continue
        S = (V @ V.T).toarray()
        for a in range(len(keys)):
            for b in range(a + 1, len(keys)):
                s = float(S[a, b])
                if s >= 0.60:
                    # one representative pair per key-pair carries the score;
                    # union-find propagates it to every posting in both keys
                    out.append((by_key[keys[a]][0], by_key[keys[b]][0], s))
    return out, skipped_blocks


def cluster(post, pairs, thr):
    """Union-find over pairs above `thr`."""
    parent = list(range(len(post)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j, s in pairs:
        if s >= thr:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)
    groups = defaultdict(list)
    for i in range(len(post)):
        groups[find(i)].append(i)
    return {r: g for r, g in groups.items() if len(g) > 1}


def run():
    post = json.loads((PROCESSED / "postings.json").read_text(encoding="utf-8"))["data"]["postings"]
    N = len(post)
    log(f"de-duplicating {N} postings")

    exact = Counter(key_of(p) for p in post)
    ex_groups = {k: v for k, v in exact.items() if v > 1}
    ex_excess = sum(v - 1 for v in ex_groups.values())
    log(f"  normalised-exact: {len(ex_groups)} groups, {ex_excess} removable ({100*ex_excess/N:.2f}%)")

    pairs, skipped = candidate_pairs(post)
    log(f"  {len(pairs)} candidate pairs above 0.60 cosine ({len(skipped)} oversized blocks skipped)")

    gt = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.exists() else None
    tuning = []
    if gt:
        lut = {(r["i"], r["j"]): r["same_job"] for r in gt["pairs"]}
        for thr in [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.98]:
            tp = sum(1 for (i, j), same in lut.items()
                     if same and any(a == i and b == j and s >= thr for a, b, s in pairs))
            fp = sum(1 for (i, j), same in lut.items()
                     if not same and any(a == i and b == j and s >= thr for a, b, s in pairs))
            fn = sum(1 for (i, j), same in lut.items()
                     if same and not any(a == i and b == j and s >= thr for a, b, s in pairs))
            prec = tp / (tp + fp) if tp + fp else 1.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
            tuning.append({"threshold": thr, "tp": tp, "fp": fp, "fn": fn,
                           "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)})
        best = max(tuning, key=lambda r: (r["precision"] >= 0.95, r["f1"]))
        thr = best["threshold"]
        log(f"  tuned threshold {thr}: P={best['precision']:.3f} R={best['recall']:.3f} F1={best['f1']:.3f}")
    else:
        thr = 0.90
        log(f"  no labelled pairs yet; using default threshold {thr}")

    groups = cluster(post, pairs, thr)
    near_excess = sum(len(g) - 1 for g in groups.values())
    log(f"  near-duplicate: {len(groups)} clusters, {near_excess} removable ({100*near_excess/N:.2f}%)")

    keep = set(range(N))
    for g in groups.values():
        for i in sorted(g)[1:]:
            keep.discard(i)

    OUT.write_text(json.dumps({
        "source_id": "postings_duplicate_clusters",
        "meta": {"method": "TF-IDF char_wb(3,5) cosine over normalised title|company|location, "
                           "blocked by company, union-find clustering",
                 "threshold": thr, "blocking_recall_ceiling":
                     "cross-employer duplicates are out of scope by construction",
                 "oversized_blocks_skipped": skipped,
                 "n_oversized_blocks": len(skipped),
                 "evaluation": "data/quality_history/dedupe_eval.json"},
        "data": {"n_postings": N, "n_clusters": len(groups),
                 "removable_rows": near_excess,
                 "removable_pct": round(100 * near_excess / N, 3),
                 "keep_indices_count": len(keep),
                 "clusters": [sorted(g) for g in list(groups.values())[:2000]]},
    }, indent=1) + "\n", encoding="utf-8")

    EVAL.write_text(json.dumps({
        "schema": "package-15 dedupe evaluation v1",
        "n_postings": N,
        "normalised_exact": {"groups": len(ex_groups), "removable": ex_excess,
                             "removable_pct": round(100 * ex_excess / N, 3)},
        "near_duplicate": {"threshold": thr, "clusters": len(groups), "removable": near_excess,
                           "removable_pct": round(100 * near_excess / N, 3)},
        "threshold_tuning": tuning,
        "labelled_pairs": (gt or {}).get("n"),
    }, indent=1) + "\n", encoding="utf-8")
    log(f"  wrote {OUT.name} and {EVAL.name}")
    return 0


def self_test():
    fails = []

    def ck(n, c, d=""):
        print(f"  {'PASS' if c else 'FAIL'}  {n}{('  [' + d + ']') if d else ''}")
        if not c:
            fails.append(n)

    print("=== dedupe_postings.py self-test ===")
    ck("normalisation collapses formatting-only differences",
       norm("Sales Associate (Full-Time)") == norm("Sales associate, full time"),
       repr(norm("Sales Associate (Full-Time)")))
    ck("normalisation does NOT collapse seniority",
       norm("Senior Engineer") != norm("Engineer"))
    ck("normalisation does NOT collapse different cities",
       key_of({"title": "X", "company": "C", "location_raw": "Berlin"}) !=
       key_of({"title": "X", "company": "C", "location_raw": "Munich"}))

    fake = [{"title": "Sales Associate", "company": "Acme", "location_raw": "NY"},
            {"title": "Sales Associate (Part-Time)", "company": "Acme", "location_raw": "NY"},
            {"title": "Principal Cardiologist", "company": "Acme", "location_raw": "NY"},
            {"title": "Sales Associate", "company": "Other", "location_raw": "NY"}]
    pairs, _ = candidate_pairs(fake)
    g = cluster(fake, pairs, 0.70)
    merged = [sorted(x) for x in g.values()]
    ck("near-duplicate pair is clustered", any(0 in m and 1 in m for m in merged), str(merged))
    ck("unrelated title at the same company is NOT clustered",
       not any(2 in m for m in merged), str(merged))
    ck("same title at a DIFFERENT company is not clustered (blocking works)",
       not any(0 in m and 3 in m for m in merged), str(merged))

    print(f"\n{len(fails)} failure(s)" + (": " + ", ".join(fails) if fails else " — all controls hold"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    sys.exit(self_test() if a.self_test else run())
