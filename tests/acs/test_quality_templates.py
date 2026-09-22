"""Contract tests for the quality/ doc-set templates (MAR-112 spec 03).

Pins AC-4: test-strategy.md and coverage-policy.md ship under
plugins/acs/templates/quality/ with the design's required sections and no
runtime {placeholder} tokens. Written TDD-first (RED before the two files
exist); turns GREEN once spec 03 lands. Kept in its own module (rather than
test_skill_contracts.py) so this task's diff stays file-disjoint from spec
04's test_skill_contracts.py edits (iter-1-plan.md Task 3)."""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def template_path(name):
    return os.path.join(PLUGIN, "templates", "quality", "%s.md" % name)


class TestQualityTemplatesExist(unittest.TestCase):
    """AC-4: both quality/ template files ship at the fixed plugin-relative
    paths spec 01's executor names directly."""

    def test_test_strategy_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("test-strategy")),
                         "plugins/acs/templates/quality/test-strategy.md must exist")

    def test_coverage_policy_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("coverage-policy")),
                         "plugins/acs/templates/quality/coverage-policy.md must exist")


class TestTestStrategyRequiredSections(unittest.TestCase):
    """Design inventory (design.md:468): 5 required sections."""

    def setUp(self):
        self.body = read(template_path("test-strategy"))

    def test_has_philosophy_pyramid_section(self):
        self.assertIn("pyramid", self.body.lower(),
                      "test-strategy.md must cover testing philosophy/pyramid")

    def test_has_coverage_percent_policy_section(self):
        self.assertIn("test_coverage_percent", self.body,
                      "test-strategy.md must reference the test_coverage_percent policy")

    def test_has_suite_inventory_section(self):
        self.assertIn("configured test suites", self.body,
                      "test-strategy.md must phrase the suite inventory generically "
                      "(design R5 — suites key is MAR-114 scope)")

    def test_has_ci_gates_section(self):
        self.assertIn("CI gates", self.body,
                      "test-strategy.md must document CI gates (tests/enforcement)")

    def test_has_flaky_test_policy_section(self):
        self.assertIn("Flaky", self.body,
                      "test-strategy.md must document a flaky-test policy")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "test-strategy.md must not carry {curly-brace} runtime "
                          "placeholders (spec 03 Approach — HTML-comment style only)")


class TestCoveragePolicyRequiredSections(unittest.TestCase):
    """Design inventory (design.md:469): 4 required sections."""

    def setUp(self):
        self.body = read(template_path("coverage-policy"))

    def test_has_target_hard_fail_section(self):
        self.assertIn("test_coverage_percent", self.body,
                      "coverage-policy.md must mirror the test_coverage_percent target "
                      "and hard-fail rule")

    def test_has_exclusions_section(self):
        self.assertIn("Exclusions", self.body,
                      "coverage-policy.md must document exclusions")

    def test_has_per_stack_measurement_section(self):
        self.assertIn("per stack", self.body.lower(),
                      "coverage-policy.md must document how coverage is measured per stack")

    def test_has_escalation_section(self):
        self.assertIn("Escalation", self.body,
                      "coverage-policy.md must document escalation when a PR misses target")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "coverage-policy.md must not carry {curly-brace} runtime "
                          "placeholders (spec 03 Approach — HTML-comment style only)")


if __name__ == "__main__":
    unittest.main()
