"""Contract tests for the standards/ doc-set templates (MAR-118 spec 01).

Pins AC-9: coding-standards.md, conventions.md, and review-checklist.md ship
under plugins/acs/templates/standards/ with required sections and no runtime
{placeholder} tokens. Written TDD-first (RED before the three files exist);
turns GREEN once spec 01 lands. Mirrors test_operations_templates.py's
per-file TestXRequiredSections shape (standards/ ships three files like
operations/, not one like principles/).
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def template_path(name):
    return os.path.join(PLUGIN, "templates", "standards", "%s.md" % name)


class TestStandardsTemplatesExist(unittest.TestCase):
    """AC-9: all three standards/ template files ship at the fixed
    plugin-relative paths D2 Option A names directly."""

    def test_coding_standards_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("coding-standards")),
                         "plugins/acs/templates/standards/coding-standards.md must exist")

    def test_conventions_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("conventions")),
                         "plugins/acs/templates/standards/conventions.md must exist")

    def test_review_checklist_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("review-checklist")),
                         "plugins/acs/templates/standards/review-checklist.md must exist")


class TestCodingStandardsRequiredSections(unittest.TestCase):
    """Spec 01 inventory: language/style, error handling, testing conventions."""

    def setUp(self):
        self.body = read(template_path("coding-standards"))

    def test_has_language_and_style_section(self):
        self.assertIn("style", self.body.lower(),
                      "coding-standards.md must document language/style conventions")

    def test_has_error_handling_section(self):
        self.assertIn("error", self.body.lower(),
                      "coding-standards.md must document error handling")

    def test_has_testing_conventions_section(self):
        self.assertIn("test", self.body.lower(),
                      "coding-standards.md must document testing conventions")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "coding-standards.md must not carry {curly-brace} runtime "
                          "placeholders (spec 01 Approach — HTML-comment style only)")


class TestConventionsRequiredSections(unittest.TestCase):
    """Spec 01 inventory: naming, project layout, formatting."""

    def setUp(self):
        self.body = read(template_path("conventions"))

    def test_has_naming_conventions_section(self):
        self.assertIn("naming", self.body.lower(),
                      "conventions.md must document naming conventions")

    def test_has_project_layout_section(self):
        self.assertIn("layout", self.body.lower(),
                      "conventions.md must document project layout")

    def test_has_formatting_section(self):
        self.assertIn("formatting", self.body.lower(),
                      "conventions.md must document formatting rules")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "conventions.md must not carry {curly-brace} runtime "
                          "placeholders (spec 01 Approach — HTML-comment style only)")


class TestReviewChecklistRequiredSections(unittest.TestCase):
    """Spec 01 inventory: pre-review checklist, reviewer checklist."""

    def setUp(self):
        self.body = read(template_path("review-checklist"))

    def test_has_pre_review_checklist_section(self):
        self.assertIn("pre-review", self.body.lower(),
                      "review-checklist.md must document a pre-review checklist")

    def test_has_reviewer_checklist_section(self):
        self.assertIn("reviewer", self.body.lower(),
                      "review-checklist.md must document a reviewer checklist")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "review-checklist.md must not carry {curly-brace} runtime "
                          "placeholders (spec 01 Approach — HTML-comment style only)")


if __name__ == "__main__":
    unittest.main()
