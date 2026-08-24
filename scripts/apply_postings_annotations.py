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
import normalise  # noqa: E402
from _common import PROCESSED, ROOT, banner, log, record_provenance, write_processed  # noqa: E402
from postings_common import country_from_location  # noqa: E402

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

# The pay figure is restricted to ONE class, not to "any shipped class". SALES
# ships too, but a software-migration site's advertised-pay figure is about
# software roles; mixing sales compensation into it would answer a different
# question. Named here and published in pay_summary_meta so validate_data.py can
# re-derive the same subset instead of assuming which classes were used -- an
# assumption that silently made its first recount 1,239 against a real 1,117.
PAY_SUMMARY_CLASS = "SW"

# Advertised pay from 2016 and from 2026 are not the same quantity, and pooling
# them into one median produces a number that describes neither. Measured on the
# US: the corpus holds 2026 rows at a median of $203,963 and 2016-2017 rows at
# ~$87,000, and an unrestricted median lands at $175,000 -- between two
# populations $115,000 apart, 53% of one and 29% of the other. That is a
# bimodal mixture wearing a point estimate.
#
# An adversarial review found this by asking what the headline number was made
# of. Nothing on screen carried a date, which breaks this project's own standing
# rule that every published number carries a source, a date and a denominator.
#
# Three years: the current year and two behind it. Wide enough to hold a usable
# sample, narrow enough that nominal pay has not moved much across it. Rows with
# no posted_at are excluded from the published figure -- an undated row cannot be
# placed in or out of the window, and 8.4% of the US subset is undated.
PUBLISH_FROM_YEAR = 2024

# The same absolute annual band audit_data.py uses (_ABSOLUTE_SANITY_BANDS).
# Package 14 established that an implausible posting is FLAGGED, never deleted,
# and that still holds -- the row stays in postings.json with its own value
# untouched. But flagging is not the same as averaging it into a published
# median, and nothing stopped that until now.
#
# It became visible when package 17 relaxed the FX year-matching rule: postings
# like "250-400 SGD/year" (an employer typo, almost certainly a daily rate)
# could not convert before and were invisible; converted, one of them lands at
# $249/year inside a country's software population. A median is a robust
# statistic and would mostly shrug this off, but "mostly" is not a reason to
# feed it values the repo's own audit calls implausible.
PUBLISH_ANNUAL_USD_BAND = (500, 5_000_000)

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


def reresolve_countries(rows: list[dict]) -> dict:
    """Re-run the location parser over every row, filling blanks and correcting
    what it can now name.

    Applied HERE rather than by re-running the harvesters, because re-harvesting
    would re-fetch six provider APIs to recompute a pure function of text
    already committed.

    The rule is asymmetric on purpose: where the parser produces a country it
    wins, and where it produces nothing the existing value is KEPT. That second
    half matters -- 154 rows carry a country the parser cannot derive from their
    location text at all, because the provider supplied it directly (Teamtailor
    stamps SE, USAJOBS stamps US on "Location Negotiable After Selection").
    Overwriting those with None would destroy real information to satisfy a
    parser."""
    filled, corrected = 0, []
    for r in rows:
        got = country_from_location(r.get("location_raw"))
        if not got:
            continue
        if not r.get("country"):
            r["country"] = got
            filled += 1
        elif r["country"] != got:
            corrected.append({"location": r.get("location_raw"), "was": r["country"], "now": got})
            r["country"] = got
    log(f"    country re-resolution: filled {filled:,} blanks, corrected {len(corrected)}")
    from collections import Counter as _C
    for (was, now), k in _C((c["was"], c["now"]) for c in corrected).most_common():
        log(f"      {was} -> {now}: {k}")
    return {"filled": filled, "corrected": corrected}


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
    # A short CODE per row, with the prose held once in title_class_summary.
    # An earlier revision wrote the full explanatory sentence onto every row.
    # It was true on all 48,267 of them and identical on 27,656, and it cost
    # 5.1 MB -- pushing the shipped postings payload from 21.5 MB to 28.2 MB and
    # the /postings Lighthouse performance score from 0.80 to 0.71. A caveat
    # repeated 27,656 times is not 27,656 caveats; it is one caveat and a
    # performance regression.
    for r in rows:
        rec = by_title.get((r.get("title") or "").strip())
        if rec is None:
            r["title_class"] = {"class": "unclassified", "proba": None, "why": "not_in_vocabulary"}
        elif rec["class"] == "unclassified":
            # The classifier itself returned no class (below its probability
            # floor). An earlier version routed this down the "class_withheld"
            # branch too, which labelled 24,474 rows as withheld when only
            # 3,182 were — anyone filtering on the reason code over-selected by
            # 8.7x, and the documented `not_in_vocabulary` code fired on none.
            r["title_class"] = {"class": "unclassified", "proba": rec.get("proba"),
                                "why": "model_declined", "model_said": None}
        elif rec["class"] not in ship:
            r["title_class"] = {"class": "unclassified", "proba": rec.get("proba"),
                                "why": "class_withheld", "model_said": rec["class"]}
        else:
            r["title_class"] = {"class": rec["class"], "proba": rec.get("proba")}
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
        rep = rows[dup_of[i]]["id"] if i in dup_of else None
        # Three ids are duplicated in the corpus, so pointing BY id can produce a
        # row that claims to be a re-listing of itself. Two rows did
        # (usajobs:464745500, usajobs:464770500). The id collision is upstream
        # and not this step's to fix, but emitting a self-referential pointer is.
        r["duplicate_of"] = None if rep == r.get("id") else rep
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
    implausible: Counter = Counter()

    def mid(r):
        c = r.get("compensation") or {}
        u = c.get("usd")
        if not u or c.get("period") != "year":
            return None
        m = (u["min"] + u["max"]) / 2
        lo, hi = PUBLISH_ANNUAL_USD_BAND
        if not (lo <= m <= hi):
            implausible[r.get("country") or "?"] += 1
            return None
        return m

    def posted_year(r):
        s = (r.get("posted_at") or "")[:4]
        return int(s) if s.isdigit() else None

    def in_window(r):
        y = posted_year(r)
        return y is not None and y >= PUBLISH_FROM_YEAR

    pops: dict[str, dict[str, list[float]]] = {k: defaultdict(list) for k in
                                               ("as_published", "deduped", "software",
                                                "software_all_years")}
    # who and when the published figure is actually made of. A median with no
    # description of its own composition is how this figure came to be 77%
    # nine-year-old federal listings without anyone noticing.
    comp_rows: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        cc, m = r.get("country"), mid(r)
        if not cc or m is None:
            continue
        pops["as_published"][cc].append(m)
        if r.get("duplicate_of"):
            continue
        pops["deduped"][cc].append(m)
        if (r.get("title_class") or {}).get("class") == PAY_SUMMARY_CLASS:
            pops["software_all_years"][cc].append(m)
            if in_window(r):
                pops["software"][cc].append(m)
                comp_rows[cc].append(r)

    out = []
    for cc in sorted(pops["as_published"], key=lambda c: -len(pops["as_published"][c])):
        pub = pops["as_published"][cc]
        ded = pops["deduped"][cc]
        sw = pops["software"][cc]
        sw_all = pops["software_all_years"][cc]
        rec = {"country": cc,
               "n_as_published": len(pub), "n_deduped": len(ded), "n_software_only": len(sw),
               "n_software_all_years": len(sw_all),
               "published_from_year": PUBLISH_FROM_YEAR,
               # Rounded like every other published figure. This is the raw,
               # all-occupation, duplicates-included median and it is shipped to
               # the browser for every country including the withheld ones, so
               # leaving it at two decimals kept the manufactured FX cents
               # DATA-FITNESS rules out ($152,969.52 was the original defect
               # value) alive on the wire.
               "median_as_published_usd_year": _round(float(np.median(pub))) if pub else None,
               # kept as a DIAGNOSTIC, never published: this is the figure that
               # pools every vintage, and the gap between it and the windowed
               # one is the reason the window exists.
               "diagnostic_median_all_years_usd_year": (round(float(np.median(sw_all)), 2)
                                                        if sw_all else None)}
        rec["publishable"] = bool(len(sw) >= MIN_N_PUBLISH)
        if rec["publishable"]:
            cr = comp_rows[cc]
            yrs = Counter((r.get("posted_at") or "")[:4] for r in cr)
            prov = Counter(r.get("provider") for r in cr)
            top_p, top_n = prov.most_common(1)[0]
            # How much of this median rests on a substituted FX rate. Package 17
            # relaxed year-matching for postings and took GB, CA, FR and DE from
            # unpublishable to publishable -- but 76-94% of the rows that made
            # that possible are converted at a NEIGHBOURING year's rate, and the
            # summary said nothing about it. A figure that exists only because a
            # rule was relaxed has to carry how far it leaned on the relaxation.
            # Adversarial review H2.
            est_n = sum(1 for r in cr
                        if ((r.get("compensation") or {}).get("usd") or {}).get("estimated"))
            gaps = [((r.get("compensation") or {}).get("usd") or {}).get("fx_gap_years") or 0
                    for r in cr]
            # The USAJOBS sentence is about the US and was emitted verbatim for
            # every publishable country -- "USAJOBS supplies 872 US software
            # rows" appeared under the GB, CA, FR and DE figures, where it is
            # simply false. It is now stated only where it is true, computed
            # rather than asserted.
            # title_class is a dict — {"class": "SW", "proba": …} — not a bare
            # string. Reading it as a string made `fed` silently zero and
            # dropped a caveat that IS true for the US, which is the same shape
            # of bug as the one being fixed: a condition that never fires reads
            # exactly like a condition that is never met.
            fed = sum(1 for r in rows
                      if r.get("country") == cc and r.get("provider") == "usajobs"
                      and (r.get("title_class") or {}).get("class") == PAY_SUMMARY_CLASS
                      and not r.get("duplicate_of")
                      and ((r.get("posted_at") or "")[:4] or "0") < str(PUBLISH_FROM_YEAR))
            caveat = (f"{round(100 * top_n / len(cr))}% of these advertisements come from one "
                      f"source ({top_p}).")
            # Only where it is a real selection. GB has exactly one such row,
            # and "the restriction removes federal listings entirely" is not a
            # statement worth making about one row -- the same MIN_N_PUBLISH
            # floor the medians use is the honest bar for saying anything.
            if fed >= MIN_N_PUBLISH:
                caveat += (f" The window that makes the figure current also makes it narrower: "
                           f"USAJOBS supplies {fed:,} {cc} software rows dated before "
                           f"{PUBLISH_FROM_YEAR}, so the restriction removes federal listings "
                           f"entirely and leaves private ATS boards. That is a real selection, "
                           f"stated rather than absorbed.")
            if est_n:
                pct = 100 * est_n / len(cr)
                caveat += (f" {est_n:,} of {len(cr):,} "
                           f"({'under 1' if 0 < pct < 1 else round(pct)}%) were "
                           f"converted to USD at a rate from a neighbouring year, never more than "
                           f"{max(gaps)} away, because no rate for the posting's own year is "
                           f"published yet. Each such row is an estimate, so this median is one "
                           f"too" + (" — and is why the figure exists at all." if pct >= 50
                                     else "."))
            rec["composition"] = {
                "by_year": {y: k for y, k in sorted(yrs.items())},
                "by_provider": dict(prov.most_common()),
                "share_from_latest_year_pct": round(100 * yrs[max(yrs)] / len(cr), 1),
                "largest_provider": top_p,
                "largest_provider_share_pct": round(100 * top_n / len(cr), 1),
                "fx_estimated_n": est_n,
                "fx_estimated_pct": round(100 * est_n / len(cr), 1),
                "fx_max_gap_years": max(gaps) if gaps else 0,
                "caveat": caveat,
            }
        # A median is emitted ONLY for a country that clears the floor. An
        # earlier revision computed one for every country with any software row
        # and relied on the UI to filter -- so the JSON still carried medians
        # for DE (n=2), PT (n=1), IN (n=2) and QA (n=2), quotable by anyone
        # reading the file. validate_data.py's new check caught it. The floor
        # has to hold in the DATA, not just in the view; a caveat that only one
        # consumer honours is not a caveat.
        if sw and rec["publishable"]:
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
        rec["withheld_reason"] = None if rec["publishable"] else (
            f"only {len(sw)} distinct software roles state an annual pay range; the floor to "
            f"publish a median is {MIN_N_PUBLISH}")
        out.append(rec)

    meta = {
        "excluded_as_implausible": dict(implausible),
        "excluded_as_implausible_band_usd_year": list(PUBLISH_ANNUAL_USD_BAND),
        "excluded_as_implausible_note": (
            "rows whose annualised USD midpoint falls outside the band audit_data.py already "
            "flags. They remain in postings.json with their own values untouched — package 14's "
            "rule that an implausible posting is flagged and never deleted still holds — but they "
            "are not averaged into a published median. Mostly employer typos: a daily or hourly "
            "figure tagged as annual."),
        "basis": f"de-duplicated (one row per distinct role), restricted to titles classified "
                 f"{PAY_SUMMARY_CLASS}, posted {PUBLISH_FROM_YEAR} or later",
        "restricted_to_class": PAY_SUMMARY_CLASS,
        "published_from_year": PUBLISH_FROM_YEAR,
        "vintage_reason": (
            "advertised pay from 2016 and from 2026 are not the same quantity. Pooled, the US "
            "median lands at $175,000 between a 2026 population near $204,000 (53% of rows) and a "
            "2016-2017 one near $87,000 (29%) — a bimodal mixture wearing a point estimate, and "
            "one that carried no date on screen at all. diagnostic_median_all_years_usd_year "
            "keeps the pooled figure per country so the gap stays visible."),
        # This used to assert "USAJOBS supplies 872 US software rows" — a
        # hardcoded count that had drifted to 893, restating a fact the US
        # composition block now computes and states itself. A number written
        # down in two places is a number that will disagree with itself; the
        # per-country caveat is the one that recomputes.
        "vintage_cost": (
            "the window has a composition cost as well as a currency benefit: it removes older "
            "listings wholesale, and where those came from one provider it removes that provider "
            "with them. Each country's `composition` block states its own year mix, provider mix "
            "and what the window took out, computed per country rather than asserted once."),
        "undated_rows_excluded": (
            "a row with no posted_at cannot be placed inside or outside the window and is "
            "excluded from the published figure"),
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

    resolution = reresolve_countries(rows)
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

    # Cross-rates for the display-currency picker, derived from the same
    # World Bank series everything else uses and carrying the year they came
    # from. USD is the pivot because that is what every posting is already
    # converted through; these turn USD into the reader's chosen currency.
    #
    # A FULL YEAR TABLE, not one latest rate. The first version of this shipped
    # `max(series, key=year)` — a single 2025 rate applied to every posting
    # regardless of its own year — and adversarial review priced what that
    # costs: a 2016 US federal listing displayed in Australian dollars came out
    # 15.4% high, converted across a nine-year gap against a stated ceiling of
    # two, with no estimate marker, because `estimated` was computed from the
    # native->USD leg alone. 3,989 rows on the wire are dated 2023 or earlier.
    #
    # A second conversion is a conversion. It obeys the same rule as the first:
    # match the posting's own year, reach no further than MAX_FX_GAP_YEARS, and
    # say so when it reaches. The client cannot do that from one number, so it
    # gets the series. Four currencies x 66 years is 4.1 KB.
    fx = json.loads((PROCESSED / "fx_rates.json").read_text(encoding="utf-8"))["data"]
    display_fx = {}
    for code, cc in (("EUR", "DE"), ("GBP", "GB"), ("CAD", "CA"), ("AUD", "AU")):
        got = [x for x in (fx.get(cc) or []) if x.get("value") is not None]
        if got:
            latest = max(got, key=lambda x: x["year"])
            display_fx[code] = {
                "rate": latest["value"], "year": latest["year"],
                "by_year": {str(x["year"]): x["value"] for x in sorted(got, key=lambda r: r["year"])},
            }

    country_counts = Counter(r.get("country") or "unresolved" for r in rows)
    n_unresolved = country_counts.get("unresolved", 0)
    d = doc["data"]
    d["postings"] = rows
    d["country_counts"] = dict(country_counts)
    # build_postings.py leaves this behind as a deliberate tripwire, and this
    # step is what earns the right to remove it. Leaving it set while also
    # writing real figures would make the tripwire fire forever, which trains
    # people to ignore it.
    d.pop("pay_summary_status", None)
    d["pay_summary_by_country"] = summary
    d["pay_summary_meta"] = summary_meta
    d["pay_summary_min_n"] = MIN_N_PUBLISH
    d["display_fx"] = {
        "pivot": "USD",
        "rates": display_fx,
        "max_gap_years": normalise.MAX_FX_GAP_YEARS,
        "source": "fx_rates (World Bank PA.NUS.FCRF, annual period average)",
        "note": ("multiply a posting's USD figure by the rate for THAT POSTING'S OWN YEAR to show "
                 "it in another currency — by_year carries the whole series for exactly that "
                 "reason. Annual period averages, not live rates. Reaching past the posting's year "
                 "is allowed up to max_gap_years and makes the result an estimate, the same rule "
                 "and the same ceiling the native→USD conversion obeys. Native currency needs none "
                 "of this and is always the default."),
    }
    d["country_resolution"] = {
        "unresolved": n_unresolved,
        "unresolved_pct": round(100 * n_unresolved / n, 2),
        "filled_this_run": resolution["filled"],
        "corrected_this_run": resolution["corrected"],
        "residual_failure_modes": {
            "remote_with_no_country_named": "the largest remaining group. 'Remote', 'Anywhere', "
                                            "'Fully Remote', 'Remoto' — these are not unparsed "
                                            "locations, they are postings that genuinely state no "
                                            "country, and coercing them into one would invent a "
                                            "denominator.",
            "supra_national_regions": "'Asia', 'Europe', 'LATAM', 'North America', 'EMEA'. Real "
                                      "information, but not a country. Left unresolved rather than "
                                      "assigned to a member state.",
            "bare_city_or_office_shorthand": "'Santa Clara', 'Scotts Valley', 'SF Office', "
                                             "'Emeryville HQ'. Resolvable in principle with a wider "
                                             "gazetteer, but the ambiguous cases are real "
                                             "('Worcester' is Massachusetts or England, 'Cali' is "
                                             "Colombia or California) and this parser has already "
                                             "shipped one substring-matching incident.",
            "junk": "'550', ''. Nothing to resolve.",
        },
        "known_unfixed": (
            "three country names are deliberately NOT in the table — panama, lebanon and jordan — "
            "because each collides with a US place ('Panama City Beach, FL', 'Lebanon, OH', "
            "'West Jordan, UT') that the 2-letter state code, checked after the country table, "
            "would lose to. The ordering question this raises is recorded in NEEDS-DECISION.md."),
    }
    d["title_class_summary"] = {
        "shipped_classes": stats["ship"],
        "class_decisions": stats["decisions"],
        "counts": stats["class_counts"],
        "proba_floor": stats["proba_floor"],
        "why_codes": {
            "not_in_vocabulary": "the title does not appear in the classifier's own output",
            "model_declined": "the classifier returned no class for this title — its top class "
                              "fell below the probability floor. NOT the same as a class this "
                              "build withholds, and counting the two together overstated the "
                              "withheld group 8.7x.",
            "class_withheld": ("the model assigned a class this build does not ship, because its "
                               f"F1 95% confidence interval does not lie entirely above "
                               f"{F1_SHIP_THRESHOLD}. model_said records which class it was."),
        },
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
    # This step FETCHES NOTHING; it joins and re-derives files that already
    # exist. Every field below therefore has to describe a derivation. An
    # earlier version passed urls=["https://github.com/"] with no coverage,
    # which put a link to GitHub's homepage in the source column of /data —
    # this site's transparency page, on a site whose promise is that every
    # number is sourced and dated — with a licence sentence in the licence slot
    # and "raw committed" against a file nothing was downloaded for. Found by an
    # adversarial review reading the rendered page rather than the call.
    record_provenance(
        source_id=SOURCE_ID,
        name="Job postings (merged ATS providers, classified and de-duplicated)",
        urls=[],
        license_note="derived; each provider's own provenance entry carries its API, its licence "
                     "and its fetch date",
        redistribution="derived — nothing is fetched by this step",
        coverage=f"{len(doc['data'].get('seed_companies') or {}):,} companies across "
                 f"{sum(1 for v in (doc['data'].get('provider_summary') or {}).values() if v.get('available'))} "
                 f"providers",
        transforms=[
            "merged every postings_<provider>.json (build_postings.py)",
            "joined postings_title_classes.json as title_class; only classes whose F1 95% CI lies "
            "entirely above 0.70 ship, the rest are emitted as unclassified",
            "joined postings_duplicate_clusters.json as duplicate_of; no row removed",
            f"re-derived pay_summary_by_country on distinct roles, software titles only, posted "
            f"{PUBLISH_FROM_YEAR} or later, with bootstrap CIs, a {MIN_N_PUBLISH}-posting floor "
            f"and ${PUBLISH_ROUNDING:,} rounding",
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
    _Y = f"{PUBLISH_FROM_YEAR}-06-01"

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
    rows = [{"id": "a", "title": "Software Engineer", "country": "US", "posted_at": _Y,
             "compensation": {"period": "year", "usd": {"min": 100000, "max": 100000}}},
            {"id": "b", "title": "Software Engineer", "country": "US", "posted_at": _Y,
             "compensation": {"period": "year", "usd": {"min": 100000, "max": 100000}}},
            {"id": "c", "title": "Registered Nurse", "country": "US", "posted_at": _Y,
             "compensation": {"period": "year", "usd": {"min": 40000, "max": 40000}}}]
    cls = {"meta": {"proba_floor": 0.4}, "data": {"classified_titles": [
        {"title": "Software Engineer", "class": "SW", "proba": 0.9},
        {"title": "Registered Nurse", "class": "HEALTH", "proba": 0.9}]}}
    clus = {"data": {"clusters": [[0, 1]], "n_postings": 3}}
    st = annotate(rows, cls, clus, ev)
    ck("a shipped class survives the join", rows[0]["title_class"]["class"] == "SW")
    ws = [{"id": "w", "title": "  Software Engineer ", "country": "US", "posted_at": _Y,
           "compensation": {"period": "year", "usd": {"min": 1e5, "max": 1e5}}}]
    annotate(ws, cls, {"data": {"clusters": [], "n_postings": 1}}, ev)
    ck("an untrimmed title still joins (6.7% of the real corpus has one)",
       ws[0]["title_class"]["class"] == "SW", repr(ws[0]["title"]))
    ck("a WITHHELD class becomes unclassified, with the reason recorded",
       rows[2]["title_class"]["class"] == "unclassified" and rows[2]["title_class"]["model_said"] == "HEALTH")
    ck("the duplicate points at its representative and the representative does not",
       rows[1]["duplicate_of"] == "a" and rows[0]["duplicate_of"] is None)
    ck("no row is dropped by the join", len(rows) == 3 and st["n_distinct_roles"] == 2)

    summ, smeta = pay_summary(rows)
    us = [r for r in summ if r["country"] == "US"][0]
    ck("derived stats EXCLUDE the duplicate and the withheld class",
       us["n_as_published"] == 3 and us["n_software_only"] == 1, str(us["n_software_only"]))
    ck("a country below the floor is withheld with a stated reason",
       not us["publishable"] and "floor to publish" in us["withheld_reason"])
    old_rows = [{"id": f"o{i}", "title": "Software Engineer", "country": "ZZ",
                 "posted_at": f"{PUBLISH_FROM_YEAR - 5}-06-01",
                 "compensation": {"period": "year", "usd": {"min": 5e4, "max": 5e4}}}
                for i in range(60)]
    annotate(old_rows, cls, {"data": {"clusters": [], "n_postings": 60}}, ev)
    s_old, _ = pay_summary(old_rows)
    ck("60 software rows from BEFORE the window cannot publish a median",
       not s_old[0]["publishable"] and s_old[0]["n_software_only"] == 0
       and s_old[0]["n_software_all_years"] == 60,
       "pooling vintages is what produced a $175,000 median between two populations")
    undated = [{"id": f"u{i}", "title": "Software Engineer", "country": "ZY",
                "compensation": {"period": "year", "usd": {"min": 5e4, "max": 5e4}}}
               for i in range(60)]
    annotate(undated, cls, {"data": {"clusters": [], "n_postings": 60}}, ev)
    s_und, _ = pay_summary(undated)
    ck("undated rows cannot publish a median either — they cannot be placed in the window",
       not s_und[0]["publishable"] and s_und[0]["n_software_only"] == 0)
    ck("a country below the floor carries NO median in the data, not just in the view",
       "median_usd_year" not in us and "median_published_usd_year" not in us,
       "the floor must hold in the payload, not only in the UI")

    # a country must not pass the floor on duplicated rows alone
    many = [{"id": f"d{i}", "title": "Software Engineer", "country": "XX", "posted_at": _Y,
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
