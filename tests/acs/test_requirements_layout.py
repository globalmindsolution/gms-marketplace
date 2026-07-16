"""MAR-145 Spec 01 — `requirements_layout` settings key + /acs:code's
requirements-merge classify-then-route prose contract + `contracts.md`
settings note + ADR 0060 + CHANGELOG entry.

Stdlib-only unittest. Mirrors `TestQualityPathSettings`
(tests/acs/test_acs_plugin.py) for the schema/settings-default assertions and
`test_docs_reflection_topology.py`'s `ChangelogMar123EntryTest` for the durable
CHANGELOG assertion (never pins a literal `[Unreleased]`/dated heading).

Run: python3 -m unittest tests.acs.test_mar145_requirements_layout -v
"""

import glob
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
import acs_lib as lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class RequirementsLayoutSchemaTest(unittest.TestCase):
    """T1.1 (AC-1, AC-6): schema defines `requirements_layout` (additive,
    functional/non-functional shape, defaults); `requirements_path` stays a
    plain string (no `oneOf` promotion); the marketplace's own
    `.acs/settings.json` carries the block."""

    SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")

    @classmethod
    def setUpClass(cls):
        with open(cls.SCHEMA_PATH) as fh:
            cls.schema = json.load(fh)

    def test_requirements_layout_in_schema(self):
        self.assertIn("requirements_layout", self.schema["properties"])

    def test_requirements_layout_is_object_with_subdir_keys(self):
        prop = self.schema["properties"]["requirements_layout"]
        self.assertEqual(prop.get("type"), "object")
        props = prop.get("properties", {})
        self.assertEqual(props.get("functional_subdir", {}).get("type"), "string")
        self.assertEqual(props.get("functional_subdir", {}).get("default"), "functional")
        self.assertEqual(props.get("non_functional_subdir", {}).get("type"), "string")
        self.assertEqual(props.get("non_functional_subdir", {}).get("default"), "non-functional")

    def test_requirements_layout_additional_properties_true(self):
        prop = self.schema["properties"]["requirements_layout"]
        self.assertTrue(prop.get("additionalProperties"))

    def test_requirements_path_still_a_plain_string(self):
        """No `oneOf` promotion — every existing string reader stays
        unaffected (design 'Settings-key shape', rejected alternative)."""
        prop = self.schema["properties"]["requirements_path"]
        self.assertEqual(prop.get("type"), "string")
        self.assertNotIn("oneOf", prop)

    def test_top_level_schema_stays_additive(self):
        self.assertTrue(self.schema.get("additionalProperties"))

    def test_marketplace_settings_carries_requirements_layout(self):
        settings_path = os.path.join(REPO_ROOT, ".acs", "settings.json")
        with open(settings_path) as fh:
            settings = json.load(fh)
        layout = settings.get("requirements_layout")
        self.assertIsInstance(layout, dict)
        self.assertEqual(layout.get("functional_subdir"), "functional")
        self.assertEqual(layout.get("non_functional_subdir"), "non-functional")


class RequirementsLayoutDefaultResolutionTest(unittest.TestCase):
    """T1.1: an absent `requirements_layout` key resolves to the
    functional/non-functional defaults — zero-config repos keep working with
    no settings edit."""

    def test_default_settings_seeds_requirements_layout(self):
        self.assertEqual(
            lib.DEFAULT_SETTINGS.get("requirements_layout"),
            {"functional_subdir": "functional", "non_functional_subdir": "non-functional"},
        )

    def test_load_settings_resolves_default_when_absent(self):
        tmp = tempfile.mkdtemp(prefix="acs-req-layout-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = os.path.join(tmp, "shop")
        os.makedirs(os.path.join(repo, ".acs"))
        with open(os.path.join(repo, ".acs", "settings.json"), "w") as fh:
            json.dump({"ticket_prefix": "SHOP"}, fh)
        merged, _found = lib.load_settings(repo)
        self.assertEqual(merged["requirements_layout"]["functional_subdir"], "functional")
        self.assertEqual(merged["requirements_layout"]["non_functional_subdir"], "non-functional")


class MergeRoutingProseContractTest(unittest.TestCase):
    """T1.2 (AC-3): `code/SKILL.md` and `code-executor.md` carry the
    classify-then-route rubric (functional=behavior, non-functional=quality,
    default-to-functional tie-break) and name both target subfolders; the
    additive, per-area, no-overwrite phrasing is present; `code-verifier.md`
    names wrong-subfolder routing as a blocking finding condition."""

    SKILL_MD = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
    EXECUTOR_MD = os.path.join(PLUGIN, "agents", "code-executor.md")
    VERIFIER_MD = os.path.join(PLUGIN, "agents", "code-verifier.md")

    def test_skill_md_names_functional_behavior_definition(self):
        body = read(self.SKILL_MD)
        self.assertRegex(body, re.compile(r"FUNCTIONAL\*\*.*BEHAVIOR", re.DOTALL))

    def test_skill_md_names_non_functional_quality_definition(self):
        body = read(self.SKILL_MD)
        self.assertRegex(body, re.compile(r"NON-FUNCTIONAL\*\*.*QUALITY", re.DOTALL))

    def test_skill_md_names_tie_break_default_to_functional(self):
        body = read(self.SKILL_MD)
        self.assertRegex(
            body,
            re.compile(r"[Tt]ie-break.*defaults\s*to\s*\*\*functional\*\*", re.DOTALL),
        )

    def test_skill_md_names_both_target_subfolders(self):
        body = read(self.SKILL_MD)
        self.assertIn("functional_subdir", body)
        self.assertIn("non_functional_subdir", body)

    def test_skill_md_preserves_no_overwrite_phrasing(self):
        body = read(self.SKILL_MD)
        self.assertRegex(body, r"no-overwrite|never overwrit|never replace")
        self.assertRegex(body, r"additive")
        self.assertRegex(body, r"per-(feature-)?area")

    def test_code_executor_md_names_classify_then_route_rubric(self):
        body = read(self.EXECUTOR_MD)
        self.assertRegex(body, re.compile(r"FUNCTIONAL\*\*.*BEHAVIOR", re.DOTALL))
        self.assertRegex(body, re.compile(r"NON-FUNCTIONAL\*\*.*QUALITY", re.DOTALL))

    def test_code_executor_md_names_both_target_subfolders(self):
        body = read(self.EXECUTOR_MD)
        self.assertIn("functional_subdir", body)
        self.assertIn("non_functional_subdir", body)

    def test_code_executor_md_preserves_no_overwrite_phrasing(self):
        body = read(self.EXECUTOR_MD)
        self.assertRegex(body, r"never overwrit|no-overwrite|never replac")
        self.assertRegex(body, r"additive")

    def test_code_verifier_md_names_wrong_subfolder_routing_as_blocking(self):
        body = read(self.VERIFIER_MD)
        self.assertRegex(body, r"wrong subfolder|wrong-subfolder")
        self.assertRegex(body, re.compile(r"outside.*requirements_layout", re.DOTALL))


class Adr0060ExistsAndOnTopicTest(unittest.TestCase):
    """T1.3 (AC-7): `docs/adr/0060-*.md` exists (glob, not a hardcoded slug)
    and its body mentions `requirements_layout`, the functional/
    non-functional split, and Decision E-i's rubric."""

    def test_adr_0060_file_exists(self):
        matches = glob.glob(os.path.join(REPO_ROOT, "docs", "adr", "0060-*.md"))
        self.assertEqual(len(matches), 1, "expected exactly one docs/adr/0060-*.md file")
        self._path = matches[0]

    def test_adr_0060_is_on_topic(self):
        matches = glob.glob(os.path.join(REPO_ROOT, "docs", "adr", "0060-*.md"))
        self.assertTrue(matches, "docs/adr/0060-*.md must exist")
        body = read(matches[0])
        self.assertIn("requirements_layout", body)
        self.assertRegex(body, r"functional.*non-functional|non-functional.*functional", )
        self.assertRegex(body, r"[Dd]ecision E-i|producing-skill")


class ChangelogMar145EntryTest(unittest.TestCase):
    """T1.4 (AC-7): durable-invariant CHANGELOG entry — lives under
    `[Unreleased]` OR the current dated-semver heading (never a literal pin),
    and names the requirements-MODEL foundation."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def test_changelog_mar145_entry_in_topmost_section(self):
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if re.search(r"\(MAR-145\b", candidate):
                section_text = candidate
                break
        self.assertIsNotNone(
            section_text,
            "CHANGELOG.md must contain '(MAR-145)' inside a section span")
        heading = section_text[:section_text.index("\n")] if "\n" in section_text else section_text
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-145)' entry must live under [Unreleased] or a dated "
            "semver release heading (release cuts legitimately graduate it)")
        self.assertTrue(
            re.search(r"requirements_layout|functional.*non-functional", section_text, re.DOTALL),
            "the MAR-145 CHANGELOG entry must name the requirements-MODEL foundation")


class ContractsMdSettingsNoteTest(unittest.TestCase):
    """T1.5 (AC-2, contracts half): `contracts.md`'s Settings-keys list gains
    `requirements_layout?` + a nearby functional/non-functional resolution
    note; the conformance-chain line is UNCHANGED (D1 — no chain rewrite in
    this spec; that clarifying note is MAR-144's)."""

    CONTRACTS_MD = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")

    def test_settings_keys_list_gains_requirements_layout(self):
        body = read(self.CONTRACTS_MD)
        self.assertIn("requirements_layout?", body)

    def test_functional_non_functional_resolution_documented(self):
        body = read(self.CONTRACTS_MD)
        self.assertRegex(
            body,
            re.compile(
                r"resolves a.{0,40}functional.{0,40}non-functional.{0,80}requirements_layout",
                re.DOTALL,
            ),
        )

    def test_conformance_chain_line_unchanged(self):
        body = read(self.CONTRACTS_MD)
        self.assertIn(
            "Conformance chain: `PRD → architecture → principles → standards → design → specs → code`, "
            "each level verified against the one above it.",
            body,
        )


if __name__ == "__main__":
    unittest.main()
