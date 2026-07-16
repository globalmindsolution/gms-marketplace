"""Guard the test-file-naming convention: name test modules by behavior, not ticket id.

Two assertion sets pin the convention codified for MAR-147:
  (A) the naming rule is present in every pipeline guidance surface and in the
      first-class standard doc, so the pipeline keeps emitting behavior-named
      test files;
  (B) no file under tests/acs/ carries a ticket id in its FILENAME (contents are
      never scanned — module docstrings legitimately keep their MAR-<NNN> ref).
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
TESTS_ACS = os.path.dirname(os.path.abspath(__file__))

# The canonical distinctive phrase inserted verbatim at every guidance surface
# and in the standard doc; assertion set (A) pins it so wording cannot silently
# drift away from the codified rule.
CANONICAL = "named by the component/behavior under test, never by a ticket id"

# The five pipeline guidance surfaces (skills + agents) plus the first-class
# standard doc that must all carry the rule.
GUIDANCE_SURFACES = [
    os.path.join(PLUGIN, "skills", "code", "SKILL.md"),
    os.path.join(PLUGIN, "skills", "create-spec", "SKILL.md"),
    os.path.join(PLUGIN, "agents", "code-executor.md"),
    os.path.join(PLUGIN, "agents", "code-planner.md"),
    os.path.join(PLUGIN, "agents", "create-spec-planner.md"),
]
STANDARD_DOC = os.path.join(REPO_ROOT, "docs", "standards", "standards.md")

# Filename patterns that flag a ticket id: the anchored test_mar<digit> form and
# the embedded mar[-_]?<digit> token anywhere in the name.
_ANCHORED = re.compile(r"test_mar[0-9]", re.IGNORECASE)
_EMBEDDED = re.compile(r"mar[-_]?[0-9]", re.IGNORECASE)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def normalized(path):
    """Collapse whitespace so a phrase matches regardless of prose line wrapping."""
    return re.sub(r"\s+", " ", read(path))


def flags_ticket_id(filename):
    """A test filename carries a ticket id when either pattern matches."""
    return bool(_ANCHORED.search(filename) or _EMBEDDED.search(filename))


class TestNamingRuleGuidancePresent(unittest.TestCase):
    """Assertion set (A): the codified rule text is present everywhere it must be."""

    def test_rule_present_in_five_guidance_surfaces(self):
        for path in GUIDANCE_SURFACES:
            self.assertIn(CANONICAL, normalized(path),
                          "%s must carry the test-file-naming rule" % path)

    def test_rule_present_in_standard_doc(self):
        self.assertTrue(os.path.isfile(STANDARD_DOC),
                        "docs/standards/standards.md must exist")
        self.assertIn(CANONICAL, normalized(STANDARD_DOC),
                      "the standard doc must state the test-file-naming rule")


class TestNoTicketIdTestFilenames(unittest.TestCase):
    """Assertion set (B): no tests/acs/ filename carries a ticket id."""

    def filenames(self):
        return sorted(os.path.basename(p)
                      for p in glob.glob(os.path.join(TESTS_ACS, "*.py")))

    def test_no_test_filename_carries_a_ticket_id(self):
        offenders = [name for name in self.filenames() if flags_ticket_id(name)]
        self.assertEqual(offenders, [],
                         "test filenames must not carry a ticket id: %s" % offenders)

    def test_marketplace_consistency_is_not_flagged(self):
        # Negative case: 'marketplace' is mar+k with no digit — must not flag.
        self.assertFalse(flags_ticket_id("test_marketplace_consistency.py"))

    def test_guard_matcher_flags_a_ticket_id_name(self):
        # Positive control: the matcher actually fires on a ticket-id name.
        self.assertTrue(flags_ticket_id("test_mar147_rename.py"))


if __name__ == "__main__":
    unittest.main()
