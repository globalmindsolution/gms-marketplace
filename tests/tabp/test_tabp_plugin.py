"""Deterministic tests for the tabp plugin scaffold and registration.

Covers:
  AC1 -- plugins/tabp/.claude-plugin/plugin.json exists, name=="tabp", skills-only shape.
  AC2 -- screen-cvs SKILL.md + 3 references present, frontmatter intact.
  AC3 -- marketplace.json tabp entry exists, entry name == plugin.json name == "tabp".
  AC4 -- this module is discovered by unittest discover -s tests and is green.
  AC5 -- plugin shape proven by the TestSkillsOnlyShape assertions.
  AC6 -- namespace guard enforced by TestNamespaceGuard.

No model call. Stdlib only.
Run: python3 -m unittest tests.tabp.test_tabp_plugin -v
"""

import json
import os
import re
import subprocess
import unittest

# Three dirname calls: __file__ is tests/tabp/test_tabp_plugin.py
# dirname x1 -> tests/tabp
# dirname x2 -> tests
# dirname x3 -> repo root
# Mirrors tests/acs/test_acs_plugin.py line 22.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TABP_DIR = os.path.join(REPO_ROOT, "plugins", "tabp")
PLUGIN_JSON = os.path.join(TABP_DIR, ".claude-plugin", "plugin.json")
SKILL_DIR = os.path.join(TABP_DIR, "skills", "screen-cvs")
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
REFS_DIR = os.path.join(SKILL_DIR, "references")
MARKETPLACE = os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")


def frontmatter(text, path):
    """Parse YAML frontmatter delimited by triple-dash lines.

    Mirrors tests/acs/test_skill_contracts.py lines 31-34.
    Returns (frontmatter_str, body_str).
    """
    parts = text.split("---\n", 2)
    assert len(parts) >= 3 and parts[0] == "", "%s: missing frontmatter" % path
    return parts[1], parts[2]


class TestPluginJson(unittest.TestCase):
    """Group 1 -- plugin.json validity (AC1)."""

    def test_plugin_json_exists(self):
        self.assertTrue(
            os.path.isfile(PLUGIN_JSON),
            "plugins/tabp/.claude-plugin/plugin.json not found at %s" % PLUGIN_JSON,
        )

    def test_plugin_json_parses(self):
        with open(PLUGIN_JSON, encoding="utf-8") as fh:
            data = json.load(fh)  # raises on invalid JSON
        self.assertIsInstance(data, dict)

    def test_plugin_json_name_is_tabp(self):
        with open(PLUGIN_JSON, encoding="utf-8") as fh:
            pj = json.load(fh)
        self.assertEqual(
            pj.get("name"),
            "tabp",
            "plugin.json name must be 'tabp', got %r" % pj.get("name"),
        )


class TestSkillsOnlyShape(unittest.TestCase):
    """Group 2 -- plugin shape assertions (AC5, AC6).

    After MAR-2: plugins/tabp/ gains schemas/ (spec 01 JSON schemas) and
    agents/ (spec 03 subagent charters). These directories MUST exist.
    plugins/tabp/hooks/ and plugins/tabp/.acs/ must NOT exist:
    the tabp helper lives under helpers/ (not hooks/) and tabp does
    not use the acs partition.
    """

    def test_no_acs_dir(self):
        acs_dir = os.path.join(TABP_DIR, ".acs")
        self.assertFalse(
            os.path.isdir(acs_dir),
            "plugins/tabp/.acs/ must not exist for a tabp plugin",
        )

    def test_no_schemas_dir(self):
        schemas_dir = os.path.join(TABP_DIR, "schemas")
        self.assertTrue(
            os.path.isdir(schemas_dir),
            "plugins/tabp/schemas/ must exist after MAR-2 (spec 01 adds JSON schemas)",
        )

    def test_no_hooks_dir(self):
        hooks_dir = os.path.join(TABP_DIR, "hooks")
        self.assertFalse(
            os.path.isdir(hooks_dir),
            "plugins/tabp/hooks/ must not exist",
        )

    def test_no_agents_dir(self):
        agents_dir = os.path.join(TABP_DIR, "agents")
        self.assertTrue(
            os.path.isdir(agents_dir),
            "plugins/tabp/agents/ must exist after MAR-2 (spec 03 adds subagent charters)",
        )


class TestScreenCvsSkill(unittest.TestCase):
    """Group 3 -- skill structure and frontmatter (AC2)."""

    def _read_skill_md(self):
        with open(SKILL_MD, encoding="utf-8") as fh:
            return fh.read()

    def test_skill_md_exists(self):
        self.assertTrue(
            os.path.isfile(SKILL_MD),
            "plugins/tabp/skills/screen-cvs/SKILL.md not found at %s" % SKILL_MD,
        )

    def test_frontmatter_name(self):
        text = self._read_skill_md()
        fm, _body = frontmatter(text, SKILL_MD)
        self.assertRegex(
            fm,
            r"(?m)^name: screen-cvs$",
            "SKILL.md frontmatter must contain 'name: screen-cvs'",
        )

    def test_frontmatter_description(self):
        text = self._read_skill_md()
        fm, _body = frontmatter(text, SKILL_MD)
        self.assertRegex(
            fm,
            r"(?m)^description: \S",
            "SKILL.md frontmatter must contain a non-empty description",
        )

    def test_scoring_rubric_exists(self):
        path = os.path.join(REFS_DIR, "scoring-rubric.md")
        self.assertTrue(
            os.path.isfile(path),
            "references/scoring-rubric.md not found at %s" % path,
        )

    def test_fairness_guidelines_exists(self):
        path = os.path.join(REFS_DIR, "fairness-guidelines.md")
        self.assertTrue(
            os.path.isfile(path),
            "references/fairness-guidelines.md not found at %s" % path,
        )

    def test_scorecard_template_exists(self):
        path = os.path.join(REFS_DIR, "scorecard-template.md")
        self.assertTrue(
            os.path.isfile(path),
            "references/scorecard-template.md not found at %s" % path,
        )


class TestMarketplaceRegistration(unittest.TestCase):
    """Group 4 -- marketplace registration live regression (AC3).

    Mirrors tests/acs/test_marketplace_consistency.py lines 350-378
    (test_live_acs_entry_name_matches).
    """

    def _load(self):
        with open(MARKETPLACE, encoding="utf-8") as fh:
            mkt = json.load(fh)
        with open(PLUGIN_JSON, encoding="utf-8") as fh:
            pj = json.load(fh)
        return mkt, pj

    def _find_tabp_entry(self, mkt):
        for entry in mkt.get("plugins", []):
            if entry.get("name") == "tabp":
                return entry
        return None

    def test_tabp_entry_exists(self):
        mkt, _pj = self._load()
        entry = self._find_tabp_entry(mkt)
        self.assertIsNotNone(
            entry,
            "No 'tabp' entry found in .claude-plugin/marketplace.json plugins[]",
        )

    def test_tabp_entry_name_matches_plugin_json(self):
        mkt, pj = self._load()
        entry = self._find_tabp_entry(mkt)
        self.assertIsNotNone(entry, "tabp entry missing from marketplace.json")
        self.assertEqual(
            entry.get("name"),
            pj.get("name"),
            "marketplace.json tabp entry name %r != plugin.json name %r"
            % (entry.get("name"), pj.get("name")),
        )

    def test_plugin_json_name_is_tabp(self):
        _mkt, pj = self._load()
        self.assertEqual(
            pj.get("name"),
            "tabp",
            "plugin.json name must be 'tabp' (AC3 cross-check), got %r" % pj.get("name"),
        )


class TestNamespaceGuard(unittest.TestCase):
    """Group N -- CI-enforced HARD C-3 namespace guard (AC-6).

    Asserts that no acs: prefix or .acs/ token exists anywhere in
    plugins/tabp/. Implements design R2 (design.md:922) as a unit test
    so the guard runs on every CI pass.
    """

    def test_no_acs_namespace_tokens_in_plugins_tabp(self):
        result = subprocess.run(
            ["grep", "-rE", r"\.acs/|acs:", "plugins/tabp"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        # grep exits 1 when no match is found (which is the passing condition).
        # grep exits 0 when at least one match is found (which is a failure).
        self.assertNotEqual(
            result.returncode,
            0,
            "HARD C-3 VIOLATION: acs: or .acs/ token found in plugins/tabp:\n"
            + result.stdout,
        )


class TestSkillMdDecisionWrite(unittest.TestCase):
    """Group D -- SKILL.md decision-write wiring assertions (AC-5, AC-3 audit).

    Verifies that SKILL.md contains the Step 5b decision-write section (TC-06),
    that the decision-write invocation appears after the self-verification step
    (TC-07), and that SKILL.md contains no acs: token (TC-08).
    """

    def _read_skill_md(self):
        with open(SKILL_MD, encoding="utf-8") as fh:
            return fh.read()

    def test_tc06_decision_write_present(self):
        """TC-06 (AC-5): SKILL.md contains the Step 5b Record the decision section."""
        content = self._read_skill_md()
        self.assertIn(
            "## Step 5b",
            content,
            "SKILL.md must contain '## Step 5b' heading (Step 5b wiring, spec 04, AC-5)",
        )
        self.assertIn(
            "decision-write",
            content,
            "SKILL.md must contain 'decision-write' invocation in Step 5b (spec 04, AC-5)",
        )

    def test_tc07_decision_write_after_self_verification(self):
        """TC-07 (AC-5): decision-write invocation appears AFTER the self-verification heading."""
        content = self._read_skill_md()
        # Find the Step 5b heading position (this is the section containing decision-write)
        step5b_idx = content.find("## Step 5b")
        self.assertNotEqual(
            step5b_idx,
            -1,
            "SKILL.md must contain '## Step 5b' heading (spec 04)",
        )
        # Find the self-verification heading position (Step 5a)
        self_verification_idx = content.find("## Step 5a")
        self.assertNotEqual(
            self_verification_idx,
            -1,
            "SKILL.md must contain '## Step 5a' heading (spec 03)",
        )
        self.assertGreater(
            step5b_idx,
            self_verification_idx,
            "Step 5b (decision-write) must appear AFTER Step 5a (self-verification) in SKILL.md "
            "(design.md:769 ordering: verification pass then decision-write)",
        )

    def test_tc08_no_acs_token_in_skill_md(self):
        """TC-08 (AC-6): SKILL.md contains no acs: token."""
        content = self._read_skill_md()
        self.assertNotIn(
            "acs:",
            content,
            "SKILL.md must not contain 'acs:' token (AC-6, HARD C-3 namespace invariant)",
        )


if __name__ == "__main__":
    unittest.main()
