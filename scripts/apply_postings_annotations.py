"""Package 16, Tier 1 — join package 15's measurements back into the postings.

Package 15 measured the postings panel and wrote three artifacts. None of them
was joined to anything, so the site kept serving the uncorrected numbers:
`title_class` was absent from every row, `postings_duplicate_clusters.json`
identified 2,884 removable rows that were still counted, and
`pay_summary_by_country` published seven countries to the cent on samples as
small as five. This script applies all three.

ORDERING. It must run AFTER build_postings.py, dedupe_postings.py and
classify_titles.py, because it consumes what those three produce. That creates
a real hazard: the cluster artifact stores POSTING INDICES, so if postings.json
is rebuilt in a different order the clusters silently describe different rows.
Package 15 hit exactly this with its hand labels. The join therefore refuses to
run unless the corpus still fingerprints identically -- same row count, same id
sequence -- rather than trusting that nothing moved.

WHAT IS AND IS NOT WRITTEN TO `occupation`. Nothing. `occupation` is typed
`{occupation_key, confidence}` where occupation_key is an ISCO-08 code from
data/occupations.json, assigned by the (never-run) Gemini classifier. The
TF-IDF classifier produces coarse job FAMILIES -- SW, SALES -- which are not
ISCO codes; postings_title_classes.json says so itself ("not the ISCO crosswalk
and must not be compared against wage-spine occupations"). Writing families
into an ISCO-shaped field would disguise one vocabulary as the other and invite
precisely the cross-comparison the standing rules forbid. The class goes in its
own `title_class` field and `occupation` stays null, which is the true state of
it. See NEEDS-DECISION.md.

    python scripts/apply_postings_annotations.py
    python scripts/apply_postings_annotations.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, ROOT, banner, log, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "postings"
CLASSES = PROCESSED / "postings_title_classes.json"
CLUSTERS = PROCESSED / "postings_duplicate_clusters.json"
EVAL = ROOT / "data" / "quality_history" / "title_classifier_eval.json"

# A class ships only if the LOWER BOUND of its F1 confidence interval clears
# the bar -- not its point estimate. Package 15 shipped on the point estimate,
# deliberately, because that rule was fixed before the numbers were seen and it
# refused to move a threshold after the fact. Its own review then showed four of
# seven classes have an interval straddling 0.70, so a point estimate above the
# bar is not evidence the class is above the bar. Package 16's work order
# resolves it: do not ship a class its own evidence does not support. That drops
# HEALTH (F1 0.741, CI [0.588, 0.857]) and leaves SW and SALES.
F1_SHIP_THRESHOLD = 0.70

# Below this, a country gets no published median. 30 is the same floor
# rederive_postings_pay.py applies and for the same reason.
MIN_N_PUBLISH = 30

# §0-D measured advertised pay heaped to round thousands: 77.5% of native
# annual minima end in 0 or 5, 65% end in 000, terminal-digit uniformity
# rejected at p < 0.001. A median of heaped data resolves no finer than the
# heaping, so publishing cents is manufactured precision.
PUBLISH_ROUNDING = 1000

# Below this an interval is not describing a distribution, it is relabelling a
# handful of order statistics. Same constant, same reason, as
# rederive_postings_pay.MIN_N_FOR_MEANINGFUL_CI.
MIN_N_FOR_MEANINGFUL_CI = 12


def corpus_fingerprint(rows: list[dict]) -> str:
    """Identity of the corpus AS ORDERED. Index-based artifacts are only valid
    against the exact sequence they were computed from."""
    h = hashlib.sha256()
    for r in rows:
        h.update(str(r.get("id")).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def shipped_classes(eval_doc: dict) -> tuple[list[str], dict]:
    """Classes whose F1 interval lies ENTIRELY above the bar, plus the evidence
    for every class so the decision is auditable rather than asserted."""
    ci = eval_doc.get("per_class_f1_ci95") or {}
    decisions = {}
    for c, m in sorted(ci.items()):
        lo, hi = m["ci95"]
        decisions[c] = {
            "f1": m["f1"], "ci95": [lo, hi], "n_true": m.get("n_true"),
            "ships": bool(lo >= F1_SHIP_THRESHOLD),
            "why": ("interval lies entirely above the bar"
                    if lo >= F1_SHIP_THRESHOLD else
                    "interval straddles the bar -- the point estimate clears it but the class "
                    "cannot be distinguished from one that does not"
                    if hi >= F1_SHIP_THRESHOLD else
                    "interval lies entirely below the bar"),
        }
    return [c for c, d in decisions.items() if d["ships"]], decisions


def median_with_ci(vals: list[float], n_boot: int = 10000, seed: int = 20260101):
    v = np.asarray(vals, float)
    n = v.size
    rng = np.random.default_rng(seed)
    b = np.array([np.median(v[rng.integers(0, n, n)]) for _ in range(n_boot)])
    lo, hi = (float(x) for x in np.percentile(b, [2.5, 97.5]))
    m = float(np.median(v))
    quality = {
        "n": int(n),
        "below_min_n_for_ci": bool(n < MIN_N_FOR_MEANINGFUL_CI),
        "distinct_values": int(np.unique(v).size),
        "spans_full_sample_range": bool(lo <= v.min() and hi >= v.max()),
    }
    quality["do_not_quote"] = bool(quality["below_min_n_for_ci"] or quality["spans_full_sample_range"])
    return m, lo, hi, quality


def _round(x: float | None) -> float | None:
    return None if x is None else round(x / PUBLISH_ROUNDING) * PUBLISH_ROUNDING


def annotate(rows: list[dict], classes_doc: dict, clusters_doc: dict, eval_doc: dict) -> dict:
    n = len(rows)
    ship, decisions = shipped_classes(eval_doc)
    log(f"    classes shipped on interval evidence: {ship or 'NONE'}")
    for c, d in decisions.items():
        if not d["ships"]:
            log(f"      withheld {c:<7} F1={d['f1']:.3f} CI[{d['ci95'][0]:.3f},{d['ci95'][1]:.3f}] — {d['why']}")

    # ---- 1.1 title class, keyed by TITLE (robust to reordering, unlike indices)
    # Look up on the STRIPPED title. classify_titles.py built its vocabulary
    # from stripped titles, but 3,251 postings (6.7%) carry leading or trailing
    # whitespace, so a raw-key join silently drops every one of them to
    # "unclassified" -- 928 of them SW. That is not a small mismatch: it moved
    # the US software sample from 1,117 to 1,067 and shifted the published
    # interval by about $2,000 at both ends. Caught only by checking this
    # join's US count against package 15's independently-computed one.
    by_title = {r["title"]: r for r in classes_doc["data"]["classified_titles"]}
    assert all(k == k.strip() for k in by_title), "classifier vocabulary is not stripped"
    floor = (classes_doc.get("meta") or {}).get("proba_floor")
    counts: Counter = Counter()
    for r in rows:
        rec = by_title.get((r.get("title") or "").strip())
        if rec is None:
            r["title_class"] = {"class": "unclassified", "proba": None,
                                "reason": "title not present in the classifier's own output"}
        elif rec["class"] not in ship:
            r["title_class"] = {"class": "unclassified", "proba": rec.get("proba"),
                                "reason": f"model said {rec['class']}, a class this build does not "
                                          f"ship: its F1 interval does not clear "
                                          f"{F1_SHIP_THRESHOLD}"}
        else:
            r["title_class"] = {"class": rec["class"], "proba": rec.get("proba"), "reason": None}
        counts[r["title_class"]["class"]] += 1
    log(f"    title_class: " + ", ".join(f"{k} {v:,}" for k, v in counts.most_common()))

    # ---- 1.2 duplicate_of, keeping every raw row
    clusters = clusters_doc["data"]["clusters"]
    dup_of = {}
    for g in clusters:
        idx = sorted(g)
        keep = idx[0]
        for i in idx[1:]:
            dup_of[i] = keep
    for i, r in enumerate(rows):
        r["duplicate_of"] = rows[dup_of[i]]["id"] if i in dup_of else None
    n_dup = len(dup_of)
    log(f"    duplicate_of set on {n_dup:,} of {n:,} rows ({100*n_dup/n:.2f}%); "
        f"{n - n_dup:,} distinct roles. No row removed.")
    return {"ship": ship, "decisions": decisions, "class_counts": dict(counts),
            "n_duplicate_rows": n_dup, "n_distinct_roles": n - n_dup, "proba_floor": floor}


def pay_summary(rows: list[dict]) -> tuple[list[dict], dict]:
    """Re-derive per-country advertised pay on the de-duplicated, software-only
    subset, and report the delta against what each stage would have published.

    Three nested populations, reported together on purpose, because the whole
    finding is that the published figure is the widest and worst of them:
      as_published  every row, duplicates included, every occupation
      deduped       one row per distinct role
      software      + only titles this build ships as SW
    """
    def mid(r):
        c = r.get("compensation") or {}
        u = c.get("usd")
        if not u or c.get("period") != "year":
            return None
        return (u["min"] + u["max"]) / 2

    pops: dict[str, dict[str, list[float]]] = {k: defaultdict(list) for k in
                                               ("as_published", "deduped", "software")}
    for r in rows:
        cc, m = r.get("country"), mid(r)
        if not cc or m is None:
            continue
        pops["as_published"][cc].append(m)
        if r.get("duplicate_of"):
            continue
        pops["deduped"][cc].append(m)
        if (r.get("title_class") or {}).get("class") == "SW":
            pops["software"][cc].append(m)

    out = []
    for cc in sorted(pops["as_published"], key=lambda c: -len(pops["as_published"][c])):
        pub = pops["as_published"][cc]
        ded = pops["deduped"][cc]
        sw = pops["software"][cc]
        rec = {"country": cc,
               "n_as_published": len(pub), "n_deduped": len(ded), "n_software_only": len(sw),
               "median_as_published_usd_year": round(float(np.median(pub)), 2) if pub else None}
        if sw:
            m, lo, hi, q = median_with_ci(sw)
            rec.update({
                "median_usd_year": round(m, 2),
                "median_published_usd_year": _round(m),
                "ci_lo_usd_year": round(lo), "ci_hi_usd_year": round(hi),
                "ci_lo_published_usd_year": _round(lo), "ci_hi_published_usd_year": _round(hi),
                "ci_quality": q,
            })
            if rec["median_as_published_usd_year"]:
                rec["delta_vs_as_published_pct"] = round(
                    100 * (m - rec["median_as_published_usd_year"]) / rec["median_as_published_usd_year"], 1)
        rec["publishable"] = bool(len(sw) >= MIN_N_PUBLISH)
        rec["withheld_reason"] = None if rec["publishable"] else (
            f"only {len(sw)} distinct software roles state an annual pay range; the floor to "
            f"publish a median is {MIN_N_PUBLISH}")
        out.append(rec)

    meta = {
        "basis": "de-duplicated (one row per distinct role), restricted to titles shipped as SW",
        "min_n_to_publish": MIN_N_PUBLISH,
        "published_rounding_usd": PUBLISH_ROUNDING,
        "rounding_reason": "advertised pay is heaped to round thousands (77.5% of native annual "
                           "minima end in 0 or 5; terminal-digit uniformity rejected p<0.001), so "
                           "a median of it resolves no finer than the heaping. Cents were "
                           "manufactured by FX conversion, never present in any source.",
        "n_publishable": sum(1 for r in out if r["publishable"]),
        "n_countries_considered": len(out),
        "midpoint_caveat": "each posting contributes the midpoint of its advertised RANGE. That is "
                           "a property of the advertisement, not a salary anyone is paid, and it "
                           "must never be compared against survey earnings.",
    }
    return out, meta


def run() -> int:
    banner(SOURCE_ID, "join package 15's classification, de-duplication and re-derivation")
    doc = json.loads((PROCESSED / f"{SOURCE_ID}.json").read_text(encoding="utf-8"))
    rows = doc["data"]["postings"]
    n = len(rows)

    clusters_doc = json.loads(CLUSTERS.read_text(encoding="utf-8"))
    classes_doc = json.loads(CLASSES.read_text(encoding="utf-8"))
    eval_doc = json.loads(EVAL.read_text(encoding="utf-8"))

    # The clusters are INDEX-based. Refuse rather than silently mis-join.
    if clusters_doc["data"]["n_postings"] != n:
        log(f"  FATAL: clusters were computed against {clusters_doc['data']['n_postings']:,} "
            f"postings, corpus now has {n:,}. Re-run dedupe_postings.py.")
        return 2
    fp = corpus_fingerprint(rows)
    log(f"    corpus fingerprint {fp[:16]} over {n:,} rows")

    stats = annotate(rows, classes_doc, clusters_doc, eval_doc)
    summary, summary_meta = pay_summary(rows)

    for r in summary[:8]:
        if r["publishable"]:
            log(f"      {r['country']:<4} PUBLISH {r['median_published_usd_year']:>9,.0f} "
                f"(CI {r['ci_lo_published_usd_year']:,.0f}-{r['ci_hi_published_usd_year']:,.0f}) "
                f"n={r['n_software_only']:<5} delta {r.get('delta_vs_as_published_pct'):+.1f}%")
        else:
            log(f"      {r['country']:<4} withheld  n_sw={r['n_software_only']:<4} "
                f"(as published: n={r['n_as_published']}, "
                f"median {r['median_as_published_usd_year']})")

    country_counts = Counter(r.get("country") or "unresolved" for r in rows)
    d = doc["data"]
    d["postings"] = rows
    d["country_counts"] = dict(country_counts)
    d["pay_summary_by_country"] = summary
    d["pay_summary_meta"] = summary_meta
    d["pay_summary_min_n"] = MIN_N_PUBLISH
    d["title_class_summary"] = {
        "shipped_classes": stats["ship"],
        "class_decisions": stats["decisions"],
        "counts": stats["class_counts"],
        "proba_floor": stats["proba_floor"],
        "caveat": "a job FAMILY, not an ISCO occupation code. It is not the wage spine's "
                  "vocabulary and must never be compared against it.",
    }
    d["duplicate_summary"] = {
        "raw_rows": n,
        "distinct_roles": stats["n_distinct_roles"],
        "re_listings": stats["n_duplicate_rows"],
        "re_listings_pct": round(100 * stats["n_duplicate_rows"] / n, 2),
        "reading": "every raw row is preserved and carries duplicate_of. 99.9% of re-listings have "
                   "their own URL, so these are genuine re-postings and simultaneous openings, not "
                   "scraping artifacts. Derived statistics use distinct roles; the raw count is "
                   "still the honest answer to 'how many advertisements were harvested'.",
    }

    meta = dict(doc.get("meta") or {})
    meta.update({
        "postings_count": n,
        "distinct_roles": stats["n_distinct_roles"],
        "corpus_fingerprint_sha256": fp,
        "occupation_field_status": (
            "still null on every row, truthfully. `occupation` is an ISCO-08 code assigned by the "
            "Gemini classifier, which has never run (it needs an API key). The TF-IDF classifier "
            "added by package 15 produces coarse job families, NOT ISCO codes, so they are carried "
            "in `title_class` rather than written into an ISCO-shaped field where they would be "
            "compared against the wage spine."),
        "annotations_applied_by": "scripts/apply_postings_annotations.py (package 16, tier 1)",
    })
    write_processed(SOURCE_ID, d, meta=meta)
    record_provenance(
        source_id=SOURCE_ID,
        name="Job postings (merged ATS providers, classified and de-duplicated)",
        urls=["https://github.com/"],
        license_note="each provider's own public job board API; see per-provider provenance entries",
        transforms=[
            "merged every postings_<provider>.json (build_postings.py)",
            "joined postings_title_classes.json as title_class; only classes whose F1 95% CI lies "
            "entirely above 0.70 ship, the rest are emitted as unclassified",
            "joined postings_duplicate_clusters.json as duplicate_of; no row removed",
            "re-derived pay_summary_by_country on distinct roles, software titles only, with "
            "bootstrap CIs, a 30-posting floor and $1,000 rounding",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=n,
        notes=(f"{stats['n_distinct_roles']:,} distinct roles among {n:,} raw rows; "
               f"{summary_meta['n_publishable']} of {summary_meta['n_countries_considered']} "
               f"countries clear the publication floor"),
    )
    return 0


def self_test() -> int:
    fails = []

    def ck(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  [' + detail + ']') if detail else ''}")
        if not cond:
            fails.append(name)

    print("=== apply_postings_annotations.py self-test ===")

    # ship rule: interval, not point estimate
    ev = {"per_class_f1_ci95": {
        "SW": {"f1": 0.822, "ci95": [0.765, 0.872], "n_true": 116},
        "HEALTH": {"f1": 0.741, "ci95": [0.588, 0.857], "n_true": 28},
        "MGT": {"f1": 0.594, "ci95": [0.506, 0.680], "n_true": 86}}}
    ship, dec = shipped_classes(ev)
    ck("ships a class whose whole interval clears the bar", ship == ["SW"], str(ship))
    ck("WITHHOLDS a class whose point estimate clears but interval straddles",
       not dec["HEALTH"]["ships"] and dec["HEALTH"]["f1"] > F1_SHIP_THRESHOLD,
       "HEALTH F1 0.741 > 0.70 yet withheld")
    ck("withholds a class entirely below the bar", not dec["MGT"]["ships"])

    # corpus fingerprint must detect reordering, which an index join cannot survive
    a = [{"id": "x"}, {"id": "y"}, {"id": "z"}]
    ck("fingerprint is stable for an unchanged corpus",
       corpus_fingerprint(a) == corpus_fingerprint([dict(r) for r in a]))
    ck("fingerprint CHANGES when the corpus is reordered",
       corpus_fingerprint(a) != corpus_fingerprint([a[1], a[0], a[2]]))
    ck("fingerprint CHANGES when a row is inserted",
       corpus_fingerprint(a) != corpus_fingerprint([{"id": "w"}] + a))

    # rounding must not invent precision
    ck("publishes to the nearest $1,000", _round(98688.0) == 99000)
    ck("rounding a CI keeps it a band, not a point",
       _round(95307) == 95000 and _round(101357) == 101000)

    # degenerate interval must be flagged
    _, _, _, q6 = median_with_ci([1.0, 2, 3, 4, 5, 9], n_boot=800)
    ck("flags an interval computed from n=6 as not quotable", q6["do_not_quote"], f"n={q6['n']}")
    _, _, _, qb = median_with_ci(list(np.linspace(1, 100, 400)), n_boot=800)
    ck("does NOT flag a healthy n=400 interval", not qb["do_not_quote"])

    # the join itself
    rows = [{"id": "a", "title": "Software Engineer", "country": "US",
             "compensation": {"period": "year", "usd": {"min": 100000, "max": 100000}}},
            {"id": "b", "title": "Software Engineer", "country": "US",
             "compensation": {"period": "year", "usd": {"min": 100000, "max": 100000}}},
            {"id": "c", "title": "Registered Nurse", "country": "US",
             "compensation": {"period": "year", "usd": {"min": 40000, "max": 40000}}}]
    cls = {"meta": {"proba_floor": 0.4}, "data": {"classified_titles": [
        {"title": "Software Engineer", "class": "SW", "proba": 0.9},
        {"title": "Registered Nurse", "class": "HEALTH", "proba": 0.9}]}}
    clus = {"data": {"clusters": [[0, 1]], "n_postings": 3}}
    st = annotate(rows, cls, clus, ev)
    ck("a shipped class survives the join", rows[0]["title_class"]["class"] == "SW")
    ws = [{"id": "w", "title": "  Software Engineer ", "country": "US",
           "compensation": {"period": "year", "usd": {"min": 1e5, "max": 1e5}}}]
    annotate(ws, cls, {"data": {"clusters": [], "n_postings": 1}}, ev)
    ck("an untrimmed title still joins (6.7% of the real corpus has one)",
       ws[0]["title_class"]["class"] == "SW", repr(ws[0]["title"]))
    ck("a WITHHELD class becomes unclassified, with the reason recorded",
       rows[2]["title_class"]["class"] == "unclassified" and "HEALTH" in rows[2]["title_class"]["reason"])
    ck("the duplicate points at its representative and the representative does not",
       rows[1]["duplicate_of"] == "a" and rows[0]["duplicate_of"] is None)
    ck("no row is dropped by the join", len(rows) == 3 and st["n_distinct_roles"] == 2)

    summ, smeta = pay_summary(rows)
    us = [r for r in summ if r["country"] == "US"][0]
    ck("derived stats EXCLUDE the duplicate and the withheld class",
       us["n_as_published"] == 3 and us["n_software_only"] == 1, str(us["n_software_only"]))
    ck("a country below the floor is withheld with a stated reason",
       not us["publishable"] and "floor to publish" in us["withheld_reason"])

    # a country must not pass the floor on duplicated rows alone
    many = [{"id": f"d{i}", "title": "Software Engineer", "country": "XX",
             "compensation": {"period": "year", "usd": {"min": 1e5, "max": 1e5}}} for i in range(40)]
    st2 = annotate(many, cls, {"data": {"clusters": [list(range(40))], "n_postings": 40}}, ev)
    s2, _ = pay_summary(many)
    ck("40 rows that are ONE role cannot satisfy the 30-posting floor",
       not s2[0]["publishable"] and s2[0]["n_software_only"] == 1,
       f"n_sw={s2[0]['n_software_only']} of 40 raw")

    print(f"\n{len(fails)} failure(s)" + (" — all controls hold" if not fails else f": {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    raise SystemExit(self_test() if a.self_test else run())
