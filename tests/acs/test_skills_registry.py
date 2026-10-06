"""A skill is described by its own directory (§2.4).

Replaces tests/acs/test_phases_registry.py, which pinned the central
`workflows/phases.yaml`. That file was the fifth copy of the skill list —
after the 18-name enum in the pipeline-state schema, the 33-name enum in the
skill-state schema and the two `argparse` copies — and removing four of five
would have left the one the others were copies of.

What these pin:

  * discovery is by LISTING, so a skill cannot be missing from a registry
  * there is no per-skill manifest: each skill is independent, and nothing
    declares what it reads or writes for a gate to enforce
  * a leg is not a step
  * subagents are per skill, named for what they do, and every role has a
    kind the hooks act on
  * PRD G8 (every agent file is reachable) is a naming-convention check

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

    def test_there_is_no_per_skill_manifest(self):
        """acs.yaml is gone: a skill is its SKILL.md, and the workflow only
        orders skills -- it asks nothing of what they read or write."""
        for skill in K.registered_skills():
            self.assertFalse(os.path.exists(os.path.join(K.skill_dir(skill), "acs.yaml")),
                             skill)
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "schemas",
                                                     "acs-skill.schema.json")))

    def test_the_deprecated_test_alias_is_gone(self):
        self.assertNotIn("test", K.registered_skills())

    def test_analyze_ticket_was_renamed(self):
        skills = K.registered_skills()
        self.assertNotIn("analyze-" + "ticket", skills)
        self.assertIn("analyze-requirements", skills)


class LegTest(unittest.TestCase):

    def test_the_legs_are_legs(self):
        legs = K.skill_legs()
        for leg in ("code-trivial", "code-small", "code-standard", "code-complex"):
            self.assertEqual(legs.get(leg), "code", leg)
        self.assertEqual(sorted(legs), ["code-complex", "code-small", "code-standard",
                                        "code-trivial"])

    def test_all_four_code_legs_survive_the_redesign(self):
        self.assertEqual(K.legs_of("code"),
                         ["code-complex", "code-small", "code-standard", "code-trivial"])

    def test_every_leg_and_entry_point_ships(self):
        for leg, entry in K.skill_legs().items():
            self.assertTrue(K.is_skill(leg), leg)
            self.assertTrue(K.is_skill(entry), entry)

    def test_a_user_facing_skill_is_nobodys_leg(self):
        self.assertIsNone(K.entry_point_of("code"))
        self.assertIsNone(K.entry_point_of("review-code"))

    def test_no_leg_is_a_step_of_ship(self):
        wf = W.validate_workflow_file(SHIP)
        self.assertEqual(set(W.steps_of(wf)) & set(K.skill_legs()), set())


class AgentConventionTest(unittest.TestCase):
    """PRD G8 — every agent file is reachable — by naming convention rather
    than by a registry kept in step with the tree."""

    def test_no_agent_file_is_unreachable(self):
        self.assertEqual(K.unreachable_agents(), [])

    def test_every_role_has_a_kind(self):
        for role, kind in K.ROLE_KINDS.items():
            self.assertIn(kind, K.ROLE_KIND_NAMES, role)

    def test_hyphenated_skills_and_roles_split_right(self):
        """Neither half is positional: `code` is a prefix of `code-small`, and
        `plan-reviewer` is a role with a hyphen of its own."""
        self.assertEqual(K.split_agent_name("create-impl-plan-plan-reviewer"),
                         ("create-impl-plan", "plan-reviewer"))
        self.assertEqual(K.split_agent_name("code-implementer"), ("code", "implementer"))
        self.assertEqual(K.split_agent_name("create-pr-executor"), (None, None))
        self.assertEqual(K.split_agent_name("nope-reviewer"), (None, None))

    def test_no_skill_owns_the_generic_triad(self):
        """Subagents are named for what they do. No agent is a generic
        `executor` or `verifier` any more."""
        for name in K.agent_files():
            self.assertFalse(name.endswith(("-executor", "-verifier")), name)

    def test_agents_are_read_from_the_tree(self):
        """`code` has an implementer and nothing else: the review is
        /acs:review-code's (§3.5)."""
        self.assertEqual(K.agent_roles_of("code"), ["implementer"])

    def test_review_code_owns_a_lens_and_an_adjudicator(self):
        self.assertEqual(sorted(K.agent_roles_of("review-code")), ["adjudicator", "lens"])

    def test_mechanical_skills_own_no_agents(self):
        """A dispatcher, and a skill whose work is a sequence of commands
        (breakdown-ticket, create-pr, merge-pr), runs inline. create-ticket
        left this list with ADR-0138: one type author drafts, a reviewer judges."""
        for skill in ("ship", "breakdown-ticket", "create-pr", "merge-pr"):
            self.assertEqual(K.agent_roles_of(skill), [], skill)

    def test_create_ticket_owns_four_type_authors_and_a_reviewer(self):
        self.assertEqual(sorted(K.agent_roles_of("create-ticket")),
                         ["bug-author", "epic-author", "reviewer",
                          "story-author", "task-author"])


if __name__ == "__main__":
    unittest.main()
