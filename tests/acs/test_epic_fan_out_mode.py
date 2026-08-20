"""MAR-78 — epic fan-out moves to /acs:create-ticket --fan-out, run after
create-design (slice 8).

Covers AC-1 (a new `--fan-out` mode that runs Step 4, and only Step 4,
against an existing epic, reusing Step 2 item 7's confirmation gate), AC-2
(Step 4 no longer fans out unconditionally at epic-creation time), AC-3 (the
Step-4 self-contradiction, F4/DRIFT-4, is resolved to match shipped
behavior), AC-4 (new-ticket.py's stale /create-spec comment, F5/DRIFT-3, is
corrected to name /acs:code), and AC-5 (an existing epic with an approved
design.md fans out children derived from the design's own slice/seam
content).

Prose-contract cases are section-scoped (never file-wide assertIn) so an
unrelated edit elsewhere in a touched file cannot make one spuriously pass or
fail. Behavior cases drive the real CLIs via acs_case.AcsWorkspaceCase.

Stdlib + acs_case, in the style of tests/acs/test_planning_skills_registry.py.

Run:
  python3 -m unittest tests.acs.test_epic_fan_out_mode -v
"""

import json
import os
import re
import sys
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_ACS))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
AGENTS_DIR = os.path.join(PLUGIN, "agents")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")

sys.path.insert(0, TESTS_ACS)
sys.path.insert(0, HOOKS_DIR)

import acs_case  # noqa: E402
import acs_lib as lib  # noqa: E402

CREATE_TICKET_SKILL = os.path.join(SKILLS_DIR, "create-ticket", "SKILL.md")
SHIP_SKILL = os.path.join(SKILLS_DIR, "ship", "SKILL.md")
CREATE_TICKET_EXECUTOR = os.path.join(AGENTS_DIR, "create-ticket-executor.md")
NEW_TICKET_PY = os.path.join(HOOKS_DIR, "new-ticket.py")

REPO_ID = "acme-shop"

FAN_OUT_HEADING = "## Epic fan-out mode (`--fan-out`)"
STEP4_HEADING = "### Step 4 — Epic fan-out via new-ticket.py"
STEP5_HEADING = "### Step 5 — Tracker sync"
SHIP_FAN_OUT_HEADING = "## Epic fan-out"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    """Collapse whitespace runs to a single space, so a phrase-spanning
    check can't fail solely because markdown word-wrap inserted a line
    break between two words."""
    return re.sub(r"\s+", " ", text)


def _section(body, heading):
    """Extract the section starting at `heading` up to (not including) the
    next heading of the same or a shallower level. Mirrors
    tests/acs/test_planning_skills_registry.py's helper."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading not found: %r" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def fan_out_section():
    return _section(read(CREATE_TICKET_SKILL), FAN_OUT_HEADING)


def step4_section():
    return _section(read(CREATE_TICKET_SKILL), STEP4_HEADING)


def step5_section():
    return _section(read(CREATE_TICKET_SKILL), STEP5_HEADING)


def ship_fan_out_section():
    return _section(read(SHIP_SKILL), SHIP_FAN_OUT_HEADING)


def executor_step4_section():
    body = read(CREATE_TICKET_EXECUTOR)
    start = body.index("4. **Epic fan-out**")
    end = body.index("5. **Tracker sync**")
    return body[start:end]


class FanOutSectionExistsAndNamesTheFlagCase(unittest.TestCase):
    """AC-1: a `##` section documents the mode and names the invocation."""

    def test_fan_out_section_documents_the_flag(self):
        section = fan_out_section()
        self.assertIn("/acs:create-ticket <epic-id> --fan-out", norm(section))


class FanOutStartResolvesExistingPartitionWithoutAllocateCase(unittest.TestCase):
    """AC-1: Start uses skill-start.py --skill create-ticket --ticket, and
    the shown command never carries --allocate (id-burn guard,
    skill-start.py:132-144) -- checked on the actual command line, not on
    whether the section discusses --allocate in prose (the split mode above
    legitimately says "no --allocate" in words)."""

    def test_fan_out_start_resolves_existing_partition_without_allocate(self):
        section = fan_out_section()
        m = re.search(r"skill-start\.py[^\n`]*", section)
        self.assertIsNotNone(m, "section must show the skill-start.py command")
        cmd = norm(m.group(0))
        self.assertIn("--skill create-ticket", cmd)
        self.assertIn("--ticket", cmd)
        self.assertNotIn("--allocate", cmd)


class FanOutReusesStepTwoConfirmationGateCase(unittest.TestCase):
    """AC-1: the section points at Step 2's gate and states no child is
    minted before confirmation."""

    def test_fan_out_reuses_step_2_confirmation_gate(self):
        section_norm = norm(fan_out_section())
        self.assertIsNotNone(
            re.search(r"(?i)Step 2.{0,120}confirm|confirm.{0,120}Step 2", section_norm),
            "section must co-locate a Step 2 reference with 'confirm'")
        self.assertIsNotNone(
            re.search(r"(?i)no child is minted before|before any child is minted",
                      section_norm),
            "section must state no child is minted before user confirmation")


class FanOutRunsStepFourOnlyCase(unittest.TestCase):
    """AC-1: the section names Step 4 and states Steps 1-3 are not re-run."""

    def test_fan_out_runs_step_4_only_not_steps_1_to_3(self):
        section_norm = norm(fan_out_section())
        self.assertIn("Step 4", section_norm)
        self.assertIsNotNone(
            re.search(r"(?i)Steps 1-3 do NOT run|Steps 1-3 are not re-run", section_norm),
            "section must state Steps 1-3 do not re-run in this mode")
        self.assertIsNotNone(
            re.search(r"(?i)not re-analyzed or rewritten", section_norm),
            "section must state the epic's own ticket.json is not rewritten")


class FanOutRefusesNonEpicTargetCase(unittest.TestCase):
    """AC-1: the section states the mode applies to epics only."""

    def test_fan_out_refuses_a_non_epic_target(self):
        section_norm = norm(fan_out_section())
        self.assertIsNotNone(
            re.search(r"(?i)--fan-out.{0,60}applies to epics only|"
                      r"applies to epics only", section_norm),
            "section must state --fan-out applies to epics only")


class FanOutBreakdownDerivesFromDesignSlicesCase(unittest.TestCase):
    """AC-5: the section co-locates design.md with slice/seam content."""

    def test_fan_out_breakdown_derives_from_the_design_slices(self):
        section_norm = norm(fan_out_section())
        self.assertIsNotNone(
            re.search(r"(?i)design\.md.{0,200}(slice|seam)|(slice|seam).{0,200}design\.md",
                      section_norm),
            "section must co-locate design.md with slice/seam content")


class FanOutSyncSetExcludesAlreadySyncedTicketsCase(unittest.TestCase):
    """AC-1: Step 5's sync-set clause excludes a ticket whose external is
    already non-null (duplicate-issue guard, MAR-69 precedent #354/#355-363)."""

    def test_fan_out_sync_set_excludes_already_synced_tickets(self):
        section_norm = norm(step5_section())
        self.assertIsNotNone(
            re.search(r"(?i)external.{0,120}non-null.{0,200}exclud|"
                      r"exclud.{0,200}external.{0,120}non-null", section_norm),
            "Step 5 must state a ticket whose external is already non-null "
            "is excluded from the sync set")


class StepFourDeferredOutOfEpicCreationRunCase(unittest.TestCase):
    """AC-2: Step 4's own section states it does not run at epic-creation
    time and names --fan-out as the deferral target."""

    def test_step_4_is_deferred_out_of_the_epic_creation_run(self):
        section_norm = norm(step4_section())
        self.assertIsNotNone(
            re.search(r"(?i)ONLY under `?--fan-out`? mode|runs ONLY.{0,20}--fan-out",
                      section_norm),
            "Step 4 must state it runs only under --fan-out mode")
        self.assertIsNotNone(
            re.search(r"(?i)never (at|during) the epic's own creation", section_norm),
            "Step 4 must state it never runs at epic-creation time")


class ShipEpicFanOutStepNamesTheFlagCase(unittest.TestCase):
    """AC-2: ship/SKILL.md's Epic fan-out section names --fan-out."""

    def test_ship_epic_fan_out_step_names_the_flag(self):
        self.assertIn("--fan-out", ship_fan_out_section())


class StepFourChildReconfirmationContradictionIsGoneCase(unittest.TestCase):
    """AC-3: the F4 self-contradiction is resolved -- the reconfirmation
    clause is gone, and the positive replacement (single confirmation point,
    plus the surviving "their pipeline starts at /acs:code" phrase) is
    present."""

    def test_step_4_child_reconfirmation_contradiction_is_gone(self):
        section_norm = norm(step4_section())
        self.assertIsNone(
            re.search(r"confirmed individually when their own\s+"
                      r"`/acs:create-ticket`\s+runs", section_norm),
            "Step 4 must no longer claim children are confirmed "
            "individually when their own /acs:create-ticket runs")
        self.assertIn("their pipeline starts at /acs:code", section_norm)
        self.assertIsNotNone(
            re.search(r"(?i)confirmed ONCE|confirmed once", section_norm),
            "Step 4 must name the single confirmation point")


class ExecutorContractIsFanOutModeAwareCase(unittest.TestCase):
    """AC-1: create-ticket-executor.md states that in fan-out mode only
    steps 4-5 run (step 3's root rewrite is skipped)."""

    def test_executor_contract_is_fan_out_mode_aware(self):
        section_norm = norm(executor_step4_section())
        self.assertIsNotNone(
            re.search(r"(?i)ONLY in `?--fan-out`? mode|runs ONLY.{0,20}--fan-out",
                      section_norm),
            "executor step 4 must state it runs only in --fan-out mode")
        self.assertIsNotNone(
            re.search(r"(?i)step 3.{0,80}skipped", section_norm),
            "executor step 4 must state step 3's root rewrite is skipped "
            "in that mode")


class NewTicketChildPipelineCommentNamesCodeCase(unittest.TestCase):
    """AC-4: new-ticket.py carries no create-spec token, and its
    child-pipeline comment names /acs:code as the positive replacement."""

    def test_new_ticket_child_pipeline_comment_names_code_not_create_spec(self):
        body = read(NEW_TICKET_PY)
        self.assertNotIn("create-spec", body)
        body_norm = norm(body)
        self.assertIsNotNone(
            re.search(r"(?i)pipeline starts at.{0,40}/acs:code", body_norm),
            "new-ticket.py's child-pipeline comment must name /acs:code")


class SecondCreateTicketRunOnAnExistingEpicCase(acs_case.AcsWorkspaceCase):
    """AC-1: the fan-out mode's own Start command (skill-start.py --skill
    create-ticket --ticket <epic>, no --allocate) resolves the existing
    epic -- allocates no new id, mints no new partition."""

    def test_second_create_ticket_run_on_an_existing_epic_allocates_no_new_id(self):
        epic = self.new_ticket("Wishlist epic", "epic")
        index_before = lib.read_json(lib.index_path(self.ws, REPO_ID))
        ids_before = set((index_before or {}).get("tickets", {}).keys())

        result = self.start("create-ticket", epic)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["ticket_id"], epic)
        self.assertEqual(payload["ticket"]["type"], "epic")

        index_after = lib.read_json(lib.index_path(self.ws, REPO_ID))
        ids_after = set((index_after or {}).get("tickets", {}).keys())
        self.assertEqual(ids_after, ids_before)


class FannedOutChildNeverRerunsCreateTicketCase(acs_case.AcsWorkspaceCase):
    """AC-3, executable half: a child minted via new-ticket.py --parent has
    a completed create-ticket run recorded for it -- it never reruns
    /acs:create-ticket itself."""

    def test_fanned_out_child_never_reruns_create_ticket(self):
        epic = self.new_ticket("Wishlist epic", "epic")
        child = self.new_ticket("Wishlist API", "story", "--parent", epic,
                                 "--needs-design", "false")
        child_tdir = self.tdir(child)
        self.assertTrue(lib.skill_completed(child_tdir, "create-ticket"))


class FanOutRunLeavesEpicCreateTicketStepCompletedCase(acs_case.AcsWorkspaceCase):
    """AC-1: after a second skill-start + post-create-ticket.py cycle on the
    epic (the fan-out run), skill_completed(epic_tdir, "create-ticket") is
    still True -- _require_completed consumers such as gate_create_design
    keep passing."""

    def test_fan_out_run_leaves_the_epic_create_ticket_step_completed(self):
        epic = self.new_ticket("Wishlist epic", "epic")
        epic_tdir = self.tdir(epic)

        start = self.start("create-ticket", epic)
        self.assertEqual(start.returncode, 0, start.stderr)

        post = self.post("create-ticket", epic, {
            "status": "completed",
            "stop_reason": "fan-out run: no new children confirmed",
            "states": {
                "ticket_id": epic, "type": "epic", "needs_design": True,
                "children": [], "prd_trace": {"feature": None, "divergence": None},
            },
        })
        self.assertEqual(post.returncode, 0, post.stderr)
        self.assertTrue(lib.skill_completed(epic_tdir, "create-ticket"))


if __name__ == "__main__":
    unittest.main()
