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


if __name__ == "__main__":
    unittest.main()
