"""Contract tests for the principles/ doc-set template (MAR-117 spec 01).

Pins AC-9: principles.md ships under plugins/acs/templates/principles/ with
the design's required sections (D2 Option A — a single coarse file) and no
runtime {placeholder} tokens. Written TDD-first (RED before the file exists);
turns GREEN once spec 01 lands. Mirrors tests/acs/test_quality_templates.py,
scoped to the single file.

Run:  python3 -m unittest tests.acs.test_principles_templates -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
TEMPLATE_PATH = os.path.join(PLUGIN, "templates", "principles", "principles.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestPrinciplesTemplateExists(unittest.TestCase):
    """AC-9: the principles/ template file ships at the fixed plugin-relative
    path spec 01's executor names directly."""

    def test_principles_file_exists(self):
        self.assertTrue(os.path.isfile(TEMPLATE_PATH),
                         "plugins/acs/templates/principles/principles.md must exist")


class TestPrinciplesRequiredSections(unittest.TestCase):
    """D2 (design.md:142-146): a single file with a principles list + rationale."""

    def setUp(self):
        self.body = read(TEMPLATE_PATH)

    def test_has_principles_section(self):
        self.assertIn("Principles", self.body,
                      "principles.md must have a Principles section")

    def test_has_rationale_section(self):
        self.assertIn("Rationale", self.body,
                      "principles.md must have a Rationale section")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "principles.md must not carry {curly-brace} runtime "
                          "placeholders (AC-9 — HTML-comment style only)")


if __name__ == "__main__":
    unittest.main()
