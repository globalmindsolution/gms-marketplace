"""Every verifier polices grounding for truth, not for citation precision.

The 2026-09-15 release gate ran the app-profile /acs:analyze-requirements through
three executor+verifier iterations and was killed one second short of the
1800s setup budget. Iteration 1 found one real omission (a test file missing
from the impact map); iterations 2 and 3 were spent entirely on citations
that named the right file at the wrong lines while the cited fact held. The
shared grounding rule in every verifier charter — "police grounding too" —
now carries one carve-out: a right-file, wrong-lines citation or a loose
paraphrase is noted, not a finding; a source that says otherwise, a missing
file, or an uncited repo fact still blocks.

Assertions are by substring on every *-verifier.md under src/acs/agents.
Run: python3 -m unittest tests.acs.test_verifier_grounding_precision -v
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AGENTS = os.path.join(REPO_ROOT, "src", "acs", "agents")


def norm(text):
    return re.sub(r"\s+", " ", text)


class VerifierGroundingPrecisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifiers = sorted(glob.glob(os.path.join(AGENTS, "*-verifier.md")))
        cls.bodies = {os.path.basename(p): norm(open(p, encoding="utf-8").read())
                      for p in cls.verifiers}

    def test_there_are_verifiers_to_check(self):
        # /acs:code's verifier left with the review (§3.5); the rule still
        # binds every verifier that remains.
        self.assertGreaterEqual(len(self.verifiers), 13, self.verifiers)

    def test_every_verifier_still_polices_grounding(self):
        for name, body in self.bodies.items():
            self.assertIn("police grounding", body, name)
            self.assertIn("unverifiable work is unverified work", body, name)

    def test_every_verifier_blocks_on_truth_not_precision(self):
        for name, body in self.bodies.items():
            self.assertIn("Precision is not the test; truth is.", body, name)
            self.assertIn("the right file but the wrong lines or section", body, name)
            self.assertRegex(body, r"(?i)is not a finding while the cited fact holds", name)
            self.assertRegex(body, r"(?i)What blocks: a source that does not say what the draft claims", name)

    def test_the_analysis_and_plan_grounding_dimensions_say_so_too(self):
        for name in ("analyze-requirements-verifier.md", "create-impl-plan-verifier.md"):
            self.assertIn("The right file cited at the wrong lines, with the fact intact, is not",
                          self.bodies[name], name)


if __name__ == "__main__":
    unittest.main()
