"""Package 15, Tier 5.2 — near-duplicate detection over postings, measured.

Exact matching on the normalised (title, company, location) key finds 2,258
groups and 2,702 removable rows (5.60%). Near-duplicate matching finds 2,384
clusters and 2,884 removable (5.98%) -- a genuine superset, but only 182 rows
larger. Near-duplicates were EXPECTED to be the larger problem; measured, they
are not, and that expectation is recorded here because it was wrong.

WHAT "REMOVABLE" DOES AND DOES NOT MEAN: it is an upper bound on duplication,
not a count of scrape artifacts. 99.9% of removable rows carry a distinct URL
and 33.6% sit in a cluster spanning more than one posted_at. The largest
cluster is 18 USAJOBS rows with 18 distinct announcement IDs -- a US federal
role genuinely re-announced over time, not one posting seen 18 times. This
collapses a (title, company, location) triple to one row, which is the right
denominator for "how many distinct roles does this panel describe"; it is NOT
evidence that 6% of the harvest is a scraping defect.

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
from _common import PROCESSED, ROOT, log, record_provenance, write_processed  # noqa: E402

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
        # Score the CLUSTERING, not the candidate-pair list, because the
        # clustering is what this script ships and what removes rows.
        #
        # An earlier revision asked "was this exact (i, j) tuple emitted above
        # thr?", which was wrong twice over. First it matched on orientation:
        # candidate_pairs() emits its TF-IDF representative as (key_a_first,
        # key_b_first) with keys sorted alphabetically, so 28 of the 120
        # labelled pairs are emitted only reversed and were counted as misses.
        # Second, and larger, a representative pair carries the score for its
        # whole key group -- so for 38 of the 120 labelled pairs at least one
        # index is not its group's representative, and 15 appear in no
        # orientation at all, yet union-find still puts them in one cluster by
        # transitivity. The pair lookup therefore scored transitive successes
        # as failures and UNDERSTATED recall at loose thresholds.
        #
        # Both defects cancel at the shipped 0.98, where the surviving links
        # are exact-key collisions emitted for every member pair in index
        # order: P=0.958 R=0.719 is unchanged from the previous revision. The
        # rows below 0.95 were wrong and are now corrected.
        lut = {(r["i"], r["j"]): r["same_job"] for r in gt["pairs"]}
        for thr in [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.98]:
            lbl = {}
            for root, members in cluster(post, pairs, thr).items():
                for i in members:
                    lbl[i] = root
            together = {(i, j): lbl.get(i, -1) == lbl.get(j, -2) for i, j in lut}
            tp = sum(1 for k, same in lut.items() if same and together[k])
            fp = sum(1 for k, same in lut.items() if not same and together[k])
            fn = sum(1 for k, same in lut.items() if same and not together[k])
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

    # What "removable" actually is, measured rather than assumed. A cluster
    # collapses a (title, company, location) triple; the labels behind the
    # tuning table see only that triple, so they cannot distinguish one req
    # scraped twice from a role genuinely re-announced or opened N times.
    multi_date = multi_url = 0
    for g in groups.values():
        idx = sorted(g)
        if len({post[i].get("posted_at") for i in idx if post[i].get("posted_at")}) > 1:
            multi_date += len(idx) - 1
        if len({post[i].get("url") or post[i].get("apply_url") for i in idx}) > 1:
            multi_url += len(idx) - 1
    biggest = sorted(max(groups.values(), key=len))
    log(f"  of {near_excess} removable rows, {multi_url} ({100*multi_url/near_excess:.1f}%) carry a "
        f"distinct URL and {multi_date} ({100*multi_date/near_excess:.1f}%) a distinct posted_at")

    keep = set(range(N))
    for g in groups.values():
        for i in sorted(g)[1:]:
            keep.discard(i)

    write_processed("postings_duplicate_clusters",
        {"n_postings": N, "n_clusters": len(groups), "removable_rows": near_excess,
         "removable_pct": round(100 * near_excess / N, 3),
         "keep_indices_count": len(keep),
         "clusters": [sorted(g) for g in groups.values()]},
        meta={"method": "TF-IDF char_wb(3,5) cosine over normalised title|company|location, "
                        "blocked by company, union-find clustering",
              "threshold": thr,
              "blocking_recall_ceiling": "cross-employer duplicates are out of scope by construction",
              "n_oversized_blocks_skipped": len(skipped),
              "evaluation": "data/quality_history/dedupe_eval.json",
              "removable_is_an_upper_bound": {
                  "with_distinct_url": multi_url,
                  "with_distinct_url_pct": round(100 * multi_url / near_excess, 1),
                  "with_distinct_posted_at": multi_date,
                  "with_distinct_posted_at_pct": round(100 * multi_date / near_excess, 1),
                  "largest_cluster_rows": len(biggest),
                  "largest_cluster_employer": post[biggest[0]].get("company"),
                  "largest_cluster_distinct_urls": len({post[i].get("url") or post[i].get("apply_url")
                                                        for i in biggest}),
                  "reading": "these clusters collapse a (title, company, location) triple to one "
                             "distinct ROLE. They are not a count of scraping artifacts: nearly "
                             "every removable row has its own URL, and a third sit in clusters "
                             "spanning several posting dates -- re-announcements and simultaneous "
                             "openings, which no (title, company, location) label can tell apart "
                             "from a true duplicate."},
              "note": "nothing is deleted from postings.json; this records WHICH rows are "
                      "duplicates so a consumer can choose."})

    EVAL.write_text(json.dumps({
        "schema": "package-15 dedupe evaluation v1",
        "n_postings": N,
        "normalised_exact": {"groups": len(ex_groups), "removable": ex_excess,
                             "removable_pct": round(100 * ex_excess / N, 3)},
        "near_duplicate": {"threshold": thr, "clusters": len(groups), "removable": near_excess,
                           "removable_pct": round(100 * near_excess / N, 3)},
        "threshold_tuning": tuning,
        "labelled_pairs": (gt or {}).get("n"),
        "recall_ceilings": {
            "cross_employer": "duplicates posted by two different employers (an agency and the "
                              "employer) are out of scope by construction",
            "oversized_blocks_skipped": skipped,
            "labelled_pairs_not_directly_compared": "15 of the 120 labelled pairs are emitted as no "
                    "candidate pair in either orientation, and 38 involve a posting that is not its "
                    "key group's representative. They are still scored, because the table above "
                    "evaluates cluster co-membership, which is what the script ships.",
            "note": "companies above the distinct-key cap get EXACT-key de-duplication only, not "
                    "near-duplicate matching. boxlunch is one of them, which matters because it "
                    "is the employer used to illustrate duplicates in docs/DATA-FITNESS.md.",
        },
        "pair_label_caveat": "the ground truth labels (title, company, location) triples only. It "
                             "cannot see posted_at or the requisition id, so a re-listing and N "
                             "genuine simultaneous openings are indistinguishable to the labeller "
                             "-- see the posted_at spread reported alongside the clusters.",
    }, indent=1) + "\n", encoding="utf-8")
    record_provenance(
        source_id="postings_duplicate_clusters",
        name="Postings near-duplicate clusters — package 15",
        urls=[],
        license_note="Derived from data/processed/postings.json; adds no new source data.",
        redistribution="derived — index clusters over postings already committed",
        transforms=[
            "Normalised (title | company | location), removing formatting-only tokens but NOT "
            "seniority or location, which distinguish genuinely different vacancies.",
            "Blocked by company, collapsed to distinct normalised keys, then TF-IDF char_wb(3,5) "
            "cosine within each block.",
            f"Threshold {thr} tuned against 120 hand-labelled pairs sampled across the whole "
            "cosine range (data/labels/dedupe_pair_ground_truth.json); the de-duplicator's own "
            "precision and recall are in data/quality_history/dedupe_eval.json.",
            "Union-find clustering. Nothing is deleted from postings.json — this file records "
            "WHICH rows are duplicates so a consumer can choose.",
        ],
        output=f"data/processed/{OUT.stem}.json",
        rows=len(groups),
        coverage=f"{near_excess} removable rows of {N} ({100*near_excess/N:.2f}%)",
        notes="Recall is bounded by company blocking: a cross-employer duplicate (the same "
              "requisition posted by an agency and the employer) is out of scope by construction.",
    )
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
