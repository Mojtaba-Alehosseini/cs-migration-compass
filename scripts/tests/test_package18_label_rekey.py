"""Package 18 — the de-duplication labels must survive a real re-harvest.

The labels were keyed by array index, so any harvest that added, removed or
reordered one row invalidated all 240 endpoints at once and stopped the weekly
refresh dead. They are keyed by (id, occurrence) now. These tests run the churn
a weekly refresh actually produces against the REAL corpus and the REAL labels,
because a fix that only works on two synthetic rows is the bug again.

Every test here calls the shipped functions -- `resolve_labels()` and
`floor_verdict()` -- and never a local copy of their logic. The self-test this
replaces reimplemented the index comparison inline, so it never exercised the
guard at all and went on passing after the re-key while asserting the exact
behaviour the re-key removed.
"""
from __future__ import annotations

import json
import random
import sys
import unittest
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import dedupe_postings as dp  # noqa: E402

PROCESSED = SCRIPTS.parent / "data" / "processed"
LABELS = SCRIPTS.parent / "data" / "labels" / "dedupe_pair_ground_truth.json"


def _corpus():
    return json.loads((PROCESSED / "postings.json").read_text(encoding="utf-8"))["data"]["postings"]


def _labels():
    return json.loads(LABELS.read_text(encoding="utf-8"))


class TestTheKeyItself(unittest.TestCase):
    def test_every_pair_carries_an_id_key(self):
        gt = _labels()
        self.assertEqual(len(gt["pairs"]), gt["n"])
        missing = [r["k"] for r in gt["pairs"]
                   if "id_a" not in r or "id_b" not in r
                   or r["id_a"] is None or r["id_b"] is None]
        self.assertEqual(missing, [], f"{len(missing)} pair(s) have no id key")

    def test_the_index_fields_are_provenance_and_are_not_read(self):
        """`i`/`j` stay in the file as a record of where the pair was labelled.
        If resolution ever reads them again, corrupting them would change the
        answer -- so corrupting them must NOT change the answer."""
        post, gt = _corpus(), _labels()
        base, _, _ = dp.resolve_labels(post, gt)
        wrecked = {**gt, "pairs": [{**r, "i": -1, "j": 10 ** 9} for r in gt["pairs"]]}
        base_exp, base_ed = dp.resolve_labels(post, gt)[1:]
        after, expired, edited = dp.resolve_labels(post, wrecked)
        self.assertEqual(len(after), len(base))
        self.assertEqual((len(expired), len(edited)), (len(base_exp), len(base_ed)))
        self.assertEqual([(r["_i"], r["_j"]) for r in after],
                         [(r["_i"], r["_j"]) for r in base])

    def test_the_one_colliding_id_resolves_to_two_different_rows(self):
        """Pair 115 is two rows sharing usajobs:464770500. Keying on the id
        alone would pair a row with itself, which is trivially 'clustered
        together' at every threshold -- a true positive no threshold can fail."""
        post, gt = _corpus(), _labels()
        pair = next(r for r in gt["pairs"] if r["k"] == 115)
        self.assertEqual(pair["id_a"], pair["id_b"])
        self.assertNotEqual(pair["occ_a"], pair["occ_b"])
        s, _, _ = dp.resolve_labels(post, {"pairs": [pair]})
        self.assertEqual(len(s), 1)
        self.assertNotEqual(s[0]["_i"], s[0]["_j"], "the pair resolved to one row twice")
        self.assertEqual(post[s[0]["_i"]]["id"], post[s[0]["_j"]]["id"])


class TestOrdinaryChurnMustNotFire(unittest.TestCase):
    """The failure this package exists to remove.

    Everything here is measured AGAINST THE BASELINE resolution of the committed
    corpus, never against 120. The committed corpus is refreshed weekly by the
    workflow this package unblocked, and after the first such refresh landed it
    resolved 109 of 120 — so ten tests that asserted "all 120 survive" went red
    on data that was completely healthy. A test that only passes on the corpus
    it was written against is the same defect as a label keyed to array
    position, one level up."""

    def setUp(self):
        self.post = _corpus()
        self.gt = _labels()
        self.n = len(self.gt["pairs"])
        base, base_exp, base_ed = dp.resolve_labels(self.post, self.gt)
        self.base = base
        self.base_keys = {r["k"] for r in base}
        self.base_expired, self.base_edited = len(base_exp), len(base_ed)

    def _all_survive(self, corpus, what):
        """Churn must not change WHICH pairs resolve, whatever the baseline is."""
        s, expired, edited = dp.resolve_labels(corpus, self.gt)
        self.assertEqual(len(edited), self.base_edited, f"{what}: edited count moved")
        self.assertEqual(len(expired), self.base_expired, f"{what}: expiry count moved")
        self.assertEqual({r["k"] for r in s}, self.base_keys,
                         f"{what}: {len(s)} pairs survived against a baseline of {len(self.base)}")
        return s

    # DISTINCT rows, not 500 copies of one. An earlier version injected 500
    # identical postings, which generated 124,750 exact-key candidate pairs at
    # cosine 1.0 and inflated the top band's candidate population 33x -- so the
    # reweighted recall moved 0.678 -> 0.986 while the report claimed "every
    # figure is identical". A real harvest adds distinct adverts. Adversarial
    # review, package 18.
    @staticmethod
    def _fresh(n, tag):
        return [{"id": f"{tag}:{i}", "title": f"{tag.title()} Specialist {i}",
                 "company": f"{tag}co{i % 37}", "location_raw": f"City {i % 23}"}
                for i in range(n)]

    def test_prepending_rows(self):
        self._all_survive(self._fresh(500, "new") + self.post, "500 distinct rows prepended")

    def test_appending_rows(self):
        self._all_survive(self.post + self._fresh(500, "late"), "500 distinct rows appended")

    def test_reordering_the_whole_corpus(self):
        shuffled = list(self.post)
        random.Random(18).shuffle(shuffled)
        self._all_survive(shuffled, "corpus shuffled")

    def test_removing_rows_that_are_not_labelled(self):
        keep_ids = {r[f"id_{s}"] for r in self.gt["pairs"] for s in ("a", "b")}
        rng = random.Random(1818)
        thinned = [p for p in self.post
                   if p.get("id") in keep_ids or rng.random() > 0.10]
        self.assertLess(len(thinned), len(self.post))
        self._all_survive(thinned, "10% of unlabelled rows removed")

    def test_the_churn_a_weekly_refresh_actually_produces(self):
        """Rows leave, rows arrive, order changes, all at once -- and some of
        the rows that leave ARE labelled endpoints. Survivors must drop by
        exactly the pairs whose endpoints went, nothing else, and the result
        must still clear the floor."""
        rng = random.Random(2026)
        by_id = {}
        for p in self.post:
            by_id.setdefault(p.get("id"), []).append(p)

        labelled_ids = sorted({r[f"id_{s}"] for r in self.gt["pairs"] for s in ("a", "b")})
        expire = set(rng.sample(labelled_ids, 12))          # 12 labelled postings close
        churned = [p for p in self.post
                   if p.get("id") not in expire and rng.random() > 0.05]
        churned += [{"id": f"fresh:{i}", "title": f"Software Engineer {i}",
                     "company": f"NewCo{i % 61}", "location_raw": f"Berlin {i % 17}"}
                    for i in range(2000)]
        rng.shuffle(churned)

        s, expired, edited = dp.resolve_labels(churned, self.gt)
        self.assertEqual(len(edited), self.base_edited,
                         "ordinary churn must not change how many adverts look edited")

        # Which pairs SHOULD have dropped, derived from the churned corpus
        # rather than from the 12 ids deliberately expired -- the random 5%
        # takes labelled rows too, and an earlier version of this test counted
        # only the deliberate ones and blamed the difference on the code.
        have = Counter(p.get("id") for p in churned)
        newly_gone = {r["k"] for r in self.base
                      if have[r["id_a"]] <= r["occ_a"] or have[r["id_b"]] <= r["occ_b"]}
        self.assertTrue(newly_gone, "the churn removed no labelled endpoint at all — not a real test")
        self.assertEqual(self.base_keys - {r["k"] for r in s}, newly_gone,
                         "the pairs that dropped are not exactly the ones whose postings left")
        self.assertEqual(len(s), len(self.base) - len(newly_gone))
        self.assertGreater(len(expired), self.base_expired)

        ok, why, stats = dp.floor_verdict(s)
        self.assertTrue(ok, f"a realistic week of churn broke the floor: {why} ({stats})")


class TestTheGuardCanStillFail(unittest.TestCase):
    """A guard that cannot fail is worse than none. Packages 15, 16 and 17 each
    shipped one, and package 17's own was this script's."""

    def test_an_edited_advert_drops_its_pair_and_does_not_abort_the_run(self):
        """The employer edited a title. Measured on the two real consecutive
        harvests, 8 of 19,399 surviving ids did exactly this in one week — all
        benign. Treating it as fatal put the pipeline back where package 18
        found it, so the pair leaves the sample and the run continues."""
        post, gt = _corpus(), _labels()
        base, _, base_ed = dp.resolve_labels(post, gt)
        victim = next(r for r in base)          # a pair that still resolves today
        idx = next(i for i, p in enumerate(post) if p.get("id") == victim["id_a"])
        tampered = list(post)
        tampered[idx] = {**post[idx], "title": post[idx]["title"] + " Marketing"}
        s, _, edited = dp.resolve_labels(tampered, gt)
        self.assertEqual(len(edited), len(base_ed) + 1, "a materially changed title went undetected")
        self.assertIn(victim["k"], {e["k"] for e in edited})
        self.assertNotIn(victim["k"], {r["k"] for r in s})
        self.assertEqual(len(s), len(base) - 1)
        share = len(edited) / (2 * len(s) + len(edited))
        self.assertLessEqual(share, dp.MAX_EDITED_ENDPOINT_FRACTION,
                             "one edited advert must not reach the abort ceiling")

    def test_a_formatting_only_edit_keeps_its_pair(self):
        """`norm()` deliberately strips "(Full-Time)" and friends: this script's
        whole thesis is that such differences do not change what a posting is.
        Calling the same edit a broken identity would be incoherent."""
        post, gt = _corpus(), _labels()
        base, _, base_ed = dp.resolve_labels(post, gt)
        idx = next(i for i, p in enumerate(post) if p.get("id") == base[0]["id_a"])
        tampered = list(post)
        tampered[idx] = {**post[idx], "title": post[idx]["title"] + " (Full-Time)"}
        s, expired, edited = dp.resolve_labels(tampered, gt)
        self.assertEqual(len(edited), len(base_ed),
                         "a formatting-only edit was treated as a changed posting")
        self.assertEqual(len(s), len(base))

    def test_wholesale_id_reuse_is_still_fatal(self):
        """The case the original guard was built for. One edit is noise; a
        provider recycling its id space is not, and then the endpoints that did
        NOT visibly change are suspect too."""
        post, gt = _corpus(), _labels()
        targets = {r[f"id_{s}"] for r in gt["pairs"] for s in ("a", "b")}
        tampered = [{**p, "title": "Chief Financial Officer", "company": "Zzz",
                     "company_slug": "zzz"} if p.get("id") in targets else p
                    for p in post]
        s, _, edited = dp.resolve_labels(tampered, gt)
        share = len(edited) / (2 * len(s) + len(edited))
        self.assertGreater(share, dp.MAX_EDITED_ENDPOINT_FRACTION,
                           f"recycling every labelled id only reached {share:.0%}, "
                           f"below the {dp.MAX_EDITED_ENDPOINT_FRACTION:.0%} abort ceiling")

    def test_a_below_floor_survivor_set_is_refused(self):
        post, gt = _corpus(), _labels()
        s, _, _ = dp.resolve_labels(post, gt)
        by_band = {}
        for r in s:
            by_band.setdefault(dp._band_of(r["cosine"]), []).append(r)
        starved = [r for b, rows in by_band.items() for r in rows[:11]]
        ok, why, _ = dp.floor_verdict(starved)
        self.assertFalse(ok, "11 per band passed a floor of 12")
        self.assertTrue(any(str(dp.MIN_PAIRS_PER_BAND) in w for w in why), why)

    def test_losing_one_band_is_refused_at_eighty_percent_survival(self):
        """The case a total-count floor cannot see: 96 of 120 pairs survive and
        the measurement is meaningless, because 23 of the 32 positives are in
        the band that went."""
        post, gt = _corpus(), _labels()
        s, _, _ = dp.resolve_labels(post, gt)
        top_gone = [r for r in s if dp._band_of(r["cosine"]) != 4]
        self.assertGreaterEqual(len(top_gone) / len(s), 0.75)
        ok, why, stats = dp.floor_verdict(top_gone)
        self.assertFalse(ok, f"{len(top_gone)} of {len(s)} pairs passed the floor with a band empty")
        self.assertEqual(stats["per_band"]["4"], 0)

    def test_a_one_sided_survivor_set_is_refused(self):
        """Note which floor does the work here: the BAND floor. These sets are
        also band-starved, so they do not demonstrate the class floor — see
        test_the_class_floor_fires_on_its_own for that."""
        post, gt = _corpus(), _labels()
        s, _, _ = dp.resolve_labels(post, gt)
        for name, subset in (("all positive", [r for r in s if r["same_job"]]),
                             ("all negative", [r for r in s if not r["same_job"]])):
            with self.subTest(subset=name):
                ok, why, _ = dp.floor_verdict(subset)
                self.assertFalse(ok, f"a {name} survivor set passed the floor")

    def test_the_class_floor_fires_on_its_own(self):
        """Every band full, only the class balance wrong. Without this,
        disabling MIN_PAIRS_PER_CLASS entirely left every test green — the
        one-sided sets above are caught by the band floor and their names took
        the credit. Adversarial review, package 18."""
        one_sided = []
        for b, (lo, _hi) in enumerate(dp.GT_BANDS):
            for n in range(24):
                one_sided.append({"k": len(one_sided), "cosine": lo + 0.005,
                                  "same_job": b == 0 and n < 8})
        ok, why, stats = dp.floor_verdict(one_sided)
        self.assertFalse(ok, "a set with every band full but 8 positives passed the floor")
        self.assertEqual(len(why), 1, f"the band floor also fired, so this proves nothing: {why}")
        self.assertIn("same_job=True", why[0])
        self.assertTrue(all(v >= dp.MIN_PAIRS_PER_BAND for v in stats["per_band"].values()))

    def test_the_class_floor_barely_binds_on_this_label_file(self):
        """Stated because the code says so and a claim like that must be
        checkable: with the band floor at 12 and package 15's stratification,
        the class floor almost never binds. The worst constructible case
        reaches 11 positives; random band-satisfying sets do not reach it."""
        gt = _labels()
        by_band = {}
        for r in gt["pairs"]:
            by_band.setdefault(dp._band_of(r["cosine"]), []).append(r)
        worst = []
        for b, rows in by_band.items():
            worst += sorted(rows, key=lambda r: r["same_job"])[:dp.MIN_PAIRS_PER_BAND]
        n_true = sum(1 for r in worst if r["same_job"])
        self.assertLess(n_true, dp.MIN_PAIRS_PER_CLASS,
                        "the constructed worst case no longer trips the class floor")
        ok, why, _ = dp.floor_verdict(worst)
        self.assertFalse(ok)
        self.assertTrue(any("same_job=True" in w for w in why), why)

    def test_the_floor_is_not_satisfiable_by_duplicating_one_pair(self):
        """A degenerate set that meets every count without carrying any
        information: the same pair repeated. It has one band and one class, so
        both floors must catch it."""
        post, gt = _corpus(), _labels()
        s, _, _ = dp.resolve_labels(post, gt)
        ok, why, _ = dp.floor_verdict([dict(s[0]) for _ in range(1000)])
        self.assertFalse(ok, "1,000 copies of one pair satisfied the floor")


class TestTheVerdictIsActuallyENFORCED(unittest.TestCase):
    """floor_verdict() was thoroughly tested in isolation and the line that
    makes its verdict matter was not covered at all — adversarial review
    deleted `raise SystemExit(2)` from run() twice and from the edited-share
    check once, and every test stayed green. These drive run() itself."""

    def _refuses_with(self, corpus, labels, expected_phrase):
        """Point run() at a constructed corpus and assert it refuses FOR THE
        STATED REASON.

        Asserting only `SystemExit(2)` is not enough and an earlier version of
        these tests did exactly that: delete the floor's `raise` and the run
        carries on to the threshold-stability check, which also exits 2, so the
        test passes while the guard it names is gone. Adversarial review found
        three such mutations surviving. The message is the path."""
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "postings.json").write_text(
                json.dumps({"data": {"postings": corpus}}), encoding="utf-8")
            lab = tmp / "labels.json"
            lab.write_text(json.dumps(labels), encoding="utf-8")
            old_p, old_l = dp.PROCESSED, dp.LABELS
            dp.PROCESSED, dp.LABELS = tmp, lab
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    dp.run()
            except SystemExit as e:
                self.assertEqual(e.code, 2, buf.getvalue()[-800:])
            else:
                self.fail(f"run() did not refuse.\n{buf.getvalue()[-800:]}")
            finally:
                dp.PROCESSED, dp.LABELS = old_p, old_l
            out = buf.getvalue()
        # The LAST fatal is the one that stopped the run. Matching anywhere in
        # the output is not enough: each guard logs before it raises, so
        # deleting a `raise` leaves its message in the log while a later guard
        # does the exiting — and the test passes over the hole. Adversarial
        # review's `edited-share SystemExit deleted` mutation survived exactly
        # that way.
        fatals = [ln for ln in out.splitlines() if "FATAL:" in ln]
        self.assertTrue(fatals, f"refused with no FATAL line.\n{out[-900:]}")
        self.assertIn(expected_phrase, fatals[-1],
                      f"refused, but the guard that stopped it was not the one under test.\n"
                      f"last fatal: {fatals[-1]}\nall fatals: {fatals}")
        return out

    def _corpus_and_labels(self, n_per_band=24):
        """A synthetic corpus whose labelled pairs sit at known cosines."""
        corpus, pairs, k = [], [], 0
        for b, (lo, _hi) in enumerate(dp.GT_BANDS):
            for n in range(n_per_band):
                a = {"id": f"a{k}", "title": f"Engineer {k}", "company": "Acme",
                     "location_raw": "NY"}
                bb = {"id": f"b{k}", "title": f"Engineer {k} Senior", "company": "Acme",
                      "location_raw": "NY"}
                corpus += [a, bb]
                pairs.append({"k": k, "cosine": lo + 0.005, "same_job": b == 4,
                              "i": 2 * k, "j": 2 * k + 1,
                              "id_a": a["id"], "occ_a": 0, "id_b": bb["id"], "occ_b": 0,
                              "a": dp.display_of(a), "b": dp.display_of(bb)})
                k += 1
        return corpus, {"n": len(pairs), "pairs": pairs}

    def test_run_exits_two_when_the_floor_is_not_met(self):
        corpus, labels = self._corpus_and_labels(n_per_band=24)
        # remove every endpoint of one whole band: bands go 0/24/24/24/24
        drop = {p["id_a"] for p in labels["pairs"] if dp._band_of(p["cosine"]) == 0}
        drop |= {p["id_b"] for p in labels["pairs"] if dp._band_of(p["cosine"]) == 0}
        starved = [r for r in corpus if r["id"] not in drop]
        self._refuses_with(starved, labels, "too few labelled pairs survive")

    def test_run_exits_two_when_too_many_endpoints_were_edited(self):
        """Edited above the ceiling, but the survivors still clear BOTH floors —
        otherwise the floor takes the credit and deleting this check changes
        nothing, which is exactly what adversarial review demonstrated.

        share = E / (240 - E) for E edits in E distinct pairs, so E must exceed
        48 to pass 25%. 49 edits spread 10/10/10/10/9 leave bands at
        14/14/14/14/15 and 15 positives."""
        corpus, labels = self._corpus_and_labels(n_per_band=24)
        per_band = {0: 10, 1: 10, 2: 10, 3: 10, 4: 9}
        hit, seen = set(), Counter()
        for p in labels["pairs"]:
            b = dp._band_of(p["cosine"])
            if seen[b] < per_band[b]:
                seen[b] += 1
                hit.add(p["id_a"])
        self.assertEqual(len(hit), 49)
        edited_corpus = [{**r, "title": "Chief Financial Officer"} if r["id"] in hit else r
                         for r in corpus]
        s, _, edited = dp.resolve_labels(edited_corpus, labels)
        share = len(edited) / (2 * len(s) + len(edited))
        self.assertGreater(share, dp.MAX_EDITED_ENDPOINT_FRACTION,
                           f"only {share:.1%} edited — below the ceiling, so this proves nothing")
        ok, why, _ = dp.floor_verdict(s)
        self.assertTrue(ok, f"the survivors fail the floor, so the floor would take the credit: {why}")
        self._refuses_with(edited_corpus, labels, "point at materially different content")

    def test_run_exits_two_when_the_sample_selects_a_different_threshold(self):
        """The consequence the floor exists to prevent: a survivor set that
        picks a threshold other than the one the shipped clusters were built at
        changes how many rows get removed. Constructed so that BOTH floors pass
        — every band has 24, and the classes are 24 True / 96 False — leaving
        the threshold check as the only thing that can refuse."""
        _, labels = self._corpus_and_labels(n_per_band=24)
        corpus = []
        for p in labels["pairs"]:
            # every labelled pair is an exact-key duplicate, so it is clustered
            # together at EVERY threshold; only the top band is labelled a true
            # duplicate, so the rest are false positives everywhere and no
            # threshold can reach precision 0.95.
            a = {"id": p["id_a"], "title": f"Engineer {p['k']}", "company": "Acme",
                 "location_raw": "NY"}
            b = {"id": p["id_b"], "title": f"Engineer {p['k']}", "company": "Acme",
                 "location_raw": "NY"}
            p["same_job"] = dp._band_of(p["cosine"]) == 4
            p["a"], p["b"] = dp.display_of(a), dp.display_of(b)
            corpus += [a, b]
        out = self._refuses_with(corpus, labels, "selects threshold")
        self.assertIn("not the 0.98", out)


class TestThePerBandFloorIsNotJustATotal(unittest.TestCase):
    """Adversarial review replaced the per-band check with a total-count check
    of 12x5=60 and every test still passed. This is the case that separates
    them: a set well above any total, with one band empty and both classes
    healthy, so neither the total nor the class floor can take the credit."""

    def test_a_set_above_the_equivalent_total_is_still_refused(self):
        mixed = []
        for b, (lo, _hi) in enumerate(dp.GT_BANDS):
            for n in range(24):
                mixed.append({"k": len(mixed), "cosine": lo + 0.005, "same_job": n % 2 == 0})
        starved = [r for r in mixed if dp._band_of(r["cosine"]) != 0]
        ok, why, stats = dp.floor_verdict(starved)
        self.assertGreater(stats["n_surviving"], dp.MIN_PAIRS_PER_BAND * len(dp.GT_BANDS),
                           "this set does not exceed the equivalent total, so it proves nothing")
        self.assertGreaterEqual(stats["same_job_true"], dp.MIN_PAIRS_PER_CLASS)
        self.assertGreaterEqual(stats["same_job_false"], dp.MIN_PAIRS_PER_CLASS)
        self.assertFalse(ok, "a set with 96 pairs and one empty band passed the floor")
        self.assertEqual(len(why), 1, f"another floor also fired, so this proves nothing: {why}")
        self.assertIn("band", why[0])


class TestTheReportedFiguresNameTheirN(unittest.TestCase):
    def test_the_eval_artifact_states_the_n_it_was_tuned_on(self):
        path = SCRIPTS.parent / "data" / "quality_history" / "dedupe_eval.json"
        if not path.exists():
            self.skipTest("dedupe_eval.json not built")
        doc = json.loads(path.read_text(encoding="utf-8"))
        meta = doc.get("meta", doc)
        self.assertIn("tuned_on_n_pairs", meta)
        lc = meta["label_corpus_integrity"]
        self.assertEqual(meta["tuned_on_n_pairs"], lc["n_pairs_surviving"])
        self.assertEqual(lc["keyed_by"], "(id, occurrence)")
        # the floor it was accepted under travels with the figure
        self.assertEqual(lc["floor"]["per_band"], dp.MIN_PAIRS_PER_BAND)
        self.assertEqual(lc["floor"]["per_class"], dp.MIN_PAIRS_PER_CLASS)
        self.assertEqual(sum(int(v) for v in lc["per_band_surviving"].values()),
                         lc["n_pairs_surviving"])


if __name__ == "__main__":
    unittest.main()


class TestTheGroundTruthMustBeWellFormed(unittest.TestCase):
    """A malformed label file must say so, not degrade into "everything
    expired" — the sample would shrink for a reason that has nothing to do
    with the corpus, and the floor would eventually refuse for the wrong
    reason. Adversarial review, package 18."""

    def setUp(self):
        self.post = _corpus()
        self.gt = _labels()

    def test_a_missing_id_is_an_error_not_an_expiry(self):
        broken = {**self.gt, "pairs": [{**self.gt["pairs"][0], "id_a": None}]}
        with self.assertRaises(ValueError) as cm:
            dp.resolve_labels(self.post, broken)
        self.assertIn("has no id_a", str(cm.exception))

    def test_a_negative_occurrence_is_an_error(self):
        """`idxs[-1]` silently indexes from the END of the id's row list, which
        resolves to a real row that is not the labelled one."""
        broken = {**self.gt, "pairs": [{**self.gt["pairs"][0], "occ_a": -1}]}
        with self.assertRaises(ValueError) as cm:
            dp.resolve_labels(self.post, broken)
        self.assertIn("non-negative integer", str(cm.exception))

    def test_a_non_integer_occurrence_is_an_error(self):
        for bad in ("0", 1.5, True):
            with self.subTest(occ=bad):
                broken = {**self.gt, "pairs": [{**self.gt["pairs"][0], "occ_b": bad}]}
                with self.assertRaises(ValueError):
                    dp.resolve_labels(self.post, broken)

    def test_the_committed_label_file_has_no_duplicate_endpoint_pair(self):
        """Two pairs resolving to the same row pair would be scored once by the
        tuning and counted twice by n."""
        s, _, _ = dp.resolve_labels(self.post, self.gt)
        keys = [(r["_i"], r["_j"]) for r in s]
        self.assertEqual(len(set(keys)), len(keys))
        self.assertFalse(any(i == j for i, j in keys), "a pair resolves to one row twice")


class TestTheRekeyScriptItself(unittest.TestCase):
    """`rekey_dedupe_labels.py` had no tests at all and is what produced the
    file everything else depends on."""

    def test_it_reproduces_the_key_for_every_pair_that_still_resolves(self):
        """Re-running the migration must be idempotent for the pairs still in
        the corpus. It resolves by id first now — `i`/`j` are the array
        positions the pair was labelled at and point at unrelated rows after a
        single harvest, which made the script un-rerunnable the moment the
        weekly refresh started working."""
        import rekey_dedupe_labels as rk
        post, gt = _corpus(), _labels()
        kept, dropped, stats = rk.rekey(post, gt)
        by_k = {r["k"]: r for r in gt["pairs"]}
        self.assertTrue(kept)
        for a in kept:
            b = by_k[a["k"]]
            self.assertEqual((a["id_a"], a["occ_a"]), (b["id_a"], b["occ_a"]))
            self.assertEqual((a["id_b"], a["occ_b"]), (b["id_b"], b["occ_b"]))
        # whatever it kept must be exactly what the runtime guard keeps
        survivors, _, _ = dp.resolve_labels(post, gt)
        self.assertEqual({r["k"] for r in kept}, {r["k"] for r in survivors})
        self.assertEqual(stats["pairs_rekeyed"] + stats["pairs_dropped"], stats["pairs_in"])

    def test_it_refuses_to_write_a_partial_file(self):
        """A ground truth describing a different sample than the threshold was
        chosen on is worse than none, so a single unresolved endpoint must stop
        the whole write."""
        import contextlib
        import io
        import rekey_dedupe_labels as rk
        post, gt = _corpus(), _labels()
        broken = {**gt, "pairs": [{**gt["pairs"][0], "id_a": "does:not:exist"}] + gt["pairs"][1:]}
        kept, dropped, stats = rk.rekey(post, broken)
        self.assertTrue(any(d["k"] == gt["pairs"][0]["k"] for d in dropped))
        self.assertLess(stats["pairs_rekeyed"], stats["pairs_in"])

        # and run() must refuse rather than write, on any corpus where a label
        # no longer resolves — which is every corpus after a refresh
        survivors, _, _ = dp.resolve_labels(post, gt)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = rk.run(check_only=True)
        if len(survivors) == len(gt["pairs"]):
            self.assertEqual(code, 0, buf.getvalue()[-400:])
        else:
            self.assertEqual(code, 2, "it wrote a partial ground truth")
            self.assertIn("REFUSING to write", buf.getvalue())
