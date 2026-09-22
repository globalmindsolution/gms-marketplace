"""/acs:create-ticket — an up-front delegation satisfies the confirmation gate.

Step 2 of the skill is a deliberate human-in-the-loop checkpoint (MAR-55
invariant (c)): the coordinator presents the proposal and blocks for the
user. Headless, with nothing decided, it hands off with `needs_input` — which
is right, and is also why all three PIPE-create-ticket runs of the 2026-09-14
gate measurement produced nothing: the prompt gave the skill no answer to
"story or task?", "due date?", "AC changes?". The skill's own rule for a user
who says "you decide" is to record assumptions and continue; these tests pin
that a request delegating the decisions up front takes that path, that the
two guarded values stay guarded, and that the genuine non-interactive hand-off
survives.

Assertions are by whitespace-normalized substring, never by line number.
Run: python3 -m unittest tests.acs.test_create_ticket_delegated_confirmation -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "create-ticket", "SKILL.md")


def norm(text):
    return re.sub(r"\s+", " ", text)


class DelegationIsConfirmationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SKILL, encoding="utf-8") as fh:
            cls.body = norm(fh.read())

    def test_step_two_accepts_an_up_front_delegation(self):
        self.assertIn("A request that delegates the record up front IS the confirmation",
                      self.body)
        self.assertIn('"you decide"', self.body)
        self.assertIn("--source assumption --rationale", self.body)

    def test_a_delegated_question_is_never_handed_off(self):
        self.assertIn("Never return `needs_input` for a question the request already delegated",
                      self.body)

    def test_the_guarded_values_stay_guarded(self):
        # docs_only relaxes /code's gates and a PRD divergence changes scope:
        # neither is something a blanket "you decide" may settle.
        self.assertIn("keep `docs_only` at `false` (the one value a delegation never sets to `true`)",
                      self.body)
        self.assertIn("a delegation never confirms going beyond the PRD", self.body)

    def test_the_genuine_non_interactive_hand_off_survives(self):
        self.assertIn("If you genuinely cannot reach the user (e.g. a non-interactive run), return "
                      '`<handoff skill="create-ticket" ticket-id="<id>" status="needs_input">`',
                      self.body)
        self.assertIn("A request that delegates the decisions up front is not such a case",
                      self.body)


if __name__ == "__main__":
    unittest.main()
