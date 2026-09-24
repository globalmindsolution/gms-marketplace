"""MAR-112 -- /acs:setup and `quality_path` (AC-3), inverted by ADR-0102.

AC-3 was a prose-contract test that /acs:setup's optional-settings batch
defaulted `quality_path` to `docs/quality` and named `/acs:create-docs quality` as
its consumer. ADR-0102 removed every document-locating settings key: the
quality set is found where the repo keeps it, else created at the conventional
`docs/quality/` that `acs_lib.DOC_SETS` declares. AC-3 is therefore inverted
into a guard that setup -- its skill prose and its deterministic half,
`setup_wizard.py` -- never names the key and that `DEFAULT_SETTINGS` never
seeds it. The "always ask explicitly" carve-out check was deleted with it: a
key setup never offers has no batch placement to pin.

Renamed under MAR-1 (the skill formerly invoked as acs:initialize is now
acs:setup).

Run:  python3 -m unittest tests.acs.test_setup_quality_path -v
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


class SetupOffersNoQualityPathCase(unittest.TestCase):
    """AC-3, inverted by ADR-0102: no setting locates the quality set, so
    /acs:setup neither offers nor seeds `quality_path`."""

    def test_setup_never_names_quality_path(self):
        for path in (SKILL_PATH, WIZARD_PATH):
            with self.subTest(file=os.path.relpath(path, REPO_ROOT)):
                self.assertNotIn("quality_path", read(path))

    def test_default_settings_never_seed_quality_path(self):
        self.assertNotIn("quality_path", acs_lib.DEFAULT_SETTINGS)

    def test_the_quality_set_default_is_declared_on_its_row(self):
        self.assertEqual(acs_lib.DOC_SETS["quality"]["default_dir"], "docs/quality")


if __name__ == "__main__":
    unittest.main()
