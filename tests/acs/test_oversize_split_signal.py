"""MAR-164 spec 01 — oversize signal + split-answer termination (Gap 1,
Decision 1, Option C).

Covers AC-1 (a non-blocking, plan-time oversize signal in code-planner.md
plus the honest rewrite of create-ticket/SKILL.md's split path), the Gap-1
half of AC-4 (cross-file consistency of the split-path evidence contract and
the split-answer termination, including both Finish-step-3 sub-sites), and
the Gap-1 half of AC-5 (no regression, and the ADR-0069-driven repair of
test_no_new_adr_number_minted stays a durable invariant).

Every assertion is by file + substring/regex, never by line number (line
numbers drift as sibling specs 02/03 land on the same files).

Stdlib-only (glob, json, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_oversize_split_signal -v
"""

import glob
import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import evidence_sidecar  # noqa: E402

CODE_PLANNER = os.path.join(PLUGIN, "agents", "code-planner.md")
CREATE_TICKET_SKILL = os.path.join(PLUGIN, "skills", "create-ticket", "SKILL.md")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
SHIP_SKILL = os.path.join(PLUGIN, "skills", "ship", "SKILL.md")
SETTINGS_SCHEMA = os.path.join(PLUGIN, "schemas", "settings.schema.json")
SKILLS_REQ = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")
REQ_README = os.path.join(REPO_ROOT, "docs", "requirements", "README.md")
INTERNALS = os.path.join(PLUGIN, "docs", "INTERNALS.md")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")
ADR_README = os.path.join(ADR_DIR, "README.md")
REQ_FUNCTIONAL = os.path.join(REPO_ROOT, "docs", "requirements", "functional")
REQ_NON_FUNCTIONAL = os.path.join(REPO_ROOT, "docs", "requirements", "non-functional")

# Fixture-pinned skills.md clauses (tests/acs/fixtures/mar145_clause_inventory.json)
# that MUST survive verbatim somewhere under docs/requirements/{functional,non-functional}/.
PINNED_CLAUSES = (
    "- MAY **split an existing oversized ticket** (`/create-ticket split <id> ...`,",
    "- MUST escalate an **oversized ticket** instead of producing a monster spec",
    "`/create-ticket split <id>` (user-confirmed); the user MAY explicitly accept",
)

C9_STOP_REASON = "user chose to split; restructure required before implementation"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _req_tree_bodies():
    bodies = []
    for d in (REQ_FUNCTIONAL, REQ_NON_FUNCTIONAL):
        for name in os.listdir(d):
            if name.endswith(".md") and not evidence_sidecar.is_evidence_sidecar(name):
                bodies.append(read(os.path.join(d, name)))
    return bodies


class CodePlannerOversizeSignalTest(unittest.TestCase):
    """AC-1 half 1: code-planner.md's charter item 2 gains a non-blocking
    oversize-signal clause."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_PLANNER)
        start = cls.body.index("2. **Executor decomposition with a file map.**")
        end = cls.body.index("3. **Test strategy per spec")
        cls.item2 = cls.body[start:end]

    def test_rubric_numbers_present(self):
        """Assertion 1: reuses create-ticket-planner.md's ~4/~400/~7 rubric."""
        self.assertIn("~4", self.item2)
        self.assertIn("~400", self.item2)
        self.assertIn("~7", self.item2)
        self.assertIn("create-ticket-planner.md", self.item2)

    def test_surface_never_block_contract(self):
        """Assertion 1 / C-5: the signal surfaces, it never blocks."""
        self.assertIsNotNone(
            re.search(r"(?i)surface.{0,60}never block", self.item2, re.DOTALL),
            "code-planner.md item 2 must state the 'surface ... never block' "
            "contract for the oversize signal")

    def test_plan_artifact_records_seams_sentence(self):
        """Assertion 1: the plan artifact is the evidence-of-seams source."""
        self.assertIn("split seams", self.item2)
        self.assertIn("plan artifact", self.item2)

    def test_no_stop_or_halt_branch(self):
        """C-5: detection surfaces a question, never a stop/halt branch."""
        self.assertNotRegex(self.item2, r"(?i)\bstop the run\b")
        self.assertNotRegex(self.item2, r"(?i)\bhalts? the run\b")

    def test_no_new_create_spec_token_beyond_provenance(self):
        """Assertion 9: the only create-spec hit in code-planner.md stays
        the single pre-existing provenance line."""
        lines = [ln for ln in self.body.splitlines() if "create-spec" in ln]
        self.assertEqual(len(lines), 1,
                         "code-planner.md must carry exactly one create-spec "
                         "line (the pre-existing provenance note): %r" % lines)
        self.assertIn("migrated from the deleted create-spec-planner.md", lines[0])


class SplitEvidenceContractIdentityTest(unittest.TestCase):
    """Assertion 11: Sites 1 (code-planner.md) and 2 (create-ticket/SKILL.md)
    name the SAME plan-artifact evidence source."""

    @classmethod
    def setUpClass(cls):
        planner_body = read(CODE_PLANNER)
        start = planner_body.index("2. **Executor decomposition with a file map.**")
        end = planner_body.index("3. **Test strategy per spec")
        cls.item2 = planner_body[start:end]

        ticket_body = read(CREATE_TICKET_SKILL)
        start = ticket_body.index("## Splitting an existing oversized ticket")
        end = ticket_body.index("## Resume & reconcile")
        cls.split_section = ticket_body[start:end]

    def test_planner_clause_names_plan_artifact_path_token(self):
        self.assertIn("phases/code/iter-", self.item2)

    def test_split_section_names_same_artifact(self):
        self.assertTrue(
            "`/code` plan artifact" in self.split_section
            or "phases/code/iter-" in self.split_section,
            "create-ticket/SKILL.md's split section must name the same "
            "plan-artifact evidence source Site 1 names")

    def test_neither_site_names_create_spec_plan_artifact(self):
        self.assertNotIn("create-spec plan artifact", self.item2)
        self.assertNotIn("create-spec plan artifact", self.split_section)


class CreateTicketSplitPathRewriteTest(unittest.TestCase):
    """AC-1 half 2: create-ticket/SKILL.md's split path is honestly
    rewritten — no create-spec reference, no 'escalation ... emits' framing."""

    @classmethod
    def setUpClass(cls):
        body = read(CREATE_TICKET_SKILL)
        start = body.index("## Splitting an existing oversized ticket")
        end = body.index("## Resume & reconcile")
        cls.section = body[start:end]

    def test_no_create_spec_reference(self):
        self.assertNotIn("create-spec", self.section)

    def test_no_escalation_emits_framing(self):
        self.assertNotIn("escalation", self.section)

    def test_names_code_plan_artifact_as_evidence_source(self):
        self.assertIn("plan-time oversize", self.section)

    def test_downstream_work_rule_unchanged(self):
        """':75-77' — untouched by this spec; still governs re-entry."""
        normalized = re.sub(r"\s+", " ", self.section)
        self.assertIn(
            "If downstream work already exists (specs, a branch), say so and "
            "get the user's confirmation first", normalized)


class CodeSkillFoldPointerTest(unittest.TestCase):
    """Assertion 10: the fold section gains a pointer to the new oversize
    signal, without disturbing the test-pinned provenance clauses."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_SKILL)
        start = cls.body.index("**Spec authoring fold")
        end = cls.body.index("### Docs-only tickets")
        cls.fold = cls.body[start:end]

    def test_fold_slice_points_at_planner_charter_item_2(self):
        self.assertIn("oversize", self.fold.lower())
        self.assertIn("code-planner.md", self.fold)
        self.assertIn("charter item 2", self.fold)

    def test_provenance_clauses_survive_verbatim_in_slice(self):
        self.assertIn(
            "create-spec planner would once have produced", self.fold)
        self.assertIn(
            "no separate /acs:create-spec invocation and no separate "
            "create-spec planner", self.fold)


class CodeSkillUserInteractionSplitTest(unittest.TestCase):
    """Assertion 3 + 13: '## User interaction' states the split-answer
    termination contract in full."""

    @classmethod
    def setUpClass(cls):
        body = read(CODE_SKILL)
        start = body.index("## User interaction")
        end = body.index("## Context pressure")
        cls.section = body[start:end]

    def test_states_failed_status_and_next_step(self):
        self.assertIn('"failed"', self.section)
        self.assertIn("/acs:create-ticket split", self.section)

    def test_summary_restates_the_instruction(self):
        self.assertIsNotNone(
            re.search(r"(?i)summary.{0,200}restate", self.section, re.DOTALL),
            "the split clause must state that <summary> restates the split "
            "instruction, not only <next-step>")

    def test_answer_recorded_via_clarify_add(self):
        """Assertion 13(a)."""
        self.assertIn("clarify.py add", self.section)

    def test_accept_one_large_pr_continues_planning(self):
        """Assertion 13(b)."""
        normalized = re.sub(r"\s+", " ", self.section)
        self.assertIsNotNone(
            re.search(r"(?i)accept one large PR.{0,200}continue planning",
                      normalized))

    def test_c9_stop_reason_verbatim(self):
        """Assertion 13(c)."""
        normalized = re.sub(r"\s+", " ", self.section)
        self.assertIn(C9_STOP_REASON, normalized)

    def test_finish_steps_run_before_handoff_returned(self):
        """Assertion 13(d)."""
        self.assertIsNotNone(
            re.search(r"(?i)Finish steps.{0,300}(before|then).{0,120}handoff",
                      self.section, re.DOTALL),
            "the split clause must state the mandatory Finish steps run "
            "before the handoff is returned")

    def test_status_attribute_not_only_result_json_field(self):
        self.assertIsNotNone(
            re.search(r"(?i)handoff.{0,40}status.{0,80}attribute", self.section,
                      re.DOTALL),
            "must distinguish the handoff element's own status attribute "
            "from result.json's field")

    def test_no_new_xml_element_or_status(self):
        normalized = re.sub(r"\s+", " ", self.section)
        self.assertIn("No new XML element and no new status value", normalized)


class CodeSkillFinishStep3BothSitesTest(unittest.TestCase):
    """Assertion 4 + 12 (R11): Finish step 3 carries the split exception at
    BOTH sub-sites — the direct-run summary line and the /ship sentence —
    asserted independently so a half-landed edit fails."""

    @classmethod
    def setUpClass(cls):
        body = read(CODE_SKILL)
        start = body.index("3. Report a compact summary")
        end = body.index("## Completion report")
        cls.step3 = body[start:end]
        direct_run, ship_part = cls.step3.split("Under /acs:ship", 1)
        cls.direct_run = direct_run
        cls.ship_part = ship_part

    def test_direct_run_sentence_carries_split_exception(self):
        self.assertIn("/acs:create-pr", self.direct_run)
        self.assertIn("create-ticket split", self.direct_run)

    def test_ship_sentence_carries_split_exception(self):
        self.assertIn("/acs:create-pr", self.ship_part)
        self.assertIn("create-ticket split", self.ship_part)


class SkillsReqOversizeClauseTest(unittest.TestCase):
    """Assertion 5: the requirements set's oversized-ticket clause no longer
    carries [OPEN], states the implemented mechanism AND the split-answer
    termination; the three fixture-pinned substrings still appear exactly
    once each across functional/non-functional."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILLS_REQ)
        start = cls.body.index("- MUST escalate an **oversized ticket**")
        end = cls.body.index("`/code`'s own obligations")
        cls.clause = cls.body[start:end]
        cls.tree_bodies = _req_tree_bodies()

    def test_open_tag_removed(self):
        self.assertNotIn("[OPEN]", self.clause)

    def test_states_implemented_mechanism(self):
        self.assertIn("ADR 0069", self.clause)

    def test_states_split_answer_termination(self):
        self.assertIn('"failed"', self.clause)
        self.assertIn("/acs:create-ticket split", self.clause)

    def test_pinned_clauses_survive_exactly_once(self):
        for clause in PINNED_CLAUSES:
            homes = [b for b in self.tree_bodies if clause in b]
            self.assertEqual(
                len(homes), 1,
                "fixture-pinned clause must appear in exactly one "
                "functional/non-functional file: %r (found in %d)" %
                (clause, len(homes)))


class InternalsSizingTodayTest(unittest.TestCase):
    """Assertion 6: INTERNALS.md 'Sizing today' states the implemented
    mechanism, and drops the follow-up-worthy-gap framing."""

    @classmethod
    def setUpClass(cls):
        body = read(INTERNALS)
        start = body.index("3. **Sizing today.**")
        end = body.index("The numbers are deliberate rules of thumb")
        cls.section = body[start:end]

    def test_no_longer_flags_a_gap(self):
        self.assertNotIn("follow-up-worthy mechanism gap", self.section)
        self.assertNotIn("There is currently no", self.section)

    def test_states_implemented_mechanism(self):
        self.assertIn("ADR 0069", self.section)
        self.assertIn("/acs:create-ticket split", self.section)


class RequirementsReadmeSizeControlRowTest(unittest.TestCase):
    """Assertion 7: the size-control decision-log row reflects the closure."""

    def test_row_reflects_closure(self):
        body = read(REQ_README)
        row = body[body.index("**Size control**"):]
        row = row[:row.index("|\n")]
        self.assertIn("ADR 0069", row)
        self.assertIn("code-planner.md", row)


class Adr0069RecordTest(unittest.TestCase):
    """Assertion 8: exactly one docs/adr/0069-*.md exists, is Accepted,
    records Decision 1's outcome, and has an index row."""

    def test_exactly_one_0069_file(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0069-*.md"))
        self.assertEqual(len(matches), 1,
                         "expected exactly one docs/adr/0069-*.md: %r" % matches)
        self.adr_path = matches[0]

    def test_adr_is_accepted_and_records_decision(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0069-*.md"))
        body = read(matches[0])
        self.assertIn("**Status**: Accepted", body)
        self.assertIn("two-lever", body.lower().replace("Two-lever", "two-lever"))
        self.assertIn("code-planner.md", body)

    def test_index_row_present(self):
        body = read(ADR_README)
        matches = glob.glob(os.path.join(ADR_DIR, "0069-*.md"))
        basename = os.path.basename(matches[0])
        self.assertIn("[0069](%s)" % basename, body)
        self.assertIn("Accepted", body[body.index("[0069]"):body.index("[0069]") + 300])


class NegativeGuardsTest(unittest.TestCase):
    """Assertion 9: no new create-spec token beyond the pre-existing
    provenance lines; no create-spec-triad token; no new settings key;
    ship/SKILL.md untouched."""

    def test_code_skill_create_spec_lines_unchanged(self):
        body = read(CODE_SKILL)
        lines = [ln for ln in body.splitlines() if "create-spec" in ln]
        self.assertEqual(len(lines), 2,
                         "code/SKILL.md must still carry exactly the two "
                         "pre-existing create-spec provenance lines: %r" % lines)

    def test_no_create_spec_triad_token(self):
        body = read(CODE_SKILL)
        for token in ("acs:create-spec-planner", "acs:create-spec-executor",
                      "acs:create-spec-verifier"):
            self.assertNotIn(token, body)

    def test_settings_schema_unchanged(self):
        body = read(SETTINGS_SCHEMA)
        self.assertNotIn("oversize", body)
        self.assertNotIn("split_threshold", body)

    def test_ship_skill_unchanged(self):
        body = read(SHIP_SKILL)
        self.assertNotIn("create-spec", body)
        self.assertNotIn("oversize", body.lower())


if __name__ == "__main__":
    unittest.main()
