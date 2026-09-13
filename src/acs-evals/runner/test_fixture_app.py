#!/usr/bin/env python3
"""Self-test for the fixture app: it must rebuild byte-for-byte, deterministically,
with a green test suite at HEAD, and its hash must be the one scenarios.json pins."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fixture_app as fx  # noqa: E402


def _log(repo, *args):
    return subprocess.run(["git", "log"] + list(args), cwd=repo, capture_output=True,
                          text=True, check=True).stdout


class FixtureAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="acs-fixture-test-")
        cls.repo = os.path.join(cls.tmp, "one")
        cls.head = fx.build(cls.repo)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_history_has_thirty_plus_commits_and_a_revert(self):
        subjects = _log(self.repo, "--format=%s").splitlines()
        self.assertGreaterEqual(len(subjects), 30)
        self.assertTrue(any(s.startswith('Revert "') for s in subjects))

    def test_build_is_deterministic(self):
        again = fx.build(os.path.join(self.tmp, "two"))
        self.assertEqual(again, self.head)

    def test_tests_are_green_at_head(self):
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                              cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr[-1500:])

    def test_hash_is_pinned_in_scenarios(self):
        self.assertEqual(fx.fixture_hash(), fx.recorded_hash())

    def test_every_tree_file_is_added_exactly_once(self):
        with open(fx.HISTORY) as fh:
            history = json.load(fh)
        added = [f for c in history["commits"] for f in c.get("files", [])]
        self.assertEqual(sorted(added), sorted(set(added)))
        self.assertEqual(sorted(added), sorted(fx.tree_files()))

    def test_the_payments_path_exists_for_the_stakes_trigger(self):
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "orders", "payments", "gateway.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "docs", "api.md")))


if __name__ == "__main__":
    unittest.main()
