"""A subject opens its run from the CLI, not only from the pre-hook.

`/acs:ship` begins with `acs run next`, which its SKILL.md said "takes the
same subject flags" -- it took only --run, so shipping a prompt, or a ticket
with no run yet, stopped at "no current run". And `acs step start --args
"<prompt>"`, the coordinator's mandatory first action, failed the same way
unless a PreToolUse(Skill) hook had created the run first -- i.e. on every
host that does not fire it.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib  # noqa: E402


class RunNextResolvesASubjectTest(AcsWorkspaceCase):

    def run_next(self, *argv):
        out = self.run_script("acs.py", "run", "next", *argv)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_a_prompt_opens_a_run_and_a_second_call_resumes_it(self):
        first = self.run_next("--prompt", "cap the customer page size at 100")
        self.assertEqual(first["next"], lib.steps_of(self.workflow())[0])
        again = self.run_next("--prompt", "cap the customer page size at 100")
        self.assertEqual(again["run_id"], first["run_id"])
        self.assertEqual(self.run_next()["run_id"], first["run_id"],
                         "the checkout now points at it")

    def test_a_ticket_opens_its_run_once(self):
        story = self.new_ticket("Wishlist API", "story")
        first = self.run_next("--ticket", story)
        self.assertEqual(first["run_id"], story)
        self.assertEqual(self.run_next("--ticket", story)["run_id"], story)

    def test_an_unknown_ticket_is_refused(self):
        out = self.run_script("acs.py", "run", "next", "--ticket", "SHOP-99")
        self.assertEqual(out.returncode, 2)
        self.assertIn("no ticket SHOP-99", out.stderr)


class StepStartFromItsArgumentsTest(AcsWorkspaceCase):

    def test_a_prompt_subject_opens_its_run_without_a_hook(self):
        step = lib.steps_of(self.workflow())[0]
        out = self.run_script("acs.py", "step", "start", "--step", step,
                              "--args", "fix the login timeout")
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual(doc["subject"], {"kind": "prompt", "text": "fix the login timeout"})

    def test_an_epic_named_in_the_arguments_is_braked_before_any_run(self):
        epic = self.new_ticket("Order tracking", "epic")
        out = self.run_script("acs.py", "step", "start", "--step", "analyze-requirements",
                              "--args", epic)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.rdir(epic), "run.json")))


if __name__ == "__main__":
    import unittest
    unittest.main()
