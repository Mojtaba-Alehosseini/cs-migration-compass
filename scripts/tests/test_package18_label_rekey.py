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
        after, expired, reused = dp.resolve_labels(post, wrecked)
        self.assertEqual(len(after), len(base))
        self.assertEqual((len(expired), len(reused)), (0, 0))
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
    """The failure this package exists to remove."""

    def setUp(self):
        self.post = _corpus()
        self.gt = _labels()
        self.n = len(self.gt["pairs"])

    def _all_survive(self, corpus, what):
        s, expired, reused = dp.resolve_labels(corpus, self.gt)
        self.assertEqual(len(reused), 0, f"{what}: reported id reuse")
        self.assertEqual(len(expired), 0, f"{what}: reported expiry")
        self.assertEqual(len(s), self.n, f"{what}: only {len(s)} of {self.n} pairs survived")
        return s

    def test_prepending_rows(self):
        extra = [{"id": f"new:{i}", "title": "Warehouse Picker", "company": "Acme",
                  "location_raw": "NY"} for i in range(500)]
        self._all_survive(extra + self.post, "500 rows prepended")

    def test_appending_rows(self):
        extra = [{"id": f"new:{i}", "title": "Barista", "company": "Cafe",
                  "location_raw": "LA"} for i in range(500)]
        self._all_survive(self.post + extra, "500 rows appended")

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
        churned += [{"id": f"fresh:{i}", "title": "Software Engineer", "company": "NewCo",
                     "location_raw": "Berlin"} for i in range(2000)]
        rng.shuffle(churned)

        s, expired, reused = dp.resolve_labels(churned, self.gt)
        self.assertEqual(len(reused), 0, "ordinary churn must never look like id reuse")

        # Which pairs SHOULD have dropped, derived from the churned corpus
        # rather than from the 12 ids deliberately expired -- the random 5%
        # takes labelled rows too, and an earlier version of this test counted
        # only the deliberate ones and blamed the difference on the code.
        have = Counter(p.get("id") for p in churned)
        gone = {r["k"] for r in self.gt["pairs"]
                if have[r["id_a"]] <= r["occ_a"] or have[r["id_b"]] <= r["occ_b"]}
        self.assertTrue(gone, "the churn removed no labelled endpoint at all — not a real test")
        self.assertEqual({r["k"] for r in self.gt["pairs"]} - {r["k"] for r in s}, gone,
                         "the pairs that dropped are not exactly the ones whose postings left")
        self.assertEqual(len(s), self.n - len(gone))
        self.assertGreater(len(expired), 0)

        ok, why, stats = dp.floor_verdict(s)
        self.assertTrue(ok, f"a realistic week of churn broke the floor: {why} ({stats})")


class TestTheGuardCanStillFail(unittest.TestCase):
    """A guard that cannot fail is worse than none. Packages 15, 16 and 17 each
    shipped one, and package 17's own was this script's."""

    def test_id_reuse_is_detected_and_the_pair_does_not_survive(self):
        post, gt = _corpus(), _labels()
        victim = gt["pairs"][0]
        idx = next(i for i, p in enumerate(post) if p.get("id") == victim["id_a"])
        tampered = list(post)
        tampered[idx] = {**post[idx], "title": "Chief Financial Officer"}
        s, _, reused = dp.resolve_labels(tampered, gt)
        self.assertEqual(len(reused), 1, "a changed title on a surviving id went undetected")
        self.assertEqual(reused[0]["k"], victim["k"])
        self.assertNotIn(victim["k"], {r["k"] for r in s})

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
        post, gt = _corpus(), _labels()
        s, _, _ = dp.resolve_labels(post, gt)
        for name, subset in (("all positive", [r for r in s if r["same_job"]]),
                             ("all negative", [r for r in s if not r["same_job"]])):
            with self.subTest(subset=name):
                ok, why, _ = dp.floor_verdict(subset)
                self.assertFalse(ok, f"a {name} survivor set passed the floor")

    def test_the_floor_is_not_satisfiable_by_duplicating_one_pair(self):
        """A degenerate set that meets every count without carrying any
        information: the same pair repeated. It has one band and one class, so
        both floors must catch it."""
        post, gt = _corpus(), _labels()
        s, _, _ = dp.resolve_labels(post, gt)
        ok, why, _ = dp.floor_verdict([dict(s[0]) for _ in range(1000)])
        self.assertFalse(ok, "1,000 copies of one pair satisfied the floor")


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
