"""Package 15, Tier 5.1 — the hand-labelled title ground truth.

The 400 labels below were assigned by READING each title, one at a time,
before any classifier existed. They are not the output of a keyword rule,
and that matters: if the labels came from a rule and the classifier then
learned that rule, the evaluation would measure "can TF-IDF reproduce my
regex" rather than "is the classifier right about jobs". The work order's
own adversarial-review brief asks specifically whether the classifier was
evaluated on data it trained on, and a rule-derived label set is the
subtler version of that same failure.

The sample is provider-stratified over DISTINCT titles (30,528 distinct
across 48,267 postings). Stratifying matters because Ashby alone is 41% of
the corpus and its titles look nothing like USAJOBS'; a uniform sample
would have evaluated the classifier almost entirely on startup job titles
and then shipped it against federal ones.

Judgement calls are recorded in `known_ambiguities` in the output rather
than smoothed over, because they are where the classifier's own errors
should be expected to concentrate, and a confusion matrix is much easier
to read honestly when the ambiguity was declared in advance.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, log  # noqa: E402

OUT = ROOT / "data" / "labels" / "title_ground_truth.json"
SEED = 15
STRATA = {"ashby": 150, "greenhouse": 110, "lever": 80, "usajobs": 40, "hn": 10, "teamtailor": 10}

CLASSES = {
    "SW": "software/data/IT engineering, development, DevOps, ML, security engineering, sysadmin",
    "ENG": "engineering that is NOT software (mechanical, electrical, civil, manufacturing, hardware, aerospace)",
    "SALES": "sales, account management, business development, partnerships, marketing, customer success",
    "MGT": "general management, operations, HR, finance, legal, admin, recruiting, strategy, programme/product management",
    "HEALTH": "clinical, medical, nursing, therapy, veterinary",
    "SVC": "retail, hospitality, warehouse, food service, front-line customer service, seasonal store",
    "OTHER": "design, non-software research, education, media, and undecidable/placeholder postings",
}

AMBIGUITIES = [
    "Product and programme management is labelled MGT even at software companies: a title alone "
    "does not establish that the holder writes software.",
    "Solutions and pre-sales engineering is labelled SALES: the role is quota-carrying even though "
    "the title says engineer.",
    "A bare 'Engineer I' or 'Senior Engineer' with no domain is labelled ENG, the larger prior "
    "across this corpus. This is expected to be a real source of SW/ENG confusion and should show "
    "up in the confusion matrix rather than be hidden by it.",
    "USAJOBS 'Interdisciplinary' postings genuinely span several occupations by design; labelled "
    "on the dominant reading of the title.",
    "'AI Trainer' freelance postings are labelled OTHER, not SW: they are data-annotation work "
    "advertised by subject-matter domain (chemistry, law, Bengali), not software engineering.",
]

# 40 rows of 10, index-aligned, so a miscount is caught by the assertion below
# rather than silently shifting every label after it.
LABELS: list[str] = sum([
    "SALES SW SW SALES MGT SALES SW MGT MGT SW".split(),            # 0-9
    "MGT SW ENG SW OTHER SW SALES ENG MGT MGT".split(),             # 10-19
    "SALES OTHER HEALTH SW SALES SALES MGT SALES MGT SALES".split(),  # 20-29
    "SW SALES MGT SW MGT SALES MGT OTHER SW ENG".split(),           # 30-39
    "SW SALES SW SW MGT SW MGT MGT MGT OTHER".split(),              # 40-49
    "OTHER MGT SALES SALES SW SW SALES SALES SALES ENG".split(),    # 50-59
    "SW ENG SW SW ENG SW SALES OTHER OTHER SW".split(),             # 60-69
    "SALES ENG SW ENG SALES MGT SALES SW ENG SW".split(),           # 70-79
    "MGT SW MGT MGT SW SALES MGT SW OTHER SW".split(),              # 80-89
    "MGT SALES MGT MGT SALES MGT SW OTHER MGT SALES".split(),       # 90-99
    "OTHER SW SALES SW ENG MGT SALES MGT SALES SW".split(),         # 100-109
    "SW SALES MGT SW HEALTH MGT SW SW HEALTH OTHER".split(),        # 110-119
    "MGT SALES HEALTH SALES MGT SW SALES MGT ENG MGT".split(),      # 120-129
    "HEALTH SW ENG SW OTHER OTHER SW MGT SW SW".split(),            # 130-139
    "SW SVC ENG SVC SALES SW SW SW MGT SW".split(),                 # 140-149
    "ENG ENG OTHER SW MGT SALES MGT MGT MGT SW".split(),            # 150-159
    "SALES MGT SW ENG SALES SW SW SVC OTHER ENG".split(),           # 160-169
    "SVC ENG SVC SALES SVC SALES ENG HEALTH OTHER MGT".split(),     # 170-179
    "ENG SALES SW SW SW MGT SW OTHER SALES SVC".split(),            # 180-189
    "HEALTH ENG SALES SW ENG MGT SALES SW SALES SW".split(),        # 190-199
    "MGT SALES MGT MGT MGT SW MGT SALES SW HEALTH".split(),         # 200-209
    "OTHER SVC SVC MGT OTHER MGT SW MGT SW ENG".split(),            # 210-219
    "SW SVC SW ENG ENG ENG SALES SVC ENG SVC".split(),              # 220-229
    "MGT SALES SALES SALES ENG OTHER OTHER HEALTH ENG ENG".split(),  # 230-239
    "SALES SALES MGT SALES SW SW ENG MGT SW ENG".split(),           # 240-249
    "OTHER SVC SW SALES SW MGT SVC MGT SVC SW".split(),             # 250-259
    "MGT SW SVC SW MGT MGT MGT SW SW ENG".split(),                  # 260-269
    "SALES SALES HEALTH SW OTHER SVC SW OTHER MGT MGT".split(),     # 270-279
    "SALES SALES SALES MGT SW HEALTH SW SALES MGT SW".split(),      # 280-289
    "SALES SVC SALES SVC SW SVC OTHER SW ENG SALES".split(),        # 290-299
    "ENG MGT OTHER HEALTH MGT SALES SALES SALES SW SVC".split(),    # 300-309
    "SALES SALES SW SALES MGT SW HEALTH SW MGT SW".split(),         # 310-319
    "SW OTHER SALES SVC MGT SW MGT OTHER HEALTH SW".split(),        # 320-329
    "MGT SW SALES MGT SW SALES MGT SVC ENG MGT".split(),            # 330-339
    "SW MGT HEALTH SW OTHER HEALTH HEALTH HEALTH MGT SW".split(),   # 340-349
    "HEALTH HEALTH HEALTH HEALTH HEALTH HEALTH HEALTH HEALTH SW OTHER".split(),  # 350-359
    "SW MGT SW SW ENG ENG SW SW SW MGT".split(),                    # 360-369
    "ENG MGT MGT SW HEALTH HEALTH MGT SW SW MGT".split(),           # 370-379
    "SW SW SW OTHER OTHER SW SW SW SW SW".split(),                  # 380-389
    "MGT SVC SW SALES MGT MGT ENG ENG OTHER SW".split(),            # 390-399
], [])


def sample_titles():
    """Reproduce the exact stratified sample the labels were assigned to."""
    post = json.loads((PROCESSED / "postings.json").read_text(encoding="utf-8"))["data"]["postings"]
    by_prov = defaultdict(list)
    for p in post:
        t = (p.get("title") or "").strip()
        if t:
            by_prov[p.get("provider")].append(t)
    random.seed(SEED)
    out = []
    for prov, n in STRATA.items():
        pool = sorted(set(by_prov.get(prov, [])))
        out += [(prov, t) for t in random.sample(pool, min(n, len(pool)))]
    return out


def run():
    for i, row in enumerate(range(0, 400, 10)):
        assert len(LABELS[row:row + 10]) == 10, f"row starting {row} is not 10 labels"
    assert len(LABELS) == 400, f"expected 400 labels, got {len(LABELS)}"
    assert set(LABELS) <= set(CLASSES), f"unknown label(s): {set(LABELS) - set(CLASSES)}"

    samp = sample_titles()
    assert len(samp) == len(LABELS), f"sample is {len(samp)}, labels are {len(LABELS)}"

    recs = [{"i": i, "provider": p, "title": t, "label": LABELS[i]} for i, (p, t) in enumerate(samp)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema": "package-15 hand-labelled title ground truth v1",
        "n": len(recs),
        "seed": SEED,
        "stratification": STRATA,
        "sampled_from": "distinct titles in data/processed/postings.json",
        "labeller_note": "assigned by reading each title individually, before any classifier "
                         "existed; no keyword rule was used to produce a label",
        "classes": CLASSES,
        "known_ambiguities": AMBIGUITIES,
        "records": recs,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"  wrote {OUT.relative_to(ROOT)}  n={len(recs)}")
    for k, v in Counter(LABELS).most_common():
        log(f"    {k:<7}{v:>4}  {100*v/len(LABELS):>5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(run())
