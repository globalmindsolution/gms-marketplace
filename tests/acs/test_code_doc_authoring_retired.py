"""MAR-162 spec 01 — retire /code's execute-phase doc-authoring instructions.

Falsifiable AC-1 guard: asserts the doc-authoring instructions (README/API/
usage/changelog authoring, the living-requirements merge, the HLD/lld-flows/
ADR-commit clause, the functional/non-functional classification rubric, the
`.evidence.md` sidecar routing rule) are ABSENT from the exact span they are
retired from in `code/SKILL.md`'s execute step and `code-executor.md`'s
charter, that the relocated clauses (code-comment policy, test-filename rule,
Simplicity First pointer) and the retained product-doc factual-reconciliation
paragraph survive in those same producers, that the re-homed content actually
landed in `docs-sync-executor.md`, and that `code-planner.md` still carries
its Boy-scout drift-repair paragraph with only the terminal clause rewritten
to carry drift items into the execute report's `problems` field.

Stdlib-only (os, unittest). Run:
  python3 -m unittest tests.acs.test_code_doc_authoring_retired -v
"""

import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_EXECUTOR = os.path.join(PLUGIN, "agents", "code-executor.md")
CODE_PLANNER = os.path.join(PLUGIN, "agents", "code-planner.md")
DOCS_SYNC_EXECUTOR = os.path.join(PLUGIN, "agents", "docs-sync-executor.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def execute_span(body):
    """code/SKILL.md's Execute (per iteration) section, up to Verify."""
    return body[body.index("### Execute (per iteration)"):
                body.index("### Verify (per iteration)")]


def charter_span(body):
    """code-executor.md's Charter section, up to Phase artifact."""
    return body[body.index("## Charter"):
                body.index("## Phase artifact")]


class CodeSkillExecuteSpanRetiredTest(unittest.TestCase):
    """The doc-authoring tokens no longer appear inside code/SKILL.md's
    Execute span — the span this ticket retires them from."""

    @classmethod
    def setUpClass(cls):
        cls.span = execute_span(read(CODE_SKILL))

    def test_absence_update_the_docs_heading(self):
        self.assertNotIn("**Update the docs", self.span)

    def test_absence_readme_api_and(self):
        # Deliberately "README, API and" — NOT "README, API and usage docs",
        # which spans the old :382-383 line break and would assert nothing.
        self.assertNotIn("README, API and", self.span)

    def test_absence_changelog(self):
        self.assertNotIn("changelog", self.span)

    def test_absence_mermaid_sequence_diagrams(self):
        self.assertNotIn("Mermaid sequence diagrams", self.span)

    def test_absence_lld_flows(self):
        # Span-scoped ONLY: "lld/flows" legitimately survives elsewhere in
        # code/SKILL.md (spec 02's Verify bullet and the result.json
        # example), both outside the Execute span — do not widen this to a
        # whole-body assertion.
        self.assertNotIn("lld/flows", self.span)

    def test_absence_accepted_decision_records(self):
        self.assertNotIn("accepted decision records", self.span)

    def test_absence_architecture_path(self):
        self.assertNotIn("architecture_path", self.span)

    def test_absence_adr_path(self):
        self.assertNotIn("adr_path", self.span)

    def test_absence_merge_ticket_acceptance_criteria(self):
        self.assertNotIn("Merge the ticket's acceptance criteria", self.span)

    def test_absence_requirements_path(self):
        self.assertNotIn("requirements_path", self.span)

    def test_absence_requirements_layout(self):
        self.assertNotIn("requirements_layout", self.span)

    def test_presence_reconcile_product_doc_facts_heading(self):
        self.assertIn("Reconcile product-doc facts", self.span)

    def test_presence_product_doc_factual_reconciliation(self):
        self.assertIn("Product-doc factual reconciliation", self.span)

    def test_presence_code_comment_policy_relocated(self):
        # "and" form — code/SKILL.md's wording, distinct from
        # code-executor.md's comma form.
        self.assertIn("minimal and idea-only", self.span)

    def test_presence_test_filename_rule_relocated(self):
        self.assertIn("never by a ticket id", self.span)

    def test_presence_simplicity_first_relocated(self):
        self.assertIn("Simplicity First", self.span)

    def test_boy_scout_drift_carry_window(self):
        """F3 window assertion 1: 'Boy-scout' and 'problems' co-occur within
        800 chars, proving the drift-carry paragraph is checked, not merely
        narrated."""
        anchor = self.span.find("Boy-scout")
        self.assertGreater(anchor, 0)
        self.assertIn("problems", self.span[anchor:anchor + 800])


class CodeExecutorWholeBodyRetiredTest(unittest.TestCase):
    """The doc-authoring tokens no longer appear ANYWHERE in code-executor.md
    — every one of these nine tokens is a single-purpose occurrence inside
    this spec's own edit set, so the whole-body form is satisfiable."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_EXECUTOR)

    def test_absence_readme_api_usage_docs(self):
        # "README, API/usage docs" — CORRECTED from "README, API and usage
        # docs", which does not exist in this file.
        self.assertNotIn("README, API/usage docs", self.body)

    def test_absence_changelog(self):
        self.assertNotIn("changelog", self.body)

    def test_absence_mermaid_sequence_diagrams(self):
        self.assertNotIn("Mermaid sequence diagrams", self.body)

    def test_absence_decision_records(self):
        # "decision records" — CORRECTED from "accepted decision records",
        # which does not exist in this file.
        self.assertNotIn("decision records", self.body)

    def test_absence_behavior_defining(self):
        # CORRECTED from "Merge the ticket's acceptance criteria", which
        # does not exist in this file.
        self.assertNotIn("behavior-defining", self.body)

    def test_absence_requirements_path(self):
        self.assertNotIn("requirements_path", self.body)

    def test_absence_requirements_layout(self):
        self.assertNotIn("requirements_layout", self.body)

    def test_absence_architecture_path(self):
        self.assertNotIn("architecture_path", self.body)

    def test_absence_adr_path(self):
        self.assertNotIn("adr_path", self.body)


class CodeExecutorCharterSpanTest(unittest.TestCase):
    """Charter-span-scoped checks — F1's resolution: 'lld/flows' at :126 is
    inside the span and removed; the retained example under '## Phase
    artifact' sits outside it, so this must be span-scoped, not whole-body."""

    @classmethod
    def setUpClass(cls):
        cls.span = charter_span(read(CODE_EXECUTOR))

    def test_absence_lld_flows(self):
        self.assertNotIn("lld/flows", self.span)

    def test_presence_code_comment_policy_comma_form(self):
        # Comma form — this file's wording (F2's resolution), distinct from
        # code/SKILL.md's "and" form.
        self.assertIn("minimal, idea-only", self.span)

    def test_presence_test_filename_rule(self):
        self.assertIn("never by a ticket id", self.span)

    def test_presence_simplicity_first(self):
        self.assertIn("Simplicity First", self.span)

    def test_presence_product_doc_factual_reconciliation(self):
        self.assertIn("Product-doc factual reconciliation", self.span)

    def test_boy_scout_drift_carry_window(self):
        """F3 window assertion 2: same window check, in the executor's
        register."""
        anchor = self.span.find("Boy-scout")
        self.assertGreater(anchor, 0)
        self.assertIn("problems", self.span[anchor:anchor + 800])


class DocsSyncExecutorRehomeTest(unittest.TestCase):
    """The re-home landed: docs-sync-executor.md's charter now carries the
    tokens this spec removed from /code's producers, proving re-home rather
    than plain deletion."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(DOCS_SYNC_EXECUTOR)

    def test_presence_functional(self):
        self.assertIn("FUNCTIONAL", self.body)

    def test_presence_requirements_layout(self):
        self.assertIn("requirements_layout", self.body)

    def test_presence_requirements_path(self):
        self.assertIn("requirements_path", self.body)

    def test_presence_evidence_sidecar(self):
        self.assertIn(".evidence.md", self.body)

    def test_presence_architecture_path(self):
        self.assertIn("architecture_path", self.body)

    def test_presence_lld_flows(self):
        self.assertIn("lld/flows", self.body)

    def test_presence_adr_path(self):
        self.assertIn("adr_path", self.body)


class CodePlannerBoyScoutRetainedTest(unittest.TestCase):
    """code-planner.md's Boy-scout drift-repair detection/scheduling
    sub-paragraph is RETAINED — only its terminal clause is rewritten so the
    EXECUTOR (not the planner) carries drift items into `problems`."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_PLANNER)

    def test_absence_name_the_hld_files(self):
        self.assertNotIn("name the HLD files", self.body)

    def test_absence_list_the_adrs_to_commit(self):
        self.assertNotIn("list the ADRs to commit", self.body)

    def test_presence_boy_scout_drift_repair(self):
        self.assertIn("Boy-scout drift repair", self.body)

    def test_presence_compare_current_code(self):
        self.assertIn("compare", self.body)
        self.assertIn("CURRENT code", self.body)

    def test_presence_prd_roadmap_factual_sentence(self):
        self.assertIn("prd.md", self.body)
        self.assertIn("roadmap.md", self.body)

    def test_boy_scout_drift_carry_window(self):
        """F3 window assertion 3: proves the terminal-clause rewrite landed
        and that the planner names the carrier (the executor), not the
        writer, of `problems`."""
        anchor = self.body.find("Boy-scout")
        self.assertGreater(anchor, 0)
        self.assertIn("problems", self.body[anchor:anchor + 800])


if __name__ == "__main__":
    unittest.main()
