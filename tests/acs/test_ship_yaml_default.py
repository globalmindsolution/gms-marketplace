"""The shipped default workflows/ship.yaml: it validates (against the stdlib
subset validator AND the jsonschema package, so the two agree), every step
names a build/test/ship skill per phases.yaml, the DAG is acyclic with
`needs` pointing at earlier steps, and the skills a human always drives --
merge-pr, release, every design-phase skill, every utility skill -- are
rejected at the line that names them.

Run:  python3 -m unittest tests.acs.test_ship_yaml_default -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402
from acs_lib import workflow  # noqa: E402

#: The step order the refactor brief fixes (brief section 2.1).
EXPECTED_IDS = ["analyze-requirements", "create-impl-plan", "create-api-contract", "create-test-docs",
                "code", "create-e2e-tests", "docs-sync", "run-e2e-tests", "create-pr"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestShippedDefault(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.path = lib.default_workflow_path()
        cls.text = read(cls.path)
        cls.doc = lib.validate_workflow_file(cls.path)
        cls.phases = lib.load_phases()
        cls.steps = {step["id"]: step for step in cls.doc["steps"]}

    def test_it_lives_under_the_plugin_workflows_dir(self):
        self.assertEqual(self.path, os.path.join(PLUGIN, "workflows", "ship.yaml"))

    def test_the_shipped_default_validates(self):
        self.assertEqual(self.doc["version"], workflow.WORKFLOW_VERSION)
        self.assertEqual(self.doc["version"], 2)
        self.assertEqual(self.doc["name"], "ship")

    def test_it_declares_the_four_delivery_paths(self):
        delivery = workflow.delivery_of(self.doc)
        self.assertIsNotNone(delivery, "the shipped default declares delivery paths")
        self.assertEqual(delivery["classify_after"], "create-impl-plan")
        self.assertEqual(delivery["paths"], ["trivial", "small", "standard", "complex"])

    def test_it_validates_with_jsonschema_too(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        with open(os.path.join(PLUGIN, "schemas", "workflow.schema.json"), encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(self.doc, schema)

    def test_the_schema_skill_enum_mirrors_the_registry(self):
        with open(os.path.join(PLUGIN, "schemas", "workflow.schema.json"), encoding="utf-8") as fh:
            schema = json.load(fh)
        # `skill` and `boundary` are each `oneOf` a scalar and a per-path
        # mapping since ADR-0095, so the enum lives on the scalar branch and on
        # the mapping's value schema -- both must mirror the registry.
        skill_def = schema["$defs"]["skillName"]
        self.assertEqual(skill_def["enum"], workflow.allowed_step_skills(self.phases))
        self.assertEqual(sorted(schema["$defs"]["predicate"]["enum"]), sorted(lib.PREDICATES))
        boundary = schema["$defs"]["step"]["properties"]["boundary"]
        self.assertEqual(boundary["oneOf"][0]["enum"], list(lib.BOUNDARIES))
        self.assertEqual(boundary["oneOf"][1]["additionalProperties"]["enum"],
                         list(lib.BOUNDARIES))
        self.assertEqual(schema["properties"]["stop_after"]["default"], lib.DEFAULT_STOP_AFTER)
        self.assertEqual(schema["properties"]["max_parallel"]["default"], lib.DEFAULT_MAX_PARALLEL)

    def test_step_order_matches_the_brief(self):
        self.assertEqual([step["id"] for step in self.doc["steps"]], EXPECTED_IDS)

    def test_every_listed_skill_is_build_test_or_ship(self):
        for step in self.doc["steps"]:
            with self.subTest(step=step["id"]):
                for name in workflow.step_skills(step):
                    # phase_of resolves an internal leg through its entry point,
                    # so a `code-*` leg reports `build` like `code` itself.
                    self.assertIn(lib.phase_of(name, self.phases), workflow.SHIP_PHASES)
                    self.assertNotIn(name, workflow.SHIP_EXCLUDED_SKILLS)

    def test_needs_name_earlier_steps_and_the_dag_is_acyclic(self):
        seen = []
        for step in self.doc["steps"]:
            for need in step.get("needs", []):
                self.assertIn(need, seen, "%s needs %s which is not earlier" % (step["id"], need))
            seen.append(step["id"])
        # An explicit topological sort as the independent acyclicity check.
        remaining = {s["id"]: set(s.get("needs", [])) for s in self.doc["steps"]}
        while remaining:
            free = [sid for sid, needs in remaining.items() if not needs]
            self.assertTrue(free, "cycle among %s" % sorted(remaining))
            for sid in free:
                del remaining[sid]
            for needs in remaining.values():
                needs.difference_update(free)

    def test_stop_after_and_max_parallel(self):
        self.assertEqual(self.doc["stop_after"], "create-pr")
        self.assertEqual(self.doc["max_parallel"], 2)

    def test_create_impl_plan_requires_design_approved(self):
        self.assertEqual(self.steps["create-impl-plan"]["requires"], "design_approved")
        self.assertEqual(self.steps["create-impl-plan"]["needs"], ["analyze-requirements"])

    def test_create_api_contract_runs_after_the_plan_when_the_api_surface_changed(self):
        self.assertEqual(self.steps["create-api-contract"]["needs"], ["create-impl-plan"])
        self.assertEqual(self.steps["create-api-contract"]["when"], "api_surface_changed")
        self.assertEqual(self.steps["create-test-docs"]["needs"], ["create-impl-plan", "create-api-contract"])

    def test_code_is_exclusive_with_the_boundary_and_replan(self):
        code = self.steps["code"]
        self.assertTrue(code["exclusive"])
        self.assertEqual(code["on_replan"], "create-impl-plan")
        self.assertEqual(code["needs"], ["create-test-docs"])

    def test_the_code_step_resolves_to_one_leg_per_delivery_path(self):
        self.assertEqual(self.steps["code"]["skill"], {
            "trivial": "code-trivial", "small": "code-small",
            "standard": "code-standard", "complex": "code-complex"})

    def test_only_the_two_deep_paths_carry_the_boundary(self):
        """/acs:ship's context is exhausted by the paths that fan out, not by
        the ones that run one executor and one verifier."""
        self.assertEqual(self.steps["code"]["boundary"],
                         {"standard": "full_verify_stop", "complex": "full_verify_stop"})
        for path in ("trivial", "small"):
            self.assertIsNone(workflow.per_path(self.steps["code"]["boundary"], path))

    def test_the_trivial_path_skips_test_docs_and_the_e2e_steps(self):
        """It has no test-cases.md to write e2e rows from, so those steps have
        no input on that path -- `paths` records them skipped, which satisfies
        their dependants exactly as a false `when` does."""
        for sid in ("create-test-docs", "create-e2e-tests", "run-e2e-tests"):
            with self.subTest(step=sid):
                self.assertEqual(self.steps[sid]["paths"], ["small", "standard", "complex"])

    def test_create_e2e_tests_and_docs_sync_both_need_only_code(self):
        """The parallel pair: both are READY the moment code completes."""
        self.assertEqual(self.steps["create-e2e-tests"]["needs"], ["code"])
        self.assertEqual(self.steps["create-e2e-tests"]["when"], "e2e_configured")
        self.assertEqual(self.steps["docs-sync"]["needs"], ["code"])
        self.assertFalse(self.steps["docs-sync"].get("exclusive", False))

    def test_run_e2e_tests_relays_failures_to_code_under_the_named_cap(self):
        step = self.steps["run-e2e-tests"]
        self.assertEqual(step["args"], "--for-ticket {ticket_id}")
        self.assertEqual(step["when"], "post_code_test_active")
        self.assertEqual(step["on_fail"], {"relay_to": "code", "max_loops": "post_code_test_fix_loops_cap"})
        self.assertIn(step["on_fail"]["max_loops"], lib.MAX_LOOPS_NAMES)

    def test_create_pr_is_last_and_needs_docs_sync_and_run_e2e_tests(self):
        self.assertEqual(self.steps["create-pr"]["needs"], ["docs-sync", "run-e2e-tests"])
        self.assertEqual(self.doc["steps"][-1]["id"], "create-pr")

    def test_the_header_comment_states_the_rules(self):
        head = self.text.split("version:")[0]
        for phrase in ("Only Build, Test and Ship skills", "phases.yaml", "max_parallel",
                       "exclusive: true", "Entry is a ticket id"):
            self.assertIn(phrase, head)


class TestRejectedSkills(unittest.TestCase):
    """Substituting a forbidden skill into the shipped default is refused at
    the line that names it."""

    @classmethod
    def setUpClass(cls):
        cls.text = read(lib.default_workflow_path())
        cls.phases = lib.load_phases()

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-ship-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _substitute(self, skill):
        """Replace docs-sync's `skill:` line with `skill`; return (path, line)."""
        needle = "    skill: docs-sync\n"
        self.assertIn(needle, self.text)
        lines = self.text.splitlines(True)
        line = lines.index(needle) + 1
        lines[line - 1] = "    skill: %s\n" % skill
        path = os.path.join(self.tmp, "ship.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("".join(lines))
        return path, line

    def assertRejected(self, skill):
        path, line = self._substitute(skill)
        with self.assertRaises(lib.WorkflowError) as ctx:
            lib.validate_workflow_file(path)
        self.assertEqual(ctx.exception.line, line, str(ctx.exception))
        self.assertEqual(ctx.exception.path, path)
        self.assertIn(repr(skill), str(ctx.exception))

    def test_merge_pr_is_rejected(self):
        self.assertRejected("merge-pr")

    def test_release_is_rejected(self):
        self.assertRejected("release")

    def test_each_design_skill_is_rejected(self):
        for skill in self.phases["phases"]["design"]:
            with self.subTest(skill=skill):
                self.assertRejected(skill)

    def test_each_utility_skill_is_rejected(self):
        for skill in self.phases["phases"]["utility"]:
            with self.subTest(skill=skill):
                self.assertRejected(skill)

    def test_the_test_alias_is_rejected_as_a_step_skill(self):
        """Steps name registered skills; the alias directory is not one."""
        self.assertRejected("test")

    def test_every_allowed_skill_is_accepted_in_that_position(self):
        for skill in lib.allowed_ship_skills(self.phases):
            with self.subTest(skill=skill):
                path, _line = self._substitute(skill)
                lib.validate_workflow_file(path)


if __name__ == "__main__":
    unittest.main()
