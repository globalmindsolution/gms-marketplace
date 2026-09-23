"""MAR-118 -- /acs:setup and `standards_path` (AC-7), plus the standards set's
registry membership (AC-8).

AC-7 was a prose-contract test that /acs:setup's optional-settings batch
defaulted `standards_path` to `docs/standards`. ADR-0102 removed every
document-locating settings key: the standards set is found where the repo
keeps it, else created at the conventional `docs/standards/` that
`acs_lib.DOC_SETS` declares. AC-7 is therefore inverted into a guard that
setup -- its skill prose and its deterministic half, `setup_wizard.py` --
never names the key and that `DEFAULT_SETTINGS` never seeds it. The
"always ask explicitly" carve-out check was deleted with it: a key setup
never offers has no batch placement to pin. AC-8's registry assertions
are unchanged in intent.

Renamed under MAR-1 (the skill formerly invoked as acs:initialize is now
acs:setup).

Run:  python3 -m unittest tests.acs.test_setup_standards_path -v
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


class SetupOffersNoStandardsPathCase(unittest.TestCase):
    """AC-7, inverted by ADR-0102: no setting locates the standards set, so
    /acs:setup neither offers nor seeds `standards_path`."""

    def test_setup_never_names_standards_path(self):
        for path in (SKILL_PATH, WIZARD_PATH):
            with self.subTest(file=os.path.relpath(path, REPO_ROOT)):
                self.assertNotIn("standards_path", read(path))

    def test_default_settings_never_seed_standards_path(self):
        self.assertNotIn("standards_path", acs_lib.DEFAULT_SETTINGS)


class StandardsRegistryCase(unittest.TestCase):
    """AC-8, after ADR-0094: the standards set is a row of acs_lib.DOC_SETS -- the
    one skill that delivers it, create-docs, is the registered product skill
    and joins the derived HOOKED_SKILLS; the set's delivery-ticket title is
    the row's."""

    def test_standards_is_a_declared_doc_set(self):
        self.assertIn("standards", acs_lib.DOC_SETS)
        # ADR-0102: the row declares where a NEW set is created, not a key.
        self.assertEqual(acs_lib.DOC_SETS["standards"]["default_dir"], "docs/standards")
        self.assertNotIn("settings_key", acs_lib.DOC_SETS["standards"])

    def test_standards_delivery_ticket_title(self):
        self.assertEqual(acs_lib.DOC_SET_TITLES.get("standards"), "Product standards doc set")

    def test_create_docs_in_product_and_hooked_skills(self):
        self.assertIn("create-docs", acs_lib.PRODUCT_SKILLS)
        self.assertIn("create-docs", acs_lib.HOOKED_SKILLS)
        self.assertNotIn("create-standards", acs_lib.HOOKED_SKILLS,
                         "the leg skill was folded into create-docs (ADR-0094)")

if __name__ == "__main__":
    unittest.main()
