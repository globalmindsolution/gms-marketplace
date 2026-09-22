"""Prose-contract tests for the epic-implementation boundary (MAR-75 slice 5).

Pins the surfaced, non-blocking, non-epic COMPLEX-lane breakdown
recommendation in code/SKILL.md's Start and escalation steps (S2, D7-C), and
the epic-conditional handoff routing in create-design/SKILL.md (S3, F6).
Doc-assertion tests that read the prose and assert the presence of normative
tokens — RED before the sections are added, GREEN after.
"""

import io
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
#: /acs:code's three conditional lane-change branches moved out of SKILL.md
#: into references/lane-changes.md under progressive disclosure -- they are
#: entered by few runs but were loaded on every one. The prose pinned below is
#: the same prose; only the file carrying it changed.
CODE_LANE_CHANGES = os.path.join(
    SKILLS_DIR, "code", "references", "lane-changes.md")
CREATE_DESIGN_SKILL = os.path.join(SKILLS_DIR, "create-design", "SKILL.md")

# The exact breakdown-command wording lives in acs_lib's _refuse_epic (T1,
# committed d7d345d) -- cross-consistency requires the SAME command string.
GATE_BREAKDOWN_COMMAND = "/acs:create-ticket %s (epic fan-out)"

# design.md:813-818 (D6-B) prescribes routing the user through
# /acs:create-design FIRST when the epic has no design yet, before the
# breakdown fan-out -- added in iteration 3 remediation of F-4.
GATE_DESIGN_FIRST_COMMAND = "/acs:create-design %s first if the epic has no design yet"


def _code_contract():
    """/acs:code's contract: the dispatcher, the four delivery-path legs, and
    the references they share.

    ADR-0095 split one 750-line body this way. These assertions pin what the
    SKILL SAYS, never which of its files says it, so reading the concatenation
    keeps the pin honest while the layout stays free to change -- and a rule
    that genuinely vanishes still fails.
    """
    import glob as _glob
    base = os.path.join(PLUGIN, "skills")
    parts = []
    for name in ("code", "code-trivial", "code-small", "code-standard", "code-complex"):
        path = os.path.join(base, name, "SKILL.md")
        if os.path.isfile(path):
            with io.open(path, encoding="utf-8") as fh:
                parts.append(fh.read())
    for path in sorted(_glob.glob(os.path.join(base, "code", "references", "*.md"))):
        with io.open(path, encoding="utf-8") as fh:
            parts.append(fh.read())
    return "\n".join(parts)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def code_contract():
    """/acs:code's full contract: SKILL.md plus its references/*.md.

    The escalation and de-escalation branches moved into
    references/lane-changes.md under progressive disclosure. Assertions about
    what the SKILL says — as opposed to which of its files says it — read
    both, so a later layout change cannot make a surviving rule look deleted.
    """
    return _code_contract() + "\n" + read(CODE_LANE_CHANGES)


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
    that constant against acs_lib's actual _refuse_epic source, so a drift in
    T1's message fails here loudly instead of silently desyncing the prose."""

    def test_the_refusal_contains_the_expected_breakdown_command(self):
        import inspect
        src = inspect.getsource(lib._refuse_epic)
        self.assertIn(
            GATE_BREAKDOWN_COMMAND, src,
            "acs_lib's _refuse_epic wording changed -- re-check this "
            "module's GATE_BREAKDOWN_COMMAND constant for drift")

    def test_the_refusal_routes_through_create_design_first(self):
        """F-4 (iteration 3 remediation): design.md:813-818 (D6-B) prescribes
        routing through /acs:create-design BEFORE the fan-out breakdown --
        the ordering clause must be present, and precede the fan-out
        command, not just co-occur with it."""
        import inspect
        src = inspect.getsource(lib._refuse_epic)
        self.assertIn(
            GATE_DESIGN_FIRST_COMMAND, src,
            "acs_lib's _refuse_epic must route the user through "
            "/acs:create-design first when the epic has no design yet")
        design_pos = src.index(GATE_DESIGN_FIRST_COMMAND)
        breakdown_pos = src.index(GATE_BREAKDOWN_COMMAND)
        self.assertLess(
            design_pos, breakdown_pos,
            "the create-design step must be ordered BEFORE the fan-out "
            "breakdown command in _refuse_epic's message, per design.md's "
            "prescribed ordering")
class NonEpicSectionDefenseInDepthTest(unittest.TestCase):
    """F-3: the contract states an absolute invariant ('ticket.type != "epic"')
    that is false on a best-effort pre-gate runtime; a defense-in-depth STOP
    instruction must follow it for the case where an epic reaches this step
    anyway.

    ADR-0095 moved this from the Start step's COMPLEX-breakdown subsection --
    which went with the lane machinery -- into the shared protocol every
    delivery-path leg reads. The invariant itself did not change, and it must
    not: it is the second brake behind the pre-hook's epic brake, and a leg that received an
    epic anyway has to refuse it rather than judge it onto a path."""

    def _section(self):
        return section(_code_contract(), "### Epics are never implemented", "## Branch")

    def test_invariant_sentence_still_present_verbatim(self):
        self.assertIn(
            'Every ticket that reaches this\nstep therefore has `ticket.type != "epic"`.',
            self._section(),
            "the existing invariant sentence must survive this ticket's "
            "insertion verbatim -- ADD the defense-in-depth instruction "
            "after it, never replace it")

    def test_defense_in_depth_stop_instruction_present(self):
        body_norm = norm(self._section())
        self.assertIsNotNone(
            re.search(
                r'(?i)if `ticket\.type == "epic"`.{0,60}nonetheless reaches '
                r'this step.{0,200}STOP immediately.{0,200}same breakdown '
                r'message.{0,60}gate.{0,60}would have raised',
                body_norm),
            "code/SKILL.md's Non-epic COMPLEX section must instruct the "
            "coordinator to STOP immediately and surface the same "
            "breakdown message the epic brake would have raised, if an epic "
            "nonetheless reaches this step")

    def test_defense_in_depth_never_implement_epic_clause_present(self):
        body_norm = norm(self._section())
        self.assertIsNotNone(
            re.search(r"(?i)never implement an epic under any circumstance",
                      body_norm),
            "code/SKILL.md's defense-in-depth instruction must state an "
            "epic is never implemented under any circumstance, regardless "
            "of the pre-gate's enforcement")

    def test_defense_in_depth_instruction_follows_invariant_sentence(self):
        body = self._section()
        invariant_pos = body.index('ticket.type != "epic"')
        stop_pos = body.index("STOP immediately")
        self.assertGreater(
            stop_pos, invariant_pos,
            "the defense-in-depth STOP instruction must be inserted AFTER "
            "the existing invariant sentence, not before or in place of it")
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
        # A handoff carries at most one <next-step>; guard against a literal
        # second element sneaking into the prose as a copy-paste artifact
        # within the /acs:ship handoff bullet specifically (the file has an
        # unrelated <next-step> example elsewhere, in the needs_input block).
        body = self._body()
        ship_bullet_start = body.index("Under /acs:ship")
        ship_bullet_end = body.index("## Completion report", ship_bullet_start)
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
    """Cross-consistency: the literal breakdown command named in acs_lib's
    _refuse_epic message also appears in create-design/SKILL.md's epic branch
    (T1 + T2 must route the user to the same place)."""

    def test_same_breakdown_command_string(self):
        import inspect
        gate_src = norm(inspect.getsource(lib._refuse_epic))
        design_body = norm(read(CREATE_DESIGN_SKILL))
        self.assertIn(
            GATE_BREAKDOWN_COMMAND, gate_src,
            "sanity check: _refuse_epic's own message wording")
        self.assertIsNotNone(
            re.search(r"/acs:create-ticket <(id|ticket-id)>`? \(epic fan-out\)",
                      design_body),
            "create-design/SKILL.md must name the SAME breakdown command "
            "(/acs:create-ticket <epic-id>, epic fan-out) that gate_code's "
            "GateError message names")

    def test_the_refusal_orders_create_design_before_fan_out(self):
        """F-4 (iteration 3 remediation): gate_code's own message must place
        the /acs:create-design step before the fan-out breakdown command,
        per design.md:813-818's (D6-B) prescribed ordering."""
        import inspect
        gate_src = inspect.getsource(lib._refuse_epic)
        self.assertIn(GATE_DESIGN_FIRST_COMMAND, gate_src)
        self.assertLess(
            gate_src.index(GATE_DESIGN_FIRST_COMMAND),
            gate_src.index(GATE_BREAKDOWN_COMMAND),
            "gate_code's message must route through /acs:create-design "
            "before the /acs:create-ticket fan-out step")


if __name__ == "__main__":
    unittest.main()
