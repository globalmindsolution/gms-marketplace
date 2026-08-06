"""Bidirectional drift guard for the skillName enum (MAR-176).

`plugins/acs/schemas/acs-messages.xsd`'s `skillName` enumeration, the identical
copies in `plugins/acs/schemas/skill-state.schema.json` and
`clarifications.schema.json`, and `validate_xml.py`'s hardcoded `SKILLS` mirror
must each equal the live set of directories under `plugins/acs/skills/` plus
the single documented backward-compat exemption, `create-spec` (retired in
v0.4.6 / MAR-156 / ADR 0066, retained deliberately per MAR-164). Every
"expected" value here is recomputed from disk or from the source files at run
time — never a frozen baseline constant — so the guard cannot itself re-drift
from either side.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
SCHEMAS_DIR = os.path.join(PLUGIN, "schemas")
HOOKS_SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

XSD = os.path.join(SCHEMAS_DIR, "acs-messages.xsd")
SKILL_STATE_SCHEMA = os.path.join(SCHEMAS_DIR, "skill-state.schema.json")
CLARIFICATIONS_SCHEMA = os.path.join(SCHEMAS_DIR, "clarifications.schema.json")

sys.path.insert(0, HOOKS_SCRIPTS)
import validate_xml  # noqa: E402

XS_NS = "{http://www.w3.org/2001/XMLSchema}"

# The single documented backward-compat exemption (AC-1/AC-4 of MAR-176):
# retired from plugins/acs/skills/ in MAR-156, retained in every skill-name
# enum deliberately per MAR-164.
BACKWARD_COMPAT_EXEMPTION = "create-spec"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def shipped_skill_dirs():
    """Every directory directly under plugins/acs/skills/ -- the live skill set."""
    return {
        name for name in os.listdir(SKILLS_DIR)
        if os.path.isdir(os.path.join(SKILLS_DIR, name))
    }


def xsd_skill_enum_list():
    """The skillName simpleType's <xs:enumeration> values, parsed live from the XSD."""
    root = ET.parse(XSD).getroot()
    simple_type = root.find("%ssimpleType[@name='skillName']" % XS_NS)
    return [e.get("value") for e in simple_type.iter("%senumeration" % XS_NS)]


def json_schema_skill_enum_list(path, pointer):
    """Walk *pointer* (a list of keys) into the JSON document at *path* to its enum list."""
    doc = json.loads(read(path))
    node = doc
    for key in pointer:
        node = node[key]
    return node


SKILL_STATE_POINTER = ["properties", "skill", "enum"]
CLARIFICATIONS_POINTER = [
    "properties", "clarifications", "items", "properties", "skill", "enum",
]


def skill_state_enum_list():
    return json_schema_skill_enum_list(SKILL_STATE_SCHEMA, SKILL_STATE_POINTER)


def clarifications_enum_list():
    return json_schema_skill_enum_list(CLARIFICATIONS_SCHEMA, CLARIFICATIONS_POINTER)


class SkillEnumSourcesTest(unittest.TestCase):
    """The 4 mirrors this ticket reconciles, each checked against live disk state."""

    @classmethod
    def setUpClass(cls):
        cls.shipped = shipped_skill_dirs()
        cls.expected = cls.shipped | {BACKWARD_COMPAT_EXEMPTION}
        cls.sources = {
            "acs-messages.xsd skillName": set(xsd_skill_enum_list()),
            "skill-state.schema.json skill.enum": set(skill_state_enum_list()),
            "clarifications.schema.json skill.enum": set(clarifications_enum_list()),
            "validate_xml.SKILLS": set(validate_xml.SKILLS),
        }

    def test_no_shipped_skill_missing_from_any_source(self):
        # Direction A of the bidirectional guard: every directory on disk must
        # have a matching enum value in every source.
        for label, values in self.sources.items():
            with self.subTest(source=label):
                missing = self.shipped - values
                self.assertEqual(
                    missing, set(),
                    "%s is missing shipped skill(s): %s" % (label, sorted(missing)))

    def test_no_stale_value_without_directory_or_exemption(self):
        # Direction B of the bidirectional guard: every enum value must have a
        # matching directory, except the single documented exemption.
        for label, values in self.sources.items():
            with self.subTest(source=label):
                stale = values - self.shipped - {BACKWARD_COMPAT_EXEMPTION}
                self.assertEqual(
                    stale, set(),
                    "%s has stale value(s) with no matching directory: %s"
                    % (label, sorted(stale)))

    def test_source_equals_shipped_plus_backward_compat_exemption(self):
        # The combined equality that makes the guard bidirectional by
        # construction: this is the single assertion neither of the two above
        # can be satisfied without also satisfying.
        for label, values in self.sources.items():
            with self.subTest(source=label):
                self.assertEqual(
                    values, self.expected,
                    "%s (%s) does not equal shipped dirs + {%r} (%s)"
                    % (label, sorted(values), BACKWARD_COMPAT_EXEMPTION,
                       sorted(self.expected)))

    def test_backward_compat_exemption_retained_everywhere(self):
        for label, values in self.sources.items():
            with self.subTest(source=label):
                self.assertIn(
                    BACKWARD_COMPAT_EXEMPTION, values,
                    "%s must retain %r as a documented backward-compat value"
                    % (label, BACKWARD_COMPAT_EXEMPTION))

    def test_all_sources_agree_with_each_other(self):
        labels = list(self.sources)
        first_label, first_values = labels[0], self.sources[labels[0]]
        for label in labels[1:]:
            with self.subTest(source=label):
                self.assertEqual(
                    self.sources[label], first_values,
                    "%s disagrees with %s" % (label, first_label))


class NoDuplicateEnumValuesTest(unittest.TestCase):
    """A set-only comparison cannot see a duplicated <xs:enumeration>/enum
    entry -- closes that hole for the three list-shaped sources. (validate_xml.SKILLS
    is a Python set literal: duplicates are deduplicated at parse time and
    cannot be observed from the resulting object.)"""

    def test_xsd_enum_has_no_duplicates(self):
        values = xsd_skill_enum_list()
        self.assertEqual(len(values), len(set(values)))

    def test_skill_state_schema_enum_has_no_duplicates(self):
        values = skill_state_enum_list()
        self.assertEqual(len(values), len(set(values)))

    def test_clarifications_schema_enum_has_no_duplicates(self):
        values = clarifications_enum_list()
        self.assertEqual(len(values), len(set(values)))


class EveryShippedSkillValidatesTest(unittest.TestCase):
    """AC-3/AC-5: validate_xml accepts every shipped skill name, plus the
    retained create-spec exemption, and still rejects an unknown one."""

    def test_every_shipped_skill_name_is_accepted(self):
        for name in sorted(shipped_skill_dirs()):
            with self.subTest(skill=name):
                message = (
                    '<task skill="%s" phase="plan" ticket-id="MAR-1" iteration="1">'
                    '<objective>x</objective></task>' % name
                )
                errors = validate_xml.validate_structurally(message)
                self.assertEqual(errors, [])

    def test_docs_sync_task_accepted_verbatim(self):
        # The exact reproduction of the ticket's live symptom.
        message = (
            '<task skill="docs-sync" phase="plan" ticket-id="MAR-1" iteration="1">'
            '<objective>x</objective></task>'
        )
        errors = validate_xml.validate_structurally(message)
        self.assertEqual(errors, [])

    def test_retained_create_spec_still_accepted(self):
        message = (
            '<task skill="create-spec" phase="plan" ticket-id="MAR-1" iteration="1">'
            '<objective>x</objective></task>'
        )
        errors = validate_xml.validate_structurally(message)
        self.assertEqual(errors, [])

    def test_unknown_skill_still_rejected(self):
        message = (
            '<task skill="nope" phase="plan" ticket-id="MAR-1" iteration="1">'
            '<objective>x</objective></task>'
        )
        errors = validate_xml.validate_structurally(message)
        self.assertNotEqual(errors, [])


class XmllintParityTest(unittest.TestCase):
    """Proves the XSD file itself (the ACS_XML_AUTHORITATIVE path), not just
    the Python mirror, accepts the widened set."""

    def _assert_xmllint_accepts(self, skill):
        message = (
            '<task skill="%s" phase="plan" ticket-id="MAR-1" iteration="1">'
            '<objective>x</objective></task>' % skill
        )
        proc = subprocess.run(
            ["xmllint", "--noout", "--schema", XSD, "-"],
            input=message, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    @unittest.skipUnless(shutil.which("xmllint"), "xmllint not on PATH")
    def test_xmllint_accepts_docs_sync_task(self):
        self._assert_xmllint_accepts("docs-sync")

    @unittest.skipUnless(shutil.which("xmllint"), "xmllint not on PATH")
    def test_xmllint_accepts_retained_create_spec_task(self):
        self._assert_xmllint_accepts("create-spec")


class XsdDocumentsBackwardCompatRetentionTest(unittest.TestCase):
    """AC-1: the retained create-spec value carries a comment explaining why
    it is kept -- proven by locating an MAR-164 backward-compat comment near
    the enumeration line itself, not merely present somewhere in the file."""

    def test_create_spec_enumeration_has_adjacent_backward_compat_comment(self):
        text = read(XSD)
        idx = text.index('<xs:enumeration value="create-spec"/>')
        window = text[max(0, idx - 400):idx + 100]
        self.assertIn("MAR-164", window)
        self.assertRegex(window.lower(), r"backward.?compat")


if __name__ == "__main__":
    unittest.main()
