#!/usr/bin/env python3
"""Self-test for the catch-rate judge (pure) and the runner's dry run."""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verifier_catch_rate import judge  # noqa: E402

SEC = {"dimension": "Security", "expected_severity": "blocking"}
DOC = {"dimension": "Documentation", "expected_severity": "info"}


def verdict(*findings):
    return {"findings": [{"severity": s, "dimension": d, "detail": "x"} for s, d in findings]}


class JudgeTest(unittest.TestCase):
    def test_blocking_finding_on_the_dimension_is_a_catch(self):
        caught, matched = judge(SEC, [verdict(("blocking", "security"))])
        self.assertTrue(caught)
        self.assertEqual(matched[0]["severity"], "blocking")

    def test_info_does_not_satisfy_an_expected_blocking(self):
        self.assertFalse(judge(SEC, [verdict(("info", "security"))])[0])

    def test_blocking_satisfies_an_expected_info(self):
        self.assertTrue(judge(DOC, [verdict(("blocking", "documentation"))])[0])
        self.assertTrue(judge(DOC, [verdict(("info", "documentation"))])[0])

    def test_other_dimensions_do_not_count(self):
        self.assertFalse(judge(SEC, [verdict(("blocking", "tests"), ("blocking", "quality"))])[0])

    def test_no_verdict_is_a_miss(self):
        self.assertFalse(judge(SEC, [])[0])

    def test_dry_run_spends_nothing(self):
        here = os.path.dirname(os.path.abspath(__file__))
        proc = subprocess.run([sys.executable, os.path.join(here, "verifier_catch_rate.py"), "--dry-run"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("7 defect(s) x 1 run(s)", proc.stdout)
        self.assertIn("nothing spent", proc.stdout)


if __name__ == "__main__":
    unittest.main()
