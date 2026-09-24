"""MAR-125 (E2E-1) — documentation-conformance guards for the e2e required
merge gate. spec 03's own deliverable is prose/diagram, not executable code;
these are the mechanically-checkable file-existence + marker-presence +
doc-only-diff guards named in spec 03's Test plan (verifier inspection covers
the rest — e.g. verbatim fidelity of the new flow diagram to design.md's
Flow 1).

Run:  python3 -m unittest discover -s tests -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
MERGE_PR_PATH = os.path.join(PLUGIN, "skills", "merge-pr", "SKILL.md")
DEPLOYMENT_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "deployment.md")
FLOW_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "flows",
                         "enforce-e2e-merge-gate.md")
CONTRACTS_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")
C4_CONTAINER_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestMergePrNote(unittest.TestCase):
    """[AC-5] merge-pr doc note is present, doc-only, adds no 5th dimension."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(MERGE_PR_PATH)

    def test_mergepr_note_present_and_doc_only(self):
        m = re.search(r"(?s)- \*\*ci\*\*.{0,1200}", self.body)
        self.assertIsNotNone(m, "the `ci` readiness bullet must exist")
        window = m.group(0)
        self.assertTrue(
            re.search(r"(?i)e2e", window) and re.search(r"(?i)ci", window),
            "a note near the `ci` bullet must state e2e is covered by the "
            "existing `ci` readiness dimension",
        )

    def test_mergepr_no_new_readiness_dimension(self):
        dims = re.findall(r"(?m)^- \*\*(\w+)\*\*", self.body)
        # The four readiness-dimension bullets, in order, unchanged.
        self.assertEqual(
            [d for d in dims if d in ("ci", "approvals", "conflicts", "protections")],
            ["ci", "approvals", "conflicts", "protections"],
        )

    def test_mergepr_gains_no_e2e_specific_github_read(self):
        """AC-5's real invariant: the e2e gate rides on the EXISTING `ci`
        dimension and adds no read of its own.

        This replaces a `git diff -- SKILL.md` check (MAR-524). That form could
        only ever see UNCOMMITTED work: once MAR-125 landed, its own diff was
        empty and the test asserted nothing — while any later ticket touching
        this file failed it for reasons MAR-125 never had an opinion about.
        The property below holds against the committed file, forever."""
        self.assertNotIn("gh api", self.body,
                        "merge-pr must not reach GitHub through the raw API (AC-5)")
        for number, line in enumerate(self.body.splitlines(), start=1):
            if re.search(r"(?i)e2e", line):
                self.assertNotIn(
                    "gh ", line,
                    msg="line %d couples e2e to its own gh call; e2e is enforced "
                        "through the `ci` dimension's existing read (AC-5)" % number)


class TestFlowFile(unittest.TestCase):
    """[AC-7] the new enforce-e2e-merge-gate flow file."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(FLOW_PATH)

    def test_flow_file_exists_with_sequence_diagram(self):
        self.assertIn("```mermaid", self.body)
        self.assertIn("sequenceDiagram", self.body)

    def test_flow_file_names_key_participants(self):
        for token in ("acs-e2e.yml", "run-e2e.py", "Branch protection",
                     "/acs:merge-pr"):
            self.assertIn(token, self.body)


class TestContractsMd(unittest.TestCase):
    """[AC-7] contracts.md drift-repair + e2e artifact-family note."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CONTRACTS_PATH)

    def test_contracts_md_lists_tests_and_enforcement(self):
        self.assertIn("tests?", self.body)
        self.assertIn("enforcement?", self.body)

    def test_contracts_md_notes_e2e_artifact_family(self):
        self.assertIn("acs-e2e.yml", self.body)
        self.assertIn("run-e2e.py", self.body)
        self.assertIn("E2E suite", self.body)


class TestDeploymentMd(unittest.TestCase):
    def test_deployment_md_mentions_e2e_gate(self):
        body = read(DEPLOYMENT_PATH)
        self.assertTrue(
            re.search(r"(?i)acs-e2e\.yml", body)
            and re.search(r"(?i)required", body)
            and re.search(r"(?i)branch protection", body),
            "deployment.md must mention acs-e2e.yml + required + branch "
            "protection (AC-7)",
        )


class TestC4ContainerMd(unittest.TestCase):
    def test_c4_container_md_notes_e2e_templates(self):
        body = read(C4_CONTAINER_PATH)
        self.assertTrue(re.search(r"(?i)e2e", body))


if __name__ == "__main__":
    unittest.main()
