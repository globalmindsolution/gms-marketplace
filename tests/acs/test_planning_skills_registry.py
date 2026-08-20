"""Behavior + registry tests for the PLANNING_SKILLS/WORKFLOW_SKILLS split.

Originating ticket: MAR-77. `create-design` moves out of `WORKFLOW_SKILLS`
into a new `PLANNING_SKILLS` list; `HOOKED_SKILLS` becomes the explicit
three-way concatenation `PRODUCT_SKILLS + WORKFLOW_SKILLS + PLANNING_SKILLS`
so every existing `HOOKED_SKILLS` consumer (dispatch.py, skill-start.py,
clarify.py, metrics_aggregate.py, handoff.py, acs_lib.py's own GATES/
compute_ticket_totals/session-end sweep) keeps seeing `create-design` with
no code change of its own. `metrics_render.py`'s coverage of the same
invariant is not duplicated here — see
tests/acs/test_metrics_render.py:162-165, which loops
`acs_lib.HOOKED_SKILLS` and asserts each name renders in panel 2.
"""

import importlib
import json
import os
import re
import sys
import unittest
from tempfile import TemporaryDirectory

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_ACS))
HOOKS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
SHIP_SKILL = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "ship", "SKILL.md")

sys.path.insert(0, TESTS_ACS)
sys.path.insert(0, HOOKS_DIR)

import acs_case  # noqa: E402
import acs_lib  # noqa: E402

metrics_aggregate = importlib.import_module("metrics_aggregate")  # noqa: E402

PINNED_SORTED_HOOKED_SKILLS = [
    "code", "create-architecture", "create-design", "create-operations",
    "create-pr", "create-prd", "create-principles", "create-project",
    "create-quality", "create-requirements", "create-standards",
    "create-ticket", "docs-sync", "merge-pr", "standardize-project",
]


def _read_ship_skill():
    with open(SHIP_SKILL, encoding="utf-8") as fh:
        return fh.read()


def _section(body, heading):
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class RegistryShapeCase(unittest.TestCase):
    """AC-1: the three-list shape and unchanged total membership."""

    def test_planning_skills_is_exactly_create_design(self):
        self.assertEqual(acs_lib.PLANNING_SKILLS, ["create-design"])

    def test_create_design_not_in_workflow_skills(self):
        self.assertNotIn("create-design", acs_lib.WORKFLOW_SKILLS)

    def test_create_design_not_in_product_skills(self):
        self.assertNotIn("create-design", acs_lib.PRODUCT_SKILLS)

    def test_create_design_in_hooked_skills(self):
        self.assertIn("create-design", acs_lib.HOOKED_SKILLS)

    def test_hooked_skills_is_three_way_concatenation(self):
        self.assertEqual(
            acs_lib.HOOKED_SKILLS,
            acs_lib.PRODUCT_SKILLS + acs_lib.WORKFLOW_SKILLS + acs_lib.PLANNING_SKILLS,
        )

    def test_hooked_skills_count_unchanged_fifteen(self):
        self.assertEqual(len(acs_lib.HOOKED_SKILLS), 15)

    def test_sorted_hooked_skills_membership_pinned(self):
        # Count alone cannot catch a silent membership swap -- pin the names.
        self.assertEqual(sorted(acs_lib.HOOKED_SKILLS), PINNED_SORTED_HOOKED_SKILLS)

    def test_gates_still_carries_create_design(self):
        self.assertIn("create-design", acs_lib.GATES)
        self.assertEqual(len(acs_lib.GATES), 15)


class DispatchRoutingCase(acs_case.AcsWorkspaceCase):
    """AC-2: dispatch.py's pre-hook still routes create-design through
    gate_create_design. Asserted on the unresolvable-ticket refusal arm
    (_resolve_ticket_for_gate), not the needs_design arm -- the latter is
    sibling ticket MAR-76's to change."""

    def test_create_design_still_gated_not_passed_through(self):
        result = self.pre("create-design")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ticket id", result.stderr)


class SkillStartChoicesCase(acs_case.AcsWorkspaceCase):
    """AC-2: skill-start.py's --skill choices still accept create-design."""

    def test_create_design_accepted_by_skill_start_argparse(self):
        epic = self.new_ticket("Wishlist", "epic")
        result = self.start("create-design", epic)
        self.assertNotIn("invalid choice", result.stderr)


class ClarifySkillChoicesCase(acs_case.AcsWorkspaceCase):
    """AC-2: clarify.py add --skill choices still accept create-design."""

    def test_create_design_accepted_by_clarify_argparse(self):
        ticket = self.new_ticket("Wishlist API", "story")
        result = self.run_script(
            "clarify.py", "add", "--skill", "create-design",
            "--question", "Approve the layout?", "--ticket", ticket,
        )
        self.assertNotIn("invalid choice", result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = json.loads(result.stdout)
        self.assertEqual(entry["skill"], "create-design")


class MetricsAggregateFunnelCase(unittest.TestCase):
    """AC-2: metrics_aggregate.py's panel-2 funnel still counts create-design."""

    def test_create_design_is_a_funnel_key(self):
        with TemporaryDirectory() as ws:
            repo_id = "acme-shop"
            repo_dir = os.path.join(ws, repo_id)
            os.makedirs(repo_dir)
            with open(os.path.join(repo_dir, "tickets-index.json"), "w") as fh:
                json.dump({"tickets": {"MAR-1": {"status": "in_progress", "type": "task"}}}, fh)
            with open(os.path.join(repo_dir, "metrics.json"), "w") as fh:
                json.dump({"prs": {"created": 0, "merged": 0}}, fh)
            tdir = os.path.join(repo_dir, "MAR-1")
            os.makedirs(tdir)
            with open(os.path.join(tdir, "pipeline-state.json"), "w") as fh:
                json.dump({"ticket_id": "MAR-1", "flow": "ticket", "steps": {}, "totals": {}}, fh)
            out = metrics_aggregate.aggregate(ws, repo_id)
            self.assertIn("create-design", out["panels"]["2"]["steps"])


class HandoffScanOrderCase(acs_case.AcsWorkspaceCase):
    """AC-2: handoff.py's in-progress-run resume actually picks create-design
    up as a candidate via HOOKED_SKILLS, and classifies its pipeline flow as
    "ticket" -- the PRODUCT_SKILLS hazard guard (create-design must never be
    folded into PRODUCT_SKILLS, which would silently flip this to
    "product")."""

    def test_create_design_resumes_via_handoff(self):
        ticket = self.new_ticket("Design system revamp", "story")
        tdir = self.tdir(ticket)
        acs_lib.append_in_progress_run(tdir, "create-design", ticket)
        result = self.run_script("handoff.py", "--summary", "s", "--ticket", ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["skill"], "create-design")
        self.assertEqual(payload["continue_with"], "/acs:create-design %s" % ticket)
        pipeline = acs_lib.read_json(os.path.join(tdir, "pipeline-state.json"))
        self.assertEqual(pipeline["flow"], "ticket")


class ShipPipelineOrderTableCase(unittest.TestCase):
    """AC-3: the numbered implementation-step rows no longer list
    create-design, while the design-step rules and the "Picking the next
    step" walk still name it (over-deletion guard, R7)."""

    @classmethod
    def setUpClass(cls):
        cls.body = _read_ship_skill()

    def test_numbered_pipeline_order_rows_omit_create_design(self):
        table = _section(self.body, "## Pipeline order")
        rows = re.findall(r"(?m)^\|\s*\d+\s*\|\s*(\S[^|]*?)\s*\|", table)
        self.assertNotIn("create-design", rows,
                         "numbered Pipeline order rows must not list create-design: %r" % rows)

    def test_design_step_rules_still_name_create_design(self):
        section_start = self.body.index("Design step rules")
        next_heading = re.search(r"\n## ", self.body[section_start:])
        rules = self.body[section_start:section_start + next_heading.start()] \
            if next_heading else self.body[section_start:]
        self.assertIn("create-design", rules)

    def test_picking_next_step_walk_still_names_create_design(self):
        section_start = self.body.index("## Picking the next step")
        next_heading = re.search(r"\n## ", self.body[section_start + 1:])
        walk = self.body[section_start:section_start + 1 + next_heading.start()] \
            if next_heading else self.body[section_start:]
        self.assertIn("create-design", walk)


if __name__ == "__main__":
    unittest.main()
