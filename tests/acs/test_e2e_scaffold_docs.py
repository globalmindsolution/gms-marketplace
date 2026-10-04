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


class TestAdr0048(unittest.TestCase):
    """ADR 0048 for design D1 exists, records D1 + the D2 rejection rationale,
    and is marked superseded now that ADR-0118 removed standardize-project."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ADR_PATH)

    def test_status_superseded_by_0118(self):
        self.assertIn("**Status**: Superseded by [0118]", self.body)

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
        self.assertIn("Superseded by [0118]", row)


if __name__ == "__main__":
    unittest.main()
