"""MAR-126 (E2E-2) — documentation-conformance guards for the brownfield e2e
scaffold. spec 01's own deliverable is prose/docs, not executable code; these
are the mechanically-checkable marker-presence + no-new-diagram + ADR-indexed
guards named in spec 01's Test plan.

Run:  python3 -m unittest tests.acs.test_mar126_e2e_scaffold_docs -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLOW_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "flows",
                         "standardize-project.md")
DEPLOYMENT_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "deployment.md")
REQUIREMENTS_PATH = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")
ADR_PATH = os.path.join(REPO_ROOT, "docs", "adr",
                        "0048-standardize-project-scaffolds-e2e-no-branch-protection.md")
ADR_README_PATH = os.path.join(REPO_ROOT, "docs", "adr", "README.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class TestFlowFileDeltaNote(unittest.TestCase):
    """[AC-6] lld/flows/standardize-project.md carries a delta-note marker;
    no new mermaid diagram is added (spec adds no new diagram)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(FLOW_PATH)

    def test_delta_note_names_both_scaffold_targets(self):
        self.assertIn("acs-e2e.yml", self.body)
        self.assertIn("run-e2e.py", self.body)

    def test_delta_note_gated_on_e2e_set_and_file_missing(self):
        self.assertTrue(
            re.search(r"(?is)(settings\.e2e|suites\.e2e).{0,300}missing", self.body)
        )

    def test_delta_note_references_e2e1_reuse(self):
        self.assertIsNotNone(re.search(r"(?i)E2E-1", self.body))
        self.assertIsNotNone(re.search(r"(?i)verbatim", self.body))

    def test_no_new_mermaid_diagram(self):
        self.assertEqual(self.body.count("```mermaid"), 1,
                          "the flow delta note must not add a new diagram")


class TestDeploymentMdBrownfieldNote(unittest.TestCase):
    """[AC-6] hld/deployment.md's required-check-gates bullet gains a
    brownfield /acs:standardize-project route note; no diagram change."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(DEPLOYMENT_PATH)

    def test_mentions_standardize_project_brownfield_route(self):
        self.assertIn("/acs:standardize-project", self.body)

    def test_still_mentions_e2e_gate(self):
        self.assertIn("acs-e2e.yml", self.body)

    def test_no_new_diagram(self):
        self.assertEqual(self.body.count("```mermaid"), 1,
                          "the deployment note must not add a new diagram")


class TestRequirementsSkillsMd(unittest.TestCase):
    """[AC-6] living-requirements merge into the
    `## /acs:standardize-project` section."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(REQUIREMENTS_PATH)
        cls.section = section(cls.body, "## `/acs:standardize-project`")

    def test_mentions_e2e_scaffold_targets(self):
        self.assertIn("acs-e2e.yml", self.section)
        self.assertIn("run-e2e.py", self.section)

    def test_states_never_wires_branch_protection(self):
        self.assertIsNotNone(
            re.search(r"(?i)never wires? branch protection", self.section)
        )


class TestAdr0048(unittest.TestCase):
    """ADR 0048 for design D1 exists, is Accepted, and records D1 + the D2
    rejection rationale."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ADR_PATH)

    def test_status_accepted(self):
        self.assertIn("**Status**: Accepted", self.body)

    def test_records_d1_scaffold_no_branch_protection(self):
        self.assertIn("acs-e2e.yml", self.body)
        self.assertIn("run-e2e.py", self.body)
        self.assertIsNotNone(re.search(r"(?i)never wires? branch protection", self.body))

    def test_records_conflict_case(self):
        self.assertIsNotNone(re.search(r"(?i)recommended_follow_ups", self.body))

    def test_records_d2_rejection_rationale(self):
        self.assertIsNotNone(
            re.search(r"(?is)invisible.{0,200}diff --name-status", self.body)
            or re.search(r"(?is)diff --name-status.{0,200}invisible", self.body)
        )


class TestAdrReadmeIndex(unittest.TestCase):
    """ADR 0048 is indexed in docs/adr/README.md."""

    def test_0048_row_present(self):
        body = read(ADR_README_PATH)
        m = re.search(r"(?m)^\| \[0048\].*$", body)
        self.assertIsNotNone(m, "docs/adr/README.md must have a row for ADR 0048")
        row = m.group(0)
        self.assertIn("0048-standardize-project-scaffolds-e2e-no-branch-protection.md", row)
        self.assertIn("Accepted", row)


if __name__ == "__main__":
    unittest.main()
