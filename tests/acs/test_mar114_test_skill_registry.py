"""MAR-114 — /acs:test registry wiring (AC-6 registry half).

`"test"` must land in `UNHOOKED_SKILLS` only — never `HOOKED_SKILLS`,
`PRODUCT_SKILLS`, or `WORKFLOW_SKILLS` — proving `dispatch.py`'s existing
`skill not in acs_lib.HOOKED_SKILLS` passthrough (`dispatch.py:57`) exempts
`/acs:test` with zero dispatch code change, and that `skill-start.py`'s
`--skill choices=lib.HOOKED_SKILLS` cannot select it.

Run:  python3 -m unittest tests.acs.test_mar114_test_skill_registry -v
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOKS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402


class Mar114TestSkillRegistryCase(unittest.TestCase):
    def test_test_in_unhooked_skills(self):
        self.assertIn(
            "test", acs_lib.UNHOOKED_SKILLS,
            msg="'test' must be registered in UNHOOKED_SKILLS (AC-6)",
        )

    def test_test_not_in_hooked_skills(self):
        self.assertNotIn(
            "test", acs_lib.HOOKED_SKILLS,
            msg="'test' must NOT be in HOOKED_SKILLS — it is not a hooked "
                "pipeline skill (proves dispatch.py passthrough at exit 0)",
        )

    def test_test_not_in_product_skills(self):
        self.assertNotIn(
            "test", acs_lib.PRODUCT_SKILLS,
            msg="'test' must NOT be miscategorized into PRODUCT_SKILLS",
        )

    def test_test_not_in_workflow_skills(self):
        self.assertNotIn(
            "test", acs_lib.WORKFLOW_SKILLS,
            msg="'test' must NOT be miscategorized into WORKFLOW_SKILLS",
        )


if __name__ == "__main__":
    unittest.main()
