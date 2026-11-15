"""ADR-0123: an audit skill's report follows its template, and its counts are derived.

acs_lib.audit_report reads the contract from the template itself -- the `## `
sections in order, and the ones marked `<!-- acs:count <key> -->` -- so a repo
that overrides the template changes the contract with it. run_post refuses a
completed audit whose report breaks it, and writes the counted numbers over
whatever the result document claimed.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

from acs_lib import audit_report as A  # noqa: E402

TEMPLATE = """<!--
  header comment with `## ` and `### ` inside it
-->
# Title
## Scope
## High
<!-- acs:count high -->
## Low
<!-- acs:count low -->
<!-- `### <id>` guidance -->
## Notes
"""


class ContractTest(unittest.TestCase):

    def test_the_contract_is_read_from_the_template(self):
        self.assertEqual(A.contract(TEMPLATE),
                         [("Scope", None), ("High", "high"), ("Low", "low"), ("Notes", None)])

    def test_the_built_in_templates_count_what_the_skills_record(self):
        def keys(name):
            with open(os.path.join(PLUGIN, "templates", name), encoding="utf-8") as fh:
                return [k for _t, k in A.contract(fh.read()) if k]
        self.assertEqual(keys("audit-security-report.md"),
                         ["critical", "high", "medium", "low", "advisory", "refuted"])
        self.assertEqual(keys("audit-design-report.md"),
                         ["unimplemented", "planned", "undocumented", "drifted", "unversioned"])

    def test_entries_are_counted_outside_comments_and_fences(self):
        report = ("## Scope\n## High\n### F-1\n```\n### not one\n```\n<!--\n### nor this\n-->\n"
                  "### F-2\n## Low\n_None._\n## Notes\n")
        self.assertEqual(A.check(report, TEMPLATE), ([], {"high": 2, "low": 0}))

    def test_a_missing_or_reordered_section_is_named(self):
        problems, _ = A.check("## High\n## Scope\n## Notes\n", TEMPLATE)
        self.assertIn("section `## Low` is missing", problems)
        self.assertTrue(any("out of the template's order" in p for p in problems))

    def test_a_report_may_add_sections(self):
        self.assertEqual(A.check("## Scope\n## Extra\n## High\n## Low\n## Notes\n", TEMPLATE)[0], [])

    def test_other_skills_have_no_report(self):
        self.assertEqual(A.derive("/nowhere", "code", None, PLUGIN), ([], {}, None))


class PostHookTest(AcsWorkspaceCase):

    def start(self):
        out = self.run_script("acs.py", "step", "start", "--step", "audit-security", "--args", "all")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def report(self, ctx, text):
        path = A.report_path(ctx["partition"], "audit-security")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def post(self, high=0):
        result = {"status": "completed", "summary": "s",
                  "states": {"audit": {"scope": "all", "high": high}}}
        return self.run_script("post-audit-security.py", stdin=json.dumps(result))

    def test_a_completed_audit_without_a_report_is_refused(self):
        self.start()
        out = self.post()
        self.assertEqual(out.returncode, 1)
        self.assertIn("does not follow its template", out.stderr)

    def test_the_counts_are_the_reports(self):
        ctx = self.start()
        self.report(ctx, "## Scope and coverage\n## Summary\n## Critical\n## High\n### F-1 · a\n"
                         "### F-2 · b\n## Medium\n## Low\n## Advisory\n## Refuted\n### F-3 · c\n")
        out = self.post(high=5)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("states.audit", out.stderr)  # the disagreement is reported
        with open(os.path.join(ctx["partition"], "steps", "audit-security", "result.json"),
                  encoding="utf-8") as fh:
            audit = json.load(fh)["states"]["audit"]
        self.assertEqual((audit["high"], audit["refuted"], audit["scope"]), (2, 1, "all"))

    def test_a_repo_template_replaces_the_built_in_one(self):
        ctx = self.start()
        os.makedirs(os.path.join(self.repo, ".acs", "templates"), exist_ok=True)
        with open(os.path.join(self.repo, ".acs", "templates", "audit-security-report.md"),
                  "w", encoding="utf-8") as fh:
            fh.write("## Findings\n<!-- acs:count high -->\n")
        self.report(ctx, "## Findings\n### F-1\n")
        self.assertEqual(self.post(high=1).returncode, 0)


if __name__ == "__main__":
    unittest.main()
