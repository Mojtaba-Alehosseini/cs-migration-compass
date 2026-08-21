"""Package 14, Tier 4.1/4.2 — regression tests for the external audit's
Finding 4: DATA-QUALITY.md reported "Overall: PASSING" while its own
Snapshot module said COULD NOT RUN (a real TypeError,
generate_data_quality_doc.py calling snapshot_stats.main(append=...) when
the live main() had no such parameter — described as fixed in an earlier
package's own report, but never actually landed in the file). Two distinct
bugs, two distinct tests: the crash itself (4.1) and the overall-status
computation that let a crash still say "PASSING" (4.2).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import generate_data_quality_doc as gen  # noqa: E402
import snapshot_stats  # noqa: E402


class TestSnapshotStatsAcceptsAppendFalse(unittest.TestCase):
    """Tier 4.1 — calls the REAL snapshot_stats.main(), the same way
    generate_data_quality_doc.py's own _run_module() does, not a
    reimplementation of the call. This is the exact call that raised
    TypeError: main() got an unexpected keyword argument 'append' before
    this fix — reproduced live against the real file, not assumed from the
    traceback text alone, before landing the fix."""

    def test_main_accepts_append_false_without_raising(self):
        try:
            snapshot_stats.main(append=False)
        except TypeError as exc:
            self.fail(f"snapshot_stats.main(append=False) raised {exc!r} — the Tier 4.1 fix regressed")

    def test_append_false_does_not_grow_the_history_file(self):
        history_before = snapshot_stats.load_history()
        snapshot_stats.main(append=False)
        history_after = snapshot_stats.load_history()
        self.assertEqual(len(history_before), len(history_after),
                          "append=False must never write a real entry to snapshots.jsonl — "
                          "this is finding L16 (package 13) recurring")


class TestRunModuleReportsACrashHonestly(unittest.TestCase):
    """Tier 4.1's own general case: _run_module() must render a broken
    module's failure, never let it look like a clean pass. Uses a real,
    nonexistent module name to exercise the REAL __import__ failure path
    inside _run_module() itself, not a mock standing in for it."""

    def test_a_module_that_cannot_be_imported_is_marked_could_not_run(self):
        result = gen._run_module("Fake — a module that does not exist", "this_module_does_not_exist_xyz",
                                  "python -c 'pass'")
        self.assertFalse(result["ran"])
        self.assertIsNotNone(result["exception"])
        self.assertEqual(result["errors"], [])  # nothing to sum — it never got that far


class TestOverallStatusCountsAnUnrunModuleAsFailing(unittest.TestCase):
    """Tier 4.2's own explicit instruction: "add a test that constructs a
    crashing module and asserts the overall status is not PASSING." Calls
    overall_status() directly with a hand-built results list shaped
    exactly like _run_module()'s own real return value — this is the
    computation that the old code got wrong (a crashed module's own empty
    ERRORS list contributed zero, so total_errors alone could stay 0)."""

    def _clean(self) -> dict:
        return {"ran": True, "exception": None, "errors": [], "warnings": [], "flags": [], "drops": []}

    def _crashed(self) -> dict:
        return {"ran": False, "exception": "Traceback ...\nTypeError: boom", "errors": [], "warnings": [],
                "flags": [], "drops": []}

    def test_all_clean_modules_report_passing(self):
        overall, errors, flags, unverified = gen.overall_status([self._clean(), self._clean()])
        self.assertEqual(overall, "PASSING")
        self.assertEqual(unverified, 0)

    def test_one_crashed_module_among_clean_ones_is_not_passing(self):
        # The exact real-world shape this bug shipped with: three clean
        # modules (Validate, Audit with flags-only, Reconcile) and one that
        # could not run (Snapshot) — DATA-QUALITY.md's own real table the
        # day the audit found this.
        results = [self._clean(), self._clean(), self._clean(), self._crashed()]
        overall, errors, flags, unverified = gen.overall_status(results)
        self.assertNotEqual(overall, "PASSING")
        self.assertEqual(overall, "FAILING")
        self.assertEqual(unverified, 1)
        self.assertEqual(errors, 0)  # the crashed module contributes 0 to error COUNT...

    def test_a_module_with_real_errors_still_counts_them_separately_from_unverified(self):
        with_errors = self._clean()
        with_errors["errors"] = ["a real error"]
        overall, errors, flags, unverified = gen.overall_status([with_errors, self._crashed()])
        self.assertEqual(overall, "FAILING")
        self.assertEqual(errors, 1)
        self.assertEqual(unverified, 1)


if __name__ == "__main__":
    unittest.main()
