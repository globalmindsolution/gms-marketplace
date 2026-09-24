"""Probe expectations that used to ride along in the CI doc tests -- locally.

Each class here asserts something about the eval CASE FILES: that a probe for a
given skill exists, names what it must, and no probe asserts a retired or
renamed skill. They lived inside per-ticket doc tests (the create-docs fold,
standardize-project, the suite runner, the setup rename) until evals left CI
(ADR-0108); the doc assertions stayed in tests/acs/, the eval ones moved here.
Their docstrings keep the history of the tickets that introduced them.

Local-only like everything under tests/evals/: run by the `acs-eval-checks`
pre-commit hook and the release gate, never by CI.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, HERE)
import eval_cases  # noqa: E402  (the case files are the probe set)

#: The doc sets /acs:create-docs folded in, and the legs that retired with it.
SETS = ("quality", "operations", "principles", "standards")
RETIRED = tuple("create-%s" % s for s in SETS)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class CreateDocsProbeTest(unittest.TestCase):
    """One routing probe for the fold, read from the curated dataset (no paid
    call): a description-shaped probe that names two sets and routes to
    create-docs; no probe survives for a retired leg.

    The probe set used to live in s04_skill_triggers.py's CASES list, parsed
    out of its AST. Routing consolidated onto the `claude plugin eval` tree, so
    the probe set is the case files under plugins/acs/evals/, read through
    tests/evals/eval_cases.py."""

    @staticmethod
    def _probes(positive=None):
        probes = eval_cases.probe_dicts()
        if positive is not None:
            probes = [p for p in probes if p["must_route"] is positive]
        return probes

    @staticmethod
    def _skill(probe):
        return probe["skill"].split(":", 1)[1]

    def test_create_docs_case_present_and_internally_consistent(self):
        matches = [p for p in self._probes(positive=True)
                   if self._skill(p) == "create-docs"]
        self.assertTrue(matches, "no create-docs probe")
        for probe in matches:
            self.assertNotIn("create-docs", probe["prompt"],
                             "the probe describes intent without naming the skill")
        self.assertTrue(
            any(len([x for x in SETS if x in p["prompt"]]) >= 2 for p in matches),
            "a probe should name more than one set, so routing must reach the "
            "umbrella and not a leg")

    def test_no_case_survives_for_a_retired_leg(self):
        probed = {self._skill(p) for p in self._probes()}
        for retired in RETIRED:
            self.assertNotIn(retired, probed)


class StandardizeProjectProbeTest(unittest.TestCase):
    """AC-9: standardize-project's routing cases (no paid model call).

    These parsed s04_skill_triggers.py's CASES/NEGATIVE lists, then read a
    routing dataset; both are gone, and the case files under plugins/acs/evals/
    are the probe set, read through tests/evals/eval_cases.py. The rule carried
    through every move: counts the suite states about itself are DERIVED here
    and never pinned, so a case change cascades to zero test edits. Applied to
    the old dataset it found the description claiming 24 natural-language
    probes when there were 26; the suite's README is where those counts live
    now, so that is what is held to them."""

    README = os.path.join(PLUGIN, "evals", "README.md")

    @staticmethod
    def _probes():
        return eval_cases.probe_dicts()

    @staticmethod
    def _skill(probe):
        return probe["skill"].split(":", 1)[1]

    def test_standardize_project_case_present_and_internally_consistent(self):
        probes = self._probes()
        positives = [p for p in probes
                     if p["must_route"] and self._skill(p) == "standardize-project"]
        self.assertTrue(positives, "the suite must carry a standardize-project positive")
        # ADR 0091 made this an internal leg, so its positive probe is the
        # explicit command, and the description that used to be the positive is
        # now the NEGATIVE -- the one that must NOT auto-route. The no-naming
        # rule follows the description to where it lives.
        self.assertEqual(
            positives[0]["prompt"].strip(), "/acs:standardize-project",
            "an internal leg's positive probe is the explicit command")
        negatives = [p for p in probes
                     if not p["must_route"] and self._skill(p) == "standardize-project"]
        self.assertTrue(negatives, "an internal leg needs a no-auto-route negative case")
        self.assertNotIn(
            "standardize", negatives[0]["prompt"],
            "the probe request must describe brownfield audit intent "
            "without naming the skill")

    def test_no_create_spec_routing_case(self):
        for probe in self._probes():
            self.assertNotEqual(self._skill(probe), "create-spec",
                                "no case may route to the deleted create-spec")
        # Nothing anywhere in the eval suite may mention the deleted skill
        # (AC-1, scope extension): scan every file of it, not just the graders.
        for dirpath, dirnames, filenames in os.walk(eval_cases.EVALS):
            dirnames[:] = [d for d in dirnames if d != "results"]
            for name in filenames:
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as fh:
                    self.assertNotIn(
                        "create-spec", fh.read(),
                        "%s references the deleted create-spec skill"
                        % os.path.relpath(path, REPO_ROOT))

    def test_readme_tag_counts_match_the_cases(self):
        """The README's tag table is part of the suite: a stale count there is
        how a reader forms a wrong belief about what it covers."""
        with open(self.README, encoding="utf-8") as fh:
            readme = fh.read()
        cases = eval_cases.all_cases()
        for tag in ("routing", "description", "explicit", "negative", "control",
                    "artifacts", "setup"):
            n = len([c for c in cases if tag in c.tags])
            with self.subTest(tag=tag):
                self.assertRegex(
                    readme, r"\| `%s` \| [^|]*?\b%d\b" % (re.escape(tag), n),
                    "README's %r row does not state the real count %d" % (tag, n))

    def test_readme_does_not_claim_more_coverage_than_the_cases_carry(self):
        shipped = set(eval_cases.shipped_skills())
        probed = {self._skill(p) for p in self._probes()}
        self.assertEqual(probed, shipped,
                         "every shipped skill must have a case before the "
                         "suite may be described as covering them")


class SuiteRunnerProbeTest(unittest.TestCase):
    """Approach item 4: one suite-runner routing probe, read from the curated
    dataset (no paid model call).

    MAR-114 added it as `test`; the skills-independence refactor renamed that
    skill to `run-e2e-tests` and left `test` behind as a deprecated alias
    directory, which v0.5.0 then deleted. The probe must expect
    `run-e2e-tests` — pinning `test` would pin an alias that no longer ships,
    which is exactly the stale assertion the guide-format migration found and
    removed from this dataset."""

    @staticmethod
    def _probes():
        return eval_cases.probe_dicts()

    @staticmethod
    def _skill(probe):
        return probe["skill"].split(":", 1)[1]

    def test_suite_runner_case_present_and_internally_consistent(self):
        probed = [self._skill(p) for p in self._probes()]
        self.assertIn("run-e2e-tests", probed,
                      "the suite must carry a run-e2e-tests routing case")
        self.assertNotIn("test", probed,
                         "no probe may name the deleted `test` alias directory")


class SetupRenameProbeTest(unittest.TestCase):
    """AC-5: no routing probe expects the stale skill literal "init".

    The probe set moved out of s04_skill_triggers.py's CASES list and into
    the routing case files under plugins/acs/evals/ when routing
    consolidated onto the `claude plugin eval` suite. The assertion is unchanged: `init` was renamed
    to `setup`, and a probe still naming the old literal asserts a skill that
    does not ship."""

    def test_eval_trigger_case_expects_setup(self):
        expected_skills = sorted({p["skill"].split(":", 1)[1]
                                  for p in eval_cases.probe_dicts()})
        self.assertNotIn(
            "init", expected_skills,
            "a probe expects the stale skill literal \"init\" -- expected "
            "\"setup\" (got expected-skill values: %s)" % expected_skills)

    def test_the_setup_routing_grader_names_the_skill(self):
        """Moved from the rename sweep's list of files that must positively
        name /acs:setup: the one eval-layer file on that list."""
        grader = os.path.join(eval_cases.EVALS, "routing", "route-setup", "graders",
                              "routes-to-setup.md")
        self.assertRegex(read(grader), r"/acs:setup|(?<![A-Za-z0-9_-])setup(?![A-Za-z0-9_-])")


class ArtifactCoverageClaimTest(unittest.TestCase):
    """The testing strategy's behavioural-coverage claim, "N of M skills",
    DERIVED from the eval suite: the distinct skills its artifact cases invoke.
    It was the literal "only 3 of" until the forge-tier create-pr scenario was
    retired with the behavioural harness; a literal would have gone on
    asserting that stale count. Moved from tests/acs/test_doc_fact_pins.py when
    evals left CI (ADR-0108); the doc's other two claims are still pinned there."""

    def test_the_artifact_numerator_matches_the_suite(self):
        artifact_skills = {g.skill() for c in eval_cases.all_cases()
                           if "artifacts" in c.tags for g in c.graders if g.skill()}
        self.assertTrue(artifact_skills, "found no artifact case to count")
        shipped = len(eval_cases.shipped_skills())
        text = read(os.path.join(REPO_ROOT, "docs", "quality", "testing-strategy.md"))
        self.assertIn("%d of %d skills" % (len(artifact_skills), shipped), text)


if __name__ == "__main__":
    unittest.main()
