"""MAR-587 -- the deterministic golden tier is green, and its docs say so truthfully.

`make -C src/acs-evals eval-source` is `release.pre_release_gate[0]` in
`.acs/settings.json`, but CI runs only `python3 -m unittest discover -s tests`,
so nothing on a pull request ever read that gate. It rotted to 65 failing cases
across a release cycle before anyone looked. These tests run the tier inside the
suite CI does run, so the same drift cannot accumulate unseen again.

They also pin the two claims a reader trusts without re-running anything: that
the run was measured against the build the goldens were recorded against, and
that the tier's own documentation states the case count the dataset actually
carries.

No model, no network, no cost: `run_golden.py` drives the shipped CLI over
sandbox fixtures, and the JSON result is written to a temporary file rather than
the working tree.

Run:  python3 -m unittest tests.acs.test_eval_deterministic_tier_green -v
"""

import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVALS = os.path.join(REPO_ROOT, "src", "acs-evals")
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
CASE_DIR = os.path.join(EVALS, "dataset", "cases")

#: Files whose prose quotes the tier's total. Each is a doc a release reader
#: uses to decide whether a green run means anything.
COUNT_DOCS = (
    os.path.join(EVALS, "README.md"),
    os.path.join(EVALS, "docs", "EVALUATION-PROCESS.md"),
    os.path.join(EVALS, "Makefile"),
)

#: "502 cases", "502 deterministic cases", "all 502 tier-1 cases" -- the forms
#: the tier's own total is written in. Derived from the dataset on every run, so
#: this cannot rot into a hard-coded number the way the prose it guards did.
TOTAL_CLAIM = re.compile(r"\b(\d+)\s+(?:deterministic\s+|tier-1\s+)*cases\b")


def live_case_total():
    """How many cases `dataset/cases/*.json` actually carries right now."""
    total = 0
    for path in sorted(glob.glob(os.path.join(CASE_DIR, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            total += len(json.load(fh).get("cases", []))
    return total


def run_tier():
    """Run the deterministic tier the way `make eval-source` does."""
    handle, json_path = tempfile.mkstemp(suffix=".json", prefix="acs-golden-")
    os.close(handle)
    try:
        env = dict(os.environ, ACS_PLUGIN_ROOT=PLUGIN)
        done = subprocess.run(
            [sys.executable, os.path.join("runner", "run_golden.py"), "--json", json_path],
            cwd=EVALS, env=env, capture_output=True, text=True)
        with open(json_path, encoding="utf-8") as fh:
            return done, json.load(fh)
    finally:
        os.unlink(json_path)


class DeterministicTierIsGreenTest(unittest.TestCase):
    """AC-1: the release gate's first step, run where CI can see it."""

    @classmethod
    def setUpClass(cls):
        cls.done, cls.result = run_tier()

    def test_eval_source_reports_no_failed_case(self):
        failed = [case["id"] for case in self.result["cases"]
                  if case.get("status") not in ("pass", "known")]
        self.assertEqual(self.result["totals"]["failed"], 0,
                         "deterministic tier is not green against src/acs; "
                         "failing cases: %s" % failed)

    def test_the_gate_exits_zero(self):
        self.assertEqual(self.done.returncode, 0,
                         "run_golden.py exited %d:\n%s%s"
                         % (self.done.returncode, self.done.stdout, self.done.stderr))

    def test_every_case_on_disk_was_actually_run(self):
        # A tier that silently stops selecting cases reports a green run over
        # nothing at all, which is the failure mode a pass count cannot show.
        self.assertGreaterEqual(self.result["totals"]["total"], live_case_total())

    def test_the_run_matches_the_recorded_baseline(self):
        # `baseline_match` is false when the build's skill-surface fingerprint
        # differs from `manifest.recorded_against_fingerprint` -- i.e. the
        # goldens pin a build that is not the one under test, so a green run is
        # evidence about the wrong tree.
        self.assertTrue(
            self.result["baseline_match"],
            "the goldens were recorded against a different build than src/acs; "
            "re-stamp dataset/manifest.json's recorded_against_fingerprint")


class TierDocsStateTheLiveCaseCountTest(unittest.TestCase):
    """A documented total that no longer matches the dataset misreports the gate."""

    def test_no_shipped_doc_states_a_stale_case_count(self):
        live = live_case_total()
        stale = []
        for path in COUNT_DOCS:
            with open(path, encoding="utf-8") as fh:
                for number, line in enumerate(fh, 1):
                    for claim in TOTAL_CLAIM.finditer(line):
                        if int(claim.group(1)) != live:
                            stale.append("%s:%d %r"
                                         % (os.path.relpath(path, REPO_ROOT),
                                            number, claim.group(0)))
        self.assertEqual(stale, [],
                         "the tier carries %d cases; these claim otherwise: %s"
                         % (live, stale))


if __name__ == "__main__":
    unittest.main()
