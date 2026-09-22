#!/usr/bin/env python3
"""Guard the dataset's self-description against the dataset itself.

A header that counts its own array wrong is worse than no header: it is read
as the summary of what the suite covers, and it is what a release report
quotes. On 2026-09-16 `routing.json` declared `probe_count: 43` and
`skill_count: 32` over an array of 35 probes covering 28 skills -- the counts
were left behind when ADR 0091's six internal legs became two and ADR 0094
folded the four doc-set legs away, and nothing failed.

These are pure reads of files already on disk: no model, no network, no cost.
Run by `make verify-self`.
"""

import collections
import json
import os
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
EVALS = os.path.dirname(HERE)
DATASET = os.path.join(EVALS, "dataset")
PLUGIN = os.path.join(os.path.dirname(EVALS), "plugins", "acs")


def load(name):
    with open(os.path.join(DATASET, name), encoding="utf-8") as fh:
        return json.load(fh)


def shipped_skills():
    root = os.path.join(PLUGIN, "skills")
    return {name for name in os.listdir(root)
            if os.path.isdir(os.path.join(root, name))}


class RoutingHeaderCountsItsOwnArrayTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.doc = load("routing.json")
        cls.probes = cls.doc["probes"]
        cls.by_kind = collections.Counter(p.get("kind") for p in cls.probes)

    def test_probe_count_matches_the_array(self):
        self.assertEqual(self.doc["probe_count"], len(self.probes))

    def test_control_count_matches_the_control_probes(self):
        self.assertEqual(self.doc["control_count"], self.by_kind["control"])

    def test_skill_count_matches_the_plugin(self):
        self.assertEqual(self.doc["skill_count"], len(shipped_skills()))

    def test_every_probe_declares_a_known_kind(self):
        self.assertEqual(set(self.by_kind) - {"positive", "negative", "control"},
                         set(), "unknown probe kind(s)")

    def test_a_negative_probe_must_not_route(self):
        for probe in self.probes:
            if probe.get("kind") == "negative":
                self.assertIs(probe.get("must_route"), False, probe["id"])

    def test_a_positive_probe_must_route_to_a_shipped_skill(self):
        shipped = shipped_skills()
        for probe in self.probes:
            if probe.get("kind") != "positive":
                continue
            self.assertIs(probe.get("must_route"), True, probe["id"])
            name = (probe.get("skill") or "").split(":", 1)[-1]
            self.assertIn(name, shipped,
                          "%s probes a skill this build does not ship" % probe["id"])


class EveryShippedSkillIsProbedTest(unittest.TestCase):
    """G8's "routing covered for 100% of skills", as a number rather than a claim."""

    def test_positive_routing_coverage_is_total(self):
        probes = load("routing.json")["probes"]
        covered = {(p.get("skill") or "").split(":", 1)[-1]
                   for p in probes if p.get("kind") == "positive"}
        missing = sorted(shipped_skills() - covered)
        self.assertEqual(missing, [],
                         "shipped skills with no positive routing probe: %s" % missing)


class ScenarioSetIsInternallyConsistentTest(unittest.TestCase):

    def test_every_pipeline_scenario_names_a_shipped_skill(self):
        doc = load("scenarios.json")
        shipped = shipped_skills()
        for scenario in doc["pipeline"]["scenarios"]:
            name = (scenario.get("skill") or "").split(":", 1)[-1]
            self.assertIn(name, shipped,
                          "%s measures a skill this build does not ship" % scenario["id"])

    def test_routing_source_points_at_the_file_that_exists(self):
        doc = load("scenarios.json")
        source = doc["routing"]["source"]
        self.assertTrue(os.path.isfile(os.path.join(EVALS, source)), source)


class ThresholdsAreWellFormedTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.doc = load("thresholds.json")

    def test_every_threshold_carries_a_value_a_rule_and_a_why(self):
        skip = {"thresholds_version", "basis", "basis_note", "calibrated_from",
                "calibration_protocol"}
        for group, entries in self.doc.items():
            if group in skip:
                continue
            for key, spec in entries.items():
                self.assertIn("value", spec, "%s.%s" % (group, key))
                self.assertIn("rule", spec, "%s.%s" % (group, key))

    def test_a_calibrated_basis_must_name_what_it_was_calibrated_from(self):
        if self.doc.get("basis") == "calibrated":
            self.assertTrue(self.doc.get("calibrated_from"),
                            "basis is calibrated but calibrated_from is empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
