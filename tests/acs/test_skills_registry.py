"""A skill is described by its own directory (§2.4).

Replaces tests/acs/test_phases_registry.py, which pinned the central
`workflows/phases.yaml`. That file was the fifth copy of the skill list —
after the 18-name enum in the pipeline-state schema, the 33-name enum in the
skill-state schema and the two `argparse` copies — and removing four of five
would have left the one the others were copies of.

What these pin:

  * discovery is by LISTING, so a skill cannot be missing from a registry
  * `reads` / `writes` are the single declaration both `acs workflow validate`
    and the runtime input gate consult, so they cannot disagree
  * a leg is not a step, and a skill that declares no I/O is not one either
  * PRD G8 (every agent file is reachable) is a naming-convention check now

Run:  python3 -m unittest tests.acs.test_skills_registry -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "plugins", "acs", "hooks", "scripts"))

from acs_lib import skills as K  # noqa: E402
from acs_lib import workflow as W  # noqa: E402

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "plugins", "acs")
SHIP = os.path.join(PLUGIN, "workflows", "ship.yaml")


class DiscoveryTest(unittest.TestCase):

    def setUp(self):
        self.manifests = K.load_manifests()

    def test_a_skill_exists_when_its_directory_holds_a_skill_md(self):
        """No list to keep in step with the tree."""
        found = K.registered_skills()
        on_disk = sorted(n for n in os.listdir(K.skills_dir())
                         if os.path.isfile(os.path.join(K.skills_dir(), n, "SKILL.md")))
        self.assertEqual(found, on_disk)
        self.assertIn("review-code", found)

    def test_there_is_no_phases_yaml(self):
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "workflows", "phases.yaml")),
                         "phases.yaml is removed; a skill describes itself")

    def test_the_deprecated_test_alias_is_gone(self):
        self.assertNotIn("test", K.registered_skills())

    def test_analyze_ticket_was_renamed(self):
        skills = K.registered_skills()
        self.assertNotIn("analyze-" + "ticket", skills)
        self.assertIn("analyze-requirements", skills)

    def test_every_manifest_is_schema_valid(self):
        for skill in K.registered_skills():
            K.load_manifest(skill)   # raises SkillsError on a bad one

    def test_a_skill_may_declare_nothing(self):
        """`{}` is a legitimate answer: acs knows it exists and nothing more."""
        self.assertEqual(K.load_manifest("no-such-skill"), {})


class DeclarationTest(unittest.TestCase):

    def setUp(self):
        self.manifests = K.load_manifests()

    def test_the_legs_are_legs_and_not_steps(self):
        legs = K.skill_legs(self.manifests)
        for leg in ("code-trivial", "code-small", "code-standard", "code-complex"):
            self.assertEqual(legs.get(leg), "code", leg)
            self.assertFalse(K.is_step_candidate(leg, self.manifests), leg)

    def test_all_four_legs_survive_the_redesign(self):
        self.assertEqual(K.legs_of("code", self.manifests),
                         ["code-complex", "code-small", "code-standard", "code-trivial"])

    def test_a_leg_reports_its_entry_points_phase(self):
        self.assertEqual(K.phase_of("code-standard", self.manifests), "build")

    def test_a_skill_with_no_io_is_not_a_step(self):
        """setup, metrics, handoff and ship itself are skills, not steps, and
        that is the whole admission rule."""
        for skill in ("setup", "metrics", "handoff", "ship", "usage", "update"):
            self.assertFalse(K.is_step_candidate(skill, self.manifests), skill)

    def test_review_code_declares_what_it_needs(self):
        required, optional = K.reads_of("review-code", self.manifests)
        self.assertEqual(required, ["changeset"])
        self.assertIn("test-cases", optional)
        self.assertEqual(K.writes_of("review-code", self.manifests), ["verdict"])

    def test_every_step_of_ship_is_a_step_candidate(self):
        wf = W.validate_workflow_file(SHIP)
        for step in W.steps_of(wf):
            self.assertTrue(K.is_step_candidate(step, self.manifests), step)


class AgentConventionTest(unittest.TestCase):
    """PRD G8 — every agent file is reachable — by naming convention rather
    than by a registry kept in step with the tree."""

    def test_no_agent_file_is_unreachable(self):
        self.assertEqual(K.unreachable_agents(), [])

    def test_agents_are_read_from_the_tree(self):
        """`code` has an executor and nothing else: its verifier moved out to
        /acs:review-code, and the agent file left with it (§3.5)."""
        self.assertEqual(K.agent_roles_of("code"), ["executor"])

    def test_review_code_owns_a_lens_and_an_adjudicator(self):
        self.assertEqual(K.agent_roles_of("review-code"), ["lens", "adjudicator"])

    def test_a_dispatcher_owns_no_agents(self):
        self.assertEqual(K.agent_roles_of("ship"), [])


if __name__ == "__main__":
    unittest.main()
