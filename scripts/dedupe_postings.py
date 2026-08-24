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

# The cosine bands the 120 labels were stratified across, 24 per band. They are
# named here rather than inside run() because the survivor floor is expressed
# per band, and the floor is the reason the tuning can be trusted at all.
GT_BANDS = [(0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 0.98), (0.98, 1.0001)]


def _band_of(score: float) -> int:
    for b, (lo, hi) in enumerate(GT_BANDS):
        if lo <= score < hi:
            return b
    return len(GT_BANDS) - 1


# HOW MANY LABELLED PAIRS MUST SURVIVE A HARVEST, and why the floor is per band
# rather than a total. Package 18, measured on this corpus, not chosen by feel.
#
# A threshold tuned on 120 pairs does not become untrustworthy at 118. It does
# become untrustworthy when a whole region of the decision space empties, and
# THAT CAN HAPPEN AT A VERY HIGH SURVIVAL RATE. Measured: drop the [0.98,1.00]
# band and 96 of 120 pairs remain -- 80% -- and the tuning reports
# P=1.000 R=0.000, because 23 of the 32 same_job=True pairs live in that one
# band. A total-count floor cannot see that, and would have passed it.
#
# Attrition constrained to keep at least this many in EVERY band, 400 trials
# each, scored against the same clusterings:
#
#     per band   n range   tuned threshold moved   precision sd
#         20      102-119           0.0%              0.012
#         16       84-118           0.0%              0.018
#         12       71-115           0.0%              0.025
#         10       64-114           0.5%              0.030
#          8       49-110           1.2%              0.036
#          4       36-106           4.0%              0.057
#
# 12 -- half the design of 24 -- is the smallest floor at which the tuned
# threshold did not move once in 400 trials. Below it the selection starts to
# wobble, and uniform attrition to a comparable total (n=60) already moves it
# 1.8% of the time with a precision floor of 0.536.
MIN_PAIRS_PER_BAND = 12

# And both classes must survive in usable numbers: precision needs negatives,
# recall needs positives. The sample is 32 True against 88 False, so a survivor
# set can satisfy a count floor and still be one-sided -- all-True scores
# P=1.000 R=1.000 at threshold 0.70 with nothing to catch a false positive,
# and all-False scores P=0.000. Both are meaningless and both are reachable.
MIN_PAIRS_PER_CLASS = 12

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



def display_of(r: dict) -> str:
    """The string the labels were built from. Company first, THEN the slug --
    reversing that order makes 118 of 240 endpoints look wrong while nothing
    is, which is how this check was first written."""
    return (f"{r.get('title')} @ {r.get('company') or r.get('company_slug')} "
            f"/ {r.get('location_raw')}")


def resolve_labels(post: list[dict], gt: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Resolve every labelled pair against THIS corpus by (id, occurrence).

    Returns (survivors, expired, reused). A survivor carries `_i`/`_j`, its
    indices in the corpus passed in -- never the `i`/`j` it was labelled at.

    The labels used to store only ARRAY INDICES, and a re-harvest that added,
    removed or reordered one row moved every one of them at once. That was
    correctly detected -- a mismatch was fatal -- but the detection made this
    script unrunnable in the pipeline it belongs to: workflow run 32751240590
    against a fresh 48,708-row corpus reported 240 of 240 endpoints mismatched,
    and the weekly refresh had not shipped since 16 August. A guard that fires
    on every ordinary harvest is not measuring drift, it is measuring that time
    passed. Package 18 re-keyed the labels; `i`/`j` stay in the file as
    provenance and are deliberately not read here.

    Three outcomes, and the difference between them is the whole point:
      * an endpoint's id is GONE     -> that posting expired; the pair does not
                                        survive. Ordinary churn.
      * an id resolves, text CHANGED -> a different posting is reusing an id.
                                        The key is lying. The caller treats this
                                        as fatal -- it is the case the original
                                        guard was built for.
      * too few survivors            -> the caller refuses. See floor_verdict().
    """
    by_id: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(post):
        if row.get("id") is not None:
            by_id[row["id"]].append(idx)

    survivors, expired, reused = [], [], []
    for r in gt["pairs"]:
        resolved, lost = {}, False
        for side in ("a", "b"):
            pid, occ = r.get(f"id_{side}"), r.get(f"occ_{side}", 0)
            idxs = by_id.get(pid, [])
            if occ >= len(idxs):
                expired.append({"k": r.get("k"), "side": side, "id": pid, "occurrence": occ,
                                "rows_with_that_id_now": len(idxs)})
                lost = True
                continue
            idx = idxs[occ]
            stored = r.get(side)
            if stored is not None and display_of(post[idx]) != stored:
                reused.append({"k": r.get("k"), "side": side, "id": pid, "index_now": idx,
                               "labelled_as": stored, "now": display_of(post[idx])})
                lost = True
                continue
            resolved[side] = idx
        if not lost:
            survivors.append({**r, "_i": resolved["a"], "_j": resolved["b"]})
    return survivors, expired, reused


def floor_verdict(survivors: list[dict]) -> tuple[bool, list[str], dict]:
    """Is this survivor set enough to tune a threshold on? Returns
    (ok, reasons_it_is_not, stats). See MIN_PAIRS_PER_BAND for the measurement
    behind the numbers."""
    n_band = Counter(_band_of(r["cosine"]) for r in survivors)
    n_true = sum(1 for r in survivors if r["same_job"])
    n_false = len(survivors) - n_true
    short = {b: n_band[b] for b in range(len(GT_BANDS)) if n_band[b] < MIN_PAIRS_PER_BAND}
    reasons = []
    if short:
        reasons.append(f"cosine band(s) below {MIN_PAIRS_PER_BAND}: {short}")
    if n_true < MIN_PAIRS_PER_CLASS:
        reasons.append(f"only {n_true} same_job=True pair(s), need {MIN_PAIRS_PER_CLASS}")
    if n_false < MIN_PAIRS_PER_CLASS:
        reasons.append(f"only {n_false} same_job=False pair(s), need {MIN_PAIRS_PER_CLASS}")
    stats = {"n_surviving": len(survivors),
             "per_band": {str(b): n_band[b] for b in range(len(GT_BANDS))},
             "same_job_true": n_true, "same_job_false": n_false}
    return (not reasons), reasons, stats


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

    # The labels are resolved by (id, occurrence), NOT by array position.
    #
    # They used to store only posting INDICES, and a re-harvest that adds,
    # removes or reorders one row moved every one of them at once. That was
    # correctly detected -- a mismatch was fatal -- but the detection made this
    # script unrunnable in the pipeline it belongs to: workflow run 32751240590
    # against a fresh 48,708-row corpus reported 240 of 240 endpoints mismatched
    # and the weekly refresh had not shipped since 16 August. A guard that fires
    # on every ordinary harvest is not measuring drift, it is measuring that
    # time passed. Package 18 re-keyed the labels; `i`/`j` remain in the file as
    # provenance and are deliberately not read here.
    #
    # Three outcomes, and the difference between them is the whole point:
    #   * an endpoint's id is GONE      -> that posting expired. The pair does
    #                                      not survive. Ordinary churn.
    #   * an id resolves, text CHANGED  -> a different posting is reusing an id.
    #                                      The key is lying, so this stays FATAL,
    #                                      which is the case the original guard
    #                                      was built for.
    #   * too few survivors             -> FATAL. See the floor below.
    label_check = None
    survivors: list[dict] = []
    if gt:
        survivors, expired, reused = resolve_labels(post, gt)

        # A resolved id whose content changed means the identity itself is
        # unreliable, and every other resolution in this run is then suspect.
        if reused:
            log(f"  FATAL: {len(reused)} labelled endpoint(s) resolved by id to a row whose "
                f"content has changed -- a different posting is reusing an id, so the key cannot "
                f"be trusted. Re-label before trusting any threshold. First: {reused[0]}")
            raise SystemExit(2)

        ok, reasons, stats = floor_verdict(survivors)
        label_check = {
            "keyed_by": "(id, occurrence)",
            "n_pairs_labelled": len(gt["pairs"]),
            "n_pairs_surviving": stats["n_surviving"],
            "n_expired_endpoints": len(expired),
            "n_id_reuse": len(reused),
            "corpus_size_now": N,
            "per_band_surviving": stats["per_band"],
            "same_job_true": stats["same_job_true"],
            "same_job_false": stats["same_job_false"],
            "floor": {"per_band": MIN_PAIRS_PER_BAND, "per_class": MIN_PAIRS_PER_CLASS},
            "expired_examples": expired[:5],
            "valid": ok,
        }
        log(f"  labels resolved by (id, occurrence): {stats['n_surviving']} of {len(gt['pairs'])} "
            f"pairs survive this corpus ({len(expired)} endpoint(s) expired)")
        log(f"    per band {stats['per_band']} · same_job True={stats['same_job_true']} "
            f"False={stats['same_job_false']}")
        if not ok:
            log(f"  FATAL: too few labelled pairs survive to tune a threshold on -- "
                f"{'; '.join(reasons)}. Re-label before trusting any threshold.")
            raise SystemExit(2)

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
        # The 120 labelled pairs are STRATIFIED -- 24 drawn from each of five
        # cosine bands -- so the threshold is tuned where the decision is hard.
        # Pooling them and dividing gives precision and recall ON THAT SAMPLE,
        # which is not the population figure: the bands are oversampled very
        # unevenly, [0.60,0.70) by 544x against [0.90,0.98) by 110x. Both are
        # reported. The sample figure is what the threshold was chosen on; the
        # reweighted one is what the de-duplicator achieves over all candidate
        # pairs, and it is the lower of the two on recall.
        # Everything below is computed on the SURVIVORS, resolved by (id,
        # occurrence) above, and `_i`/`_j` are their indices in THIS corpus --
        # never the `i`/`j` the pair was originally labelled at. The reweighting
        # divides by the surviving per-band counts, not the design's 24, so a
        # band that lost pairs has each remaining pair carry proportionally more
        # weight. That is correct, and it is also why the floor is per band: the
        # smaller smp_n[b] gets, the more a single surviving pair moves the
        # population estimate.
        BANDS = GT_BANDS
        _band = _band_of

        pop_n = Counter(_band(s) for _, _, s in pairs)
        smp_n = Counter(_band(r["cosine"]) for r in survivors)
        wgt = {b: (pop_n[b] / smp_n[b] if smp_n[b] else 0.0) for b in range(len(BANDS))}
        band_of = {(r["_i"], r["_j"]): _band(r["cosine"]) for r in survivors}

        lut = {(r["_i"], r["_j"]): r["same_job"] for r in survivors}
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
            wtp = sum(wgt[band_of[k]] for k, s in lut.items() if s and together[k])
            wfp = sum(wgt[band_of[k]] for k, s in lut.items() if not s and together[k])
            wfn = sum(wgt[band_of[k]] for k, s in lut.items() if s and not together[k])
            wprec = wtp / (wtp + wfp) if wtp + wfp else 1.0
            wrec = wtp / (wtp + wfn) if wtp + wfn else 0.0
            tuning.append({"threshold": thr, "tp": tp, "fp": fp, "fn": fn,
                           "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
                           "precision_reweighted": round(wprec, 4),
                           "recall_reweighted": round(wrec, 4),
                           "f1_reweighted": round(2 * wprec * wrec / (wprec + wrec), 4)
                           if wprec + wrec else 0.0})
        best = max(tuning, key=lambda r: (r["precision"] >= 0.95, r["f1"]))
        thr = best["threshold"]
        # Every reported figure names the n it was computed on. A precision
        # quoted without its sample size is the same claim whether it rests on
        # 120 pairs or 61, and after a harvest it will not rest on 120.
        log(f"  tuned threshold {thr}: P={best['precision']:.3f} "
            f"R={best['recall']:.3f} F1={best['f1']:.3f}  (n={len(survivors)} labelled pairs)")
        log(f"    reweighted to the candidate-pair population: "
            f"P={best['precision_reweighted']:.3f} R={best['recall_reweighted']:.3f} "
            f"F1={best['f1_reweighted']:.3f}  (n={len(survivors)})")
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
        # The n every figure in threshold_tuning rests on. It is a top-level
        # field rather than a footnote because after a harvest it is no longer
        # 120, and a precision quoted without it is the same sentence whether it
        # rests on 120 pairs or 61.
        "tuned_on_n_pairs": len(survivors) if gt else 0,
        "tuned_on": (
            f"{len(survivors)} labelled pairs surviving this corpus of "
            f"{(gt or {}).get('n', 0)} labelled" if gt else "no labelled pairs"),
        "stratified_sample_disclosure": (
            f"the labelled pairs are 24 per cosine band by design (120 in total); "
            f"{len(survivors) if gt else 0} of them survive THIS corpus and every figure in "
            "threshold_tuning is computed on those. They are not a random sample of candidate "
            "pairs. 'precision'/'recall' are the figures ON THAT SAMPLE and are what the "
            "threshold was tuned on. '*_reweighted' rescales each labelled pair by its band's "
            "population/sample ratio and estimates what the de-duplicator achieves over all "
            "candidate pairs. At the shipped threshold precision is identical -- every true and "
            "false positive falls in the top band -- but recall is LOWER reweighted, because the "
            "misses sit in bands the sample deliberately over-represents. Quote the reweighted "
            "recall for the de-duplicator's real behaviour."),
        "labelled_pairs": (gt or {}).get("n"),
        "label_corpus_integrity": label_check,
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
            # The n is derived, not written down. This string ships to the site
            # in provenance.json, and a hardcoded "120" would have been wrong
            # the first week a labelled posting expired.
            f"Threshold {thr} tuned against {len(survivors)} hand-labelled pairs, stratified 24 "
            f"per cosine band"
            + (f" ({(gt or {}).get('n', 0)} labelled in total; the rest have left the corpus "
               f"since labelling)" if gt and len(survivors) != gt.get("n") else "")
            + " — data/labels/dedupe_pair_ground_truth.json; the de-duplicator's own precision "
              "and recall, with the n they were computed on, are in "
              "data/quality_history/dedupe_eval.json.",
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

    # THE LABEL/CORPUS CHECK, exercised through resolve_labels() and
    # floor_verdict() themselves -- not through a copy of their logic.
    #
    # The previous version of this section reimplemented the index comparison
    # inline and asserted it fired when a row was prepended. It therefore tested
    # a local copy rather than the shipped guard, and when package 18 re-keyed
    # the labels the two assertions went on passing while asserting the exact
    # behaviour the re-key removed. A test that reimplements the thing it tests
    # cannot notice the thing it tests changing.
    def _row(i, t, c, loc):
        return {"id": i, "title": t, "company": c, "location_raw": loc}

    corpus = [_row("p1", "Software Engineer", "Acme", "NY"),
              _row("p2", "Nurse Practitioner", "Mercy", "LA")]
    lab = {"pairs": [{"k": 0, "cosine": 0.99, "same_job": False,
                      "i": 0, "j": 1, "id_a": "p1", "occ_a": 0, "id_b": "p2", "occ_b": 0,
                      "a": display_of(corpus[0]), "b": display_of(corpus[1])}]}

    s, e, ru = resolve_labels(corpus, lab)
    ck("labels resolve against an unchanged corpus", len(s) == 1 and not e and not ru)

    # The case the whole package exists for: ordinary churn must NOT fire.
    shifted = [_row("new", "Warehouse Picker", "Acme", "NY")] + corpus
    s, e, ru = resolve_labels(shifted, lab)
    ck("a prepended row does NOT invalidate the labels (this is the fix)",
       len(s) == 1 and not e and not ru and s[0]["_i"] == 1 and s[0]["_j"] == 2,
       f"resolved to indices {s[0]['_i']},{s[0]['_j']} after the shift" if s else "no survivor")

    reordered = [corpus[1], corpus[0]]
    s, _, _ = resolve_labels(reordered, lab)
    ck("reordering the corpus does NOT invalidate the labels",
       len(s) == 1 and s[0]["_i"] == 1 and s[0]["_j"] == 0)

    # Ordinary expiry: the pair drops, and it is reported as expired, not fatal.
    s, e, ru = resolve_labels([corpus[0]], lab)
    ck("an expired posting DROPS its pair rather than failing the run",
       len(s) == 0 and len(e) == 1 and not ru and e[0]["id"] == "p2")

    # VIOLATION 1 -- an id that resolves to different content. Still fatal.
    reused_corpus = [corpus[0], _row("p2", "Chief Financial Officer", "Mercy", "LA")]
    s, e, ru = resolve_labels(reused_corpus, lab)
    ck("id REUSE is detected (id survives, content changed)",
       len(ru) == 1 and len(s) == 0,
       f"{ru[0]['labelled_as']!r} -> {ru[0]['now']!r}" if ru else "not detected")

    # The occurrence ordinal, which is what pair 115 needs: two rows, one id.
    twin = [_row("dup", "Computer Scientist", "AF", "Eglin AFB"),
            _row("dup", "Computer Scientist", "AF", "Eglin AFB")]
    twin_lab = {"pairs": [{"k": 0, "cosine": 1.0, "same_job": True, "i": 0, "j": 1,
                           "id_a": "dup", "occ_a": 0, "id_b": "dup", "occ_b": 1,
                           "a": display_of(twin[0]), "b": display_of(twin[1])}]}
    s, _, _ = resolve_labels(twin, twin_lab)
    ck("two rows sharing one id resolve to DIFFERENT indices, not the same row",
       len(s) == 1 and s[0]["_i"] == 0 and s[0]["_j"] == 1,
       f"_i={s[0]['_i']} _j={s[0]['_j']}" if s else "no survivor")
    s, e, _ = resolve_labels(twin[:1], twin_lab)
    ck("and if the second of the two is gone, the pair drops rather than pairing a row with itself",
       len(s) == 0 and len(e) == 1)

    # VIOLATION 2 -- too few survivors. Both the band floor and the class floor.
    def _synth(n_per_band, true_in_top=True):
        out, k = [], 0
        for b, (lo, _hi) in enumerate(GT_BANDS):
            for _ in range(n_per_band):
                out.append({"k": k, "cosine": lo + 0.005, "same_job": b == 4 and true_in_top})
                k += 1
        return out

    ok, why, st = floor_verdict(_synth(24))
    ck("a full survivor set passes the floor", ok, f"n={st['n_surviving']}")
    ok, why, st = floor_verdict(_synth(MIN_PAIRS_PER_BAND))
    ck(f"exactly {MIN_PAIRS_PER_BAND} per band passes", ok, f"n={st['n_surviving']}")
    ok, why, st = floor_verdict(_synth(MIN_PAIRS_PER_BAND - 1))
    ck(f"{MIN_PAIRS_PER_BAND - 1} per band FAILS the floor", not ok, "; ".join(why))
    # 96 of 120 survive -- 80% -- but one whole band is gone. A total-count
    # floor passes this; the per-band floor is the only thing that catches it.
    ok, why, st = floor_verdict([r for r in _synth(24) if r["cosine"] < 0.98])
    ck("losing one whole band FAILS even at 80% survival", not ok,
       f"n={st['n_surviving']} of 120, {'; '.join(why)}")
    # The band floor firing ON ITS OWN, with both classes comfortably healthy --
    # otherwise the case above would prove only that the class floor works.
    mixed = _synth(24)
    for i, r in enumerate(mixed):
        r["same_job"] = (i % 2 == 0)
    ok, why, st = floor_verdict([r for r in mixed if _band_of(r["cosine"]) != 0])
    ck("emptying a band fails on the BAND floor alone, both classes healthy", not ok and len(why) == 1,
       f"n={st['n_surviving']}, True={st['same_job_true']} False={st['same_job_false']}, {why}")

    ok, why, st = floor_verdict([r for r in _synth(24) if r["same_job"]])
    ck("an all-positive survivor set FAILS (nothing to catch a false positive)", not ok,
       "; ".join(why))
    ok, why, st = floor_verdict([r for r in _synth(24) if not r["same_job"]])
    ck("an all-negative survivor set FAILS (nothing to measure recall on)", not ok,
       "; ".join(why))

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
