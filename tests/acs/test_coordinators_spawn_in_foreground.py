"""Every coordinator that spawns a subagent spawns it in the foreground and
waits on the result, never on a clock.

On the 2026-09-15 release gate an /acs:analyze-requirements coordinator's executor
and verifier were both moved to the background by the runtime; the
coordinator waited on each with `for i in $(seq 1 40); do sleep 15; done`,
ten fixed minutes apiece, and the 1800s setup budget ran out as iteration 2
began. Across 56 measured sessions, 17 such sleep loops appeared in 6
transcripts. The rule now sits beside every spawn instruction.

A skill's contract is its SKILL.md plus any `references/` the skill points at:
ADR-0095's four delivery-path legs each spawn `acs:code-implementer`, and each
reads the spawn protocol from the reference all four share rather than
repeating it. Reading the concatenation is what keeps
that honest — the rule has to be somewhere the coordinator reads, and this
test does not care which file that is.

Run: python3 -m unittest tests.acs.test_coordinators_spawn_in_foreground -v
"""

import glob
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILLS = os.path.join(REPO_ROOT, "plugins", "acs", "skills")

RULE = "Spawn in the foreground and wait on the result, never on a clock."

sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
from acs_lib import skills as registry  # noqa: E402


def norm(text):
    return re.sub(r"\s+", " ", text)


class CoordinatorsSpawnInForegroundTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Every subagent acs ships, read from the agents tree
        # (`skill_agents()`, validated against ROLE_KINDS) -- never from a
        # list of role names. A regex naming only executor/verifier once let
        # `review-code`'s lens and adjudicator out of a rule that applies to
        # them word for word; a list of role names would do the same to the
        # next role a skill's logic calls for.
        cls.owned = registry.skill_agents()
        cls.agents = sorted(
            ("acs:%s-%s" % (skill, role) for skill, roles in cls.owned.items()
             for role in roles if registry.role_kind(role)),
            key=len, reverse=True)
        spawn_re = re.compile(r"(?:%s)\b" % "|".join(re.escape(a) for a in cls.agents))
        cls.spawning = {}
        for path in sorted(glob.glob(os.path.join(SKILLS, "*", "SKILL.md"))):
            skill = os.path.basename(os.path.dirname(path))
            own = open(path, encoding="utf-8").read()
            refs = cls._references(own)
            contract = "\n".join([own] + refs)
            # A coordinator spawns when its contract names a shipped agent
            # and the Agent tool it spawns it with.
            if not (spawn_re.search(contract) and "Agent tool" in contract):
                continue
            cls.spawning[skill] = norm(contract)

    @staticmethod
    def _references(body):
        """The reference files this SKILL.md tells its coordinator to read."""
        out = []
        for rel in sorted(set(re.findall(
                r"skills/([a-z0-9-]+/references/[a-z0-9-]+\.md)", body))):
            path = os.path.join(SKILLS, rel)
            if os.path.isfile(path):
                out.append(open(path, encoding="utf-8").read())
        return out

    def test_every_agent_owning_skill_has_a_spawning_coordinator(self):
        """Every skill that owns a subagent is spawned from somewhere this
        test reads: its own SKILL.md, or one of its legs' (`/acs:code`'s
        implementer is spawned by the four delivery-path legs)."""
        self.assertTrue(self.owned, "no agents found under plugins/acs/agents")
        for skill in sorted(self.owned):
            spawners = [skill] + registry.legs_of(skill)
            self.assertTrue(any(s in self.spawning for s in spawners),
                            "%s owns %s but no coordinator (%s) spawns them via the Agent tool"
                            % (skill, self.owned[skill], ", ".join(spawners)))

    def test_the_rule_covers_every_spawning_coordinator(self):
        self.assertIn("review-code", self.spawning,
                      "the reviewer spawns lenses and adjudicators; the rule "
                      "applies to it word for word")
        for skill, body in sorted(self.spawning.items()):
            if skill in ("ship", "release", "create-ticket", "create-pr", "merge-pr"):
                continue  # no reflection-loop spawn of their own, or an optional inline executor
            self.assertIn(RULE, body, skill)
            self.assertIn("`run_in_background: false`", body, skill)
            self.assertRegex(body, r"(?i)never poll with `sleep` loops", skill)


if __name__ == "__main__":
    unittest.main()
