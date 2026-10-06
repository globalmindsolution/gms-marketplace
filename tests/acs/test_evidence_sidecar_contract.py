"""MAR-152 spec 01 — `.evidence.md` sidecar convention (contract layer).

Prose-contract tests over the 6 producer/verifier charters +
`docs/architecture/lld/contracts.md` (now one file per interface under
`docs/architecture/lld/acs/api/`) that wire the `.evidence.md` sidecar
convention: create-requirements and create-architecture's executors write
body + companion sidecar (clause anchor -> code-evidence citation list, no
inline `path:line`); their verifiers actively check grounding (body-grep-to-0,
anchor-join, count-not-reduced); /acs:docs-sync's requirements-merge write path
and its verifier's `requirements-routing` dimension route/guard the same way;
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

ARCHITECTURE_EXECUTOR = os.path.join(AGENTS, "create-architecture-architect.md")
ARCHITECTURE_VERIFIER = os.path.join(AGENTS, "create-architecture-reviewer.md")
DOCS_SYNC_EXECUTOR = os.path.join(AGENTS, "docs-sync-doc-updater.md")
#: The guard side of the merge. MAR-162 moved the requirements merge onto
#: /acs:docs-sync, and v0.5.0 retired code-verifier.md with the in-skill
#: review, so the judge that guards the routing is the drift-reviewer paired
#: with the doc-updater that performs it.
DOCS_SYNC_VERIFIER = os.path.join(AGENTS, "docs-sync-drift-reviewer.md")
#: contracts.md is one file per interface under lld/acs/api/ now; the
#: contract the old file carried is all of them together (sidecars excluded).
API_DIR = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "acs", "api")

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


class ArchitectureExecutorSidecarContractTest(unittest.TestCase):
    """AC-3: create-architecture-architect's "Doing the work" gains the same
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


class DocsSyncExecutorRequirementsMergeSidecarContractTest(unittest.TestCase):
    """AC-3 (MAR-162 retarget): the requirements-merge write path routes any
    in-scope citation it would otherwise embed to the target area file's
    companion sidecar. MAR-162 re-homed this write path out of
    `/acs:code`'s `code/SKILL.md` step 4 into docs-sync's writer charter
    (C-1; `docs-sync-doc-updater.md` since the per-skill subagents); the
    rubric+sidecar block itself moved byte-identical."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(DOCS_SYNC_EXECUTOR)

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
            "docs-sync-doc-updater.md must route in-scope citations to a "
            "'.evidence.md' sidecar near the classification rubric",
        )

    def test_canonical_strip_form_sidecar_naming(self):
        self.assertIn("<doc-basename-without-.md>.evidence.md", self.body)


class DocsSyncVerifierRequirementsRoutingSidecarContractTest(unittest.TestCase):
    """AC-3, at its current home: the verifier of the merge blocks a merge
    into the requirements set (`requirements_dir`) that leaves an inline
    in-scope citation instead of routing it to the sidecar.

    MAR-162 demoted the equivalent `code-verifier` sub-check to advisory
    precisely because docs-sync's own verifier re-derives and BLOCKS on the
    same content. v0.5.0 retired that verifier, so the advisory half is gone
    and the blocking half -- always the load-bearing one -- is what is pinned.
    """

    @classmethod
    def setUpClass(cls):
        cls.body = read(DOCS_SYNC_VERIFIER)
        cls.block = dimension_block(cls.body, "requirements-routing",
                                    "authoring-conformance")

    def test_wrong_subfolder_language_preserved(self):
        self.assertRegex(self.block, r"wrong subfolder|wrong-subfolder")
        # ADR-0102: the subfolders are the resolved `functional_dir` /
        # `non_functional_dir` constraints, no longer the removed
        # `requirements_layout` setting.
        self.assertIn("`functional_dir`", self.block)
        self.assertIn("`non_functional_dir`", self.block)
        self.assertNotIn("requirements_layout", self.block)

    def test_dimension_mentions_evidence_sidecar(self):
        self.assertRegex(self.block, SIDECAR_TOKEN_RE)

    def test_an_inline_in_scope_citation_is_a_finding(self):
        self.assertRegex(
            self.block,
            r"(?i)inline[\s\S]{0,200}sidecar is a finding")


class ContractsMdSidecarNoteTest(unittest.TestCase):
    """AC-3/AC-6 (convention half): contracts.md's requirements paragraph
    names the sidecar mechanism; the producer-registration and
    conformance-chain lines stay byte-identical (owned by
    test_create_requirements_brownfield.py; re-asserted here as a guard)."""

    @classmethod
    def setUpClass(cls):
        cls.body = "\n".join(
            read(os.path.join(API_DIR, n)) for n in sorted(os.listdir(API_DIR))
            if n.endswith(".md") and not SIDECAR_TOKEN_RE.search(n))

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
            "Conformance chain: `PRD → architecture → principles → standards → design → code`, "
            "each level verified against the one above it.",
            self.body,
        )

    def test_no_requirements_producer_is_registered(self):
        """Was `test_producer_registration_line_present`, which pinned
        `/acs:create-requirements` as the set's producer skill. ADR-0118
        removed that skill: the paragraph now says acs has no producer, and
        must not go on registering the removed one."""
        self.assertNotRegex(
            self.body, r"(?i)/acs:create-requirements` is the producer skill")
        self.assertRegex(self.body, r"(?i)no longer has a producer skill")


if __name__ == "__main__":
    unittest.main()
