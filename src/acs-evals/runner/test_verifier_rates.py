#!/usr/bin/env python3
"""Self-test for the verifier finding-rate reader (pure: synthetic verdicts)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verifier_rates import DIMENSIONS, tally  # noqa: E402


def verdict(passed=True, iteration=1, results=None, findings=()):
    dims = [{"id": i, "name": DIMENSIONS[i], "result": (results or {}).get(i, "pass")}
            for i in DIMENSIONS]
    return {"skill": "code", "iteration": iteration, "passed": passed,
            "dimensions": dims, "findings": list(findings)}


class TallyTest(unittest.TestCase):
    def test_counts_results_per_dimension(self):
        docs = [("a", verdict(results={3: "fail", 14: "n/a"})),
                ("b", verdict(results={14: "n/a"}))]
        dims, totals = tally(docs)
        self.assertEqual((dims[3]["pass"], dims[3]["fail"]), (1, 1))
        self.assertEqual(dims[14]["n/a"], 2)
        self.assertEqual(totals["verdicts"], 2)

    def test_findings_map_to_their_dimension_by_name(self):
        docs = [("a", verdict(passed=False, findings=[
            {"severity": "blocking", "dimension": "Tests", "detail": "x"},
            {"severity": "info", "dimension": "documentation", "detail": "y"}]))]
        dims, totals = tally(docs)
        self.assertEqual(dims[2]["blocking"], 1)
        self.assertEqual(dims[11]["info"], 1)
        self.assertEqual((totals["blocking"], totals["info"]), (1, 1))
        self.assertEqual(totals["unmapped_findings"], [])

    def test_an_unmappable_finding_is_listed_not_dropped(self):
        docs = [("a", verdict(findings=[
            {"severity": "info", "dimension": "vibes", "detail": "z"}]))]
        _dims, totals = tally(docs)
        self.assertEqual(len(totals["unmapped_findings"]), 1)

    def test_a_dimension_that_never_failed_is_named(self):
        dims, _ = tally([("a", verdict()), ("b", verdict())])
        self.assertTrue(all(r["never_failed"] for r in dims.values()))
        dims, _ = tally([("a", verdict(results={6: "fail"}))])
        self.assertFalse(dims[6]["never_failed"])

    def test_a_dimension_no_verdict_reported_is_never_reported(self):
        doc = verdict()
        doc["dimensions"] = [d for d in doc["dimensions"] if d["id"] != 16]
        dims, _ = tally([("a", doc)])
        self.assertTrue(dims[16]["never_reported"])
        self.assertFalse(dims[16]["never_failed"])

    def test_other_severities_are_ignored_by_design(self):
        docs = [("a", verdict(findings=[{"severity": "major", "dimension": "Tests"}]))]
        dims, totals = tally(docs)
        self.assertEqual((dims[2]["blocking"], dims[2]["info"], totals["blocking"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
