"""Prose-contract tests for the epic-implementation boundary (MAR-75 slice 5).

Pins the surfaced, non-blocking, non-epic COMPLEX-lane breakdown
recommendation in code/SKILL.md's Start and escalation steps (S2, D7-C), and
the epic-conditional handoff routing in create-design/SKILL.md (S3, F6).
Doc-assertion tests that read the prose and assert the presence of normative
tokens — RED before the sections are added, GREEN after.
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
HOOKS_SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

sys.path.insert(0, HOOKS_SCRIPTS)
import acs_lib as lib  # noqa: E402

CODE_SKILL = os.path.join(SKILLS_DIR, "code", "SKILL.md")
CREATE_DESIGN_SKILL = os.path.join(SKILLS_DIR, "create-design", "SKILL.md")

# The exact breakdown-command wording landed in acs_lib.py's gate_code (T1,
# committed d7d345d) -- cross-consistency requires the SAME command string.
GATE_BREAKDOWN_COMMAND = "/acs:create-ticket %s (epic fan-out)"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    """Collapse whitespace runs (incl. newlines) to a single space, so a
    phrase-spanning check can't fail solely because markdown word-wrap
    happened to insert a line break between two words."""
    return re.sub(r"\s+", " ", text)


def section(body, start_heading, end_heading):
    """Slice body between two literal heading lines (start inclusive, end
    exclusive). Used to anchor assertions to one subsection instead of the
    whole file, so an unrelated edit elsewhere can't spuriously satisfy them."""
    start = body.index(start_heading)
    end = body.index(end_heading, start)
    return body[start:end]


class GateMessageWordingTest(unittest.TestCase):
    """GATE_BREAKDOWN_COMMAND is defined once at module level and reused by
    every assertion site below (not hand-copied per site); this test asserts
    that constant against acs_lib.py's actual gate_code source, so a drift in
    T1's message fails here loudly instead of silently desyncing the prose."""

    def test_gate_code_message_contains_expected_breakdown_command(self):
        import inspect
        src = inspect.getsource(lib.gate_code)
        self.assertIn(
            GATE_BREAKDOWN_COMMAND, src,
            "acs_lib.py's gate_code message wording changed -- re-check this "
            "module's GATE_BREAKDOWN_COMMAND constant for drift")


class StartStepBreakdownRecommendationTest(unittest.TestCase):
    """AC-2: code/SKILL.md's Start step surfaces the non-epic COMPLEX
    breakdown recommendation."""

    def _start_section(self):
        body = read(CODE_SKILL)
        return section(body, "## Start", "## Branch")

    def test_start_step_names_size_large_and_complex_lane(self):
        body_norm = norm(self._start_section())
        self.assertIsNotNone(
            re.search(r"(?i)size.{0,20}large.{0,40}complex", body_norm),
            "code/SKILL.md's Start step must name the size:large -> lane "
            "COMPLEX reading of the breakdown recommendation")

    def test_start_step_states_run_continues(self):
        body = self._start_section()
        self.assertIsNotNone(
            re.search(r"(?i)continue the run", body),
            "code/SKILL.md's Start step must state the run continues after "
            "the breakdown recommendation is surfaced")

    def test_start_step_states_surfaced_not_blocking(self):
        body = self._start_section()
        self.assertIsNotNone(
            re.search(r"(?i)surface.{0,20}—.{0,10}never block|never block", body),
            "code/SKILL.md's Start step must state the recommendation is "
            "surfaced, never blocking")

    def test_start_step_recomputes_derive_lane_not_cached_lane(self):
        body = self._start_section()
        self.assertIn(
            "derive_lane", body,
            "code/SKILL.md's Start step must name derive_lane as the "
            "recomputed predicate")
        self.assertIsNotNone(
            re.search(r"(?i)recompute", body),
            "code/SKILL.md's Start step must state derive_lane is "
            "RECOMPUTED, not read from the cache (NFR-S4)")
        self.assertIsNotNone(
            re.search(r"(?i)never read the cached|never.{0,20}ticket\.lane", body),
            "code/SKILL.md's Start step must state the cached ticket.lane "
            "must never be trusted (NFR-S4)")


class EscalationStepBreakdownRecommendationTest(unittest.TestCase):
    """AC-2: the same signal fires in the in-loop escalation step on a
    mid-flight escalate_lane raise to COMPLEX for a non-epic ticket."""

    def _escalation_section(self):
        body = read(CODE_SKILL)
        return section(
            body,
            "### In-loop escalation check (upward-only, MAR-57)",
            "### Boundary-only user-confirmed de-escalation (D3)")

    def test_escalation_section_contains_breakdown_recommendation(self):
        body_norm = norm(self._escalation_section())
        self.assertIsNotNone(
            re.search(r"(?i)complex.{0,80}breakdown|breakdown.{0,80}complex",
                      body_norm),
            "code/SKILL.md's escalation section must carry the same "
            "COMPLEX breakdown recommendation for a mid-flight raise")

    def test_escalation_recommendation_appears_after_absent_signals_block(self):
        body = self._escalation_section()
        absent_pos = body.index("Absent or ambiguous signals")
        rec_pos = body.index("breakdown recommendation", absent_pos)
        self.assertGreater(
            rec_pos, absent_pos,
            "the new breakdown-recommendation subsection must be inserted "
            "AFTER the 'Absent or ambiguous signals' block (end of the "
            "escalation section), never in the middle")

    def test_escalation_recommendation_not_inserted_between_detection_point_and_no_restart(self):
        """Regression guard mirroring test_skill_contracts.py's
        test_d4_no_restart_guarantee_anchored_near_detection_point: this
        module's own insertion must not have pushed the no-restart phrase
        outside 400 chars of 'detection point'."""
        body = read(CODE_SKILL)
        self.assertIsNotNone(
            re.search(
                r"(?i)detection point.{0,400}(no.restart|without restart|"
                r"without discard|completed work)|"
                r"(no.restart|without restart|without discard|completed work)"
                r".{0,400}detection point",
                body, re.DOTALL),
            "the no-restart guarantee must stay within 400 chars of the "
            "'detection point' label after this ticket's insertion")


class NoFourthTriggerNegativeGuardTest(unittest.TestCase):
    """AC-2 negative guard: the recommendation is a report attached to the
    existing trigger sequence's outcome, not a new (d) trigger, and it
    describes no automatic de-escalation."""

    def _body(self):
        return read(CODE_SKILL)

    def test_frozen_three_trigger_sentence_still_present_verbatim(self):
        self.assertIn(
            "Three triggers (exactly; no others) — evaluated on the FIRST "
            "signal, immediately.",
            self._body(),
            "the frozen three-trigger sentence must survive this ticket's "
            "insertion verbatim")

    def test_no_fourth_trigger_label_introduced(self):
        body = self._body()
        self.assertNotRegex(
            body, r"\(d\)\s",
            "code/SKILL.md must not introduce a fourth escalation trigger "
            "labeled (d)")

    def test_no_new_deterministic_helper_or_settings_key(self):
        body = self._body()
        self.assertNotIn(
            "recommend_size", body,
            "code/SKILL.md must not introduce a recommend_size-style "
            "deterministic helper (frozen trigger set)")

    def test_no_automatic_deescalation_language_introduced(self):
        body = self._body()
        matches = list(re.finditer(
            r"(?i)(automatic(ally)?.{0,50}(lower.{0,20}lane|de.escalat|"
            r"downgrad)|(lower.{0,20}lane|de.escalat|downgrad).{0,50}"
            r"automatic)",
            body))
        for m in matches:
            surrounding = body[max(0, m.start() - 30):m.end() + 10]
            self.assertIsNotNone(
                re.search(r"(?i)(never|not|no |cannot|must not|does not)",
                          surrounding),
                "code/SKILL.md must not describe automatic de-escalation "
                "outside of a negating context. Found: %r" % m.group(0))


class CompletionReportSurfacesRecommendationTest(unittest.TestCase):
    """Ledger C-3: the surfaced escalation must ALSO appear in code/SKILL.md's
    Completion report template -- an internal-step-only signal is not
    'surfaced' per design.md's own D7-C rationale."""

    def _completion_report_section(self):
        body = read(CODE_SKILL)
        start = body.index("## Completion report (normative)")
        return body[start:]

    def test_completion_report_mentions_breakdown_recommendation(self):
        body = self._completion_report_section()
        self.assertIsNotNone(
            re.search(r"(?i)breakdown recommendation", body),
            "code/SKILL.md's Completion report section must mention the "
            "breakdown recommendation (ledger C-3)")

    def test_completion_report_ties_recommendation_to_findings_line(self):
        body = self._completion_report_section()
        self.assertIsNotNone(
            re.search(r"(?i)breakdown recommendation.{0,200}\*\*Findings\*\*|"
                      r"\*\*Findings\*\*.{0,200}breakdown recommendation",
                      body, re.DOTALL),
            "code/SKILL.md must tie the surfaced breakdown recommendation to "
            "the Findings line of the Completion report (ledger C-3)")


class CreateDesignEpicConditionalHandoffTest(unittest.TestCase):
    """AC-4: all three unconditional /acs:code <id> routing sites in
    create-design/SKILL.md become epic-conditional (F6 + the third site at
    the normative Completion report's Next line, ledger C-2)."""

    def _body(self):
        return read(CREATE_DESIGN_SKILL)

    def test_direct_invocation_report_branch_is_epic_conditional(self):
        body_norm = norm(self._body())
        self.assertIsNotNone(
            re.search(r"(?i)for a non-epic ticket.{0,30}/acs:code <id>.{0,60}"
                      r"for an epic.{0,300}/acs:create-ticket <id>.{0,60}"
                      r"epic fan-out.{0,120}/acs:code.{0,20}child", body_norm),
            "create-design/SKILL.md's direct-invocation report branch "
            "(~:333-334) must be epic-conditional: non-epic -> /acs:code "
            "<id>; epic -> break it down via /acs:create-ticket <id> "
            "(epic fan-out), then /acs:code on a child")

    def test_handoff_next_step_is_epic_conditional_single_element(self):
        body_norm = norm(self._body())
        self.assertIsNotNone(
            re.search(r"(?i)exactly one `<next-step>`.{0,400}/acs:code <id>"
                      r".{0,60}for a non-epic ticket.{0,120}for an epic"
                      r".{0,300}/acs:create-ticket <id>.{0,60}epic fan-out",
                      body_norm),
            "create-design/SKILL.md's <handoff> next-step instruction "
            "(~:337) must be epic-conditional while staying a single "
            "<next-step> element")
        # The XSD allows at most one <next-step>; guard against a literal
        # second element sneaking into the prose as a copy-paste artifact
        # within the /acs:ship handoff bullet specifically (the file has an
        # unrelated <next-step> example elsewhere, in the needs_input XML).
        body = self._body()
        ship_bullet_start = body.index("Under /acs:ship")
        ship_bullet_end = body.index("Validate it with validate_xml.py",
                                      ship_bullet_start)
        ship_bullet = body[ship_bullet_start:ship_bullet_end]
        self.assertEqual(
            ship_bullet.count("<next-step>"), 1,
            "create-design/SKILL.md's /acs:ship handoff bullet must embed "
            "exactly one <next-step> opening tag -- the conditional is an "
            "instruction about which value to emit, not two XML elements")

    def test_completion_report_next_line_is_epic_conditional(self):
        body = self._body()
        start = body.index("## Completion report (normative)")
        report = body[start:]
        report_norm = norm(report)
        self.assertIsNotNone(
            re.search(r"(?i)\*\*Next\*\*.{0,40}/acs:code <ticket-id>.{0,60}"
                      r"for a non-epic ticket.{0,120}for an epic.{0,300}"
                      r"/acs:create-ticket <ticket-id>.{0,60}epic fan-out",
                      report_norm),
            "create-design/SKILL.md's normative Completion report Next line "
            "(~:356) must be epic-conditional")

    def test_epic_branch_never_routes_code_directly_at_epic_id(self):
        """The epic branch must route via the breakdown command, never
        directly at /acs:code <epic-id> (the exact refusal T1's gate now
        raises on)."""
        body = self._body()
        self.assertNotRegex(
            norm(body),
            r"for an epic.{0,20}/acs:code <id>(?!.{0,10}on)",
            "create-design/SKILL.md's epic branch must not route directly "
            "to /acs:code <id> -- it must break the ticket down first")


class GateAndCreateDesignSameBreakdownCommandTest(unittest.TestCase):
    """Cross-consistency: the literal breakdown command named in acs_lib.py's
    gate_code message also appears in create-design/SKILL.md's epic branch
    (T1 + T2 must route the user to the same place)."""

    def test_same_breakdown_command_string(self):
        import inspect
        gate_src = norm(inspect.getsource(lib.gate_code))
        design_body = norm(read(CREATE_DESIGN_SKILL))
        self.assertIn(
            GATE_BREAKDOWN_COMMAND, gate_src,
            "sanity check: gate_code's own message wording")
        self.assertIsNotNone(
            re.search(r"/acs:create-ticket <(id|ticket-id)>`? \(epic fan-out\)",
                      design_body),
            "create-design/SKILL.md must name the SAME breakdown command "
            "(/acs:create-ticket <epic-id>, epic fan-out) that gate_code's "
            "GateError message names")


if __name__ == "__main__":
    unittest.main()
