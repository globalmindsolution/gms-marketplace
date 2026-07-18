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
unchanged. `test_design_sections_default_byte_identical_to_skill_literal` proves
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
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")
DESIGN_TEMPLATE_PATH = os.path.join(PLUGIN, "templates", "design-default.md")
SPEC_TEMPLATE_PATH = os.path.join(PLUGIN, "templates", "spec-default.md")
CREATE_DESIGN_SKILL = os.path.join(PLUGIN, "skills", "create-design", "SKILL.md")
CREATE_SPEC_SKILL = os.path.join(PLUGIN, "skills", "create-spec", "SKILL.md")
CHANGELOG_PATH = os.path.join(PLUGIN, "CHANGELOG.md")
C4_CONTAINER_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md")
CONTRACTS_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")
ADR_PATH = os.path.join(
    REPO_ROOT, "docs", "adr",
    "0065-configurable-design-spec-templates-byte-identical-defaults.md",
)

DESIGN_HEADINGS = [
    "Context & constraints",
    "Options considered",
    "Decision & rationale",
    "Architecture",
    "Impact & risks",
    "Rollout/migration",
]
SPEC_HEADINGS = [
    "Scope",
    "Approach",
    "API/data changes",
    "Test plan",
    "Out of scope",
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


class TestFormatsTemplateKeys(unittest.TestCase):
    """AC-1: the two formats.*_template keys are declared with the right defaults."""

    @classmethod
    def setUpClass(cls):
        cls.formats = load_json(SCHEMA_PATH)["properties"]["formats"]

    def test_design_template_declared_default_design_default(self):
        props = self.formats["properties"]
        self.assertIn("design_template", props)
        self.assertEqual(props["design_template"].get("default"), "design-default")

    def test_spec_template_declared_default_spec_default(self):
        props = self.formats["properties"]
        self.assertIn("spec_template", props)
        self.assertEqual(props["spec_template"].get("default"), "spec-default")

    def test_formats_block_stays_closed(self):
        # additionalProperties:false is exactly why the two keys MUST be declared.
        self.assertIs(self.formats.get("additionalProperties"), False)

    def test_formats_description_lists_new_builtin_names(self):
        desc = self.formats.get("description", "")
        self.assertIn("design-default", desc)
        self.assertIn("spec-default", desc)


class TestEnforcementSectionKeys(unittest.TestCase):
    """AC-3/AC-4: the two enforcement.*_sections companions + exact-order defaults."""

    @classmethod
    def setUpClass(cls):
        cls.enforcement = load_json(SCHEMA_PATH)["properties"]["enforcement"]

    def test_design_sections_default_exact_and_ordered(self):
        prop = self.enforcement["properties"]["design_sections"]
        self.assertEqual(prop.get("default"), DESIGN_HEADINGS)

    def test_spec_sections_default_exact_and_ordered(self):
        prop = self.enforcement["properties"]["spec_sections"]
        self.assertEqual(prop.get("default"), SPEC_HEADINGS)

    def test_section_keys_typed_as_string_arrays(self):
        for key in ("design_sections", "spec_sections"):
            prop = self.enforcement["properties"][key]
            self.assertEqual(prop.get("type"), "array")
            self.assertEqual(prop.get("items"), {"type": "string"})

    def test_section_descriptions_mention_defaulted_from(self):
        for key in ("design_sections", "spec_sections"):
            desc = self.enforcement["properties"][key].get("description", "")
            self.assertIn("defaulted from", desc)

    def test_enforcement_block_stays_open(self):
        self.assertIs(self.enforcement.get("additionalProperties"), True)


class TestByteIdenticalDefaults(unittest.TestCase):
    """AC-4: default section lists == today's hardcoded required_sections literal."""

    def test_design_sections_default_byte_identical_to_skill_literal(self):
        default = load_json(SCHEMA_PATH)["properties"]["enforcement"]["properties"][
            "design_sections"
        ]["default"]
        skill = read_text(CREATE_DESIGN_SKILL)
        m = re.search(
            r'<constraint name="required_sections">(.*?)</constraint>',
            skill,
            re.DOTALL,
        )
        self.assertIsNotNone(m, "create-design SKILL must keep the required_sections literal")
        # The literal is HTML-encoded (&amp;) and may wrap across lines inside the
        # XML example — unescape and collapse whitespace before comparing.
        literal = html.unescape(m.group(1))
        literal = re.sub(r"\s+", " ", literal).strip()
        self.assertEqual(literal, "; ".join(default))

    def test_spec_sections_default_matches_create_spec_headings(self):
        default = load_json(SCHEMA_PATH)["properties"]["enforcement"]["properties"][
            "spec_sections"
        ]["default"]
        self.assertEqual(default, SPEC_HEADINGS)
        skill = read_text(CREATE_SPEC_SKILL)
        for heading in SPEC_HEADINGS:
            self.assertIn("## " + heading, skill)


class TestBuiltinTemplateFiles(unittest.TestCase):
    """AC-2: the two built-in template files encode today's EXACT headings/order."""

    def test_design_default_headings_exact_and_ordered(self):
        self.assertEqual(heading_lines(read_text(DESIGN_TEMPLATE_PATH)), DESIGN_HEADINGS)

    def test_spec_default_headings_exact_and_ordered(self):
        self.assertEqual(heading_lines(read_text(SPEC_TEMPLATE_PATH)), SPEC_HEADINGS)

    def test_template_files_begin_with_html_comment(self):
        for path in (DESIGN_TEMPLATE_PATH, SPEC_TEMPLATE_PATH):
            self.assertTrue(read_text(path).lstrip().startswith("<!--"))


class TestArchitectureDocs(unittest.TestCase):
    """AC-5: c4 template count bump + contracts Settings-enumeration keys."""

    def test_c4_container_template_count_bumped_to_six(self):
        text = read_text(C4_CONTAINER_PATH)
        self.assertIn("6 description templates", text)
        self.assertNotIn("4 description templates", text)

    def test_contracts_lists_all_four_new_keys(self):
        text = read_text(CONTRACTS_PATH)
        for key in (
            "formats.design_template",
            "formats.spec_template",
            "enforcement.design_sections",
            "enforcement.spec_sections",
        ):
            self.assertIn(key, text)


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
