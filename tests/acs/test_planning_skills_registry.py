"""Behavior + registry tests for the PLANNING_SKILLS/WORKFLOW_SKILLS split.

Originating ticket: MAR-77. `create-design` moves out of `WORKFLOW_SKILLS`
into a new `PLANNING_SKILLS` list; `HOOKED_SKILLS` becomes the explicit
three-way concatenation `PRODUCT_SKILLS + WORKFLOW_SKILLS + PLANNING_SKILLS`
so every existing `HOOKED_SKILLS` consumer (dispatch.py, `acs step start`,
clarify.py, metrics_aggregate.py, handoff.py, acs_lib's own
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
WORKFLOW_SCHEMA = os.path.join(REPO_ROOT, "plugins", "acs", "schemas",
                               "workflow.schema.json")

sys.path.insert(0, TESTS_ACS)
sys.path.insert(0, HOOKS_DIR)

import acs_case  # noqa: E402
import acs_lib  # noqa: E402
import acs_lib as lib  # noqa: E402
from acs_lib import workflow  # noqa: E402

metrics_aggregate = importlib.import_module("metrics_aggregate")  # noqa: E402

PINNED_SORTED_HOOKED_SKILLS = [
    "analyze-requirements", "code", "create-api-contract", "create-architecture",
    "create-design", "create-docs", "create-e2e-tests", "create-impl-plan",
    "create-pr", "create-prd", "create-project", "create-requirements",
    "create-test-docs", "create-ticket", "docs-sync", "merge-pr", "review-code",
    "run-e2e-tests", "standardize-project",
]
HOOKED_SKILL_COUNT = len(PINNED_SORTED_HOOKED_SKILLS)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _read_ship_skill():
    return _read(SHIP_SKILL)


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

    def test_hooked_skills_count_matches_the_pinned_membership(self):
        # 15 through MAR-160; the skills-independence refactor hooks the five
        # Build/Test skills (analyze-requirements, create-impl-plan,
        # create-api-contract, create-test-docs, create-e2e-tests), and
        # v0.5.0 adds review-code and run-e2e-tests as steps of their own.
        self.assertEqual(len(acs_lib.HOOKED_SKILLS), HOOKED_SKILL_COUNT)

    def test_sorted_hooked_skills_membership_pinned(self):
        # Count alone cannot catch a silent membership swap -- pin the names.
        self.assertEqual(sorted(acs_lib.HOOKED_SKILLS), PINNED_SORTED_HOOKED_SKILLS)

    def test_create_design_is_hooked(self):
        self.assertIn("create-design", lib.HOOKED_SKILLS)
        # One gate per hooked skill: the dispatch table and the registry are
        # the same list seen from two sides (test_producer_skill_gates asserts
        # the membership direction).
        self.assertEqual(len(lib.HOOKED_SKILLS), HOOKED_SKILL_COUNT)


class DispatchRoutingCase(acs_case.AcsWorkspaceCase):
    """AC-2, restated for v0.5.0: dispatch.py's pre-hook routes create-design
    as a hooked skill, and it takes NO run position because `ship.yaml` does
    not name it -- which is exactly what lets it run on its own (3.11) while
    remaining hooked.

    Taking no run position is not the same as being ungated. create-design is
    gated on its SUBJECT, through `gates.SUBJECT_GATES`, which is consulted
    before the workflow is even resolved: a ticket flagged needs_design opens,
    and anything else is refused. So a refusal here does NOT mean the workflow
    adopted the skill -- test_the_resolved_workflow_does_not_name_it below
    still holds -- it means the subject did not warrant a design."""

    def test_create_design_is_gated_on_its_subject_not_on_a_run_position(self):
        bare = self.pre("create-design")
        self.assertEqual(bare.returncode, 2, bare.stderr)
        self.assertIn("acs pre-create-design: blocked", bare.stderr)
        self.assertNotIn("Traceback", bare.stderr)

        warranted = self.pre("create-design", self.new_ticket("Wishlist", "epic"))
        self.assertEqual(warranted.returncode, 0, warranted.stderr)
        self.assertNotIn("Traceback", warranted.stderr)

    def test_the_resolved_workflow_does_not_name_it(self):
        wf = acs_lib.validate_workflow_file(acs_lib.default_workflow_path())
        self.assertFalse(acs_lib.has_step(wf, "create-design"))


class StepStartChoicesCase(acs_case.AcsWorkspaceCase):
    """AC-2: `acs step start --step` still accepts create-design -- validated
    against the resolved workflow AND the skill directories (4.8), so a
    standalone planning skill is a valid step name even though ship.yaml does
    not list it."""

    def test_create_design_accepted_by_step_start(self):
        epic = self.new_ticket("Wishlist", "epic")
        result = self.start("create-design", epic)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("invalid choice", result.stderr)

    def test_a_step_the_workflow_does_not_name_takes_no_run_position(self):
        """I5: the run's `steps` map admits only what the workflow names. The
        step machine records the invocation either way -- two machines, and
        this is the seam between them (4.3/4.4)."""
        epic = self.new_ticket("Wishlist", "epic")
        out = self.start("create-design", epic)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIs(json.loads(out.stdout)["in_workflow"], False)
        rdir = self.rdir(epic)
        self.assertNotIn("create-design", acs_lib.load_run(rdir)["steps"])
        self.assertEqual(
            acs_lib.last_invocation(
                acs_lib.load_state(rdir, "create-design"))["status"],
            "in_progress")


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
            with open(os.path.join(tdir, "run.json"), "w") as fh:
                json.dump({"ticket_id": "MAR-1", "flow": "ticket", "steps": {}, "totals": {}}, fh)
            out = metrics_aggregate.aggregate(ws, repo_id)
            self.assertIn("create-design", out["panels"]["2"]["steps"])


class HandoffResumeCase(acs_case.AcsWorkspaceCase):
    """AC-2, restated: handoff.py resumes a create-design invocation by name.

    `flow: ticket|product` is retired (6) -- a run's SUBJECT says what it is
    over, and there is no second classification to keep in step with
    PRODUCT_SKILLS. What the hazard guard was really protecting is still
    asserted: the resume names create-design itself, not whatever step the
    workflow would have pointed at."""

    def test_create_design_resumes_via_handoff(self):
        ticket = self.new_ticket("Design system revamp", "story")
        out = self.start("create-design", ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        result = self.run_script("handoff.py", "--summary", "s", "--run", ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["step"], "create-design")
        self.assertEqual(payload["continue_with"], "/acs:create-design %s" % ticket)
        self.assertEqual(payload["stop_reason"], "context_pressure")
        subject = acs_lib.load_run(self.rdir(ticket))["subject"]
        self.assertEqual(subject, {"kind": "ticket", "ticket_id": ticket})


class ShipPipelineOrderTableCase(unittest.TestCase):
    """AC-3 restated for v0.5.0: /acs:ship carries no implementation-step
    table at all, and create-design is not one of its steps -- create-design
    is Design-phase work that runs BEFORE ship, and ship.yaml simply does not
    list it.

    The `requires: design_approved` predicate that used to carry the design
    requirement is gone with every other workflow condition. The requirement
    did not go with it: it moved to `/acs:create-impl-plan`'s own start check,
    where the approval file already lives, and a skill refusing on its own
    input is what makes it independently invocable."""

    @classmethod
    def setUpClass(cls):
        cls.body = _read_ship_skill()

    def test_no_numbered_pipeline_order_table_survives(self):
        self.assertNotIn("## Pipeline order", self.body)

    def test_create_design_is_not_a_ship_workflow_step(self):
        # `steps:` is a LIST of skill names and nothing more (2): no
        # per-path mapping to union over, so membership is the whole question.
        doc = acs_lib.validate_workflow_file(acs_lib.default_workflow_path())
        self.assertNotIn("create-design", workflow.steps_of(doc))

    def test_the_workflow_carries_no_requires_predicate_at_all(self):
        """`requires:` is one of the keys the schema rejects outright, so
        there is no predicate left to block on."""
        schema = json.loads(_read(WORKFLOW_SCHEMA))
        self.assertIs(schema.get("additionalProperties"), False)
        self.assertNotIn("requires", schema.get("properties", {}))
        # The file's own header NAMES the rejected keys, which is the point;
        # the pin is on what it DECLARES, so read the parsed document.
        wf = acs_lib.validate_workflow_file(acs_lib.default_workflow_path())
        self.assertEqual(set(wf) - {"version", "steps", "loops"}, set())

    def test_a_refusal_from_a_step_is_surfaced_verbatim(self):
        """What replaced `blocked_by.pointer`: a step's own pre-hook refuses
        on its own missing input, naming which skill produces it, and
        /acs:ship relays that stderr unchanged rather than deciding for itself
        that design is needed."""
        handling = _section(self.body, "## Handling the handoff")
        self.assertIsNotNone(
            re.search(r"(?s)pre-hook exit 2.{0,400}verbatim", handling),
            "ship must surface a hook refusal verbatim")
        self.assertIsNotNone(
            re.search(r"(?s)verbatim.{0,300}which skill produces it", handling),
            "the refusal names the skill that produces the missing input")


if __name__ == "__main__":
    unittest.main()
