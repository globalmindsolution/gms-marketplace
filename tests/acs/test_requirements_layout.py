"""MAR-145 Spec 01 — the requirements set's functional/non-functional split +
/acs:code's requirements-merge classify-then-route prose contract +
`contracts.md` settings note + ADR 0060 + CHANGELOG entry.

MAR-145 introduced a `requirements_layout` settings key naming the two
subfolders; ADR-0102 ("documents are found, not configured") removed it. The
split itself stands: the requirements set (found in the repo, else
`docs/requirements/`) has a functional and a non-functional subfolder
(`functional/` and `non-functional/` by default, an existing set's own names
followed), and a coordinator hands the resolved locations to its agents as the
`requirements_dir` / `functional_dir` / `non_functional_dir` constraints. The
schema/settings classes below are now guards that the removed key stays gone.

Stdlib-only unittest. Uses `test_docs_reflection_topology.py`'s
`ChangelogMar123EntryTest` shape for the durable CHANGELOG assertion (never
pins a literal `[Unreleased]`/dated heading).

Run: python3 -m unittest tests.acs.test_requirements_layout -v
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


def flat(text):
    return " ".join(text.split())


class RequirementsLayoutSchemaTest(unittest.TestCase):
    """T1.1, inverted by ADR-0102: the schema no longer defines
    `requirements_layout` or `requirements_path` (no setting locates a
    document), stays additive so a consumer's legacy key still validates, and
    the marketplace's own `.acs/settings.json` no longer carries the block."""

    SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")

    @classmethod
    def setUpClass(cls):
        with open(cls.SCHEMA_PATH) as fh:
            cls.schema = json.load(fh)

    def test_requirements_layout_not_in_schema(self):
        self.assertNotIn("requirements_layout", self.schema["properties"])

    def test_requirements_path_not_in_schema(self):
        self.assertNotIn("requirements_path", self.schema["properties"])

    def test_schema_never_names_the_subdir_keys(self):
        body = read(self.SCHEMA_PATH)
        self.assertNotIn("functional_subdir", body)
        self.assertNotIn("non_functional_subdir", body)

    def test_top_level_schema_stays_additive(self):
        self.assertTrue(self.schema.get("additionalProperties"))

    def test_marketplace_settings_has_no_requirements_layout(self):
        settings_path = os.path.join(REPO_ROOT, ".acs", "settings.json")
        with open(settings_path) as fh:
            settings = json.load(fh)
        self.assertNotIn("requirements_layout", settings)
        self.assertNotIn("requirements_path", settings)


class RequirementsLayoutDefaultResolutionTest(unittest.TestCase):
    """T1.1, inverted by ADR-0102: nothing seeds `requirements_layout` any
    more — a zero-config repo resolves no such key, because the subfolders are
    found in the repo (or created at the `functional/` / `non-functional/`
    convention) by the skill, not read from settings."""

    def test_default_settings_does_not_seed_requirements_layout(self):
        self.assertNotIn("requirements_layout", lib.DEFAULT_SETTINGS)
        self.assertNotIn("requirements_path", lib.DEFAULT_SETTINGS)

    def test_load_settings_resolves_no_layout_when_absent(self):
        tmp = tempfile.mkdtemp(prefix="acs-req-layout-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = os.path.join(tmp, "shop")
        os.makedirs(os.path.join(repo, ".acs"))
        with open(os.path.join(repo, ".acs", "settings.json"), "w") as fh:
            json.dump({"ticket_prefix": "SHOP"}, fh)
        merged, _found = lib.load_settings(repo)
        self.assertNotIn("requirements_layout", merged)
        self.assertNotIn("requirements_path", merged)


class MergeRoutingProseContractTest(unittest.TestCase):
    """T1.2 (AC-3), retargeted by MAR-162 (C-1): the classify-then-route
    rubric (functional=behavior, non-functional=quality, default-to-functional
    tie-break), both target subfolders, and the additive/per-area/no-overwrite
    phrasing now live in `docs-sync-executor.md` — MAR-162 re-homed them out
    of `code/SKILL.md`/`code-executor.md`, which no longer author docs.
    the docs-sync VERIFIER still names wrong-subfolder routing as a blocking
    finding condition (unchanged by this spec; spec 02's territory)."""

    DOCS_SYNC_EXECUTOR_MD = os.path.join(PLUGIN, "agents", "docs-sync-executor.md")
    # The check moved with its producer: MAR-162 re-homed the requirements
    # merge onto /acs:docs-sync, and v0.5.0 retired code-verifier.md with the
    # in-skill review, so the verifier that guards the routing is the one
    # paired with the executor that does it.
    VERIFIER_MD = os.path.join(PLUGIN, "agents", "docs-sync-verifier.md")

    def test_skill_md_names_functional_behavior_definition(self):
        body = read(self.DOCS_SYNC_EXECUTOR_MD)
        self.assertRegex(body, re.compile(r"FUNCTIONAL\*\*.*BEHAVIOR", re.DOTALL))

    def test_skill_md_names_non_functional_quality_definition(self):
        body = read(self.DOCS_SYNC_EXECUTOR_MD)
        self.assertRegex(body, re.compile(r"NON-FUNCTIONAL\*\*.*QUALITY", re.DOTALL))

    def test_skill_md_names_tie_break_default_to_functional(self):
        body = read(self.DOCS_SYNC_EXECUTOR_MD)
        self.assertRegex(
            body,
            re.compile(r"[Tt]ie-break.*defaults\s*to\s*\*\*functional\*\*", re.DOTALL),
        )

    def test_skill_md_names_both_target_subfolders(self):
        """The two targets are the resolved `functional_dir` /
        `non_functional_dir` constraints, with the `functional/` /
        `non-functional/` convention for a new set — never the removed
        `requirements_layout` subdir keys."""
        body = flat(read(self.DOCS_SYNC_EXECUTOR_MD))
        self.assertIn("`<functional_dir>/<feature>.md`", body)
        self.assertIn("`<non_functional_dir>/<item>.md`", body)
        self.assertIn("(`functional/` in a new set;", body)
        self.assertIn("(`non-functional/` in a new set;", body)
        self.assertNotIn("functional_subdir", body)
        self.assertNotIn("requirements_layout", body)

    def test_skill_md_preserves_no_overwrite_phrasing(self):
        body = read(self.DOCS_SYNC_EXECUTOR_MD)
        self.assertRegex(body, r"no-overwrite|never overwrit|never replace")
        self.assertRegex(body, r"additive")
        self.assertRegex(body, r"per-(feature-)?area")

    def test_code_executor_md_names_classify_then_route_rubric(self):
        body = read(self.DOCS_SYNC_EXECUTOR_MD)
        self.assertRegex(body, re.compile(r"FUNCTIONAL\*\*.*BEHAVIOR", re.DOTALL))
        self.assertRegex(body, re.compile(r"NON-FUNCTIONAL\*\*.*QUALITY", re.DOTALL))

    def test_code_executor_md_names_both_target_subfolders(self):
        """The executor receives both subfolders as task constraints."""
        body = flat(read(self.DOCS_SYNC_EXECUTOR_MD))
        self.assertRegex(
            body,
            r"`requirements_dir`, `functional_dir`, `non_functional_dir`",
        )

    def test_code_executor_md_preserves_no_overwrite_phrasing(self):
        body = read(self.DOCS_SYNC_EXECUTOR_MD)
        self.assertRegex(body, r"never overwrit|no-overwrite|never replac")
        self.assertRegex(body, r"additive")

    def test_the_verifier_names_wrong_subfolder_routing_as_a_finding(self):
        body = read(self.VERIFIER_MD)
        self.assertRegex(body, r"wrong subfolder|wrong-subfolder")
        self.assertRegex(
            body,
            re.compile(r"outside.*`functional_dir`/`non_functional_dir`", re.DOTALL),
        )
        self.assertNotIn("requirements_layout", body)


def _dimension_block(body, label):
    """Extract a numbered check-dimension list item (backtick-labelled, as
    docs-sync-verifier.md writes them): from '^N. `label`' up to the next
    numbered item or the next heading."""
    start_m = re.search(r"(?m)^\d+\.\s+`%s`" % re.escape(label), body)
    assert start_m is not None, "dimension %r not found" % label
    rest = body[start_m.end():]
    end_m = re.search(r"(?m)^(?:\d+\.\s+`|#{1,3} )", rest)
    end = start_m.end() + end_m.start() if end_m else len(body)
    return body[start_m.start():end]


class DocsSyncVerifierRequirementsRoutingTest(unittest.TestCase):
    """MAR-162 (C-1, C5): docs-sync-verifier.md gains a 5th check dimension,
    `requirements-routing`, the docs-sync-side producer/verifier pair the
    requirements-merge re-home requires — wrong-subfolder routing and an
    unrouted inline citation are both findings, mirroring
    `code-verifier.md`'s dimension 11 guards this spec re-homes."""

    DOCS_SYNC_VERIFIER_MD = os.path.join(PLUGIN, "agents", "docs-sync-verifier.md")

    @classmethod
    def setUpClass(cls):
        cls.body = read(cls.DOCS_SYNC_VERIFIER_MD)
        cls.block = _dimension_block(cls.body, "requirements-routing")

    def test_dimension_present(self):
        self.assertIn("requirements-routing", self.body)

    def test_dimension_names_wrong_subfolder_routing(self):
        self.assertRegex(self.block, r"wrong subfolder|wrong-subfolder")
        self.assertRegex(
            self.block,
            re.compile(r"outside.*`functional_dir`/`non_functional_dir`", re.DOTALL),
        )

    def test_dimension_mentions_evidence_sidecar(self):
        self.assertRegex(self.block, re.compile(r"(?i)\.evidence\.md"))

    def test_dimension_blocks_inline_citation_in_merge(self):
        self.assertRegex(
            self.block,
            re.compile(r"(?i)citation[\s\S]{0,80}inline[\s\S]{0,250}is a finding"),
        )


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
    """T1.5 (AC-2, contracts half), re-expressed by ADR-0102: `contracts.md`'s
    Settings-keys list no longer carries `requirements_layout?` (no key locates
    a document), and the functional/non-functional resolution note now says
    the set is found in the repo, else created at the `docs/requirements/`
    convention with `functional/` + `non-functional/` subfolders; the
    conformance-chain line is UNCHANGED (D1 — no chain rewrite in this spec;
    that clarifying note is MAR-144's)."""

    CONTRACTS_MD = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")

    def test_settings_keys_list_drops_requirements_layout(self):
        body = read(self.CONTRACTS_MD)
        self.assertNotIn("requirements_layout", body)
        self.assertIn("No key locates the workspace or a document", flat(body))

    def test_functional_non_functional_resolution_documented(self):
        body = flat(read(self.CONTRACTS_MD))
        self.assertIn(
            "The requirements set (found in the repo, else `docs/requirements/`) has a "
            "**functional** and a **non-functional** subfolder (`functional/` and "
            "`non-functional/` by default; an existing set's own names are followed).",
            body,
        )

    def test_conformance_chain_line_unchanged(self):
        body = read(self.CONTRACTS_MD)
        self.assertIn(
            "Conformance chain: `PRD → architecture → principles → standards → design → code`, "
            "each level verified against the one above it.",
            body,
        )


if __name__ == "__main__":
    unittest.main()
