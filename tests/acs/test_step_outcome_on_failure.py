"""An outcome says how a step COMPLETED; a step that did not complete owes none.

/acs:run-e2e-tests' outcome vocabulary is `passed | no_harness |
nothing_to_run` -- three ways to complete. Its red run finishes `failed`, but
`validate_result` demanded an outcome from every result of a multi-outcome
skill, whatever its status, so the post-hook refused every result a red run
could write and the step could never be finalized.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib  # noqa: E402

RED = {"status": "failed",
       "summary": "1/2 suites passed; e2e failed",
       "findings": ["e2e:tests/e2e/test_customers.py::test_page_size failed; SHOP-2 minted"]}


class OutcomeVocabularyTest(unittest.TestCase):

    def test_a_failed_step_of_a_multi_outcome_skill_needs_no_outcome(self):
        self.assertEqual(lib.validate_result(dict(RED), "run-e2e-tests"), [])

    def test_an_interrupted_step_needs_no_outcome_either(self):
        doc = {"status": "interrupted", "stop_reason": "session_end"}
        self.assertEqual(lib.validate_result(doc, "run-e2e-tests"), [])

    def test_a_completed_step_still_says_which_way_it_completed(self):
        errors = lib.validate_result({"status": "completed"}, "run-e2e-tests")
        self.assertEqual(len(errors), 1)
        self.assertIn("must say which", errors[0])

    def test_an_outcome_given_on_failure_is_still_checked(self):
        errors = lib.validate_result(dict(RED, outcome="red"), "run-e2e-tests")
        self.assertEqual(len(errors), 1)
        self.assertIn("'red' is not one of", errors[0])


class RedRunFinalizesTest(AcsWorkspaceCase):

    def test_the_post_hook_finalizes_a_red_run_as_failed(self):
        ticket = self.new_ticket("Nightly e2e run", "task")
        self.walk_to(ticket, "create-e2e-tests")
        out = self.start("run-e2e-tests", ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        out = self.post("run-e2e-tests", ticket, RED)
        self.assertEqual(out.returncode, 0, out.stderr)
        entry = lib.step_entry(lib.load_run(self.rdir(ticket)), "run-e2e-tests")
        self.assertEqual(entry.get("status"), "failed", entry)


if __name__ == "__main__":
    unittest.main()
