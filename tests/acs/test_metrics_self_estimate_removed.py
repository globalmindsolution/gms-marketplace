"""Sweep test proving the self-estimated <metrics> XML element is gone (D5-A).

Originating ticket: MAR-1. D5-A removed <metrics> from acs-messages.xsd and
the matching validate_xml.py content-model tables, and dropped the "fill
tokens/cost_usd with your best estimates" instruction from every
SKILL.md/agent charter, so token/cost figures come only from measured
usage_reader/cost_sampler data. This module is the single place asserting
the sweep is complete and stays complete.
"""

import os
import sys
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_ACS))


def _files_containing(root_dirs, needle):
    """Return repo-relative paths of files under root_dirs whose text contains needle."""
    hits = []
    for root_dir in root_dirs:
        for dirpath, _dirnames, filenames in os.walk(root_dir):
            if os.sep + "__pycache__" in dirpath or dirpath.endswith("__pycache__"):
                continue
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        text = fh.read()
                except (UnicodeDecodeError, OSError):
                    continue
                if needle in text:
                    hits.append(os.path.relpath(path, REPO_ROOT))
    return hits


class TestMetricsElementRejected(unittest.TestCase):
    """(i) A <result> bearing <metrics> is now rejected in-process, not merely by the XSD."""

    def test_result_with_metrics_is_rejected_by_validate_structurally(self):
        mod = acs_case.load_module("validate_xml.py", alias="validate_xml")
        xml = (
            '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
            '<metrics tokens-input="1000" tokens-output="200" cost-usd="0.05"/>'
            '</result>'
        )
        errors = mod.validate_structurally(xml)
        self.assertTrue(
            errors,
            "Expected <metrics> to be rejected by validate_structurally now that it "
            "has been removed from the message contract (D5-A), but got []",
        )


class TestCharterSweepClean(unittest.TestCase):
    """(ii)/(iii) No agent/skill charter still instructs or uses <metrics>."""

    def test_no_metrics_element_in_agents_or_skills(self):
        hits = _files_containing(
            [os.path.join(REPO_ROOT, "plugins", "acs", "agents"),
             os.path.join(REPO_ROOT, "plugins", "acs", "skills")],
            "<metrics",
        )
        self.assertEqual(
            hits, [],
            "<metrics> usage/self-report instruction still present in: %s" % hits,
        )

    def test_no_best_estimates_instruction_under_plugins_or_docs(self):
        hits = _files_containing(
            [os.path.join(REPO_ROOT, "plugins"), os.path.join(REPO_ROOT, "docs")],
            "best estimates",
        )
        self.assertEqual(
            hits, [],
            "the retired 'best estimates' self-report instruction is still present "
            "in: %s" % hits,
        )


class TestImmutableSurfacesUntouched(unittest.TestCase):
    """Negative controls: things that must NOT have been swept away by U5a."""

    def test_historical_adrs_still_mention_metrics(self):
        """ADR 0013 and 0016 are immutable history; ADR 0080 supersedes them, not this test."""
        hits = _files_containing([os.path.join(REPO_ROOT, "docs", "adr")], "<metrics")
        relative_hits = set(hits)
        for expected in (
            "docs/adr/0013-metrics-derives-panels-from-artifacts.md",
            "docs/adr/0016-metrics-bounded-single-pass-walk.md",
        ):
            self.assertIn(
                expected, relative_hits,
                "%s must still mention <metrics> -- ADRs are immutable history, "
                "editing them would be a defect, not a fix" % expected,
            )

    def test_skill_name_enum_value_metrics_still_present(self):
        """The /acs:metrics skill's skillName enum value is unrelated to the <metrics>
        element and must survive this sweep -- guards against a self-inflicted regression."""
        xsd_path = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "acs-messages.xsd")
        with open(xsd_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        matches = [line for line in lines if "metrics" in line]
        self.assertTrue(
            any('value="metrics"' in line for line in matches),
            "Expected the skillName enumeration to still list value=\"metrics\" "
            "(the /acs:metrics skill); found only: %r" % matches,
        )


if __name__ == "__main__":
    unittest.main()
