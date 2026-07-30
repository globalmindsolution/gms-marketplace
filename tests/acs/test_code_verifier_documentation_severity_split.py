"""MAR-162 spec 02 — demote code-verifier's per-commit doc-sync sub-checks
to advisory.

Falsifiable AC-2/AC-3 guard: asserts dimension 11 (Documentation)'s
per-commit doc-sync, living-requirements, and architectural-impact
sub-checks carry advisory (`severity="info"`) wording and explicitly never
gate `verifier_passed`, that none of those three sub-checks' spans still
carry `severity="blocking" dimension="documentation"`, that the distinct
MAR-65 Product-doc-consistency sub-check is untouched and stays blocking,
that the "ALL findings block" section carries the narrow advisory carve-out,
that the C3 literal-preservation constraints on the advisory rewrite of the
living-requirements sub-check hold, and that the result-document surfacing
of advisory documentation findings (result.json `findings` /
`review.findings_open` / `verifier_passed`, and the Completion report's
`**Findings**` line) is documented in both `code/SKILL.md` and
`code-verifier.md`.

Stdlib-only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_code_verifier_documentation_severity_split -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
CODE_VERIFIER = os.path.join(PLUGIN, "agents", "code-verifier.md")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")

BLOCKING_DOC = 'severity="blocking" dimension="documentation"'


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def dimension_block(body, label, next_label):
    """Extract a numbered check-dimension list item: from the line matching
    '^N. **label**' up to (not including) the next numbered item labelled
    `next_label`. Mirrors test_evidence_sidecar_contract.py's helper."""
    start_m = re.search(r"(?m)^\d+\.\s+\*\*%s\*\*" % re.escape(label), body)
    assert start_m is not None, "dimension %r not found" % label
    rest = body[start_m.end():]
    end_m = re.search(r"(?m)^\d+\.\s+\*\*%s\*\*" % re.escape(next_label), rest)
    assert end_m is not None, "next dimension %r not found" % next_label
    return body[start_m.start():start_m.end() + end_m.start()]


def product_doc_consistency_span(block):
    """The MAR-65 sub-check's own span within the dimension-11 block."""
    start = block.find("**Product-doc-consistency check:**")
    assert start != -1, "Product-doc-consistency check not found"
    end = block.find("No factual impact", start)
    assert end != -1, "'No factual impact' terminal phrase not found"
    end = block.find(".", end) + 1
    return block[start:end]


class DocumentationDimensionAdvisoryDemotionTest(unittest.TestCase):
    """AC-3, demotion half: the per-commit doc-sync, living-requirements,
    and architectural-impact sub-checks are advisory, never gate
    verifier_passed, and their substance is still fully performed and
    reported (not deleted)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_VERIFIER)
        cls.block = dimension_block(cls.body, "Documentation", "Simplicity & scope")
        cls.mar65_span = product_doc_consistency_span(cls.block)
        # Everything in the dimension-11 block EXCEPT the byte-identical
        # MAR-65 span is the demoted (a)/(b)/(d) territory.
        mar65_start = cls.block.find(cls.mar65_span)
        cls.demoted_span = (
            cls.block[:mar65_start] + cls.block[mar65_start + len(cls.mar65_span):]
        )

    def test_dimension_label_and_position_unchanged(self):
        self.assertRegex(self.body, r"(?m)^11\.\s+\*\*Documentation\*\*")

    def test_advisory_severity_info_present(self):
        self.assertIn('severity="info"', self.demoted_span)

    def test_advisory_never_gates_verifier_passed(self):
        self.assertRegex(
            self.demoted_span,
            r'(?i)never\s+gates?\s+`?verifier_passed`?',
            "the demoted sub-checks must explicitly state they never gate "
            "verifier_passed",
        )

    def test_advisory_names_docs_sync_as_blocking_owner(self):
        self.assertRegex(
            self.demoted_span, r"(?i)docs-sync[\s\S]{0,200}(re-derives|blocks)",
            "the demoted sub-checks must name docs-sync's own verifier as "
            "the component that now blocks on this content",
        )

    def test_no_blocking_documentation_literal_outside_mar65_span(self):
        self.assertNotIn(
            BLOCKING_DOC, self.demoted_span,
            "the demoted (a)/(b)/(d) sub-checks must not carry "
            '`severity="blocking" dimension="documentation"` any more',
        )

    def test_per_commit_doc_sync_substance_retained(self):
        for token in ("README", "API/usage docs", "changelog", "architecture_path",
                      "lld/flows", "adr_path"):
            self.assertIn(token, self.demoted_span,
                          "per-commit doc-sync sub-check substance must survive: %r" % token)

    def test_living_requirements_substance_retained(self):
        self.assertRegex(self.demoted_span, r"(?i)living requirements")
        self.assertIn("requirements_path", self.demoted_span)

    def test_architectural_impact_substance_retained(self):
        self.assertRegex(self.demoted_span, r"(?i)architectural-impact")
        self.assertRegex(self.demoted_span, r"(?i)never waved through")


class ProductDocConsistencyByteIdenticalTest(unittest.TestCase):
    """AC-3, carve-out half (regression guard): the MAR-65
    Product-doc-consistency sub-check is present, unchanged, and still
    carries severity="blocking" dimension="documentation" with prd.md/
    roadmap.md — the ticket's mar65_byte_identical constraint."""

    EXPECTED = (
        "**Product-doc-consistency check:** make a positive, evidenced determination\n"
        "    of whether the changeset leaves any factual claim in `docs/product/prd.md`\n"
        "    or `docs/product/roadmap.md` stale (factual items: agent/subagent counts,\n"
        "    feature/epic shipped-vs-planned status, component topology, version numbers,\n"
        "    file path references; per the boundary defined in code-executor step 4).\n"
        "    Stale factual claim + no matching update in the SAME diff = a blocking\n"
        "    finding (`severity=\"blocking\" dimension=\"documentation\"`, with `file` set\n"
        "    to the stale prd.md or roadmap.md). An intent contradiction (goals, NFR\n"
        "    targets, scope, vision, requirements rationale) found by the changeset is\n"
        "    an explicit flagged divergence — emit a flagged divergence note, NOT a\n"
        "    blocking finding; intent content stays `/acs:create-prd`-owned and must\n"
        "    NOT be rewritten. No factual impact → no-op for this check."
    )

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_VERIFIER)

    def test_mar65_span_present_and_byte_identical(self):
        normalized_body = re.sub(r"[ \t]+", " ", self.body)
        normalized_expected = re.sub(r"[ \t]+", " ", self.EXPECTED)
        self.assertIn(
            normalized_expected, normalized_body,
            "the MAR-65 Product-doc-consistency span must survive "
            "byte-identical (modulo pure indentation)",
        )

    def test_mar65_span_still_blocking_with_prd_and_roadmap(self):
        anchor = self.body.find("**Product-doc-consistency check:**")
        self.assertGreater(anchor, 0)
        window = self.body[anchor:anchor + 1200]
        self.assertIn(BLOCKING_DOC, window)
        self.assertIn("prd.md", window)
        self.assertIn("roadmap.md", window)


class AllFindingsBlockCarveOutTest(unittest.TestCase):
    """AC-3: the global 'ALL findings block' rule names the three advisory
    documentation sub-checks as its sole exception (the plan's 'most likely
    to be missed' edit, outside dimension 11's own text block)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_VERIFIER)

    def test_all_findings_block_carve_out_present(self):
        anchor = self.body.find("ALL findings block")
        self.assertGreater(anchor, 0, "'ALL findings block' rule not found")
        window = self.body[anchor:anchor + 900]
        self.assertRegex(
            window, r'(?i)severity="info"',
            "the ALL findings block section must name the advisory "
            "severity=\"info\" carve-out",
        )
        self.assertRegex(
            window, r"(?i)documentation",
            "the carve-out sentence must reference the Documentation "
            "dimension's advisory sub-checks",
        )

    def test_zero_findings_rule_unaffected_by_advisory_findings(self):
        anchor = self.body.find("Zero findings means")
        self.assertGreater(anchor, 0, "'Zero findings means' line not found")
        window = self.body[anchor:anchor + 400]
        self.assertRegex(window, r'(?i)info|advisory')


class LivingRequirementsC3LiteralPreservationTest(unittest.TestCase):
    """C3 (R7/F5): the advisory rewrite of sub-check (b) must not drop the
    three literals live tests depend on elsewhere in the repo."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_VERIFIER)
        cls.block = dimension_block(cls.body, "Documentation", "Simplicity & scope")

    def test_requirements_layout_literal_present(self):
        self.assertIn("requirements_layout", self.body)

    def test_wrong_subfolder_phrasing_present(self):
        self.assertRegex(self.body, r"wrong subfolder|wrong-subfolder")
        self.assertRegex(
            self.body, re.compile(r"outside.*requirements_layout", re.DOTALL))

    def test_evidence_sidecar_token_present_in_dimension_block(self):
        self.assertRegex(self.block, re.compile(r"(?i)\.evidence\.md"))


class ResultDocumentAdvisorySurfacingTest(unittest.TestCase):
    """F8: advisory documentation findings surface in result.json's
    findings array and the Completion report's Findings line, but never
    count toward review.findings_open or verifier_passed. Documented in
    both `code/SKILL.md` and `code-verifier.md` (dimension 11)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_SKILL)

    def test_finish_step_states_advisory_findings_carried_but_excluded(self):
        anchor = self.body.find("Canonical `states` keys")
        self.assertGreater(anchor, 0, "canonical states keys block not found")
        window = self.body[anchor:anchor + 3000]
        self.assertRegex(window, r"(?i)advisory[\s\S]{0,200}documentation")
        self.assertRegex(
            window, r"(?i)`findings`",
            "must state advisory documentation findings populate `findings`",
        )
        self.assertRegex(
            window, r"(?i)(never|excluded|not count).{0,200}(findings_open|verifier_passed)",
            re.DOTALL,
        )

    def test_completion_report_findings_line_names_advisory_flags(self):
        anchor = self.body.find("**Findings**")
        self.assertGreater(anchor, 0, "Completion report Findings line not found")
        window = self.body[max(0, anchor - 200):anchor + 800]
        self.assertRegex(window, r"(?i)advisory[\s\S]{0,200}documentation")

    def test_verifier_dimension_11_hands_advisory_findings_to_result_document(self):
        block = dimension_block(read(CODE_VERIFIER), "Documentation", "Simplicity & scope")
        self.assertRegex(block, r"(?i)verify report")
        self.assertRegex(block, r"(?i)result document")
        self.assertRegex(block, r"(?i)coordinator")


class VerifyDocumentationBulletAc2Test(unittest.TestCase):
    """AC-2: code/SKILL.md's Verify-section Documentation bullet names
    docs-sync as the owner of per-commit doc updates, while the
    Product-doc-consistency paragraph stays as-is."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_SKILL)

    def test_documentation_bullet_names_docs_sync_ownership(self):
        anchor = self.body.find("**Documentation**")
        self.assertGreater(anchor, 0)
        window = self.body[anchor:anchor + 1200]
        self.assertRegex(window, r"(?i)docs-sync")

    def test_documentation_bullet_still_has_product_doc_consistency(self):
        anchor = self.body.find("**Documentation**")
        self.assertGreater(anchor, 0)
        window = self.body[anchor:anchor + 1200]
        self.assertRegex(window, r"(?i)Product-doc-consistency check")


if __name__ == "__main__":
    unittest.main()
