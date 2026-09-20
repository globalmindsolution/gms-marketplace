"""Every coordinator that spawns a subagent spawns it in the foreground and
waits on the result, never on a clock.

On the 2026-09-15 release gate an /acs:analyze-requirements coordinator's executor
and verifier were both moved to the background by the runtime; the
coordinator waited on each with `for i in $(seq 1 40); do sleep 15; done`,
ten fixed minutes apiece, and the 1800s setup budget ran out as iteration 2
began. Across 56 measured sessions, 17 such sleep loops appeared in 6
transcripts. The rule now sits beside every spawn instruction.

A skill's contract is its SKILL.md plus any `references/` the skill points at:
ADR-0095's four delivery-path legs each spawn `acs:code-executor` and
`acs:code-verifier`, and each reads the spawn protocol from the reference all
four share rather than repeating it. Reading the concatenation is what keeps
that honest — the rule has to be somewhere the coordinator reads, and this
test does not care which file that is.

Run: python3 -m unittest tests.acs.test_coordinators_spawn_in_foreground -v
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILLS = os.path.join(REPO_ROOT, "src", "acs", "skills")

RULE = "Spawn in the foreground and wait on the result, never on a clock."


def norm(text):
    return re.sub(r"\s+", " ", text)


class CoordinatorsSpawnInForegroundTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spawning = {}
        for path in sorted(glob.glob(os.path.join(SKILLS, "*", "SKILL.md"))):
            skill = os.path.basename(os.path.dirname(path))
            own = open(path, encoding="utf-8").read()
            # Every ROLE, not just the pair: `review-code` spawns a lens and
            # an adjudicator, and a regex naming only executor/verifier let it
            # out of a rule that applies to it word for word.
            if not (re.search(r"acs:[a-z0-9-]+-(executor|verifier|lens|adjudicator)",
                              own)
                    and "Agent tool" in own):
                continue
            cls.spawning[skill] = norm("\n".join([own] + cls._references(own)))

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

    def test_the_rule_covers_every_spawning_coordinator(self):
        self.assertGreaterEqual(len(self.spawning), 14, sorted(self.spawning))
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
