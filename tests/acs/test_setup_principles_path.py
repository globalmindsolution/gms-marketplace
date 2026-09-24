"""MAR-117 -- /acs:setup and `principles_path` (AC-7), plus the principles set's
registry membership (AC-8).

AC-7 was a prose-contract test that /acs:setup's optional-settings batch
defaulted `principles_path` to `docs/principles`. ADR-0102 removed every
document-locating settings key: the principles set is found where the repo
keeps it, else created at the conventional `docs/principles/` that
`acs_lib.DOC_SETS` declares. AC-7 is therefore inverted into a guard that
setup -- its skill prose and its deterministic half, `setup_wizard.py` --
never names the key and that `DEFAULT_SETTINGS` never seeds it. The
"always ask explicitly" carve-out check was deleted with it: a key setup
never offers has no batch placement to pin. AC-8's registry assertions
are unchanged in intent.

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
    """AC-8, after ADR-0094: the principles set is a row of acs_lib.DOC_SETS -- the
    one skill that delivers it, create-docs, is the registered product skill
    and joins the derived HOOKED_SKILLS; the set's delivery-ticket title is
    the row's."""

    def test_principles_is_a_declared_doc_set(self):
        self.assertIn("principles", acs_lib.DOC_SETS)
        # ADR-0102: the row declares where a NEW set is created, not a key.
        self.assertEqual(acs_lib.DOC_SETS["principles"]["default_dir"], "docs/principles")
        self.assertNotIn("settings_key", acs_lib.DOC_SETS["principles"])

    def test_principles_delivery_ticket_title(self):
        self.assertEqual(acs_lib.DOC_SET_TITLES.get("principles"), "Product principles doc set")

    def test_create_docs_in_product_and_hooked_skills(self):
        self.assertIn("create-docs", acs_lib.PRODUCT_SKILLS)
        self.assertIn("create-docs", acs_lib.HOOKED_SKILLS)
        self.assertNotIn("create-principles", acs_lib.HOOKED_SKILLS,
                         "the leg skill was folded into create-docs (ADR-0094)")

if __name__ == "__main__":
    unittest.main()
