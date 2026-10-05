"""MAR-151 (Decision C of epic MAR-149, ADR 0065) — settings keys + built-in
design/spec templates + doc/ADR foundation.

Structure-contract unit tests over the config/data layer for configurable
design/spec templates: the two new `formats.*_template` keys and two
`enforcement.*_sections` companion keys in `settings.schema.json`, the two
built-in template files, and the architecture-doc / ADR / CHANGELOG foundation.
Mirrors the already-shipped `pr_description_template` /
`enforcement.pr_description_sections` pattern.

The load-bearing invariant (AC-4): with NO `*_template` key set, the default
section lists are byte-identical to today's hardcoded `required_sections`
literal, so create-design/create-spec output and the structure gate are
unchanged. ADR-0135 renamed create-design to create-tech-design and changed
the template's six headings to the hand-off sections; the invariant -- the
skill's literal IS the template's headings -- is unchanged. `test_design_sections_default_byte_identical_to_skill_literal` proves
default == today's literal.

Stdlib-only (json, os, re, html, unittest) — no `jsonschema` import, mirroring
this repo's existing settings-schema tests
(`tests/acs/test_release_settings_schema.py`).

Run:  python3 -m unittest tests.acs.test_configurable_doc_templates_schema -v
"""

import html
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skill_text  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")
DESIGN_TEMPLATE_PATH = os.path.join(PLUGIN, "templates", "design-default.md")
CREATE_DESIGN_SKILL = "create-tech-design"  # read through skill_text: the literal lives in references/
CHANGELOG_PATH = os.path.join(PLUGIN, "CHANGELOG.md")
C4_CONTAINER_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md")
CONTRACTS_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")
ADR_PATH = os.path.join(
    REPO_ROOT, "docs", "architecture", "adr",
    "0065-configurable-design-spec-templates-byte-identical-defaults.md",
)

DESIGN_HEADINGS = [
    "Decision & options",
    "HLD views affected",
    "LLD",
    "NFRs",
    "Risks",
    "Open questions",
]


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def heading_lines(text):
    """The `## <heading>` headings (level-2 only), in document order."""
    out = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            out.append(m.group(1))
    return out


class TestDesignSectionsAreDerivedFromTheTemplate(unittest.TestCase):
    """The design structure gate's required sections are the built-in template's
    own headings (there is no section-list setting any more), so the skill's
    required_sections literal must equal them."""

    def test_the_skill_literal_equals_the_template_headings(self):
        skill = skill_text.skill_contract(CREATE_DESIGN_SKILL)
        m = re.search(
            r'<constraint name="required_sections">(.*?)</constraint>',
            skill,
            re.DOTALL,
        )
        self.assertIsNotNone(m, "create-tech-design SKILL must keep the required_sections literal")
        # The literal is HTML-encoded (&amp;) and may wrap across lines inside the
        # XML example — unescape and collapse whitespace before comparing.
        literal = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
        self.assertEqual(literal, "; ".join(DESIGN_HEADINGS))

    def test_the_schema_declares_no_template_or_section_settings(self):
        schema = load_json(SCHEMA_PATH)
        self.assertNotIn("formats", schema["properties"])
        self.assertNotIn("enforcement", schema["properties"])


class TestBuiltinTemplateFiles(unittest.TestCase):
    """AC-2: the two built-in template files encode today's EXACT headings/order."""

    def test_design_default_headings_exact_and_ordered(self):
        self.assertEqual(heading_lines(read_text(DESIGN_TEMPLATE_PATH)), DESIGN_HEADINGS)

    def test_template_files_begin_with_html_comment(self):
        for path in (DESIGN_TEMPLATE_PATH,):
            self.assertTrue(read_text(path).lstrip().startswith("<!--"))


class TestArchitectureDocs(unittest.TestCase):
    """AC-5: c4 template count bump + contracts Settings-enumeration keys."""

    def test_c4_container_template_count_matches_disk(self):
        """Derived, not pinned: the count was 6 until the CLAUDE.acs.md
        managed-block template went away with setup's CLAUDE.md block."""
        text = read_text(C4_CONTAINER_PATH)
        templates = os.path.join(REPO_ROOT, "plugins", "acs", "templates")
        count = len([n for n in os.listdir(templates) if n.endswith(".md")])
        self.assertIn("%d description templates" % count, text)

    def test_contracts_documents_no_removed_keys_as_live(self):
        """contracts.md's Settings paragraph says there is no formats or
        enforcement block, and names the template-by-name convention."""
        text = read_text(CONTRACTS_PATH)
        self.assertIn("There is no `formats` or `enforcement` block", text)
        self.assertIn(".acs/templates/design-default.md", text)


class TestAdrAndChangelog(unittest.TestCase):
    """AC-5: ADR 0065 authored + a durable CHANGELOG bullet."""

    def test_adr_0065_exists_and_references_prior_art(self):
        self.assertTrue(os.path.isfile(ADR_PATH))
        text = read_text(ADR_PATH)
        self.assertIn("pr_description_template", text)
        self.assertIn("byte-identical", text)

    def test_changelog_mentions_mar151_and_adr0065(self):
        # Durable invariant: the bullet exists ANYWHERE in the changelog, not
        # pinned to the [Unreleased] heading (survives a later release cut).
        text = read_text(CHANGELOG_PATH)
        self.assertIn("MAR-151", text)
        self.assertIn("0065", text)


if __name__ == "__main__":
    unittest.main()
