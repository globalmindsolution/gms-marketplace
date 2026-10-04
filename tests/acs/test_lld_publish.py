"""The analysis publish commit carries the ticket's recorded LLD files (ADR-0126).

/acs:create-data-design and /acs:create-flows are Design-phase skills: they run
before the ticket branch exists, leave their `lld/<feature>/...` documents in the
working tree, and record every path they wrote in `states.files`. The first Build
commit -- `acs.py analysis publish` -- stages those paths beside the ticket's docs
folder, and nothing else: only existing files inside the checkout, under an
`lld/` directory, from a COMPLETED result.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_analysis_loop import AnalysisLoopCase  # noqa: E402
from acs_case import lib  # noqa: E402

from acs_lib import analysis_publish as P  # noqa: E402

DATA = "docs/architecture/lld/wishlist/data"
FLOWS = "docs/architecture/lld/wishlist/flows"


class LldPublishCase(AnalysisLoopCase):

    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo] + list(args), capture_output=True,
                              text=True, check=True).stdout

    def put(self, rel, text="# doc\n"):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def record(self, skill, files, status="completed", rdir=None):
        path = lib.step.result_path(rdir or self.r, skill)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"status": status, "summary": "fixture",
                       "states": {"feature": ["wishlist"], "files": files}}, fh)

    def ctx(self):
        return {"checkout_root": self.repo, "workspace": self.ws, "repo_id": "acme-shop"}

    def committed(self):
        return sorted(self.git("show", "--name-only", "--format=", "HEAD").split())


class TestPublishCarriesRecordedLld(LldPublishCase):

    def test_recorded_lld_files_ride_the_analysis_commit_and_nothing_else(self):
        self.put(DATA + "/logical-erd.md")
        self.put(DATA + "/physical-schema.md")
        self.put(FLOWS + "/checkout.md")
        self.put("src/app.py", "print(1)\n")                       # recorded, not lld
        self.put("docs/architecture/lld/other/data/logical-erd.md")  # lld, not recorded
        outside = os.path.join(self.tmp, "lld", "escape.md")         # outside the checkout
        os.makedirs(os.path.dirname(outside))
        with open(outside, "w") as fh:
            fh.write("x\n")
        self.record("create-data-design", [
            DATA + "/logical-erd.md", DATA + "/physical-schema.md", "src/app.py",
            DATA + "/missing.md", "../lld/escape.md", "", 7])
        self.record("create-flows", [FLOWS + "/checkout.md", DATA + "/logical-erd.md"])
        self.to_publish()
        out = self.cli("publish")
        tid = self.tid
        self.assertEqual(self.committed(), sorted([
            "docs/tickets/%s/analysis.md" % tid,
            DATA + "/logical-erd.md", DATA + "/physical-schema.md", FLOWS + "/checkout.md"]))
        self.assertEqual(out["publication"]["lld_files"], [
            DATA + "/logical-erd.md", DATA + "/physical-schema.md", FLOWS + "/checkout.md"])
        untracked = self.git("status", "--porcelain")
        self.assertIn("src/", untracked)
        self.assertIn("docs/architecture/lld/other/", untracked)
        self.assertEqual(self.cli("record-publication")["next"]["action"], "completed")

    def test_a_result_that_did_not_complete_stages_nothing(self):
        self.put(DATA + "/logical-erd.md")
        self.record("create-data-design", [DATA + "/logical-erd.md"], status="failed")
        self.to_publish()
        out = self.cli("publish")
        self.assertEqual(self.committed(), ["docs/tickets/%s/analysis.md" % self.tid])
        self.assertEqual(out["publication"]["lld_files"], [])

    def test_no_design_results_is_the_docs_folder_commit_as_before(self):
        self.to_publish()
        out = self.cli("publish")
        self.assertEqual(self.committed(), ["docs/tickets/%s/analysis.md" % self.tid])
        self.assertEqual(out["publication"]["lld_files"], [])

    def test_an_lld_change_alone_still_commits_on_republish(self):
        self.to_publish()
        self.cli("publish")
        self.put(FLOWS + "/checkout.md")
        self.record("create-flows", [FLOWS + "/checkout.md"])
        out = self.cli("publish")
        self.assertTrue(out["publication"]["committed"])
        self.assertEqual(self.committed(), [FLOWS + "/checkout.md"])


class TestRecordedLldFiles(LldPublishCase):

    def test_results_in_the_tickets_own_run_are_found_from_another_run(self):
        self.put(DATA + "/logical-erd.md")
        self.record("create-data-design", [DATA + "/logical-erd.md"])
        other = tempfile.mkdtemp(prefix="acs-other-run-")
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", other]))
        found = P.recorded_lld_files(other, self.ctx(), self.tid)
        self.assertEqual(found, [os.path.realpath(os.path.join(self.repo, DATA,
                                                               "logical-erd.md"))])

    def test_sorted_deduplicated_and_lld_must_be_a_directory(self):
        self.put(FLOWS + "/b.md")
        self.put(FLOWS + "/a.md")
        self.put("docs/lld")  # a FILE named lld is not an lld/ directory
        self.record("create-flows", [FLOWS + "/b.md", FLOWS + "/a.md", FLOWS + "/b.md",
                                     "docs/lld"])
        found = P.recorded_lld_files(self.r, self.ctx(), self.tid)
        self.assertEqual([os.path.basename(p) for p in found], ["a.md", "b.md"])

    def test_no_checkout_root_means_nothing(self):
        self.put(FLOWS + "/a.md")
        self.record("create-flows", [FLOWS + "/a.md"])
        self.assertEqual(P.recorded_lld_files(self.r, {}, self.tid), [])

    def test_a_malformed_result_is_ignored(self):
        path = lib.step.result_path(self.r, "create-flows")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write('{"status": "completed", "states": {"files": "lld/x.md"}}')
        self.assertEqual(P.recorded_lld_files(self.r, self.ctx(), self.tid), [])


if __name__ == "__main__":
    unittest.main()
