"""MAR-117 -- /acs:setup and `principles_path` (AC-7), plus the principles set's
registry membership (AC-8).

AC-7 was a prose-contract test that /acs:setup's optional-settings batch
defaulted `principles_path` to `docs/principles`. ADR-0102 removed every
document-locating settings key: the principles set is found where the repo
keeps it (ADR-0124 removed /acs:create-docs, the skill that created one at
the conventional `docs/principles/`). AC-7 is therefore inverted into a guard that
setup -- its skill prose and its deterministic half, `setup_wizard.py` --
never names the key and that `DEFAULT_SETTINGS` never seeds it. The
"always ask explicitly" carve-out check was deleted with it: a key setup
never offers has no batch placement to pin. AC-8's registry assertions
pinned the skill that delivered the set; ADR-0124 removed it, so they now
pin that neither it nor the leg it folded in is registered.

Renamed under MAR-1 (the skill formerly invoked as acs:initialize is now
acs:setup).

Run:  python3 -m unittest tests.acs.test_setup_principles_path -v
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "setup", "SKILL.md")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
WIZARD_PATH = os.path.join(HOOKS_DIR, "setup_wizard.py")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class SetupOffersNoPrinciplesPathCase(unittest.TestCase):
    """AC-7, inverted by ADR-0102: no setting locates the principles set, so
    /acs:setup neither offers nor seeds `principles_path`."""

    def test_setup_never_names_principles_path(self):
        for path in (SKILL_PATH, WIZARD_PATH):
            with self.subTest(file=os.path.relpath(path, REPO_ROOT)):
                self.assertNotIn("principles_path", read(path))

    def test_default_settings_never_seed_principles_path(self):
        self.assertNotIn("principles_path", acs_lib.DEFAULT_SETTINGS)


class PrinciplesRegistryCase(unittest.TestCase):
    """AC-8, after ADR-0124: no skill delivers the principles set any more. The
    repo writes it by hand; the skills that read it find it where it is."""

    def test_no_skill_delivers_the_principles_set(self):
        for retired in ("create-docs", "create-principles"):
            with self.subTest(skill=retired):
                self.assertNotIn(retired, acs_lib.PRODUCT_SKILLS)
                self.assertNotIn(retired, acs_lib.HOOKED_SKILLS)
        self.assertFalse(hasattr(acs_lib, "DOC_SETS"))


if __name__ == "__main__":
    unittest.main()
