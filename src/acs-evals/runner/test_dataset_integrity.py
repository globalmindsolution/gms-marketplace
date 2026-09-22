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
import glob
import json
import os
import re
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
EVALS = os.path.dirname(HERE)
DATASET = os.path.join(EVALS, "dataset")
PLUGIN = os.path.join(os.path.dirname(EVALS), "acs")
ADRS = os.path.join(os.path.dirname(os.path.dirname(EVALS)), "docs", "adr")

#: What a `covers` entry may name: an ADR, the ticket that created the family,
#: or the redesign document.
COVERS_ENTRY = re.compile(r"^(?:ADR-\d{4}|MAR-\d+|REDESIGN[\w.\-]*)$")

#: What counts as an AUTHORITY in a case `note`: the document that authorised
#: the behaviour the case now records. A ticket id is not one -- a ticket says
#: who changed it, not what permitted the change.
AUTHORITY = re.compile(r"ADR-\d{4}|REDESIGN")

#: Every clause whose value is a list of needles the runner iterates.
NEEDLE_KEYS = ("stdout_contains", "stderr_contains", "stdout_excludes",
               "stderr_excludes", "errors_contain", "description_contains",
               "frontmatter_absent", "frontmatter_nonempty")


def load(name):
    with open(os.path.join(DATASET, name), encoding="utf-8") as fh:
        return json.load(fh)


def case_files():
    """Every case file, as (filename, document) pairs."""
    out = []
    for path in sorted(glob.glob(os.path.join(DATASET, "cases", "*.json"))):
        with open(path, encoding="utf-8") as fh:
            out.append((os.path.basename(path), json.load(fh)))
    return out


def shipped_adrs():
    """The ADR ids that exist, as `ADR-NNNN`."""
    return {"ADR-%s" % name[:4] for name in os.listdir(ADRS)
            if re.match(r"^\d{4}-.*\.md$", name)}


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

    def test_no_probe_names_a_retired_skill(self):
        """Every offender at once. The assertIn above stops at the first, so a
        second retired skill stays invisible until the first is repaired --
        which is how `acs:test` survived the routing pass that found
        `acs:analyze-ticket`. Controls are exempt: one names no skill and one
        names `acs:no-such-skill` on purpose."""
        shipped = shipped_skills()
        retired = sorted(
            "%s -> %s" % (p["id"], p.get("skill"))
            for p in self.probes
            if p.get("kind") != "control"
            and (p.get("skill") or "").split(":", 1)[-1] not in shipped)
        self.assertEqual(retired, [],
                         "probes naming a skill this build does not ship: %s" % retired)


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


class CaseExpectationsAreWellFormedTest(unittest.TestCase):

    def test_no_case_uses_a_bare_string_contains(self):
        """A containment clause is a LIST of needles. Written as a string it is
        iterated character by character, so the clause passes as soon as the
        stream shares a letter with it -- green while asserting nothing."""
        bare = []
        for name, doc in case_files():
            for case in doc.get("cases", []):
                expect = case.get("expect") or {}
                bare.extend(
                    "%s %s.%s = %r" % (name, case["id"], key, expect[key])
                    for key in NEEDLE_KEYS
                    if key in expect and not isinstance(expect[key], list))
        self.assertEqual(bare, [],
                         "containment clauses that assert nothing: %s" % bare)


class ReRecordedCasesCiteTheirAuthority(unittest.TestCase):
    """A golden re-recorded from what the build prints today is how a
    regression becomes a baseline. The dataset's defence is a citation: the
    file names the authority in `covers`, and a case re-recorded under it says
    which one in its `note`."""

    def test_every_case_file_names_what_it_covers(self):
        bad = []
        for name, doc in case_files():
            covers = doc.get("covers") or []
            if not covers:
                bad.append("%s: no covers" % name)
            bad.extend("%s: %r" % (name, entry) for entry in covers
                       if not COVERS_ENTRY.match(str(entry)))
        self.assertEqual(bad, [], "malformed or missing covers: %s" % bad)

    def test_every_cited_adr_exists(self):
        """A citation to an ADR nobody wrote is not a citation."""
        shipped = shipped_adrs()
        missing = set()
        for _name, doc in case_files():
            cited = list(doc.get("covers") or [])
            cited.extend(case.get("note") or "" for case in doc.get("cases", []))
            for text in cited:
                missing.update(set(re.findall(r"ADR-\d{4}", str(text))) - shipped)
        self.assertEqual(sorted(missing), [],
                         "cases cite ADRs that do not exist: %s" % sorted(missing))

    def test_every_authority_in_covers_is_cited_by_a_case(self):
        """The two halves must meet. An ADR added to `covers` that no case
        names in its `note` records an authority nothing can be traced to --
        the file claims a warrant, and no case says what it warranted."""
        uncited = []
        for name, doc in case_files():
            notes = " ".join(case.get("note") or "" for case in doc.get("cases", []))
            uncited.extend(
                "%s: %s" % (name, entry) for entry in (doc.get("covers") or [])
                if AUTHORITY.match(str(entry)) and str(entry) not in notes)
        self.assertEqual(uncited, [],
                         "authorities no case note cites: %s" % uncited)


class PlanContractCoverageTest(unittest.TestCase):
    """AC-9. `acs path` is gone (ADR-0098: the delivery path is read from the
    plan's Contract block), and deleting its five cases must not take the
    coverage with them -- the successor surface is pinned instead."""

    def test_the_delivery_path_successor_is_pinned(self):
        pinning = []
        for name, doc in case_files():
            for case in doc.get("cases", []):
                invoke = case.get("invoke") or {}
                if (invoke.get("script") == "plan-approval.py"
                        and "path" in [str(a) for a in invoke.get("argv", [])]):
                    pinning.append("%s %s" % (name, case["id"]))
        self.assertGreaterEqual(
            len(pinning), 3,
            "the delivery path's successor needs at least 3 cases over "
            "`plan-approval.py path`; found %d: %s" % (len(pinning), pinning))


if __name__ == "__main__":
    unittest.main(verbosity=2)
