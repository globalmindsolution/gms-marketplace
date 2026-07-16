"""MAR-114 — /acs:init Step 4 documents `suites` + the e2e->suites.e2e re-run
migration offer (AC-5).

Prose-contract unit test for `plugins/acs/skills/init/SKILL.md`, mirroring
tests/acs/test_init_quality_path.py's bounded-window `section()`
technique so a stray mention elsewhere in the file cannot satisfy an
assertion. `suites` must be defaulted like `quality_path`/`operations_path`
in the Step 4 optional-settings batch, and must NOT be added to the "always
ask explicitly" carve-out (which names only `### models` and `e2e`). A
separate migration-offer assertion covers the re-run behavior.

Stdlib-only (os, re, unittest).

Run:  python3 -m unittest tests.acs.test_mar114_suites_init -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "init", "SKILL.md")


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


class Mar114SuitesInitCase(unittest.TestCase):
    """Fixture: read the init SKILL.md once and isolate its Step 4 section."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.step4 = section(cls.body, "## Step 4")

    def test_step4_batch_documents_suites_default(self):
        """The Step 4 batch-default bullet list names suites with its
        default {} in a bounded window after the marker."""
        m = re.search(r"`suites`", self.step4)
        self.assertIsNotNone(m, "Step 4 must document a `suites` bullet (AC-5)")
        window = self.step4[m.start():m.start() + 300]
        self.assertIn(
            "{}", window,
            msg="the `suites` bullet must state its default {} within a bounded window of the marker (AC-5)",
        )

    def test_step4_names_test_skill_as_consumer(self):
        """The suites bullet names /acs:test as the consuming skill."""
        m = re.search(r"`suites`", self.step4)
        self.assertIsNotNone(m)
        window = self.step4[m.start():m.start() + 300]
        self.assertIn(
            "test", window.lower(),
            msg="the `suites` bullet must name /acs:test (or 'test') as the consumer (AC-5)",
        )

    def test_step4_names_reserved_e2e_name(self):
        """The suites bullet states the reserved name e2e is auto-populated
        and should not be hand-duplicated."""
        m = re.search(r"`suites`", self.step4)
        self.assertIsNotNone(m)
        window = self.step4[m.start():m.start() + 400]
        self.assertIn("e2e", window, msg="the `suites` bullet must reference the reserved e2e name (AC-5)")

    def test_carveout_does_not_name_suites(self):
        """The 'always ask explicitly' carve-out sentence (naming ### models
        and e2e) must NOT gain suites — proving suites is silently-
        defaultable, not an always-ask exception."""
        carveout = re.search(
            r"(?s)present these as a batch.{0,900}", self.step4, re.IGNORECASE
        )
        self.assertIsNotNone(
            carveout, "Step 4 must retain the 'present these as a batch' framing"
        )
        window = carveout.group(0)
        self.assertNotIn(
            "suites", window,
            msg="suites must NOT appear in the always-ask carve-out window — "
                "it is defaulted like quality_path/operations_path, not an "
                "always-ask exception (AC-5)",
        )

    def _migration_window(self):
        """Locate the migration-offer prose by anchoring on 'migrat' near
        're-run' first (the marker unique to the offer, not the suites bullet's
        general suites.e2e mention), then return a bounded window around it."""
        for m in re.finditer(r"(?i)migrat", self.body):
            window = self.body[max(0, m.start() - 400):m.start() + 400]
            if re.search(r"(?i)re-run", window):
                return window
        return None

    def test_migration_offer_prose_exists(self):
        """A re-run migration-offer marker phrase referencing both e2e and
        suites.e2e, with retained-e2e-unless-opted-out behavior stated,
        exists somewhere in the SKILL.md body (not necessarily inside
        Step 4's own section, since re-run behavior may be documented near
        the ### models re-run pattern)."""
        window = self._migration_window()
        self.assertIsNotNone(
            window, "SKILL.md must document the e2e -> suites.e2e migration offer, framed as a re-run behavior (AC-5)"
        )
        self.assertIn("e2e", window)
        self.assertIn("suites.e2e", window)

    def test_migration_offer_retains_e2e_unless_opted_out(self):
        """The migration offer must state e2e is retained/left in place
        unless the user opts to remove it — never a forced/silent removal."""
        window = self._migration_window()
        self.assertIsNotNone(window)
        self.assertTrue(
            re.search(r"(?i)(retain|leav|keep|alongside).{0,80}(unless|opt)", window)
            or re.search(r"(?i)(unless|opt).{0,80}(retain|leav|keep|remov)", window),
            "the migration-offer prose must state e2e is retained unless the user opts to remove it (AC-5): %r" % window,
        )


if __name__ == "__main__":
    unittest.main()
