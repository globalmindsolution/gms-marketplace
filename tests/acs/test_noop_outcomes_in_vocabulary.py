"""Every evidenced no-op records an outcome its step's fragment admits.

`stepgate.NO_OP_STEPS` gave run-e2e-tests `no_e2e_owed` -- create-e2e-tests'
word -- while run-e2e-tests' state fragment admits only `passed`,
`no_harness` and `nothing_to_run`. The pre-hook wrote a step result its own
post-hook's validator would refuse.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import lib  # noqa: E402
from acs_lib import stepgate  # noqa: E402


class NoOpOutcomesTest(unittest.TestCase):

    def test_every_no_op_outcome_is_in_its_steps_vocabulary(self):
        for step, (_key, outcome, _reason) in sorted(stepgate.NO_OP_STEPS.items()):
            with self.subTest(step=step):
                self.assertIn(outcome, lib.outcome_vocabulary(step))


if __name__ == "__main__":
    unittest.main()
