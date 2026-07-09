"""MAR-118 — /acs:init Step 4 documents and defaults standards_path (AC-7),
plus create-standards registry membership (AC-8).

Prose-contract unit test for `plugins/acs/skills/init/SKILL.md`. `standards_path`
must be defaulted like `principles_path`/`quality_path`/`operations_path` in
the Step 4 optional-settings batch, and must NOT be added to the "always ask
explicitly" carve-out (which names only `### models` and `e2e`).

Stdlib-only (os, re, sys, unittest), mirroring
tests/acs/test_mar117_principles_path_init.py's `section()` bounded-window
technique so a stray mention elsewhere in the file cannot satisfy either
assertion, plus direct acs_lib registry assertions mirroring
tests/acs/test_mar117_principles_path_init.py's registry-case shape.

Run:  python3 -m unittest tests.acs.test_mar118_standards_path_init -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "init", "SKILL.md")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", body)
    if m is None:
        raise AssertionError("heading %r not found in SKILL.md" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class Mar118StandardsPathInitCase(unittest.TestCase):
    """Fixture: read the init SKILL.md once and isolate its Step 4 section."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.step4 = section(cls.body, "## Step 4")

    def test_step4_batch_documents_standards_path_default(self):
        """The Step 4 batch-default bullet list names standards_path with its
        default 'docs/standards' in a bounded window after the marker, proving
        the default is documented (not merely present in the schema)."""
        m = re.search(r"`standards_path`", self.step4)
        self.assertIsNotNone(
            m, "Step 4 must document a `standards_path` bullet (AC-7)"
        )
        window = self.step4[m.start():m.start() + 300]
        self.assertIn(
            "docs/standards", window,
            msg="the `standards_path` bullet must state its default "
                "'docs/standards' within a bounded window of the marker (AC-7)",
        )

    def test_step4_names_create_standards_as_consumer(self):
        """The standards_path bullet names /acs:create-standards as the
        consuming skill, mirroring how the principles_path bullet names
        /acs:create-principles."""
        m = re.search(r"`standards_path`", self.step4)
        self.assertIsNotNone(m)
        window = self.step4[m.start():m.start() + 300]
        self.assertIn(
            "create-standards", window,
            msg="the `standards_path` bullet must name /acs:create-standards "
                "as the consumer (AC-7)",
        )

    def test_carveout_does_not_name_standards_path(self):
        """The 'always ask explicitly' carve-out sentence (naming `### models`
        and e2e) must NOT gain standards_path — proving standards_path is a
        silently-defaultable batch entry, not an always-ask exception."""
        carveout = re.search(
            r"(?s)present these as a batch.{0,900}", self.step4, re.IGNORECASE
        )
        self.assertIsNotNone(
            carveout, "Step 4 must retain the 'present these as a batch' framing"
        )
        window = carveout.group(0)
        self.assertNotIn(
            "standards_path", window,
            msg="standards_path must NOT appear in the always-ask carve-out "
                "window — it is defaulted like principles_path/quality_path/"
                "operations_path, not an always-ask exception (AC-7)",
        )


class Mar118StandardsRegistryCase(unittest.TestCase):
    """AC-8: create-standards is registered in PRODUCT_SKILLS and
    PRODUCT_TICKET_TITLES, and consequently joins the derived HOOKED_SKILLS."""

    def test_create_standards_in_product_skills(self):
        self.assertIn(
            "create-standards", acs_lib.PRODUCT_SKILLS,
            msg="'create-standards' must be registered in PRODUCT_SKILLS (AC-8)",
        )

    def test_create_standards_in_product_ticket_titles(self):
        self.assertEqual(
            acs_lib.PRODUCT_TICKET_TITLES.get("create-standards"),
            "Product standards doc set",
            msg="PRODUCT_TICKET_TITLES['create-standards'] must equal "
                "'Product standards doc set' (AC-8)",
        )

    def test_create_standards_in_hooked_skills(self):
        self.assertIn(
            "create-standards", acs_lib.HOOKED_SKILLS,
            msg="'create-standards' must join HOOKED_SKILLS via the derived "
                "PRODUCT_SKILLS + WORKFLOW_SKILLS expression (AC-8)",
        )


if __name__ == "__main__":
    unittest.main()
