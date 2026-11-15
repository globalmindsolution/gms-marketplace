"""ADR-0147: the PRD doc set is written from templates.

The built-in `prd-default` (the hub) and `prd-feature-default` (a feature's own
PRD) ship in the plugin; a repo's `.acs/templates/<name>.md` replaces either.
A template's `## ` headings are the document's required sections, which
`acs.py prd template` prints for /acs:create-prd to pass on.

Run:  python3 -m unittest tests.acs.test_prd_template -v
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
from acs_lib import prd_template  # noqa: E402
import prd_feature_check  # noqa: E402

PLUGIN = os.path.dirname(os.path.dirname(SCRIPTS))
HUB = ["Vision", "Problem statement", "Target users & personas", "Goals & success metrics",
       "Features (prioritized)", "Non-functional requirements", "Constraints & assumptions",
       "Out of scope"]
FEATURE = ["Summary", "Goals served", "Requirements", "Acceptance criteria", "Dependencies",
           "Out of scope"]


class TemplateTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-prd-template-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def override(self, name, text):
        os.makedirs(os.path.join(self.root, ".acs", "templates"), exist_ok=True)
        with open(os.path.join(self.root, ".acs", "templates", name + ".md"), "w") as fh:
            fh.write(text)

    def test_the_builtins_carry_the_sections_the_skill_always_required(self):
        self.assertEqual(prd_template.builtin_sections("prd"), HUB)
        self.assertEqual(prd_template.builtin_sections("feature"), FEATURE)
        self.assertEqual(prd_feature_check.DEFAULT_FEATURE_SECTIONS, "; ".join(FEATURE))

    def test_a_repo_template_replaces_the_builtin(self):
        self.assertEqual(prd_template.load("feature", self.root, PLUGIN)["source"], "builtin")
        self.override("prd-feature-default",
                      "# <Feature>\n\n## Summary\n\n## Goals served\n\n## Requirements\n\n"
                      "## Rollout\n\n<!-- ## Not a section -->\n")
        found = prd_template.load("feature", self.root, PLUGIN)
        self.assertEqual(found["source"], "repo")
        self.assertEqual(found["sections"], ["Summary", "Goals served", "Requirements", "Rollout"])
        self.assertEqual(found["joined"], "Summary; Goals served; Requirements; Rollout")
        self.assertEqual(found["problems"], [])

    def test_headings_in_comments_and_fences_are_not_sections(self):
        text = "## A\n\n<!--\n## B\n-->\n\n```\n## C\n```\n\n## D\n"
        self.assertEqual(prd_template.sections(text), ["A", "D"])

    def test_a_feature_template_may_not_drop_what_tickets_link(self):
        self.override("prd-feature-default", "## Summary\n\n## Details\n")
        problems = prd_template.load("feature", self.root, PLUGIN)["problems"]
        self.assertEqual(len(problems), 2)
        self.assertIn("Goals served", problems[0])
        self.assertIn("Requirements", problems[1])

    def test_an_empty_or_repeating_template_is_unusable(self):
        self.override("prd-default", "# PRD\n\nno sections\n")
        self.assertIn("no `## ` section", prd_template.load("prd", self.root, PLUGIN)["problems"][0])
        self.override("prd-default", "## Vision\n\n## vision\n")
        self.assertIn("twice", prd_template.load("prd", self.root, PLUGIN)["problems"][0])


class CliTest(AcsWorkspaceCase):

    def template(self, *args):
        return self.run_script("acs.py", "prd", "template", *args)

    def test_reports_both_templates(self):
        out = self.template()
        self.assertEqual(out.returncode, 0, out.stderr)
        found = json.loads(out.stdout)["templates"]
        self.assertEqual([t["kind"] for t in found], ["prd", "feature"])
        self.assertEqual(found[0]["sections"], HUB)
        self.assertTrue(os.path.isabs(found[0]["path"]))
        self.assertTrue(os.path.isfile(found[0]["path"]))

    def test_reports_the_repo_template_repo_relative(self):
        os.makedirs(os.path.join(self.repo, ".acs", "templates"), exist_ok=True)
        with open(os.path.join(self.repo, ".acs", "templates", "prd-default.md"), "w") as fh:
            fh.write("# PRD\n\n## Vision\n\n## Features (prioritized)\n")
        found = json.loads(self.template("--kind", "prd").stdout)["templates"]
        self.assertEqual(found[0]["path"], ".acs/templates/prd-default.md")
        self.assertEqual(found[0]["joined"], "Vision; Features (prioritized)")

    def test_an_unusable_template_exits_2(self):
        os.makedirs(os.path.join(self.repo, ".acs", "templates"), exist_ok=True)
        with open(os.path.join(self.repo, ".acs", "templates",
                               "prd-feature-default.md"), "w") as fh:
            fh.write("## Summary\n")
        out = self.template("--kind", "feature")
        self.assertEqual(out.returncode, 2)
        self.assertIn("ADR-0144", out.stderr)


if __name__ == "__main__":
    unittest.main()
