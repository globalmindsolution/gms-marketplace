"""MAR-402 (parent MAR-401) — documentation assertions for the ticket-id
allocation fail-closed reconciliation gate.

Prose-contract tests over the doc set T3 amends/adds, mirroring the
whitespace-normalized substring/regex discipline used elsewhere in this repo
(tests/acs/test_create_docs_skill.py, tests/acs/test_create_requirements_skill.py):
every assertion checks that a claim from the design/plan is actually present
in the shipped doc, never a line-number match (prose is revised; line numbers
drift). Kept in its own module so T3's file map stays disjoint from T1's
library-level tests (tests/acs/test_ticket_id_reconciliation.py).

Run:  python3 -m unittest tests.acs.test_ticket_id_reconciliation_docs -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

CREATE_TICKET_SKILL = os.path.join(PLUGIN, "skills", "create-ticket", "SKILL.md")
CONTRACTS = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")
DATA_MODEL = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "data-model.md")
C4_COMPONENT = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md")
FLOW_DOC = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "flows", "ticket-id-reconciliation.md")
WORKSPACE_AND_STATE = os.path.join(
    REPO_ROOT, "docs", "requirements", "functional", "workspace-and-state.md"
)
ADR_0087 = os.path.join(
    REPO_ROOT, "docs", "adr", "0087-ticket-id-allocation-fail-closed-reconciliation.md"
)
ADR_README = os.path.join(REPO_ROOT, "docs", "adr", "README.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match."""
    return re.sub(r"\s+", " ", body)


class CreateTicketSkillDocsTest(unittest.TestCase):
    """AC-8: create-ticket/SKILL.md documents the refusal and its recovery."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CREATE_TICKET_SKILL)
        cls.norm = norm(cls.body)

    def test_create_ticket_skill_documents_the_refusal_and_seed_next(self):
        self.assertIn("--seed-next", self.body)
        self.assertIsNotNone(
            re.search(r"(?i)skill-start exits non-zero.{0,500}--seed-next", self.norm),
            "the refusal must be named as a case of the existing "
            "'skill-start exits non-zero' STOP rule, near the --seed-next recovery",
        )
        self.assertIsNotNone(
            re.search(r"(?i)never invent", self.norm),
            "must instruct never inventing the confirmed start number",
        )


class ContractsDocsTest(unittest.TestCase):
    """AC-8: both amended contracts.md rows (skill-start.py, new-ticket.py)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CONTRACTS)
        cls.norm = norm(cls.body)

    def test_contracts_rows_document_the_exit_2_refusal_and_seed_next(self):
        skill_start_row = re.search(
            r"skill-start\.py --skill S.*\|", self.body
        )
        new_ticket_row = re.search(
            r"new-ticket\.py --title --type.*\|", self.body
        )
        self.assertIsNotNone(skill_start_row, "skill-start.py contract row must exist")
        self.assertIsNotNone(new_ticket_row, "new-ticket.py contract row must exist")
        self.assertIn("--seed-next", skill_start_row.group(0))
        self.assertIn("--seed-next", new_ticket_row.group(0))
        for row in (skill_start_row.group(0), new_ticket_row.group(0)):
            self.assertIn("exit 2", row.lower())

    def test_seed_next_without_allocate_documented_as_malformed(self):
        self.assertIsNotNone(
            re.search(r"(?i)--seed-next.{0,5}without.{0,5}--allocate.{0,80}malformed", self.norm),
        )


class DataModelDocsTest(unittest.TestCase):
    """AC-8: the COUNTERS ER attribute block and the fail-closed prose line."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(DATA_MODEL)
        cls.norm = norm(cls.body)

    def test_data_model_counters_block_declares_the_persisted_fields(self):
        block_match = re.search(r"COUNTERS \{([^}]*)\}", self.body, re.DOTALL)
        self.assertIsNotNone(block_match, "COUNTERS must have an ER attribute block")
        block = block_match.group(1)
        for field in ("next", "reconciled", "seed_source", "seeded_at"):
            self.assertIn(field, block, "COUNTERS block missing field %r" % field)

    def test_data_model_counters_block_does_not_declare_observed_max(self):
        # observed_max is never persisted (refusal-message-only) — F1.
        block_match = re.search(r"COUNTERS \{([^}]*)\}", self.body, re.DOTALL)
        self.assertIsNotNone(block_match)
        self.assertNotIn("observed_max", block_match.group(1))

    def test_documents_the_fail_closed_first_allocate_rule(self):
        self.assertIsNotNone(
            re.search(r"(?i)fail-closed", self.norm),
        )
        self.assertIsNotNone(
            re.search(r"(?i)COUNTERS note.{0,50}MAR-402", self.norm),
        )


class C4ComponentDocsTest(unittest.TestCase):
    """AC-8: the lib component description names the gate and the scan helper."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(C4_COMPONENT)
        cls.norm = norm(cls.body)

    def test_c4_component_lib_names_the_reconciliation_gate(self):
        self.assertIn("allocate_ticket_id", self.norm)
        self.assertIn("scan_local_ticket_evidence", self.norm)
        self.assertIsNotNone(
            re.search(r"(?i)reconciliation gate", self.norm),
        )

    def test_lib_component_description_has_no_release_notes_scope_bleed(self):
        # The lib component's own description line must not gain
        # release_notes.py's gh-seam disclosure -- that lives in
        # release_notes' own component description (MAR-403 D-3), not lib's.
        # The gh_failure_hint fence retired here: MAR-403 adds it to this
        # same line by design (Option F), so asserting its absence would
        # expire the moment that ticket lands.
        lib_line_match = re.search(
            r'Component\(lib, "acs_lib\.py".*?\n', self.body, re.DOTALL
        )
        self.assertIsNotNone(lib_line_match, "the lib component entry must exist")
        lib_line = lib_line_match.group(0)
        self.assertNotIn("release_notes.py", lib_line)


class FlowDocTest(unittest.TestCase):
    """AC-8: the new reconciliation sequence-diagram flow doc."""

    def test_reconciliation_flow_doc_exists_and_is_a_sequence_diagram(self):
        self.assertTrue(os.path.isfile(FLOW_DOC), "%s must exist" % FLOW_DOC)
        body = read(FLOW_DOC)
        self.assertIn("```mermaid", body)
        self.assertIn("sequenceDiagram", body)
        norm_body = norm(body)
        for token in (
            "ReconciliationRequired",
            "seed_next",
            "explicit-user",
            "committed-files",
            "git-history",
            "branch-names",
        ):
            self.assertIn(token, norm_body, "flow doc missing token %r" % token)

    def test_seed_next_wording_names_the_correct_next_write(self):
        # --seed-next n mints PREFIX-n immediately, but writes next=n+1 (so
        # the FOLLOWING mint is PREFIX-(n+1)) -- not next=n.
        body = read(FLOW_DOC)
        self.assertIn("next=seed_next+1", body)


class WorkspaceAndStateDocsTest(unittest.TestCase):
    """AC-8: counters.json's description gains the reconciliation fields."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(WORKSPACE_AND_STATE)
        cls.norm = norm(cls.body)

    def test_workspace_and_state_documents_the_fail_closed_first_allocation(self):
        self.assertIsNotNone(re.search(r"(?i)fail-closed", self.norm))
        for field in ("reconciled", "seed_source", "seeded_at"):
            self.assertIn(field, self.body)
        self.assertIn("--seed-next", self.body)

    def test_observed_max_is_documented_as_refusal_message_only(self):
        self.assertIsNotNone(
            re.search(r"(?i)observed_max.{0,80}(refusal|never persisted)", self.norm)
            or re.search(r"(?i)(refusal|never persisted).{0,80}observed_max", self.norm),
            "observed_max must be documented as surfaced only in the refusal "
            "message, never persisted to counters.json",
        )


class Adr0087Test(unittest.TestCase):
    """AC-8: ADR-0087 exists, is Accepted, scoped to reconciliation only (C-15)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ADR_0087)
        cls.norm = norm(cls.body)

    def test_adr_0087_exists_is_accepted_and_is_scoped_to_reconciliation(self):
        self.assertIsNotNone(re.search(r"\*\*Status\*\*:\s*Accepted", self.body))
        for term in ("ReconciliationRequired", "seed_source", "observed_max", "--seed-next"):
            self.assertIn(term, self.norm)
        # C-15 scoping guard: no gh-transport / call-criticality decision here.
        self.assertNotIn("critical/non-critical classification", self.norm)
        self.assertNotIn("GH_ACCESS_DENIED_MARKER", self.body)
        self.assertNotIn("gh_failure_hint", self.body)
        self.assertIsNotNone(
            re.search(r"(?i)ADR-0088", self.norm),
            "must point the gh-transport decision at its own ADR-0088",
        )

    def test_records_rejected_options(self):
        for term in ("tracker", "high-water-mark", "bare fail-closed"):
            self.assertIn(term.lower(), self.norm.lower())

    def test_observed_max_is_documented_as_refusal_message_only(self):
        self.assertIsNotNone(
            re.search(r"(?i)observed_max.{0,80}(refusal|never persisted)", self.norm)
            or re.search(r"(?i)(refusal|never persisted).{0,80}observed_max", self.norm),
            "observed_max must be documented as surfaced only in the refusal "
            "message, never persisted to counters.json",
        )

    def test_seed_next_wording_names_the_correct_next_write(self):
        # --seed-next n mints <PREFIX>-n immediately, but writes next=n+1 (so
        # the FOLLOWING mint is <PREFIX>-(n+1)) -- not next=n.
        self.assertIsNotNone(
            re.search(r"(?i)next=n\+1", self.norm),
            "must document that --seed-next n writes next=n+1, not next=n",
        )


class Adr0087IndexTest(unittest.TestCase):
    """AC-8 / K8: docs/adr/README.md indexes ADR-0087 (belt-and-braces over
    test_doc_fact_pins.py's test_every_disk_file_has_a_row)."""

    def test_adr_0087_is_indexed(self):
        body = read(ADR_README)
        self.assertIsNotNone(
            re.search(r"\[0087\]\(0087-[a-z0-9-]+\.md\)", body),
            "docs/adr/README.md must index ADR-0087",
        )
        self.assertTrue(os.path.isfile(ADR_0087))


if __name__ == "__main__":
    unittest.main()
