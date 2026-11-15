"""ADR-0148: /acs:setup scaffolds the document templates into .acs/templates/.

Every built-in template is copied, with templates.lock.json recording the
built-in hash each copy came from; a re-run refreshes a copy nobody edited
when the built-in moved on, never overwrites an edited one, and flags an
edited one whose built-in moved on as drift.

Run:  python3 -m unittest tests.acs.test_doc_templates -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, SCRIPTS  # noqa: E402

sys.path.insert(0, SCRIPTS)
from acs_lib import doc_templates  # noqa: E402

PLUGIN = os.path.dirname(os.path.dirname(SCRIPTS))
EXPECTED = {"audit-design-report", "audit-security-report", "bug-default", "design-default",
            "epic-default", "pr-default", "prd-default", "prd-feature-default",
            "story-default", "task-default"}


class ScaffoldTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-templates-repo-")
        self.plugin = tempfile.mkdtemp(prefix="acs-templates-plugin-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(shutil.rmtree, self.plugin, True)
        shutil.copytree(os.path.join(PLUGIN, "templates"), os.path.join(self.plugin, "templates"))

    def scaffold(self, **kw):
        return doc_templates.scaffold(self.root, self.plugin, **kw)

    def path(self, name):
        return os.path.join(self.root, ".acs", "templates", name + ".md")

    def builtin(self, name):
        return os.path.join(self.plugin, "templates", name + ".md")

    def test_every_builtin_document_template_and_no_ci_file(self):
        self.assertEqual(set(doc_templates.builtin_names(PLUGIN)), EXPECTED)

    def test_scaffold_copies_every_template_and_locks_it(self):
        done = self.scaffold()
        self.assertEqual(len(done["added"]), len(EXPECTED))
        self.assertIn(".acs/templates/templates.lock.json", done["written"])
        with open(self.path("prd-default")) as a, open(self.builtin("prd-default")) as b:
            self.assertEqual(a.read(), b.read())
        lock = json.load(open(os.path.join(self.root, ".acs", "templates",
                                           "templates.lock.json")))["templates"]
        self.assertEqual(set(lock), EXPECTED)
        again = self.scaffold()
        self.assertEqual((again["written"], len(again["unchanged"])), ([], len(EXPECTED)))

    def test_dry_run_writes_nothing(self):
        done = self.scaffold(dry_run=True)
        self.assertEqual(len(done["added"]), len(EXPECTED))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".acs")))

    def test_an_untouched_copy_follows_the_builtin(self):
        self.scaffold()
        with open(self.builtin("pr-default"), "a") as fh:
            fh.write("\n## New section\n")
        done = self.scaffold()
        self.assertEqual(done["refreshed"], [".acs/templates/pr-default.md"])
        self.assertIn("## New section", open(self.path("pr-default")).read())
        self.assertEqual(self.scaffold()["refreshed"], [])

    def test_an_edited_copy_is_kept_and_drift_is_flagged(self):
        self.scaffold()
        with open(self.path("pr-default"), "a") as fh:
            fh.write("\n## Ours\n")
        done = self.scaffold()
        self.assertEqual((done["customised"], done["drift"]),
                         ([".acs/templates/pr-default.md"], []))
        with open(self.builtin("pr-default"), "a") as fh:
            fh.write("\n## Theirs\n")
        done = self.scaffold()
        self.assertEqual(done["drift"], [".acs/templates/pr-default.md"])
        text = open(self.path("pr-default")).read()
        self.assertIn("## Ours", text)
        self.assertNotIn("## Theirs", text)

    def test_a_hand_made_copy_is_the_teams(self):
        os.makedirs(os.path.dirname(self.path("design-default")))
        with open(self.path("design-default"), "w") as fh:
            fh.write("## Decision\n")
        done = self.scaffold()
        self.assertIn(".acs/templates/design-default.md", done["customised"])
        self.assertEqual(open(self.path("design-default")).read(), "## Decision\n")
        states = {s["name"]: s["state"] for s in doc_templates.status(self.root, self.plugin)}
        self.assertEqual(states["design-default"], "unrecorded")
        self.assertEqual(states["pr-default"], "untouched")


class SetupApplyTest(AcsWorkspaceCase):

    def apply(self, answers):
        out = self.run_script("acs.py", "setup", "apply", "--answers", "-",
                              stdin=json.dumps(answers))
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_templates_true_scaffolds_and_stages(self):
        out = self.apply({"templates": True})
        self.assertEqual(len(out["templates"]["added"]), len(EXPECTED))
        self.assertIn(".acs/templates/templates.lock.json", out["stage_for_commit"])
        self.assertIn(".acs/templates/prd-default.md", out["stage_for_commit"])

    def test_absent_answer_refreshes_only_an_existing_scaffold(self):
        self.assertIsNone(self.apply({})["templates"])
        self.assertFalse(os.path.isdir(os.path.join(self.repo, ".acs", "templates")))
        self.apply({"templates": True})
        self.assertEqual(len(self.apply({})["templates"]["unchanged"]), len(EXPECTED))
        self.assertIsNone(self.apply({"templates": False})["templates"])

    def test_a_non_boolean_answer_is_refused(self):
        out = self.run_script("acs.py", "setup", "apply", "--answers", "-",
                              stdin=json.dumps({"templates": "yes"}))
        self.assertNotEqual(out.returncode, 0)

    def test_detect_reports_the_template_states(self):
        out = self.run_script("acs.py", "setup", "detect")
        states = {t["name"]: t["state"] for t in json.loads(out.stdout)["templates"]}
        self.assertEqual(set(states), EXPECTED)
        self.assertEqual(set(states.values()), {"missing"})


if __name__ == "__main__":
    unittest.main()
