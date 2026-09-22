"""Successor to MAR-114's `/acs:test` registry wiring (AC-6 registry half).

MAR-114 pinned `"test"` into `UNHOOKED_SKILLS` and out of every other list:
`/acs:test` ran the suites without a gate, and the point was that dispatch's
`skill not in acs_lib.HOOKED_SKILLS` passthrough exempted it with no dispatch
code change.

The skills-independence refactor renamed it `run-e2e-tests` and left `test`
behind as a deprecated alias DIRECTORY; v0.5.0 deleted the alias and made
`run-e2e-tests` a hooked step of `ship.yaml`. So the registry claim inverted:
the suite runner is gated now, and what must be asserted is that the rename
went all the way through -- one name, in the right list, with no alias left
behind for a reader to find.

Run:  python3 -m unittest tests.acs.test_run_e2e_tests_registry -v
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402


class TestAliasRetiredCase(unittest.TestCase):
    """`test` is gone as a name, a directory and a registry row."""

    def test_test_is_in_no_registry_list(self):
        for name, registry in (
            ("UNHOOKED_SKILLS", acs_lib.UNHOOKED_SKILLS),
            ("HOOKED_SKILLS", acs_lib.HOOKED_SKILLS),
            ("PRODUCT_SKILLS", acs_lib.PRODUCT_SKILLS),
            ("WORKFLOW_SKILLS", acs_lib.WORKFLOW_SKILLS),
            ("PLANNING_SKILLS", acs_lib.PLANNING_SKILLS),
        ):
            with self.subTest(registry=name):
                self.assertNotIn("test", registry)

    def test_no_test_skill_directory_on_disk(self):
        """A skill is a DIRECTORY, so the directory is the registration: an
        alias left on disk would still be model-invocable."""
        self.assertFalse(
            os.path.isdir(os.path.join(PLUGIN, "skills", "test")))

    def test_no_pre_or_post_test_hook_on_disk(self):
        for name in ("pre-test.py", "post-test.py"):
            with self.subTest(hook=name):
                self.assertFalse(os.path.isfile(os.path.join(HOOKS_DIR, name)))


class RunE2eTestsIsAGatedStepCase(unittest.TestCase):
    """The suite runner is a hooked step now, not an ungated utility."""

    def test_it_is_a_workflow_skill(self):
        self.assertIn("run-e2e-tests", acs_lib.WORKFLOW_SKILLS)
        self.assertIn("run-e2e-tests", acs_lib.HOOKED_SKILLS)
        self.assertNotIn("run-e2e-tests", acs_lib.UNHOOKED_SKILLS)

    def test_it_is_a_step_of_the_shipped_workflow(self):
        wf = acs_lib.validate_workflow_file(acs_lib.default_workflow_path())
        self.assertIn("run-e2e-tests", acs_lib.steps_of(wf))

    def test_it_has_both_hooks_on_disk(self):
        for name in ("pre-run-e2e-tests.py", "post-run-e2e-tests.py"):
            with self.subTest(hook=name):
                self.assertTrue(os.path.isfile(os.path.join(HOOKS_DIR, name)))


if __name__ == "__main__":
    unittest.main()
