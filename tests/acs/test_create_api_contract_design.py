"""ADR-0134: /acs:create-api-contract is a Design skill that writes documents only.

The deterministic half of the move (the prose half is
tests/acs/test_create_api_contract.py):

- it is a hooked Design skill (PLANNING_SKILLS), no step of `ship.yaml`, and
  owns three roles: the contract-author (write), the contract-reviewer (judge)
  and the gap-analyst (survey), like create-data-design;
- it runs on any subject -- an epic included, since Design runs on epics --
  with no epic brake and no plan-decided no-op;
- it completes `contract_written`, or `type_disabled` when the `api-contract`
  LLD type is off; `no_surface_owed` is gone;
- its recorded paths are committed in the `design` layer.

Run:  python3 -m unittest tests.acs.test_create_api_contract_design -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib as lib  # noqa: E402
from acs_lib import commit_plan, stepgate  # noqa: E402

SKILL = "create-api-contract"
ROLES = ["contract-author", "contract-reviewer", "gap-analyst"]


class RegistryTest(unittest.TestCase):

    def test_it_is_a_hooked_design_skill_and_no_step_of_ship(self):
        self.assertIn(SKILL, lib.HOOKED_SKILLS)
        self.assertIn(SKILL, lib.PLANNING_SKILLS)
        self.assertNotIn(SKILL, lib.WORKFLOW_SKILLS)
        wf = lib.validate_workflow_file(lib.default_workflow_path())
        self.assertFalse(lib.has_step(wf, SKILL))

    def test_it_owns_three_roles_with_their_kinds_and_model_defaults(self):
        self.assertEqual(lib.skills_registry.agent_roles_of(SKILL), ROLES)
        self.assertEqual(lib.ROLE_KINDS["contract-author"], "write")
        self.assertEqual(lib.ROLE_KINDS["contract-reviewer"], "judge")
        self.assertEqual(lib.ROLE_KINDS["gap-analyst"], "survey")
        for role in ROLES:
            self.assertIn(role, lib.models.covered_roles())

    def test_no_plan_decides_whether_it_runs(self):
        self.assertNotIn(SKILL, stepgate.NO_OP_STEPS)
        self.assertNotIn("api_contract", lib.plan_contract.OWES_KEYS)

    def test_its_outcomes_are_written_or_type_disabled(self):
        self.assertEqual(lib.outcome_vocabulary(SKILL), ["contract_written", "type_disabled"])

    def test_it_owns_the_api_contract_lld_type(self):
        self.assertIn("api-contract", lib.design_types.LLD_TYPES)
        self.assertIn("api-contract", lib.design_types.defaults()["lld_types"])

    def test_its_paths_are_committed_with_the_design_docs(self):
        self.assertEqual(commit_plan.SKILL_LAYER[SKILL], "design")


class StartedOnAnEpicTest(AcsWorkspaceCase):
    """Design runs on epics (ADR-0128): the pre-hook and `step start` let it."""

    def result(self, ctx, doc):
        path = os.path.join(ctx["partition"], "steps", SKILL, "result.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        return self.run_script("post-%s.py" % SKILL, "--result-file", path)

    def start(self, tid):
        out = self.run_script("acs.py", "step", "start", "--step", SKILL, "--ticket", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_the_pre_hook_opens_on_an_epic(self):
        epic = self.new_ticket("Checkout revamp", "epic")
        out = self.pre(SKILL, epic)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("blocked", out.stderr)

    def test_step_start_names_the_agents_and_a_written_contract_completes(self):
        epic = self.new_ticket("Checkout revamp", "epic")
        ctx = self.start(epic)
        self.assertEqual(ctx["ticket_id"], epic)
        for role in ROLES:
            self.assertEqual(ctx["agents"].get(role), "acs:%s-%s" % (SKILL, role))
        self.assertIn("api-contract", ctx["settings"]["design"]["lld_types"])

        api = "docs/architecture/lld/checkout/api/orders.md"
        done = self.result(ctx, {
            "status": "completed", "outcome": "contract_written",
            "summary": "orders API for checkout",
            "states": {"contract_path": "docs/architecture/lld/checkout/%s/api-contract.md"
                       % epic, "feature": ["checkout"], "files": [api],
                       "types": ["api-contract"], "interfaces": [api], "items": 3,
                       "traced_acs": ["AC-1"],
                       "gaps": {"unimplemented": 0, "undocumented": 1, "drifted": 0}},
            "findings": [], "errors": []})
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_disabled_type_completes_as_a_recorded_no_op(self):
        tid = self.new_ticket("Wishlist sharing", "story")
        ctx = self.start(tid)
        done = self.result(ctx, {
            "status": "completed", "outcome": "type_disabled",
            "summary": "the api-contract type is not enabled in design.lld_types",
            "states": {"feature": [], "files": [], "types": [], "interfaces": [],
                       "items": 0, "traced_acs": []},
            "findings": [], "errors": []})
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_the_retired_no_surface_owed_outcome_is_refused(self):
        tid = self.new_ticket("Wishlist sharing", "story")
        ctx = self.start(tid)
        done = self.result(ctx, {
            "status": "completed", "outcome": "no_surface_owed", "summary": "x",
            "states": {}, "findings": [], "errors": []})
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("no_surface_owed", done.stderr)


if __name__ == "__main__":
    unittest.main()
