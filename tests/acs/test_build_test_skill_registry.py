"""Registry + dispatch wiring for the six Build/Test skills.

The skills-independence refactor adds five HOOKED skills — analyze-ticket,
create-impl-plan, create-api-contract, create-test-docs, create-e2e-tests —
and renames today's `test` suite runner to `run-e2e-tests`, which stays
UNHOOKED with `test` retained beside it for one release as the alias
directory (workflows/phases.yaml `aliases`).

What that registration actually consists of, and what this module pins:

  * `acs_lib.HOOKED_SKILLS` (via WORKFLOW_SKILLS) — the ONLY per-skill table
    dispatch.py consults (`skill not in HOOKED_SKILLS` is its pass-through),
    the `--skill` choices of skill-start.py and clarify.py, the set
    `acs_lib.lifecycle.parse_agent_type` accepts `acs:<skill>-<role>` from,
    and the derived `MODEL_OVERRIDE_SKILLS`;
  * `acs_lib.UNHOOKED_SKILLS` — run-e2e-tests and the retained `test` alias,
    which must reach neither a gate nor a run entry;
  * one `acs_lib.GATES` entry per hooked skill (the gate bodies themselves are
    tests/acs/test_acs_lib_gates.py's);
  * a thin `pre-<name>.py` / `post-<name>.py` wrapper pair per hooked skill,
    and NO wrapper for the unhooked runner;
  * `pipeline-state.schema.json`'s steps enum (mirrored by
    `acs_lib.PIPELINE_STEP_ORDER` and pipeline-step.py's PIPELINE_STEPS) plus
    the `skipped` status the ship.yaml walk records for a `when`-false step;
  * a `skills/<name>/` directory whose SKILL.md frontmatter names it (the
    prose bodies are a later phase; only the registration is asserted here).

Run:  python3 -m unittest tests.acs.test_build_test_skill_registry -v
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
TESTS_ACS = os.path.join(REPO_ROOT, "tests", "acs")

sys.path.insert(0, HOOKS_DIR)
sys.path.insert(0, TESTS_ACS)

import acs_lib as lib  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402

#: The five that gained hooks, in ship.yaml order.
HOOKED_BUILD_TEST_SKILLS = ("analyze-ticket", "create-impl-plan", "create-api-contract",
                            "create-test-docs", "create-e2e-tests")

#: The suite runner, renamed, and the alias directory retained beside it.
UNHOOKED_TEST_SKILLS = ("run-e2e-tests", "test")

ALL_SIX = HOOKED_BUILD_TEST_SKILLS + ("run-e2e-tests",)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def pipeline_state_schema():
    return json.loads(read(os.path.join(PLUGIN, "schemas", "pipeline-state.schema.json")))


class TestRegistryLists(unittest.TestCase):

    def test_the_five_build_test_skills_are_hooked(self):
        for skill in HOOKED_BUILD_TEST_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, lib.HOOKED_SKILLS)
                self.assertNotIn(skill, lib.UNHOOKED_SKILLS)

    def test_they_join_workflow_skills_not_product_or_planning(self):
        """Ticket-scoped, so run_post's `flow` stays "ticket" and they never
        gain the delivery-ticket allocate/in_review semantics."""
        for skill in HOOKED_BUILD_TEST_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, lib.WORKFLOW_SKILLS)
                self.assertNotIn(skill, lib.PRODUCT_SKILLS)
                self.assertNotIn(skill, lib.PLANNING_SKILLS)
                self.assertNotIn(skill, lib.DELIVERY_TICKET_SKILLS)

    def test_hooked_skills_stays_the_three_way_concatenation(self):
        self.assertEqual(
            lib.HOOKED_SKILLS,
            lib.PRODUCT_SKILLS + lib.WORKFLOW_SKILLS + lib.PLANNING_SKILLS)

    def test_run_e2e_tests_and_the_test_alias_are_unhooked_only(self):
        for skill in UNHOOKED_TEST_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, lib.UNHOOKED_SKILLS)
                self.assertNotIn(skill, lib.HOOKED_SKILLS)
                self.assertNotIn(skill, lib.GATES)

    def test_every_new_hooked_skill_has_exactly_one_gate(self):
        for skill in HOOKED_BUILD_TEST_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, lib.GATES)
        self.assertEqual(sorted(lib.GATES), sorted(lib.HOOKED_SKILLS))

    def test_a_per_skill_model_override_is_accepted_for_each(self):
        """MODEL_OVERRIDE_SKILLS is derived from HOOKED_SKILLS, so registering
        the skill is what makes `models.overrides.<skill>` configurable."""
        for skill in HOOKED_BUILD_TEST_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, lib.MODEL_OVERRIDE_SKILLS)
                lib.validate_models({"overrides": {skill: {"planner": "a-model"}}})
        with self.assertRaises(lib.GateError):
            lib.validate_models({"overrides": {"run-e2e-tests": {"planner": "a-model"}}})

    def test_the_settings_schema_override_enum_carries_them(self):
        schema = json.loads(read(os.path.join(PLUGIN, "schemas", "settings.schema.json")))
        enum = schema["properties"]["models"]["properties"]["overrides"]["propertyNames"]["enum"]
        for skill in HOOKED_BUILD_TEST_SKILLS:
            self.assertIn(skill, enum)
        self.assertNotIn("run-e2e-tests", enum)


class TestAgentNameRegistration(unittest.TestCase):
    """SubagentStart/Stop carry an `acs:<skill>-<role>` agent type; the hook
    parses it against HOOKED_SKILLS, so no separate agent-name table exists to
    update. The agent .md files are a later phase — this pins only that the
    names now parse (and that the unhooked runner's do not)."""

    def test_each_new_skill_parses_as_an_agent_type(self):
        for skill in HOOKED_BUILD_TEST_SKILLS:
            for role in ("planner", "executor", "verifier"):
                with self.subTest(skill=skill, role=role):
                    self.assertEqual(
                        lib.parse_agent_type("acs:%s-%s" % (skill, role)), (skill, role))

    def test_the_unhooked_runner_has_no_agent_type(self):
        self.assertEqual(lib.parse_agent_type("acs:run-e2e-tests-executor"), (None, None))


class TestHookScripts(unittest.TestCase):

    def test_each_new_hooked_skill_has_a_pre_and_post_wrapper(self):
        for skill in HOOKED_BUILD_TEST_SKILLS:
            with self.subTest(skill=skill):
                pre = read(os.path.join(HOOKS_DIR, "pre-%s.py" % skill))
                post = read(os.path.join(HOOKS_DIR, "post-%s.py" % skill))
                self.assertIn("from acs_lib import run_pre", pre)
                self.assertIn('run_pre("%s")' % skill, pre)
                self.assertIn("from acs_lib import run_post", post)
                self.assertIn('run_post("%s")' % skill, post)

    def test_each_post_wrapper_documents_the_states_it_records(self):
        """The result-document `states` contract is the hand-off between one
        skill and the next; it is written down where the hook that persists it
        lives, not only in INTERNALS.md."""
        expected = {
            "analyze-ticket": ["ready_for_planning", "api_surface", "questions_open"],
            "create-impl-plan": ["plan_path", "plan_approved", "file_map"],
            "create-api-contract": ["contract_path", "items", "traced_acs"],
            "create-test-docs": ["cases", "e2e_cases", "untraced_acs"],
            "create-e2e-tests": ["suites_written", "cases_covered"],
        }
        for skill, keys in expected.items():
            body = read(os.path.join(HOOKS_DIR, "post-%s.py" % skill))
            for key in keys:
                with self.subTest(skill=skill, key=key):
                    self.assertIn(key, body)

    def test_the_unhooked_runner_has_no_hook_scripts(self):
        for skill in UNHOOKED_TEST_SKILLS:
            for prefix in ("pre", "post"):
                path = os.path.join(HOOKS_DIR, "%s-%s.py" % (prefix, skill))
                with self.subTest(script=os.path.basename(path)):
                    self.assertFalse(os.path.isfile(path), "%s must not exist" % path)


class TestPipelineStepRegistration(unittest.TestCase):

    def test_the_schema_steps_enum_carries_every_new_step(self):
        enum = pipeline_state_schema()["properties"]["steps"]["propertyNames"]["enum"]
        for step in ALL_SIX:
            with self.subTest(step=step):
                self.assertIn(step, enum)
        self.assertIn("test", enum, "a ledger written before the rename must still validate")

    def test_the_schema_allows_the_skipped_status(self):
        """`acs.py workflow next` records a `when`-false step as skipped; the
        ledger it writes has to validate."""
        status = pipeline_state_schema()["properties"]["steps"]["additionalProperties"][
            "properties"]["status"]
        self.assertIn("skipped", status["enum"])

    def test_pipeline_step_order_mirrors_the_schema_enum(self):
        enum = pipeline_state_schema()["properties"]["steps"]["propertyNames"]["enum"]
        self.assertEqual(lib.PIPELINE_STEP_ORDER, enum)

    def test_the_cli_accepts_every_new_step_name(self):
        source = read(os.path.join(HOOKS_DIR, "pipeline-step.py"))
        match = re.search(r"(?s)PIPELINE_STEPS = \((.*?)\)", source)
        names = set(re.findall(r'"([^"]+)"', match.group(1)))
        for step in ALL_SIX:
            with self.subTest(step=step):
                self.assertIn(step, names)


class TestSkillDirectories(unittest.TestCase):

    def test_each_new_skill_has_a_directory_whose_frontmatter_names_it(self):
        for skill in ALL_SIX:
            with self.subTest(skill=skill):
                path = os.path.join(SKILLS_DIR, skill, "SKILL.md")
                self.assertTrue(os.path.isfile(path), path)
                text = read(path)
                parts = text.split("---\n", 2)
                self.assertEqual(parts[0], "", "%s: missing frontmatter" % skill)
                self.assertRegex(parts[1], r"(?m)^name: %s$" % re.escape(skill))
                self.assertRegex(parts[1], r"(?m)^description: \S")

    def test_the_test_alias_directory_is_retained(self):
        self.assertTrue(os.path.isfile(os.path.join(SKILLS_DIR, "test", "SKILL.md")))


class TestDispatchRouting(AcsWorkspaceCase):
    """dispatch.py has no per-skill table beyond HOOKED_SKILLS membership;
    these assert the two sides of that one branch."""

    def test_each_new_hooked_skill_reaches_its_gate(self):
        # An unresolvable ticket id: only a gate can produce this refusal, so
        # exit 2 proves the skill was NOT passed through.
        for skill in HOOKED_BUILD_TEST_SKILLS:
            with self.subTest(skill=skill):
                result = self.pre(skill, "SHOP-404")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("SHOP-404", result.stderr)

    def test_the_unhooked_runner_passes_through(self):
        for skill in UNHOOKED_TEST_SKILLS:
            with self.subTest(skill=skill):
                result = self.pre(skill, "SHOP-404")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")

    def test_skill_start_selects_the_hooked_five_and_refuses_the_runner(self):
        ticket = self.new_ticket("Wire the build skills", "task")
        for skill in HOOKED_BUILD_TEST_SKILLS:
            with self.subTest(skill=skill):
                out = self.start(skill, ticket)
                self.assertEqual(out.returncode, 0, out.stderr)
                context = json.loads(out.stdout)
                self.assertEqual(context["ticket_id"], ticket)
                self.assertTrue(context["post_hook"].endswith("post-%s.py" % skill))
        for skill in UNHOOKED_TEST_SKILLS:
            with self.subTest(skill=skill):
                out = self.start(skill, ticket)
                self.assertEqual(out.returncode, 2, out.stdout)
                self.assertIn("invalid choice", out.stderr)


class TestPostHookRoundTrip(AcsWorkspaceCase):
    """One full start -> post cycle, to prove the registration is enough for
    the generic lifecycle to persist a run and a ledger step."""

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Analyze me", "task")

    def _pipeline(self):
        with open(os.path.join(self.tdir(self.ticket), "pipeline-state.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)

    def test_analyze_ticket_records_its_run_states_and_step(self):
        self.assertEqual(self.start("analyze-ticket", self.ticket).returncode, 0)
        states = {"ready_for_planning": True, "api_surface": True, "questions_open": 0}
        out = self.post("analyze-ticket", self.ticket,
                        {"status": "completed", "states": states})
        self.assertEqual(out.returncode, 0, out.stderr)

        state = lib.load_state(self.tdir(self.ticket), "analyze-ticket", self.ticket)
        self.assertEqual(state["skill"], "analyze-ticket")
        self.assertEqual(state["runs"][-1]["status"], "completed")
        self.assertEqual(state["states"], states)
        self.assertTrue(lib.skill_completed(self.tdir(self.ticket), "analyze-ticket"))

        step = self._pipeline()["steps"]["analyze-ticket"]
        self.assertEqual(step["status"], "completed")

    def test_create_e2e_tests_records_its_own_step_beside_the_others(self):
        for skill in ("create-test-docs", "create-e2e-tests"):
            self.assertEqual(self.start(skill, self.ticket).returncode, 0)
            out = self.post(skill, self.ticket,
                            {"status": "completed", "states": {"cases": 1}})
            self.assertEqual(out.returncode, 0, out.stderr)
        steps = self._pipeline()["steps"]
        self.assertEqual(steps["create-test-docs"]["status"], "completed")
        self.assertEqual(steps["create-e2e-tests"]["status"], "completed")
        enum = pipeline_state_schema()["properties"]["steps"]["propertyNames"]["enum"]
        for name in steps:
            self.assertIn(name, enum, "the written ledger must validate")


if __name__ == "__main__":
    unittest.main()
