"""MAR-152 spec 01 — `.evidence.md` sidecar convention (contract layer).

Prose-contract tests over the 6 producer/verifier charters +
`docs/architecture/lld/contracts.md` that wire the `.evidence.md` sidecar
convention: create-requirements and create-architecture's executors write
body + companion sidecar (clause anchor -> code-evidence citation list, no
inline `path:line`); their verifiers actively check grounding (body-grep-to-0,
anchor-join, count-not-reduced); `/acs:code`'s requirements-merge write path
and `code-verifier.md`'s Documentation dimension route/guard the same way;
`contracts.md`'s requirements paragraph names the mechanism. This spec is the
contract layer only — no repo doc is migrated (Spec 03) and no topology test
is touched (Spec 02).

Stdlib-only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_evidence_sidecar_contract -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
AGENTS = os.path.join(PLUGIN, "agents")

REQUIREMENTS_EXECUTOR = os.path.join(AGENTS, "create-requirements-executor.md")
REQUIREMENTS_VERIFIER = os.path.join(AGENTS, "create-requirements-verifier.md")
ARCHITECTURE_EXECUTOR = os.path.join(AGENTS, "create-architecture-executor.md")
ARCHITECTURE_VERIFIER = os.path.join(AGENTS, "create-architecture-verifier.md")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_VERIFIER = os.path.join(AGENTS, "code-verifier.md")
CONTRACTS_MD = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")

SIDECAR_TOKEN_RE = re.compile(r"(?i)\.evidence\.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _label_pattern(label):
    esc = re.escape(label)
    return r"(?:\*\*`%s`\*\*|\*\*%s\*\*|`%s`)" % (esc, esc, esc)


def dimension_block(body, label, next_label=None):
    """Extract a numbered check-dimension list item: from the line matching
    `^N. **label**` up to (not including) the next numbered item (or, when
    `next_label` is given, up to that specific item). Mirrors
    test_structure_audience_verifiers.py's helper of the same name."""
    start_m = re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body)
    assert start_m is not None, "dimension %r not found" % label
    rest = body[start_m.end():]
    if next_label:
        end_m = re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(next_label), rest)
    else:
        end_m = re.search(r"(?m)^(?:\d+\.\s+(?:\*\*|`)|Also verify|#{2,3} )", rest)
    end = start_m.end() + end_m.start() if end_m else len(body)
    return body[start_m.start():end]


def window_around(body, token, span=400):
    """Bounded window: `span` chars before/after the first occurrence of
    `token` (a literal substring), used to assert proximity between two
    tokens without depending on exact wording."""
    idx = body.find(token)
    assert idx != -1, "token %r not found" % token
    return body[max(0, idx - span):idx + len(token) + span]


class RequirementsExecutorSidecarContractTest(unittest.TestCase):
    """AC-3: the executor's step 2 ("DRAFT, code-cited write") routes the
    code-evidence citation to a companion `.evidence.md` sidecar, keyed by the
    clause's stable anchor, with no inline `path:line` left in the body."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(REQUIREMENTS_EXECUTOR)

    def test_draft_marker_still_present(self):
        self.assertRegex(self.body, r"(?i)DRAFT\s*(—|-)\s*human-confirm-required")

    def test_code_evidence_citation_phrase_still_present(self):
        self.assertRegex(self.body, r"(?i)code-evidence citation")

    def test_evidence_sidecar_token_near_citation_phrase(self):
        m = re.search(r"(?i)code-evidence citation", self.body)
        self.assertIsNotNone(m)
        near = self.body[m.start():m.start() + 600]
        self.assertRegex(
            near, SIDECAR_TOKEN_RE,
            "the '.evidence.md' sidecar token must appear within 600 chars "
            "after the 'code-evidence citation' phrase",
        )

    def test_body_states_no_inline_path_line(self):
        self.assertRegex(
            self.body, r"(?i)no\s+inline\s*`?path:line`?",
            "the executor charter must state the body carries no inline "
            "path:line citation",
        )

    def test_canonical_strip_form_sidecar_naming(self):
        self.assertIn(
            "<doc-basename-without-.md>.evidence.md", self.body,
            "the executor must encode the canonical strip-form sidecar "
            "filename rule (C-4)",
        )

    def test_open_clause_still_no_fabricated_citation(self):
        self.assertRegex(
            self.body, r"(?i)\[OPEN\][\s\S]{0,200}no\s+fabricated\s+citation",
        )


class RequirementsVerifierGroundingContractTest(unittest.TestCase):
    """AC-3: dimension 6 "Citation (100%)" is reframed IN PLACE to check the
    sidecar — body-grep-to-0, sidecar existence, anchor-join, and (amend
    mode) count-not-reduced."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(REQUIREMENTS_VERIFIER)
        cls.block = dimension_block(cls.body, "Citation (100%)", "DRAFT marker")

    def test_no_tests_path_hardcode(self):
        self.assertNotIn("tests/", self.body)

    def test_grep_spot_check_token_preserved(self):
        self.assertRegex(self.body, r"(?i)Grep-spot-check")

    def test_draft_marker_dimension_preserved_immediately_after(self):
        self.assertRegex(self.body, r"(?i)\*\*DRAFT marker\*\*")

    def test_dimension_mentions_evidence_sidecar(self):
        self.assertRegex(self.block, SIDECAR_TOKEN_RE)

    def test_dimension_asserts_body_grep_to_zero(self):
        self.assertRegex(
            self.block, r"(?i)\bgrep\b[\s\S]{0,200}\b0\b[\s\S]{0,60}match",
            "Citation (100%) must assert grepping the body for the in-scope "
            "citation regex yields 0 matches",
        )

    def test_dimension_asserts_anchor_join(self):
        self.assertRegex(
            self.block, r"(?i)anchor[\s\S]{0,120}(>=|at least)\s*1",
            "Citation (100%) must assert every clause anchor joins to >= 1 "
            "sidecar entry",
        )

    def test_dimension_asserts_count_not_reduced(self):
        self.assertRegex(
            self.block, r"(?i)not\s+reduced",
            "Citation (100%) must assert the amend-mode sidecar count is "
            "not reduced versus the prior committed version",
        )

    def test_dimension_label_and_position_unchanged(self):
        self.assertRegex(self.body, r"(?m)^6\.\s+\*\*Citation \(100%\)\*\*")
        self.assertRegex(self.body, r"(?m)^7\.\s+\*\*DRAFT marker\*\*")


class ArchitectureExecutorSidecarContractTest(unittest.TestCase):
    """AC-3: create-architecture-executor's "Doing the work" gains the same
    body+sidecar split rule, reusing the identical convention."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ARCHITECTURE_EXECUTOR)

    def test_mentions_evidence_sidecar(self):
        self.assertRegex(self.body, SIDECAR_TOKEN_RE)

    def test_reuses_convention_not_forked(self):
        self.assertRegex(
            self.body, r"(?i)(same|SAME|identical)[\s\S]{0,80}convention",
            "the architecture executor must state it reuses the SAME "
            "sidecar convention rather than forking a second scheme",
        )

    def test_canonical_strip_form_sidecar_naming(self):
        self.assertIn("<doc-basename-without-.md>.evidence.md", self.body)


class ArchitectureVerifierGroundingContractTest(unittest.TestCase):
    """AC-3: dimension 3 "codebase-match" gains the grounding check IN
    PLACE, well before structure/audience-style at the end of the list."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ARCHITECTURE_VERIFIER)
        cls.block = dimension_block(cls.body, "codebase-match", "mermaid-diagrams")

    def test_no_tests_path_hardcode(self):
        self.assertNotIn("tests/", self.body)

    def test_dimension_mentions_evidence_sidecar(self):
        self.assertRegex(self.block, SIDECAR_TOKEN_RE)

    def test_dimension_asserts_body_grep_to_zero(self):
        self.assertRegex(
            self.block, r"(?i)\bgrep\b[\s\S]{0,200}\b0\b[\s\S]{0,60}match",
        )

    def test_dimension_asserts_anchor_join(self):
        self.assertRegex(self.block, r"(?i)anchor[\s\S]{0,200}sidecar")

    def test_dimension_label_and_position_unchanged(self):
        self.assertRegex(self.body, r"(?m)^3\.\s+\*\*codebase-match\*\*")
        self.assertRegex(self.body, r"(?m)^4\.\s+\*\*mermaid-diagrams\*\*")
        structure_start = re.search(r"(?m)^\d+\.\s+\*\*structure\*\*", self.body).start()
        audience_start = re.search(r"(?m)^\d+\.\s+\*\*audience-style\*\*", self.body).start()
        self.assertLess(structure_start, audience_start,
                         "structure must directly precede audience-style, both last")


class CodeSkillRequirementsMergeSidecarContractTest(unittest.TestCase):
    """AC-3: /acs:code's requirements-merge write path (code/SKILL.md step 4)
    routes any in-scope citation it would otherwise embed to the target
    area file's companion sidecar."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_SKILL)

    def test_rubric_block_still_present(self):
        self.assertRegex(
            self.body, re.compile(r"FUNCTIONAL\*\*.*BEHAVIOR", re.DOTALL))
        self.assertRegex(
            self.body, re.compile(r"NON-FUNCTIONAL\*\*.*QUALITY", re.DOTALL))

    def test_evidence_sidecar_near_classification_rubric(self):
        m = re.search(r"deterministic at the seam\.", self.body)
        self.assertIsNotNone(m, "could not locate the end of the rubric block")
        near = self.body[m.end():m.end() + 1200]
        self.assertRegex(
            near, SIDECAR_TOKEN_RE,
            "code/SKILL.md step 4 must route in-scope citations to a "
            "'.evidence.md' sidecar near the classification rubric",
        )

    def test_canonical_strip_form_sidecar_naming(self):
        self.assertIn("<doc-basename-without-.md>.evidence.md", self.body)


class CodeVerifierDocumentationSidecarContractTest(unittest.TestCase):
    """AC-3: code-verifier.md dimension 11 (Documentation) blocks a
    requirements_path merge that leaves an inline in-scope citation instead
    of routing it to the sidecar."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_VERIFIER)
        cls.block = dimension_block(cls.body, "Documentation", "Simplicity & scope")

    def test_wrong_subfolder_language_preserved(self):
        self.assertRegex(self.body, r"wrong subfolder|wrong-subfolder")
        self.assertRegex(
            self.body, re.compile(r"outside.*requirements_layout", re.DOTALL))

    def test_dimension_mentions_evidence_sidecar(self):
        self.assertRegex(self.block, SIDECAR_TOKEN_RE)

    def test_dimension_blocks_inline_citation_in_merge(self):
        self.assertRegex(
            self.block,
            r'(?i)inline[\s\S]{0,120}citation[\s\S]{0,200}'
            r'severity="blocking"\s+dimension="documentation"',
        )


class ContractsMdSidecarNoteTest(unittest.TestCase):
    """AC-3/AC-6 (convention half): contracts.md's requirements paragraph
    names the sidecar mechanism; the producer-registration and
    conformance-chain lines stay byte-identical (owned by
    test_create_requirements_brownfield.py; re-asserted here as a guard)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CONTRACTS_MD)

    def test_requirements_paragraph_mentions_evidence_sidecar(self):
        self.assertRegex(self.body, SIDECAR_TOKEN_RE)

    def test_no_in_scope_citation_introduced(self):
        in_scope = re.compile(
            r"(?:[A-Za-z0-9_./-]+\.(?:py|json|sh|xsd)|SKILL\.md):[0-9]+(?:-[0-9]+)?")
        self.assertIsNone(
            in_scope.search(self.body),
            "contracts.md must not gain a new in-scope code-evidence "
            "citation; its only path:line is the out-of-scope ci.yml one",
        )

    def test_conformance_chain_line_unchanged(self):
        self.assertIn(
            "Conformance chain: `PRD → architecture → principles → standards → design → specs → code`, "
            "each level verified against the one above it.",
            self.body,
        )

    def test_producer_registration_line_present(self):
        self.assertRegex(
            self.body, r"(?i)/acs:create-requirements[\s\S]{0,200}producer skill")


if __name__ == "__main__":
    unittest.main()
