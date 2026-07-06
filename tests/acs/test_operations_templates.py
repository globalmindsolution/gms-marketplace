"""Contract tests for the operations/ doc-set templates (MAR-113 spec 03).

Pins AC-4: release-process.md, runbooks.md, observability.md,
incident-response.md, and test-scheduling.md ship under
plugins/acs/templates/operations/ with the design's required sections and no
runtime {placeholder} tokens. Written TDD-first (RED before the five files
exist); turns GREEN once spec 03 lands. Kept in its own module (mirroring
test_quality_templates.py) so this task's diff stays file-disjoint from spec
04's test_skill_contracts.py edits (iter-1-plan.md E3)."""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def template_path(name):
    return os.path.join(PLUGIN, "templates", "operations", "%s.md" % name)


class TestOperationsTemplatesExist(unittest.TestCase):
    """AC-4: all five operations/ template files ship at the fixed
    plugin-relative paths spec 01's executor names directly."""

    def test_release_process_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("release-process")),
                         "plugins/acs/templates/operations/release-process.md must exist")

    def test_runbooks_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("runbooks")),
                         "plugins/acs/templates/operations/runbooks.md must exist")

    def test_observability_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("observability")),
                         "plugins/acs/templates/operations/observability.md must exist")

    def test_incident_response_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("incident-response")),
                         "plugins/acs/templates/operations/incident-response.md must exist")

    def test_test_scheduling_file_exists(self):
        self.assertTrue(os.path.isfile(template_path("test-scheduling")),
                         "plugins/acs/templates/operations/test-scheduling.md must exist")


class TestReleaseProcessRequiredSections(unittest.TestCase):
    """Design inventory (design.md:470): 4 required sections."""

    def setUp(self):
        self.body = read(template_path("release-process"))

    def test_has_versioning_release_cut_section(self):
        self.assertIn("release", self.body.lower(),
                      "release-process.md must cover versioning/release-cut steps")

    def test_has_changelog_discipline_section(self):
        self.assertIn("changelog", self.body.lower(),
                      "release-process.md must document changelog discipline")

    def test_has_branch_tag_conventions_section(self):
        self.assertIn("branch", self.body.lower(),
                      "release-process.md must document branch conventions")
        self.assertIn("tag", self.body.lower(),
                      "release-process.md must document tag conventions")

    def test_has_rollback_procedure_section(self):
        self.assertIn("Rollback", self.body,
                      "release-process.md must document a rollback procedure")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "release-process.md must not carry {curly-brace} runtime "
                          "placeholders (spec 03 Approach — HTML-comment style only)")


class TestRunbooksRequiredSections(unittest.TestCase):
    """Design inventory (design.md:471): 3 required sections."""

    def setUp(self):
        self.body = read(template_path("runbooks"))

    def test_has_standard_operating_procedures_section(self):
        self.assertIn("operating procedure", self.body.lower(),
                      "runbooks.md must document standard operating procedures")

    def test_has_on_call_escalation_section(self):
        self.assertIn("on-call", self.body.lower(),
                      "runbooks.md must document the on-call escalation path")

    def test_has_incident_triage_section(self):
        self.assertIn("triage", self.body.lower(),
                      "runbooks.md must document incident triage steps")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "runbooks.md must not carry {curly-brace} runtime "
                          "placeholders (spec 03 Approach — HTML-comment style only)")


class TestObservabilityRequiredSections(unittest.TestCase):
    """Design inventory (design.md:472): 3 required sections."""

    def setUp(self):
        self.body = read(template_path("observability"))

    def test_has_logging_metrics_alerting_section(self):
        self.assertIn("metric", self.body.lower(),
                      "observability.md must document metrics conventions")
        self.assertIn("alert", self.body.lower(),
                      "observability.md must document alerting conventions")

    def test_has_dashboards_section(self):
        self.assertIn("dashboard", self.body.lower(),
                      "observability.md must document dashboards")

    def test_has_slo_sla_section(self):
        self.assertTrue("SLO" in self.body or "SLA" in self.body,
                        "observability.md must document SLO/SLA notes")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "observability.md must not carry {curly-brace} runtime "
                          "placeholders (spec 03 Approach — HTML-comment style only)")


class TestIncidentResponseRequiredSections(unittest.TestCase):
    """Design inventory (design.md:473): 3 required sections."""

    def setUp(self):
        self.body = read(template_path("incident-response"))

    def test_has_severity_levels_section(self):
        self.assertIn("severity", self.body.lower(),
                      "incident-response.md must document severity levels")

    def test_has_roles_during_incident_section(self):
        self.assertIn("role", self.body.lower(),
                      "incident-response.md must document roles during an incident")

    def test_has_postmortem_process_section(self):
        self.assertIn("postmortem", self.body.lower(),
                      "incident-response.md must document the postmortem process")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "incident-response.md must not carry {curly-brace} runtime "
                          "placeholders (spec 03 Approach — HTML-comment style only)")


class TestTestSchedulingRequiredSections(unittest.TestCase):
    """Design inventory (design.md:474): 3 required sections."""

    def setUp(self):
        self.body = read(template_path("test-scheduling"))

    def test_has_acs_test_recipe_section(self):
        self.assertIn("/acs:test", self.body,
                      "test-scheduling.md must document the /acs:test scheduling recipe")

    def test_has_cron_ci_snippets_section(self):
        self.assertTrue("cron" in self.body.lower() or "CI" in self.body,
                        "test-scheduling.md must include example cron/CI snippets")

    def test_has_results_location_section(self):
        self.assertIn("results", self.body.lower(),
                      "test-scheduling.md must document where results land")

    def test_no_runtime_placeholder_tokens(self):
        self.assertIsNone(re.search(r"\{[a-zA-Z_]+\}", self.body),
                          "test-scheduling.md must not carry {curly-brace} runtime "
                          "placeholders (spec 03 Approach — HTML-comment style only)")


if __name__ == "__main__":
    unittest.main()
