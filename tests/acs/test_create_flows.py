"""ADR-0126: /acs:create-flows, the ticket's behavioural low-level design.

- create-flows is a hooked, ticket-scoped Design skill owning three roles: the
  designer (write; survey pass and parallel write slices), the gap-analyst (survey,
  one per code area beside the survey) and the reviewer (judge, three slices).
- Documents only, under lld/<feature>/flows/ (and components/ only when enabled),
  only for the enabled lld_types; versioned with `acs.py design`; the written paths
  recorded in `states.files` for /acs:analyze-requirements' publish to commit.
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


def flat(*parts):
    with open(os.path.join(PLUGIN, *parts), encoding="utf-8") as fh:
        return " ".join(fh.read().split())


class RegistryTest(unittest.TestCase):

    def test_create_flows_is_hooked_and_owns_three_roles(self):
        self.assertIn("create-flows", lib.HOOKED_SKILLS)
        self.assertIn("create-flows", lib.PLANNING_SKILLS)
        self.assertEqual(lib.skills_registry.agent_roles_of("create-flows"),
                         ["designer", "gap-analyst", "reviewer"])

    def test_the_roles_are_a_writer_a_survey_and_a_judge_with_model_defaults(self):
        self.assertEqual(lib.ROLE_KINDS["designer"], "write")
        self.assertEqual(lib.ROLE_KINDS["gap-analyst"], "survey")
        self.assertEqual(lib.ROLE_KINDS["reviewer"], "judge")
        for role in ("designer", "gap-analyst", "reviewer"):
            self.assertIn(role, lib.models.covered_roles())

    def test_the_owned_types_are_in_the_lld_catalog(self):
        for tid in ("sequence", "activity", "state", "component-detail", "class"):
            self.assertIn(tid, lib.design_types.LLD_TYPES)


class CreateFlowsStartsOnATicketTest(AcsWorkspaceCase):

    def test_step_start_with_a_ticket_and_finish(self):
        ticket = self.new_ticket("Wishlist sharing", "story")
        start = self.run_script("acs.py", "step", "start", "--step", "create-flows",
                                "--ticket", ticket)
        self.assertEqual(start.returncode, 0, start.stderr)
        ctx = json.loads(start.stdout)
        self.assertEqual(ctx["ticket_id"], ticket)
        self.assertEqual(ctx["agents"].get("designer"), "acs:create-flows-designer")
        self.assertEqual(ctx["agents"].get("gap-analyst"), "acs:create-flows-gap-analyst")
        self.assertEqual(ctx["agents"].get("reviewer"), "acs:create-flows-reviewer")
        flow = "docs/architecture/lld/wishlist/flows/share-list.md"
        result = {"status": "completed", "summary": "1 flow, 1 state machine",
                  "states": {"feature": ["wishlist"],
                             "files": [flow, "docs/architecture/lld/wishlist/flows/state-wishlist.md"],
                             "types": ["sequence", "state"],
                             "gaps": {"undocumented": 0, "unimplemented": 0, "drifted": 0},
                             "flows": 1, "state_machines": 1}}
        done = self.run_script("post-create-flows.py", stdin=json.dumps(result))
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        # The step concludes; the ticket's run goes on to its Build steps.
        self.assertEqual((out["skill"], out["run_id"], out["status"]),
                         ("create-flows", ticket, "completed"))


class SkillProseTest(unittest.TestCase):

    def setUp(self):
        self.body = flat("skills", "create-flows", "SKILL.md")

    def test_documents_only(self):
        for phrase in ("**Documents only**", "never write source code, migrations or "
                       "machine-readable contracts"):
            self.assertIn(phrase, self.body)

    def test_only_enabled_types_are_written(self):
        for phrase in ("Only the enabled `settings.design.lld_types` it owns are written; "
                       "a disabled type is never written.",
                       "no flow types enabled in design.lld_types",
                       "`component-detail` or `class` enabled",
                       "`components/<component>.md` | `component-detail`, `class` — only when enabled"):
            self.assertIn(phrase, self.body)

    def test_write_slices_in_one_message_under_the_cap(self):
        for phrase in ("Spawn every write slice in ONE message (at most "
                       "`settings.parallel.max_agents` per wave)",
                       "`write-<flow>`", "`write-states`", "`write-components`",
                       "run_in_background: false",
                       "Spawn in the foreground and wait on the result, never on a clock."):
            self.assertIn(phrase, self.body)

    def test_integration_only_on_a_seam(self):
        for phrase in ("no seam → straight to review",
                       "ONE more designer, alone, `slice=\"integration\"`",
                       "Integration only on a seam"):
            self.assertIn(phrase, self.body)

    def test_sequence_and_state_must_agree(self):
        self.assertIn("a sequence message that changes an entity's state is a transition "
                      "in that entity's state machine, and every transition is triggered "
                      "by a sequence message or a named external event; every activity "
                      "details one sequence step", self.body)
        for phrase in ("`agreement`", "`references`", "`form`"):
            self.assertIn(phrase, self.body)

    def test_versions_name_the_feature(self):
        self.assertIn("design init --status <proposed|implemented> --ticket <id> "
                      "--feature <slug>", self.body)
        self.assertIn("design bump --ticket <id>", self.body)

    def test_zero_dollar_checks_run_beside_the_review(self):
        for phrase in ("design check <every written file>", "mermaid_lint.py",
                       "structure_lint.py\" --sections", "--ordered",
                       "blocking findings of THIS iteration"):
            self.assertIn(phrase, self.body)

    def test_written_files_are_recorded_for_the_publish(self):
        for phrase in ("record EVERY written path, repo-relative, in result `states.files`",
                       "/acs:analyze-requirements' publish commits the recorded "
                       "`states.files` with the ticket folder",
                       "\"state_machines\"", "\"flows\""):
            self.assertIn(phrase, self.body)

    def test_features_come_from_the_ticket(self):
        for phrase in ("`context.ticket.features`", "acs.py\" slug --text",
                       "ticket save --ticket <id> --from -"):
            self.assertIn(phrase, self.body)


class AgentProseTest(unittest.TestCase):

    def test_the_designer_writes_only_its_slice_and_reports_seams(self):
        body = flat("agents", "create-flows-designer.md")
        for phrase in ("## When you are one slice", "## When you are the integration pass",
                       "write ONLY the files `files` names", "\"seams\":",
                       "State machine inventory", "--feature <feature>",
                       "classDef planned stroke-dasharray: 5 5",
                       "## Grounding (anti-hallucination)"):
            self.assertIn(phrase, body)

    def test_the_reviewer_runs_its_slice_dimensions(self):
        body = flat("agents", "create-flows-reviewer.md")
        for phrase in ("## When you are one slice", "**sequence-state-agreement**",
                       "**activity-sequence-agreement**", "**documents-only**",
                       "`severity=\"info\"` finding — not a hard failure",
                       "police grounding", "Precision is not the test; truth is."):
            self.assertIn(phrase, body)

    def test_the_gap_analyst_classifies_three_ways_with_two_citations(self):
        body = flat("agents", "create-flows-gap-analyst.md")
        for phrase in ("**unimplemented**", "**undocumented**", "**drifted**",
                       "A gap is a fact with two citations", "## Unverified",
                       "iter-<n>/gap-analyst-<area>.json"):
            self.assertIn(phrase, body)


if __name__ == "__main__":
    unittest.main()
