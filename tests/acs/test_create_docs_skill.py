"""MAR-1 T-B — /acs:create-docs, the doc-bootstrap fan-out umbrella skill.

Prose-contract tests over the new unhooked coordinator, `create-docs/SKILL.md`,
mirroring the discipline in `tests/acs/test_create_quality_loop_topology.py`:
every assertion is a whitespace-normalized substring/regex check over the
prose, never a line-number assertion (prose is revised; line numbers drift).
Behavioral quality -- does the model actually spawn the subagents this prose
describes -- is the agentic-e2e tier, not unit-testable here
(tests/acs/test_skill_contracts.py:1-9's stated boundary).

Run:  python3 -m unittest tests.acs.test_create_docs_skill -v
"""

import glob
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
AGENTS_DIR = os.path.join(PLUGIN, "agents")
SKILL_PATH = os.path.join(PLUGIN, "skills", "create-docs", "SKILL.md")

sys.path.insert(0, HOOKS_DIR)
import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match."""
    return re.sub(r"\s+", " ", body)


def _body():
    return read(SKILL_PATH)


class HookIntegrityTest(unittest.TestCase):
    """AC-2: every fanned-out skill's own hooks/reflection/gating fire
    unchanged; create-docs itself carries no hook surface of its own."""

    def test_starts_are_sequential_real_skill_tool_calls(self):
        body_norm = norm(_body())
        q = body_norm.find("Skill(acs:create-quality)")
        o = body_norm.find("Skill(acs:create-operations)")
        self.assertGreater(q, -1, "must invoke create-quality's Start as a real Skill-tool call")
        self.assertGreater(o, -1, "must invoke create-operations's Start as a real Skill-tool call")
        self.assertLess(q, o, "create-quality's Start must be invoked before create-operations's")
        self.assertRegex(body_norm, r"(?i)sequential")
        self.assertIn("PreToolUse(Skill)", body_norm)

    def test_no_hook_bypass_or_simulation_language(self):
        body = _body()
        self.assertNotIn("bypass the hook", body)
        self.assertNotIn("simulate the hook", body)
        self.assertNotIn("skip the pre-hook", body)
        self.assertNotIn("skip the post-hook", body)
        self.assertIsNone(re.search(r"(?i)duplicate(?:s|d)? (?:the |a )?(?:pre|post)-hook", body))
        self.assertIsNotNone(
            re.search(r"(?i)never bypass, simulate, or duplicate", body),
            "must explicitly disclaim bypass/simulate/duplicate of any hook")

    def test_no_pre_or_post_create_docs_script_on_disk(self):
        self.assertFalse(
            os.path.isfile(os.path.join(HOOKS_DIR, "pre-create-docs.py")),
            "pre-create-docs.py must not exist -- create-docs is unhooked")
        self.assertFalse(
            os.path.isfile(os.path.join(HOOKS_DIR, "post-create-docs.py")),
            "post-create-docs.py must not exist -- create-docs is unhooked")

    def test_no_create_docs_agent_files_on_disk(self):
        self.assertEqual(
            glob.glob(os.path.join(AGENTS_DIR, "create-docs-*.md")), [],
            "no plugins/acs/agents/create-docs-*.md file may exist -- no new triad")

    def test_create_docs_not_in_hooked_skills_product_workflow_or_gates(self):
        self.assertIn("create-docs", acs_lib.UNHOOKED_SKILLS)
        self.assertNotIn("create-docs", acs_lib.HOOKED_SKILLS)
        self.assertNotIn("create-docs", acs_lib.PRODUCT_SKILLS)
        self.assertNotIn("create-docs", acs_lib.WORKFLOW_SKILLS)
        self.assertNotIn("create-docs", acs_lib.GATES)


class ParallelBatchTest(unittest.TestCase):
    """AC-1: both legs' phase subagents are spawned in parallel batches from
    one coordinator -- reusing /acs:code's existing parallel-spawn mechanism,
    never a new one."""

    def test_prose_spawns_both_planners_in_one_batch(self):
        body_norm = norm(_body())
        for m in re.finditer(r"(?i)one message|same message|single message", body_norm):
            window = body_norm[max(0, m.start() - 200):m.end() + 200]
            if "create-quality-planner" in window and "create-operations-planner" in window:
                return
        self.fail(
            "create-docs/SKILL.md must co-locate both planner names with a "
            "'one/same/single message' clause within ~200 chars")

    def test_prose_batches_executors_then_verifiers(self):
        body = _body()
        exec_idx = body.find("create-quality-executor")
        verify_idx = body.find("create-quality-verifier")
        self.assertGreater(exec_idx, -1)
        self.assertGreater(verify_idx, -1)
        self.assertLess(exec_idx, verify_idx,
                        "the executor batch must be described before the verifier batch")
        body_norm = norm(body)
        self.assertIsNotNone(
            re.search(r"(?i)both executors", body_norm),
            "must name 'both executors' as a batch")
        self.assertIsNotNone(
            re.search(r"(?i)both verifiers", body_norm),
            "must name 'both verifiers' as a batch")

    def test_cites_code_skill_parallel_spawn_mechanism_as_precedent(self):
        body_norm = norm(_body())
        self.assertIn("code/SKILL.md", body_norm)
        self.assertIsNotNone(
            re.search(r"(?i)(several executors in parallel|same agent file.{0,20}(four|4) times)", body_norm),
            "must cite /acs:code's own parallel-spawn wording as the reused mechanism")

    def test_no_new_agent_plus_skill_subagent_class(self):
        body_norm = norm(_body())
        self.assertNotIn("Agent, Skill", body_norm)
        self.assertNotIn("Agent+Skill", body_norm)


class FailureIsolationTest(unittest.TestCase):
    """AC-3: per-leg isolation, with a fail-fast carve-out scoped exclusively
    to the one shared architecture-gate precondition."""

    def test_failfast_carveout_named_and_scoped_to_shared_architecture_gate(self):
        body_norm = norm(_body())
        self.assertIn("_require_architecture_doc_set", body_norm)
        self.assertIsNotNone(
            re.search(r"(?i)fail.fast", body_norm),
            "must name the fail-fast carve-out")
        self.assertIsNotNone(
            re.search(r"(?i)scoped exclusively", body_norm),
            "must state the carve-out is scoped exclusively to the shared gate")
        self.assertIsNotNone(
            re.search(r"(?i)not_attempted", body_norm),
            "must distinguish the shared-gate carve-out's not_attempted outcome from a leg-specific failure")

    def test_every_other_failure_class_falls_through_to_per_leg_isolation(self):
        body_norm = norm(_body())
        window_match = re.search(r"(?i)scoped exclusively.{0,400}", body_norm)
        self.assertIsNotNone(window_match)
        window = window_match.group(0)
        self.assertIsNotNone(re.search(r"(?i)verifier cap", window))
        self.assertIsNotNone(re.search(r"(?i)lock held", window))
        self.assertIsNotNone(re.search(r"(?i)per-leg isolation", window))


class ResumeContractTest(unittest.TestCase):
    """AC-4: no new shared ledger; each leg's own pipeline-state.json is the
    resume record, and /acs:ship's product-flow refusal is unchanged."""

    def test_resume_is_the_legs_own_standalone_invocation_not_a_batch_resume(self):
        body_norm = norm(_body())
        self.assertIn("/acs:create-quality <ticket-id>", body_norm)
        self.assertIn("/acs:create-operations <ticket-id>", body_norm)
        self.assertIsNotNone(
            re.search(r"(?i)never a re-invocation of this umbrella", body_norm))
        self.assertIsNotNone(
            re.search(r"(?i)no fan-out batch ledger of its own", body_norm))

    def test_ship_product_flow_refusal_is_restated_not_reversed(self):
        body_norm = norm(_body())
        self.assertIn('flow: "product"', body_norm)
        self.assertIsNotNone(
            re.search(r"(?i)ship.{0,80}(never drives|does not drive|refus\w*).{0,80}unchanged"
                      r"|unchanged.{0,80}ship.{0,80}(never drives|does not drive|refus\w*)",
                      body_norm),
            "must state ship's product-flow refusal is unchanged, never reversed")


class DependencyDocTest(unittest.TestCase):
    """AC-5: the fan-out never applies to skills with a real dependency; the
    dependency edge is declared, never inferred."""

    def test_prose_states_dependencies_are_declared_not_inferred(self):
        body_norm = norm(_body())
        self.assertIn("DOC_BOOTSTRAP_DEPENDENCIES", body_norm)
        self.assertIsNotNone(
            re.search(r"(?i)declared.{0,40}never inferred|declared, not inferred", body_norm))


class DocumentationTest(unittest.TestCase):
    """AC-6: the new orchestration behavior is documented -- which skills are
    eligible for fan-out, and why."""

    def test_prose_names_v1_eligible_pair_and_why(self):
        body_norm = norm(_body())
        self.assertIn("create-quality", body_norm)
        self.assertIn("create-operations", body_norm)
        self.assertIsNotNone(
            re.search(r"(?i)v1", body_norm),
            "must name the v1-scoped eligible set")
        self.assertIsNotNone(
            re.search(r"(?i)disjoint|neither reads the other", body_norm),
            "must state why the v1 pair is independent")

    def test_prose_states_new_skill_is_a_table_data_change(self):
        body_norm = norm(_body())
        self.assertIsNotNone(
            re.search(r"(?i)data change, not a code change|data change.{0,30}never a code change", body_norm))

    def test_completion_report_section_present(self):
        self.assertIn("## Completion report (normative)", _body())

    def test_prose_states_the_v1_gate_is_a_declared_constant(self):
        # finding 2 (prose half): the v1 fan-out set is named as the
        # declared acs_lib constant, not a bare "the pair" claim.
        body_norm = norm(_body())
        self.assertIn("DOC_BOOTSTRAP_FANOUT_V1", body_norm)
        self.assertIsNotNone(
            re.search(r"(?i)declared", body_norm),
            "must state the v1 gate is declared (data), not inferred/hardcoded prose")

    def test_for_flag_reports_a_non_v1_name_as_ineligible(self):
        # finding 2 (prose half): a --for name outside v1's set is reported
        # as ineligible, never silently fanned out.
        body_norm = norm(_body())
        self.assertIn("--for", body_norm)
        self.assertIsNotNone(
            re.search(r"(?i)not in v1.s fan-out set", body_norm),
            "must report a non-v1 --for name as \"not in v1's fan-out set\"")


class LoopTopologyTest(unittest.TestCase):
    """finding 7: create-docs/SKILL.md's own Reflection-loop item 1 (Plan)
    must not read as a per-iteration re-spawn -- mirrors
    test_create_quality_loop_topology.py::SinglePlannerSpawnPerRunTest
    check-for-check, adapted to the umbrella's two-planner batch."""

    @classmethod
    def setUpClass(cls):
        cls.body = _body()
        cls.norm = norm(cls.body)

    def test_plan_list_item_is_not_per_iteration(self):
        self.assertRegex(self.body, r"(?m)^1\. \*\*Plan\*\* \(once[^)]*\)")
        self.assertNotRegex(self.body, r"(?m)^1\. \*\*Plan\*\* —")

    def test_states_exactly_one_planner_per_leg_across_the_whole_run(self):
        for m in re.finditer(r"exactly one", self.norm, re.IGNORECASE):
            window = self.norm[max(0, m.start() - 80):m.end() + 80]
            if "planner" in window.lower() and re.search(r"(?i)\bleg\b", window) and re.search(
                    r"(?i)\bwhole run\b", window):
                return
        self.fail(
            "create-docs/SKILL.md must co-locate an 'exactly one' clause "
            "with 'planner', 'leg' and a whole-run qualifier within ~80 chars")

    def test_findings_route_to_each_legs_own_executor_context_with_no_planner_between(self):
        no_planner_re = re.compile(r"(?i)(no|never|without)\W{0,20}planner")
        for m in re.finditer(r"(?i)findings", self.norm):
            window = self.norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_planner_re.search(window)):
                return
        self.fail(
            "create-docs/SKILL.md must co-locate 'findings', 'executor', "
            "'<context>' and a no-planner clause within ~300 chars")

    def test_no_unnegated_replan_instruction(self):
        negating = re.compile(r"(?i)never|no |not|without|instead of")
        for m in re.finditer(r"(?i)re-?plan\w*", self.body):
            window = self.body[max(0, m.start() - 60):m.end() + 60]
            self.assertRegex(
                window, negating,
                "un-negated 're-plan' instruction found: %r" % window)

    def test_iteration_cap_is_still_three_execute_verify_rounds(self):
        self.assertIsNotNone(
            re.search(r"(?i)max 3 execute.{0,4}(→|->)?.{0,4}verify rounds", self.norm),
            "the per-leg iteration cap (max 3 execute-verify rounds) must be pinned")


def _start_section():
    """Slice the '## Start' section (up to the next '\n## ' heading)."""
    body = _body()
    start_idx = body.index("## Start")
    rest = body[start_idx:]
    next_heading = rest.find("\n## ", 1)
    return rest if next_heading == -1 else rest[:next_heading]


def _start_bash_block():
    """The first ```bash fenced block inside the '## Start' section."""
    section = _start_section()
    m = re.search(r"```bash\n(.*?)```", section, re.DOTALL)
    return m.group(1) if m else ""


class StartSnippetContractTest(unittest.TestCase):
    """Findings 1/3/4: the Start snippet must parse `--for` through the v1
    gate, resolve fanout_batches's checkout_root properly, and guard
    validate_settings the same way every other SKILL.md Start step does."""

    @classmethod
    def setUpClass(cls):
        cls.block = _start_bash_block()
        cls.section_norm = norm(_start_section())

    def test_arguments_are_passed_into_the_snippet(self):
        self.assertIn('python3 - "$ARGUMENTS" <<\'PY\'', self.block)
        self.assertIn("sys.argv", self.block)

    def test_for_argument_is_parsed_and_v1_gated(self):
        self.assertIn("parse_fanout_for_arg", self.block)
        self.assertIn("candidates=", self.block)
        self.assertIsNotNone(
            re.search(r"fanout_batches\([^)]*candidates=", self.block, re.DOTALL),
            "fanout_batches call must pass candidates=")

    def test_fanout_batches_receives_the_resolved_checkout_root(self):
        self.assertIn("lib.checkout_root(cwd)", self.block)
        self.assertNotRegex(self.block, r"fanout_batches\(settings,\s*tickets_index,\s*cwd\b")

    def test_validate_settings_is_guarded_by_gate_error_exit_2(self):
        self.assertIsNotNone(
            re.search(
                r"try:.*?lib\.validate_settings\(.*?except lib\.GateError as exc:.*?sys\.exit\(2\)",
                self.block, re.DOTALL),
            "validate_settings must be wrapped try/except lib.GateError -> sys.exit(2)")
        self.assertIn("% exc", self.block)

    def test_rejection_is_reported_never_silently_dropped(self):
        self.assertIsNotNone(
            re.search(r"(?i)not in v1.s fan-out set", self.section_norm))
        self.assertIsNotNone(
            re.search(r"(?i)(never silently|never fanned out).{0,120}rejected"
                      r"|rejected.{0,120}(never silently|never fanned out)", self.section_norm))

    def test_exit_2_instruction_present(self):
        self.assertIsNotNone(
            re.search(r"(?i)surface.{0,20}(stderr )?verbatim.{0,80}stop", self.section_norm))


class WorktreeLifecycleTest(unittest.TestCase):
    """finding 6: the worktree is created before that leg's Execute phase
    and entered at that leg's own Branch step -- never claimed to be
    entered only at Delivery. D3.2(ii) (skill-start.py in the session
    checkout) stays intact."""

    @classmethod
    def setUpClass(cls):
        cls.body = _body()
        cls.norm = norm(cls.body)

    def test_worktree_is_entered_at_the_legs_branch_step_before_execute(self):
        self.assertIsNotNone(
            re.search(r"(?i)enters? that leg.s (own )?worktree", self.norm),
            "must state the coordinator enters that leg's own worktree")
        self.assertIsNotNone(
            re.search(r"(?i)Branch.{0,10}\(?step 1\)?|step 1.{0,10}\(Branch\)", self.norm),
            "must name Branch as the leg's own step 1")
        self.assertIsNotNone(
            re.search(r"(?i)before.{0,40}(the )?Execute phase", self.norm),
            "must state this happens before the Execute phase")

    def test_no_claim_that_the_worktree_is_entered_only_at_delivery(self):
        self.assertNotRegex(
            self.norm, r"(?i)entered\W+only\W+at.{0,40}Delivery")

    def test_clean_tree_precondition_is_reconciled_with_a_fresh_worktree(self):
        self.assertIsNotNone(
            re.search(r"(?i)git status --porcelain.{0,120}empty", self.norm),
            "must state git status --porcelain is empty for the fresh worktree")
        self.assertIsNotNone(
            re.search(r"(?i)true by construction|freshly created", self.norm),
            "must reconcile the clean-tree precondition with a freshly created worktree")

    def test_skill_start_still_runs_in_the_session_checkout(self):
        self.assertIn("skill-start.py", self.body)
        self.assertIsNotNone(re.search(r"(?i)session checkout", self.norm))
        self.assertIsNotNone(
            re.search(r"(?i)D3\.2", self.norm),
            "the D3.2(ii) session-checkout paragraph must remain cited")


if __name__ == "__main__":
    unittest.main()
