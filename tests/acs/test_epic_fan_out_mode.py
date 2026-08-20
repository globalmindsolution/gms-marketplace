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
STEP1_HEADING = "### Step 1 — Analyze and recommend fields"
STEP2_HEADING = "### Step 2 — User-confirmation gate (human-in-the-loop checkpoint)"
STEP3_HEADING = "### Step 3 — Rewrite ticket.json"
STEP4_HEADING = "### Step 4 — Epic fan-out via new-ticket.py"
STEP5_HEADING = "### Step 5 — Tracker sync"
FINISH_HEADING = "## Finish"
SHIP_FAN_OUT_HEADING = "## Epic fan-out"
SPLIT_HEADING = "## Splitting an existing oversized ticket"
RESUME_HEADING = "## Resume & reconcile"


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


def step1_section():
    return _section(read(CREATE_TICKET_SKILL), STEP1_HEADING)


def step2_section():
    return _section(read(CREATE_TICKET_SKILL), STEP2_HEADING)


def step3_section():
    return _section(read(CREATE_TICKET_SKILL), STEP3_HEADING)


def finish_section():
    return _section(read(CREATE_TICKET_SKILL), FINISH_HEADING)


def split_section():
    body = read(CREATE_TICKET_SKILL)
    start = body.index(SPLIT_HEADING)
    end = body.index(RESUME_HEADING)
    return body[start:end]


def ship_fan_out_section():
    return _section(read(SHIP_SKILL), SHIP_FAN_OUT_HEADING)


def executor_step4_section():
    body = read(CREATE_TICKET_EXECUTOR)
    start = body.index("4. **Epic fan-out**")
    end = body.index("5. **Tracker sync**")
    return body[start:end]


def executor_step3_section():
    body = read(CREATE_TICKET_EXECUTOR)
    start = body.index("3. **Rewrite")
    end = body.index("4. **Epic fan-out**")
    return body[start:end]


def executor_step5_section():
    body = read(CREATE_TICKET_EXECUTOR)
    start = body.index("5. **Tracker sync**")
    end = body.index("6. **Write the execute report**")
    return body[start:end]


def executor_hard_rules_section():
    return _section(read(CREATE_TICKET_EXECUTOR), "## Hard rules")


def executor_output_contract_section():
    return _section(read(CREATE_TICKET_EXECUTOR), "## Output contract")


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
    """AC-1/F2-a: Step 5's sync-set clause excludes a ticket whose external
    is already non-null (duplicate-issue guard, MAR-69 precedent
    #354/#355-363), in BOTH create-ticket/SKILL.md and
    create-ticket-executor.md -- widened from a SKILL.md-only check to the
    MAR-84 both-files-in-one-loop pattern (test_skill_contracts.py:2982-3040)
    so a one-sided mirror edit fails by construction."""

    def test_sync_set_excludes_already_synced_tickets_in_both_files(self):
        sections = {
            "SKILL.md Step 5": norm(step5_section()),
            "executor step 5": norm(executor_step5_section()),
        }
        for name, section_norm in sections.items():
            self.assertIsNotNone(
                re.search(r"(?i)external.{0,120}non-null.{0,200}exclud|"
                          r"exclud.{0,200}external.{0,120}non-null", section_norm),
                "%s must state a ticket whose external is already non-null "
                "is excluded from the sync set" % name)


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


# --------------------------------------------------------------------- G1-G7
# F1: the creation-run flow no longer describes a breakdown+confirm+mint at
# epic-creation time -- each site scoped by MODE, never by lane.

class StepOneChildBreakdownBulletIsScopedToFanOutRunCase(unittest.TestCase):
    """F1-a: Step 1's epic child-breakdown bullet states the breakdown is
    produced only in a --fan-out (or split/restructure) run, and an epic's
    own creation run ends with children: []."""

    def test_step_1_child_breakdown_bullet_is_scoped_to_the_fan_out_run(self):
        section_norm = norm(step1_section())
        idx = section_norm.index(
            "For epics: proposed child story/task breakdown")
        tail = section_norm[idx:idx + 600]
        self.assertIn("only in a `--fan-out` run", tail)
        self.assertIn("split/restructure run", tail)
        self.assertIn("children: []", tail)


class StepTwoChildBreakdownConfirmationIsScopedByModeNotLaneCase(unittest.TestCase):
    """F1-b/F1-c: Step 2 item 7's sentence stays byte-intact (the fan-out
    section quotes it verbatim) and gains a mode-scoping clause; the
    over-correction guard (MAR-55 invariant (c), "NOT skipped in any lane")
    must survive untouched -- scoping is by MODE, never by LANE."""

    def test_step_2_child_breakdown_confirmation_is_scoped_by_mode_not_lane(self):
        section_norm = norm(step2_section())
        idx = section_norm.index(
            "present the proposed child breakdown and obtain user "
            "confirmation or edits before any child is minted.")
        tail = section_norm[idx:idx + 300]
        self.assertIsNotNone(
            re.search(r"(?i)only in the `?--fan-out`? mode or a "
                      r"split/restructure run", tail),
            "item 7 must state it is reached only in the --fan-out mode "
            "or a split/restructure run")
        self.assertIn("NOT skipped in any lane", section_norm)


class FanOutSectionQuotesStepTwoItemSevenVerbatimCase(unittest.TestCase):
    """F1-c structural pin: the fan-out section's double-quoted Confirmation
    gate text, once markdown emphasis (**) is stripped, is a substring of
    Step 2's own section -- any future edit to item 7 that forgets to keep
    the fan-out section's quote in sync fails here."""

    def test_fan_out_section_quotes_step_2_item_7_verbatim(self):
        section = fan_out_section()
        quotes = re.findall(r'"([^"]+)"', section)
        candidates = [q for q in quotes if "Epic only" in q]
        self.assertTrue(
            candidates,
            "fan-out section must quote Step 2 item 7 in double quotes")
        quoted = norm(candidates[0])
        step2_plain = norm(step2_section()).replace("**", "")
        self.assertIn(quoted, step2_plain)


class ChildrenFieldStatesTheEmptyCreationRunInvariantInBothFilesCase(unittest.TestCase):
    """F1-d/F1-e: Step 3's (and the executor's mirror step 3's) `children`
    field description states [] on every creation run, including an epic's
    own, and names Step 4 / --fan-out as the later filler."""

    def test_children_field_states_the_empty_creation_run_invariant_in_both_files(self):
        sections = {
            "SKILL.md Step 3": norm(step3_section()),
            "executor step 3": norm(executor_step3_section()),
        }
        for name, section_norm in sections.items():
            self.assertIsNotNone(
                re.search(r"(?i)children.{0,40}`\[\]`.{0,200}every creation run",
                          section_norm),
                "%s must state children is [] on every creation run" % name)
            self.assertIsNotNone(
                re.search(r"(?i)step 4.{0,80}--fan-out|--fan-out.{0,80}step 4",
                          section_norm),
                "%s must name Step 4 / --fan-out as the later filler" % name)


class FinishResultExampleIsAnEpicCreationRunWithNoChildrenCase(unittest.TestCase):
    """F1-f: the Finish result.json example is an epic CREATION run
    (children: [], stop_reason names the deferral), parsed with json.loads
    -- non-vacuous by construction, unlike a regex over the fenced block."""

    def test_finish_result_example_is_an_epic_creation_run_with_no_children(self):
        section = finish_section()
        m = re.search(r"```json\s*(\{.*?\})\s*```", section, re.S)
        self.assertIsNotNone(m, "Finish section must contain a fenced JSON example")
        payload = json.loads(m.group(1))
        self.assertEqual(payload["states"]["type"], "epic")
        self.assertEqual(payload["states"]["children"], [])
        section_norm = norm(section)
        self.assertIsNotNone(
            re.search(r"(?i)children.{0,40}`\[\]`.{0,200}epic's own creation run",
                      section_norm),
            "Finish section prose must state children is [] for an epic's "
            "own creation run")


class HandoffExampleClaimsNoChildrenAtCreationTimeCase(unittest.TestCase):
    """F1-g: the <handoff> example's <summary> makes no children-minted
    claim and names --fan-out as the later step."""

    def test_handoff_example_claims_no_children_at_creation_time(self):
        section_norm = norm(finish_section())
        m = re.search(r"<summary>(.*?)</summary>", section_norm)
        self.assertIsNotNone(m, "Finish section must contain a <handoff> summary")
        summary = m.group(1)
        self.assertIsNone(
            re.search(r"children SHOP-\d+", summary),
            "handoff summary must not claim children were minted at "
            "creation time")
        self.assertIn("--fan-out", summary)


class ExecutorResultExampleIsLabelledAsAChildMintingRunCase(unittest.TestCase):
    """F1-i: create-ticket-executor.md's output-contract region states its
    minted-children example belongs to a --fan-out (or split) run, and that
    a plain creation run reports no children finding."""

    def test_executor_result_example_is_labelled_as_a_child_minting_run(self):
        section_norm = norm(executor_output_contract_section())
        self.assertIsNotNone(
            re.search(r"(?i)--fan-out.{0,80}\(or split\).{0,120}"
                      r"run that minted children", section_norm),
            "executor output-contract region must label the minted-children "
            "example as belonging to a --fan-out (or split) run")
        self.assertIsNotNone(
            re.search(r"(?i)creation run.{0,120}no.{0,20}children.{0,20}finding",
                      section_norm),
            "executor output-contract region must state a plain creation "
            "run carries no children finding")


# ------------------------------------------------------------------------ H1-H3
# F2: the executor mirror is complete -- both-files loops so a one-sided
# edit fails by construction (the MAR-84 pattern).

class ChildAcceptanceCriteriaWriteInstructedInBothFilesCase(unittest.TestCase):
    """F2-b: both the fan-out section (SKILL.md) and the executor's step 4
    region instruct writing the confirmed child's acceptance_criteria into
    the child's own ticket.json after minting, naming the absent
    --acceptance-criteria flag."""

    def test_child_acceptance_criteria_write_instructed_in_both_files(self):
        sections = {
            "SKILL.md fan-out section": norm(fan_out_section()),
            "executor step 4": norm(executor_step4_section()),
        }
        for name, section_norm in sections.items():
            self.assertIsNotNone(
                re.search(r"(?i)acceptance_criteria.{0,200}child's own "
                          r"`?ticket\.json`?|"
                          r"child's own `?ticket\.json`?.{0,200}acceptance_criteria",
                          section_norm),
                "%s must state acceptance_criteria is written into the "
                "child's own ticket.json after minting" % name)
            self.assertIn("--acceptance-criteria", section_norm)


class ExecutorHardRulesPermitTheChildAcceptanceCriteriaWriteCase(unittest.TestCase):
    """F2-c: the executor's Hard rules permit the child ticket.json AC
    write while still forbidding counters.json/tickets-index.json/
    pipeline-state.json hand-edits -- landing F2-b without this widening
    would leave the executor contract self-contradictory."""

    def test_executor_hard_rules_permit_the_child_acceptance_criteria_write(self):
        section_norm = norm(executor_hard_rules_section())
        self.assertIsNotNone(
            re.search(r"(?i)acceptance_criteria.{0,200}child|"
                      r"child.{0,200}acceptance_criteria", section_norm),
            "Hard rules must permit the child acceptance_criteria write")
        for token in ("counters.json", "tickets-index.json", "pipeline-state.json"):
            self.assertIn(token, section_norm)


# ------------------------------------------------------------------------ I1-I5
# F3: un-orphan the split/restructure mode -- both gating clauses widen to
# "the two modes that mint children" without breaking A8/A11.

class StepFourGatingCoversBothChildMintingModesCase(unittest.TestCase):
    """F3-a: Step 4's gating paragraph names both --fan-out and the
    split/restructure mode, and still states it never runs at the epic's
    own creation time (A8's pinned fragments must both still hold)."""

    def test_step_4_gating_covers_both_child_minting_modes(self):
        section_norm = norm(step4_section())
        self.assertIn("ONLY under `--fan-out` mode", section_norm)
        self.assertIn("split/restructure", section_norm)
        self.assertIsNotNone(
            re.search(r"(?i)never (at|during) the epic's own creation",
                      section_norm))


class ExecutorStepFourGatingCoversBothModesAndScopesTheStepThreeSkipCase(unittest.TestCase):
    """F3-d: executor step 4 names both modes; the step-3 skip is scoped
    explicitly to --fan-out only; a split run is stated to run step 3
    (A11's pinned fragments must both still hold)."""

    def test_executor_step_4_gating_covers_both_modes_and_scopes_the_step_3_skip(self):
        section_norm = norm(executor_step4_section())
        self.assertIsNotNone(
            re.search(r"(?i)--fan-out.{0,80}split/restructure|"
                      r"split/restructure.{0,80}--fan-out", section_norm),
            "executor step 4 must name both modes")
        self.assertIsNotNone(
            re.search(r"(?i)ONLY in `?--fan-out`? mode", section_norm),
            "the step-3 skip must be scoped to --fan-out mode only")
        self.assertIsNotNone(
            re.search(r"(?i)split/restructure mode, step 3 DOES run",
                      section_norm),
            "executor step 4 must state a split run runs step 3")


class StepFiveSyncSetCoversChildrenMintedByEitherModeCase(unittest.TestCase):
    """F3-c: Step 5's child-inclusion clause covers children minted by
    either mode, and states a split run's already-synced root is updated,
    never re-created."""

    def test_step_5_sync_set_covers_children_minted_by_either_mode(self):
        section_norm = norm(step5_section())
        self.assertIsNotNone(
            re.search(r"(?i)children minted in step 4.{0,80}"
                      r"(--fan-out|split/restructure)", section_norm),
            "Step 5's child-inclusion clause must cover children minted "
            "by either mode")
        self.assertIsNotNone(
            re.search(r"(?i)split/restructure run.{0,200}already-synced"
                      r".{0,120}updated", section_norm),
            "Step 5 must state a split run's already-synced root is "
            "updated, not re-created")


class SplitSectionPointsAtStepFourForChildMintingCase(unittest.TestCase):
    """F3-e: the split section (sliced exactly as
    test_oversize_split_signal.py:127-129 slices it) cross-references Step
    4's mint command and conservative-defaults rule, without introducing
    the create-spec/escalation tokens that section forbids."""

    def test_split_section_points_at_step_4_for_child_minting(self):
        section_norm = norm(split_section())
        self.assertIsNotNone(
            re.search(r"(?i)step 4.{0,80}mint command|"
                      r"mint command.{0,80}step 4", section_norm),
            "split section must cross-reference Step 4's mint command")
        self.assertIsNotNone(
            re.search(r"(?i)conservative.default", section_norm),
            "split section must cross-reference Step 4's "
            "conservative-defaults rule")
        self.assertNotIn("create-spec", section_norm)
        self.assertNotIn("escalation", section_norm)


class ConservativeDefaultsSingleConfirmationCoversBothModesCase(unittest.TestCase):
    """F3-b: Step 4's conservative-defaults paragraph names the split
    mode's own confirmation as the equivalent single gate; the literal
    "confirmed ONCE" survives."""

    def test_conservative_defaults_single_confirmation_covers_both_modes(self):
        section_norm = norm(step4_section())
        self.assertIsNotNone(re.search(r"(?i)confirmed ONCE", section_norm))
        self.assertIsNotNone(
            re.search(r"(?i)split/restructure run.{0,120}own user confirmation",
                      section_norm),
            "the conservative-defaults paragraph must name the split "
            "mode's own confirmation as the equivalent single gate")


if __name__ == "__main__":
    unittest.main()
