"""Sweep test proving the self-estimated <metrics> XML element is gone (D5-A).

D5-A removed <metrics> from the message contract and dropped every
"fill/estimate tokens and cost_usd yourself" instruction from every
SKILL.md/agent charter (several distinct
phrasings existed across skills -- "fill ... with your best estimate(s)",
"Estimate `tokens`/`cost_usd` for this run", "your estimates for this entire
run" -- all discarded now that finalize_run always overwrites a coordinator's
self-reported tokens/cost_usd with measured usage_reader/cost_sampler data),
so token/cost figures come only from that measured data. This module is the
single place asserting the sweep is complete and stays complete.

v0.5.0 retired the XML messaging surface itself (acs-messages.xsd and
validate_xml.py), so the two assertions that read it read the JSON schemas
that replaced it instead. The subject is unchanged: a result document may not
carry self-reported metrics, and the /acs:metrics SKILL name -- unrelated to
the retired element -- must survive the sweep.
"""

import os
import re
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


class TestMetricsAreMeasuredNotAsserted(unittest.TestCase):
    """(i) A result document does not carry self-reported metrics.

    The XSD element is gone with the whole XML surface; what replaced the
    rejection is stronger than a schema refusal. `finalize_invocation`
    MEASURES tokens, cost and API duration from the invocation's own recorded
    transcript and writes them itself, so a coordinator's figures are not
    rejected -- they are simply never read."""

    def test_the_result_schema_does_not_invite_self_reported_metrics(self):
        import json
        path = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "result.schema.json")
        with open(path, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertNotIn("metrics", schema["properties"])

    def test_finalize_invocation_measures_rather_than_copying(self):
        source = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts",
                              "acs_lib", "step.py")
        with open(source, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("_measure_run_usage(entry, rdir, step)", body)
        self.assertIsNotNone(
            re.search(r"(?s)never taken from `result`", body),
            "step.py must state that measurement never reads the result document")


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

    def test_no_self_estimate_cost_instruction_in_any_skill(self):
        """Broader than the literal 'best estimates' phrase above: every observed
        phrasing told the coordinator to estimate/fill tokens+cost_usd itself
        (singular "best estimate", "Estimate `tokens`/`cost_usd`", "your
        estimates for this ... run"). Match the underlying instruction --
        the word "estimate" within a short window of "cost_usd" -- so a new
        skill reintroducing any variant of it is caught, not just this one
        literal string."""
        pattern = re.compile(r"estimate.{0,80}cost_usd|cost_usd.{0,80}estimate", re.IGNORECASE | re.DOTALL)
        skills_dir = os.path.join(REPO_ROOT, "plugins", "acs", "skills")
        hits = []
        for dirpath, _dirnames, filenames in os.walk(skills_dir):
            for filename in filenames:
                if filename != "SKILL.md":
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read()
                if pattern.search(text):
                    hits.append(os.path.relpath(path, REPO_ROOT))
        self.assertEqual(
            hits, [],
            "a self-estimate-cost instruction (any phrasing) is still present in: %s "
            "-- finalize_run always overwrites a coordinator's self-reported "
            "tokens/cost_usd with measured data, so this instruction is dead" % hits,
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

    def test_the_metrics_skill_itself_still_exists(self):
        """The /acs:metrics SKILL is unrelated to the retired <metrics>
        element and must survive this sweep -- it used to be guarded through
        the XSD's skillName enum, which went with the XSD; a skill is a
        DIRECTORY now, so the directory is the pin."""
        self.assertTrue(os.path.isfile(os.path.join(
            REPO_ROOT, "plugins", "acs", "skills", "metrics", "SKILL.md")))
        self.assertIn("metrics", acs_case.lib.UNHOOKED_SKILLS)


if __name__ == "__main__":
    unittest.main()
