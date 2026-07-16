"""MAR-143 spec 02 — /acs:create-requirements brownfield extraction,
classification, interactive-confirm, docs (AC-2/3/4/5/6-settings-half/
7-remainder).

Deepens the four prose files Spec 01 scaffolded (SKILL.md +
create-requirements-{planner,executor,verifier}.md): architecture-aware
feature-area enumeration + codebase-inventory fallback, code-cited DRAFT
extraction, functional/non-functional classification-and-write
(rubric quoted verbatim from `plugins/acs/skills/code/SKILL.md`, never
paraphrased — the classification-drift regression), augment-only-absent
no-overwrite, interactive-confirm; plus ADR 0061, the CHANGELOG
`[Unreleased]` entry, and the `contracts.md` producer-registration line.

Behavioral/prose-contract testing (no new stdlib helper ships in this spec —
design.md 511-514): these tests pin the CONTRACT text and deterministic
invariants; they do not simulate an LLM run.

Stdlib-only (os, re, glob, unittest). Run:
  python3 -m unittest tests.acs.test_mar143_brownfield_extraction -v
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "create-requirements", "SKILL.md")
PLANNER_PATH = os.path.join(PLUGIN, "agents", "create-requirements-planner.md")
EXECUTOR_PATH = os.path.join(PLUGIN, "agents", "create-requirements-executor.md")
VERIFIER_PATH = os.path.join(PLUGIN, "agents", "create-requirements-verifier.md")
CODE_SKILL_PATH = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CHANGELOG_PATH = os.path.join(PLUGIN, "CHANGELOG.md")
CONTRACTS_MD = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def normalize(text):
    """Collapse whitespace so prose wrapped at different column widths can
    still be compared for exact wording (used by the rubric drift guard)."""
    return re.sub(r"\s+", " ", text).strip()


class PlannerEnumerationContractTest(unittest.TestCase):
    """AC-2: the planner charter states architecture-first enumeration +
    the codebase-inventory fallback + the verbatim checkable "feature area"
    definition (design.md "Checkable definition of 'feature area'", 465-473)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PLANNER_PATH)

    def test_architecture_aware_enumeration_sources_named(self):
        for token in ("c4-container", "c4-component", "project-structure"):
            self.assertIn(
                token, self.body,
                "planner charter must name %r as an architecture-aware "
                "enumeration source" % token)

    def test_codebase_inventory_fallback_named(self):
        for token in ("top-level modules", "route-group", "CLI surface", "package"):
            self.assertIn(
                token, self.body,
                "planner charter must name %r in the codebase-inventory "
                "fallback" % token)

    def test_checkable_feature_area_definition_present(self):
        self.assertRegex(
            self.body,
            re.compile(
                r"feature area is a top-level module\s*/\s*route-group\s*/\s*"
                r"CLI surface\s*/\s*package that the architecture "
                r"container-component view names",
            ),
            "planner charter must carry the checkable 'feature area' "
            "definition near-verbatim so the verifier can independently "
            "re-derive the same set",
        )

    def test_open_point_marker_for_ungroundable_areas(self):
        self.assertIn("[OPEN]", self.body)
        self.assertRegex(self.body, r"(?i)never\s+(silently\s+)?(dropped|invented)")

    def test_amend_boundary_definition_present(self):
        body_no_ws = normalize(self.body)
        self.assertIn(
            "at least one file exists in both", body_no_ws,
            "planner charter must state the checkable substantially-"
            "populated -> amend boundary rule",
        )
        self.assertIn("majority", body_no_ws)


class ExecutorDraftCitationContractTest(unittest.TestCase):
    """AC-3: the executor charter mandates a DRAFT/human-confirm-required
    marker + a per-requirement code-citation; an ungroundable area is an
    `[OPEN]` clause carrying no fabricated citation."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(EXECUTOR_PATH)

    def test_draft_marker_mandated(self):
        self.assertRegex(self.body, r"(?i)DRAFT\s*(—|-)\s*human-confirm-required")

    def test_per_requirement_citation_mandated(self):
        self.assertRegex(self.body, r"(?i)code-evidence citation")

    def test_open_clause_no_fabricated_citation(self):
        self.assertRegex(
            self.body,
            r"(?i)\[OPEN\][\s\S]{0,200}no\s+fabricated\s+citation",
        )


class VerifierCoverageCitationContractTest(unittest.TestCase):
    """AC-2/AC-3 verifier half: independent re-enumeration + coverage/diff
    dimension (>=90%, 0 silent omissions); citation-spot-check +
    no-fabrication dimensions; ungroundable -> [OPEN], never invented."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(VERIFIER_PATH)

    def test_independent_reenumeration_dimension(self):
        self.assertRegex(self.body, r"(?i)independently re-enumerate")

    def test_coverage_threshold_language(self):
        self.assertIn("90%", self.body)

    def test_silent_omission_language(self):
        self.assertRegex(self.body, r"(?i)\b0\b[\s\S]{0,80}silent omission")

    def test_citation_spot_check_dimension(self):
        self.assertRegex(self.body, r"(?i)Grep-spot-check")

    def test_no_fabrication_dimension(self):
        self.assertRegex(self.body, r"(?i)No-fabrication")

    def test_routing_spot_check_dimension(self):
        self.assertRegex(self.body, r"(?i)routing spot-check")

    def test_augment_only_absent_diff_dimension(self):
        self.assertRegex(self.body, r"git diff -- <requirements_path>")

    def test_interactive_confirm_dimension(self):
        self.assertRegex(self.body, r"(?i)Interactive-confirm discipline")

    def test_draft_marker_dimension(self):
        self.assertRegex(self.body, r"(?i)\*\*DRAFT marker\*\*")


class ClassificationRubricRegressionTest(unittest.TestCase):
    """AC-4: the executor's functional/non-functional rubric is quoted
    VERBATIM from `plugins/acs/skills/code/SKILL.md` — a regression test
    that fails if the two diverge (the plan's classification-drift risk)."""

    RUBRIC_RE = re.compile(
        r"\*\*FUNCTIONAL\*\*.*?deterministic at the seam\.", re.DOTALL)

    def _rubric(self, text):
        m = self.RUBRIC_RE.search(text)
        self.assertIsNotNone(m, "could not locate the FUNCTIONAL...seam. rubric block")
        return normalize(m.group(0))

    def test_executor_rubric_matches_code_skill_verbatim(self):
        code_rubric = self._rubric(read(CODE_SKILL_PATH))
        executor_rubric = self._rubric(read(EXECUTOR_PATH))
        self.assertEqual(
            code_rubric, executor_rubric,
            "create-requirements-executor.md's functional/non-functional "
            "rubric must be an exact (whitespace-insensitive) quote of "
            "code/SKILL.md's rubric — paraphrasing risks classification "
            "drift between the two producers",
        )

    def test_executor_names_settings_resolved_subdir_keys(self):
        body = read(EXECUTOR_PATH)
        self.assertIn("requirements_layout.functional_subdir", body)
        self.assertIn("requirements_layout.non_functional_subdir", body)

    def test_executor_no_overwrite_git_diff_self_check(self):
        body = read(EXECUTOR_PATH)
        self.assertRegex(body, r"git diff -- <requirements_path>")
        self.assertRegex(body, r"(?i)byte-for-byte")


class SkillInteractiveConfirmContractTest(unittest.TestCase):
    """AC-5: the coordinator presents the DRAFT baseline + open points via
    the clarify ledger BEFORE spawning the executor; an extracted
    requirement is a DRAFT baseline, never authoritative without
    confirmation."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_present_drafts_and_open_points_before_executor(self):
        self.assertRegex(
            self.body,
            r"(?i)present[\s\S]{0,300}open points[\s\S]{0,200}clarify ledger[\s\S]{0,300}"
            r"before you spawn the executor",
        )

    def test_draft_baseline_never_authoritative_language(self):
        self.assertRegex(
            normalize(self.body),
            r"(?i)DRAFT baseline,?\s*never authoritative without confirmation",
        )


class SettingsDrivenWriteTargetContractTest(unittest.TestCase):
    """AC-6 (settings-driven half): the executor references
    settings.requirements_path / settings.requirements_layout at the
    write-target sites, never a marketplace-specific hardcoded literal."""

    def test_executor_references_requirements_path_setting(self):
        body = read(EXECUTOR_PATH)
        self.assertIn("requirements_path", body)

    def test_executor_references_requirements_layout_setting(self):
        body = read(EXECUTOR_PATH)
        self.assertIn("requirements_layout", body)


class Adr0061ExistsAndOnTopicTest(unittest.TestCase):
    """AC-7: docs/adr/0061-*.md exists (glob, not a hardcoded slug) and
    names Decisions A1 and C1 (design.md 475-491, 802)."""

    def test_adr_0061_file_exists_exactly_once(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0061-*.md"))
        self.assertEqual(len(matches), 1, "expected exactly one docs/adr/0061-*.md file")

    def test_adr_0061_names_decision_a1_and_c1(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0061-*.md"))
        self.assertTrue(matches, "docs/adr/0061-*.md must exist")
        body = read(matches[0])
        self.assertRegex(body, r"\bA1\b")
        self.assertRegex(body, r"\bC1\b")
        self.assertRegex(body, r"(?i)brownfield")
        self.assertRegex(body, r"(?i)architecture-aware")


class AdrDeviationGuardTest(unittest.TestCase):
    """Guards against silently reverting to design.md's original, now-
    superseded ADR numbering (0058 for this ticket) — MAR-145 took 0060
    first, so this spec re-confirms and uses the next-free-above-max id,
    0061, instead."""

    def test_adr_0058_does_not_exist(self):
        self.assertFalse(
            glob.glob(os.path.join(ADR_DIR, "0058-*.md")),
            "docs/adr/0058-*.md must NOT exist — 0058 is a superseded "
            "reservation from design.md, not the id this spec uses",
        )

    def test_adr_0059_does_not_exist(self):
        self.assertFalse(
            glob.glob(os.path.join(ADR_DIR, "0059-*.md")),
            "docs/adr/0059-*.md must NOT exist — reserved for MAR-144, "
            "not authored by this ticket",
        )


class ChangelogMar143EntryTest(unittest.TestCase):
    """AC-7: durable-invariant CHANGELOG entry — lives under [Unreleased]
    OR the current dated-semver heading (never a literal pin), and names
    create-requirements + MAR-143 (mirrors test_mar145's
    ChangelogMar145EntryTest pattern)."""

    def test_changelog_mar143_entry_in_topmost_section(self):
        body = read(CHANGELOG_PATH)
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if re.search(r"\(MAR-143\b", candidate):
                section_text = candidate
                break
        self.assertIsNotNone(
            section_text, "CHANGELOG.md must contain '(MAR-143)' inside a section span")
        heading = section_text[:section_text.index("\n")] if "\n" in section_text else section_text
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-143)' entry must live under [Unreleased] or a dated "
            "semver release heading (release cuts legitimately graduate it)")
        self.assertIn("create-requirements", section_text)
        self.assertRegex(section_text, r"(?i)brownfield")
        self.assertIn("ADR 0061", section_text)


class ContractsMdProducerRowTest(unittest.TestCase):
    """AC-7: contracts.md gains the minimal producer-registration line for
    create-requirements, and the conformance-chain line stays byte-identical.
    (The MAR-143-era negative guard against a premature chain note is retired
    now that MAR-144 has legitimately landed the D1 living-contract note — the
    durable invariant that survives is that requirements is documented
    ALONGSIDE the chain, never inserted as a verified level INTO it. The D1
    note's presence/correctness is owned by test_mar144_docs_and_contracts.)"""

    def test_producer_registration_line_present(self):
        body = read(CONTRACTS_MD)
        self.assertRegex(body, r"(?i)/acs:create-requirements[\s\S]{0,200}producer skill")

    def test_conformance_chain_line_unchanged(self):
        body = read(CONTRACTS_MD)
        self.assertIn(
            "Conformance chain: `PRD → architecture → principles → standards → design → specs → code`, "
            "each level verified against the one above it.",
            body,
        )

    def test_requirements_not_inserted_as_chain_level(self):
        """Decision D1 — the D1 note documents requirements alongside the
        chain; it must NOT add requirements as an arrow-separated level within
        the conformance-chain line itself."""
        body = read(CONTRACTS_MD)
        m = re.search(r"Conformance chain: `([^`]+)`", body)
        self.assertIsNotNone(m, "the conformance-chain line must be present")
        chain = m.group(1)
        self.assertNotIn(
            "requirements", chain.lower(),
            "requirements must not be inserted as a conformance-chain level",
        )


if __name__ == "__main__":
    unittest.main()
