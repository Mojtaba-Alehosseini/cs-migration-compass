"""Package 15, Tier 5.1 — occupation classification from job titles, without an LLM.

The Gemini classifier this repo already ships has never run: `occupation` is
None on all 48,267 postings, and it needs an API key that no environment in
this project has had. It is also not needed for this job. A job title is a
short, highly stereotyped string; TF-IDF over word AND character n-grams
plus a linear model is a strong baseline for exactly that shape of problem,
and unlike an LLM it is deterministic, offline, free, and auditable.

EVALUATION PROTOCOL, and why it is the shape it is:

  * Every reported number comes from a model that never saw the record it is
    scoring. 5-fold STRATIFIED cross_val_predict gives an out-of-fold
    prediction for all 400 labelled titles, so the confusion matrix is
    computed on 400 honest predictions rather than on an 80-record test
    split that would put 2 SVC examples in it.
  * A separate stratified 25% holdout is ALSO reported, fitted on the other
    75% only. It is the weaker estimate (small n) but it is the one that
    cannot be argued with, and if the two disagree badly that is itself a
    finding.
  * De-duplication happens BEFORE the split. The corpus has 30,528 distinct
    titles across 48,267 postings; if the same title could land in both
    train and test the score would be inflated by memorisation. The ground
    truth is sampled from distinct titles for this reason.
  * Classes are shipped only if they clear a stated F1 threshold on the
    out-of-fold predictions. Everything else is emitted as `unclassified`,
    which is a real answer and is recorded as such.

WHAT THIS DELIBERATELY DOES NOT DO: it never produces a pay figure, and it
never touches compensation. Standing rule 3: a model classifies; it never
produces a pay figure.

    python scripts/classify_titles.py               # evaluate + classify the corpus
    python scripts/classify_titles.py --self-test   # gate 14
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, log, record_provenance, write_processed  # noqa: E402

GT = ROOT / "data" / "labels" / "title_ground_truth.json"
OUT_EVAL = ROOT / "data" / "quality_history" / "title_classifier_eval.json"
OUT_PRED = PROCESSED / "postings_title_classes.json"

# A class ships only if it earns it. 0.70 F1 is this package's own stated bar:
# high enough that a shipped class is usable for filtering, low enough to be
# reachable from 400 labels across 7 classes. Classes below it are folded into
# `unclassified` rather than published at a quality nobody measured.
F1_SHIP_THRESHOLD = 0.70

# Below this predicted probability the model is not confident enough to assert
# a class, whatever the class's own F1. Justified by the accuracy-vs-coverage
# table this script emits into the eval artifact (`confidence_calibration`):
# an earlier revision of this comment claimed it came from "the reliability
# curve in the eval artifact" when no such curve was ever computed, which is
# exactly the kind of unsupported claim this package exists to catch. The
# table is now real and the floor is read off it: out-of-fold, a 0.40 floor
# keeps 77.8% coverage at 0.797 accuracy, against 0.730 at a 0.30 floor and
# 0.888 at 0.50 for only 60.0% coverage. 0.40 is where accuracy first clears
# ~0.80 without discarding a quarter of the corpus.
PROBA_FLOOR = 0.40

SEED = 15


def build_model():
    """Word n-grams catch 'software engineer'; character n-grams catch
    'SWE', 'DevOps', 'Sr.', misspellings, and the CJK/Portuguese/Swedish
    titles in this corpus that word tokenisation handles badly."""
    feats = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True,
                                 min_df=1, lowercase=True, strip_accents="unicode")),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True,
                                 min_df=1, lowercase=True, strip_accents="unicode")),
    ])
    clf = LogisticRegression(max_iter=4000, C=4.0, class_weight="balanced", random_state=SEED)
    return Pipeline([("feats", feats), ("clf", clf)])


def _load_gt():
    d = json.loads(GT.read_text(encoding="utf-8"))
    X = [r["title"] for r in d["records"]]
    y = [r["label"] for r in d["records"]]
    return d, X, y


def evaluate():
    d, X, y = _load_gt()
    X, y = np.array(X, dtype=object), np.array(y)
    log(f"evaluating on {len(X)} hand-labelled titles, {len(set(y))} classes")

    # --- out-of-fold: every record scored by a model that never saw it
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    oof = cross_val_predict(build_model(), X, y, cv=skf, n_jobs=1)
    labels = sorted(set(y))
    rep = classification_report(y, oof, labels=labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(y, oof, labels=labels)

    # --- independent holdout, fitted on the other 75% only
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEED)
    m = build_model().fit(Xtr, ytr)
    hold_pred = m.predict(Xte)
    hold_rep = classification_report(yte, hold_pred, labels=labels, output_dict=True, zero_division=0)

    shipped = [c for c in labels if rep[c]["f1-score"] >= F1_SHIP_THRESHOLD]

    # Accuracy vs coverage at each candidate probability floor, computed
    # out-of-fold so it is honest. This is what PROBA_FLOOR is read off:
    # a floor is worth paying for only if the accuracy it buys exceeds the
    # coverage it costs.
    oof_proba = cross_val_predict(CalibratedClassifierCV(build_model(), method="sigmoid", cv=5),
                                  X, y, cv=skf, method="predict_proba", n_jobs=1)
    oof_cls = np.array(sorted(set(y)))
    top_i = oof_proba.argmax(1)
    top_p = oof_proba.max(1)
    top_lab = oof_cls[top_i]
    calib = []
    for floor in [0.0, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80]:
        m = top_p >= floor
        calib.append({"floor": floor,
                      "coverage_pct": round(100 * float(m.mean()), 2),
                      "accuracy_above_floor": round(float((top_lab[m] == y[m]).mean()), 4) if m.any() else None,
                      "n": int(m.sum())})
    # --- the rule AS SHIPPED, which is not the rule scored above.
    # classification_report() scores pure argmax over all seven classes. The
    # pipeline ships argmax + PROBA_FLOOR + the ship-list, so a row whose top
    # class is withheld or below the floor becomes "unclassified" -- which is
    # a RECALL miss the argmax table never charges. Reporting the argmax
    # numbers as though they described the shipped output would overstate it.
    as_shipped = np.where(np.isin(top_lab, shipped) & (top_p >= PROBA_FLOOR),
                          top_lab, "unclassified")
    shipped_metrics = {}
    for c in shipped:
        tp = int(((as_shipped == c) & (y == c)).sum())
        fp = int(((as_shipped == c) & (y != c)).sum())
        fn = int(((as_shipped != c) & (y == c)).sum())
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        shipped_metrics[c] = {"precision": round(pr, 4), "recall": round(rc, 4),
                              "f1": round(2 * pr * rc / (pr + rc), 4) if pr + rc else 0.0,
                              "n_true": int((y == c).sum()),
                              "lost_to_floor_or_shiplist": fn - int(((as_shipped != c)
                                                                    & (as_shipped != "unclassified")
                                                                    & (y == c)).sum())}

    # --- how much of the per-class F1 is sampling noise. With 24-116 records
    # per class, a point F1 is not a precise quantity and must not be read as
    # one, least of all near the 0.70 ship line.
    rng = np.random.default_rng(SEED)
    f1_ci = {}
    for c in labels:
        boots = []
        for _ in range(2000):
            b = rng.integers(0, len(y), len(y))
            yb, ob = y[b], oof[b]
            tp = int(((ob == c) & (yb == c)).sum())
            fp = int(((ob == c) & (yb != c)).sum())
            fn = int(((ob != c) & (yb == c)).sum())
            boots.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        f1_ci[c] = {"f1": round(rep[c]["f1-score"], 4), "ci95": [round(float(lo), 4), round(float(hi), 4)],
                    "n_true": int((y == c).sum()),
                    "ci_spans_ship_threshold": bool(lo < F1_SHIP_THRESHOLD <= hi)}

    art = {
        "schema": "package-15 title classifier evaluation v1",
        "n_labelled": int(len(X)),
        "classes": labels,
        "protocol": {
            "out_of_fold": "5-fold StratifiedKFold cross_val_predict — every one of the 400 "
                           "records is predicted by a model fitted without it",
            "holdout": "separate stratified 25% split, model fitted on the remaining 75% only",
            "leakage_control": "ground truth is sampled from DISTINCT titles, so no title can "
                               "appear in both train and test",
        },
        "f1_ship_threshold": F1_SHIP_THRESHOLD,
        "proba_floor": PROBA_FLOOR,
        "out_of_fold": {
            "accuracy": round(float(rep["accuracy"]), 4),
            "macro_f1": round(float(rep["macro avg"]["f1-score"]), 4),
            "weighted_f1": round(float(rep["weighted avg"]["f1-score"]), 4),
            "per_class": {c: {"precision": round(rep[c]["precision"], 4),
                              "recall": round(rep[c]["recall"], 4),
                              "f1": round(rep[c]["f1-score"], 4),
                              "support": int(rep[c]["support"])} for c in labels},
            "confusion_matrix": {"labels": labels, "rows_are_true": True,
                                 "matrix": cm.tolist()},
        },
        "holdout_25pct": {
            "n": int(len(yte)),
            "accuracy": round(float(hold_rep["accuracy"]), 4),
            "macro_f1": round(float(hold_rep["macro avg"]["f1-score"]), 4),
            "per_class_f1": {c: round(hold_rep[c]["f1-score"], 4) for c in labels},
        },
        "confidence_calibration": {
            "note": "out-of-fold accuracy and coverage at each candidate probability floor; "
                    "PROBA_FLOOR is read off this table",
            "table": calib,
        },
        "as_shipped_rule": {
            "rule": "argmax, then blanked to 'unclassified' unless the class is shipped AND "
                    "p >= PROBA_FLOOR",
            "why_this_differs": "the per_class table above scores pure argmax over all seven "
                                "classes and is the basis for the ship decision; THIS is what the "
                                "shipped output achieves. Quote these numbers for the pipeline.",
            "per_shipped_class": shipped_metrics,
        },
        "per_class_f1_ci95": f1_ci,
        "selection_disclosure": (
            "both the ship-list and PROBA_FLOOR were chosen on these same 400 out-of-fold "
            "predictions. The predictions are honest -- no model saw its own record -- but the "
            "THRESHOLDS are fitted to this sample, so the per-class F1 is optimistic as an "
            "estimate of a fresh sample by an unmeasured amount. The 25% holdout does not fix "
            "this: it is a split of the same 400 records, not an independent sample. Only new "
            "hand labels would settle it."),
        "ship_decisions_within_noise": [
            c for c in labels if f1_ci[c]["ci_spans_ship_threshold"]],
        "ship_line_caveat": (
            "the ship rule (F1 >= 0.70 out-of-fold) was fixed before these numbers were seen and "
            "is applied as stated. But at n=400 the per-class CIs are wide: four of seven classes "
            "have a 95% CI straddling 0.70, so for those the ship/withhold call is not resolvable "
            "on this sample. Only SW and SALES sit entirely above the line and only MGT entirely "
            "below. HEALTH ships on a point estimate of 0.741 whose interval reaches 0.588 -- "
            "treat it as provisional, not as a measured pass."),
        "shipped_classes": shipped,
        "withheld_classes": [c for c in labels if c not in shipped],
    }
    return art, labels


def classify_corpus(art, labels):
    """Fit on all 400 labels, then classify every DISTINCT title once and map
    back to postings. Distinct-title classification is ~16x less work than
    per-posting and is identical by construction, since the model sees only
    the title."""
    d, X, y = _load_gt()
    base = build_model()
    # Calibrated probabilities: an uncalibrated logistic margin is not a
    # probability, and PROBA_FLOOR would be meaningless applied to one.
    model = CalibratedClassifierCV(base, method="sigmoid", cv=5).fit(np.array(X, dtype=object), np.array(y))

    post = json.loads((PROCESSED / "postings.json").read_text(encoding="utf-8"))["data"]["postings"]
    titles = sorted({(p.get("title") or "").strip() for p in post if (p.get("title") or "").strip()})
    log(f"classifying {len(titles)} distinct titles")
    proba = model.predict_proba(np.array(titles, dtype=object))
    cls = model.classes_
    best = proba.argmax(1)
    shipped = set(art["shipped_classes"])

    out, conf_hist = {}, Counter()
    for t, bi, row in zip(titles, best, proba):
        c, p = cls[bi], float(row[bi])
        if c not in shipped or p < PROBA_FLOOR:
            out[t] = {"class": "unclassified", "proba": round(p, 4), "top": c}
        else:
            out[t] = {"class": c, "proba": round(p, 4)}
        conf_hist[out[t]["class"]] += 1

    per_posting = Counter()
    for p in post:
        t = (p.get("title") or "").strip()
        per_posting[out.get(t, {}).get("class", "unclassified")] += 1

    art["corpus"] = {
        "n_distinct_titles": len(titles),
        "n_postings": len(post),
        "distinct_title_class_counts": dict(conf_hist.most_common()),
        "posting_class_counts": dict(per_posting.most_common()),
        "software_share_of_postings_pct": round(100 * per_posting.get("SW", 0) / len(post), 2),
        "unclassified_share_of_postings_pct": round(100 * per_posting.get("unclassified", 0) / len(post), 2),
    }
    return out, art


def run():
    art, labels = evaluate()
    oof = art["out_of_fold"]
    log(f"  out-of-fold accuracy {oof['accuracy']:.3f}  macro-F1 {oof['macro_f1']:.3f}")
    for c in labels:
        m = oof["per_class"][c]
        flag = "SHIP" if c in art["shipped_classes"] else "withheld"
        log(f"    {c:<7} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} n={m['support']:<4} {flag}")
    for c, m in art["as_shipped_rule"]["per_shipped_class"].items():
        log(f"    AS SHIPPED {c:<8} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
            f"({m['lost_to_floor_or_shiplist']} of {m['n_true']} lost to the floor/ship-list)")
    if art["ship_decisions_within_noise"]:
        log(f"  ship/withhold NOT resolvable at n=400 for: "
            f"{', '.join(art['ship_decisions_within_noise'])} (95% CI straddles {F1_SHIP_THRESHOLD})")
    log(f"  holdout(25%) accuracy {art['holdout_25pct']['accuracy']:.3f} "
        f"macro-F1 {art['holdout_25pct']['macro_f1']:.3f}")

    preds, art = classify_corpus(art, labels)
    c = art["corpus"]
    log(f"  corpus: {c['software_share_of_postings_pct']}% of postings classified SW, "
        f"{c['unclassified_share_of_postings_pct']}% unclassified")

    OUT_EVAL.parent.mkdir(parents=True, exist_ok=True)
    OUT_EVAL.write_text(json.dumps(art, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    write_processed("postings_title_classes",
        {"classified_titles": [{"title": k, **v} for k, v in sorted(preds.items())]},
        meta={"model": "TF-IDF (word 1-2 + char_wb 2-5) -> calibrated logistic regression",
              "trained_on": "data/labels/title_ground_truth.json (400 hand-labelled titles)",
              "shipped_classes": art["shipped_classes"],
              "withheld_classes": art["withheld_classes"],
              "f1_ship_threshold": F1_SHIP_THRESHOLD, "proba_floor": PROBA_FLOOR,
              "out_of_fold_macro_f1": art["out_of_fold"]["macro_f1"],
              "evaluation": "data/quality_history/title_classifier_eval.json",
              "caveat": "a class assignment is a CLASSIFICATION, never a pay figure and never an "
                        "occupation code; it is not the ISCO crosswalk and must not be compared "
                        "against wage-spine occupations.",
              "shape_note": "a LIST of records, deliberately, not a title-keyed dict. A dict keyed "
                            "by free-text job titles is structurally indistinguishable from one "
                            "keyed by occupation codes, and validate_data.py's own "
                            "_occupation_like_records() correctly read it as occupation wage data "
                            "and demanded a distribution flag. Same class of collision package 14 "
                            "hit with advertised_by_country: the check is right, so the file "
                            "changed shape rather than the check being weakened."})
    record_provenance(
        source_id="postings_title_classes",
        name="Postings job-title occupation classes — TF-IDF + linear model, package 15",
        urls=[],
        license_note="Derived from data/processed/postings.json, which carries each provider's own "
                     "licence; this file adds a classification and no new source data.",
        redistribution="derived — a label per distinct job title, computed offline from titles "
                       "already committed in postings.json",
        transforms=[
            "Hand-labelled 400 provider-stratified distinct titles by reading each one "
            "(data/labels/title_ground_truth.json); no keyword rule produced a label.",
            "Fitted TF-IDF (word 1-2 + char_wb 2-5) into a calibrated logistic regression.",
            "Evaluated out-of-fold (5-fold stratified) AND on a held-out 25% split; per-class "
            "precision/recall/F1 and the confusion matrix are in "
            "data/quality_history/title_classifier_eval.json.",
            f"Shipped only classes clearing F1 >= {F1_SHIP_THRESHOLD} out-of-fold; everything "
            f"else, and anything below probability {PROBA_FLOOR}, is emitted as 'unclassified'.",
            "Never produces or touches a pay figure — standing rule 3.",
        ],
        output=f"data/processed/{OUT_PRED.stem}.json",
        rows=len(preds),
        coverage=f"{art['corpus']['n_distinct_titles']} distinct titles covering "
                 f"{art['corpus']['n_postings']} postings",
        notes="A class here is NOT an ISCO occupation code and must never be compared against the "
              "wage spine's own occupations or crosswalk.",
    )
    log(f"  wrote {OUT_EVAL.relative_to(ROOT)} and {OUT_PRED.relative_to(ROOT)}")
    return 0


def self_test():
    fails = []

    def ck(n, c, d=""):
        print(f"  {'PASS' if c else 'FAIL'}  {n}{('  [' + d + ']') if d else ''}")
        if not c:
            fails.append(n)

    print("=== classify_titles.py self-test ===")
    d, X, y = _load_gt()
    ck("ground truth loads with 400 records", len(X) == 400, f"n={len(X)}")
    ck("no title appears twice (train/test leakage impossible)",
       len(set(X)) == len(X), f"{len(set(X))} distinct of {len(X)}")

    # A model trained on shuffled labels must score near chance. If it does
    # not, the pipeline is leaking the answer through the features.
    rng = np.random.default_rng(SEED)
    yshuf = np.array(y)[rng.permutation(len(y))]
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    oof_shuf = cross_val_predict(build_model(), np.array(X, dtype=object), yshuf, cv=skf)
    f1_shuf = f1_score(yshuf, oof_shuf, average="macro", zero_division=0)
    ck("label-permutation control scores near chance (no leakage)", f1_shuf < 0.20,
       f"macro-F1 on shuffled labels = {f1_shuf:.3f}")

    oof = cross_val_predict(build_model(), np.array(X, dtype=object), np.array(y), cv=skf)
    f1_real = f1_score(y, oof, average="macro", zero_division=0)
    ck("real labels score far above the permutation control", f1_real > f1_shuf + 0.35,
       f"real={f1_real:.3f} vs shuffled={f1_shuf:.3f}")

    m = build_model().fit(np.array(X, dtype=object), np.array(y))
    probe = ["Senior Software Engineer", "Registered Nurse", "Sales Associate (Part-Time)",
             "Mechanical Engineer, Fluids"]
    got = list(m.predict(np.array(probe, dtype=object)))
    ck("obvious titles land in the obvious classes",
       got == ["SW", "HEALTH", "SVC", "ENG"], f"{dict(zip(probe, got))}")

    print(f"\n{len(fails)} failure(s)" + (": " + ", ".join(fails) if fails else " — all controls hold"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    sys.exit(self_test() if a.self_test else run())
