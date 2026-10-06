"""ADR-0138: /acs:breakdown-ticket and create-ticket's typed authors, at the
hook-library layer.

  * `breakdown-ticket` is a hooked ticket-flow skill (WORKFLOW_SKILLS, so
    HOOKED_SKILLS) that is no step of ship.yaml -- like create-ticket -- with
    its own pre/post hook scripts, its commit layer and its clarification
    ledger name;
  * its subject gate: one parent ticket that exists, is live, is not done and
    is not a bug (epics, stories and tasks are broken down); a prompt with no
    ticket is refused toward /acs:create-ticket;
  * `step start` re-applies that gate on a host that never fires the hook;
  * the epic brake points at /acs:breakdown-ticket, no longer at
    create-ticket's retired `--fan-out`;
  * create-ticket's five roles: four `write` authors, one per ticket type, and
    the existing `reviewer` judge -- kinds, scaffold values and the models
    schema fragment.

Run:  python3 -m unittest tests.acs.test_breakdown_ticket_registry -v
"""

import inspect
import json
import os
import sys
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

from acs_case import AcsWorkspaceCase, lib  # noqa: E402

from acs_lib import commit_plan, gates, models, skills  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_ACS))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
SKILL = "breakdown-ticket"
AUTHORS = ("epic-author", "story-author", "task-author", "bug-author")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class RegistryTest(unittest.TestCase):

    def test_a_hooked_ticket_flow_skill(self):
        self.assertIn(SKILL, lib.WORKFLOW_SKILLS)
        self.assertIn(SKILL, lib.HOOKED_SKILLS)
        for other in (lib.PRODUCT_SKILLS, lib.PLANNING_SKILLS, lib.AUDIT_SKILLS,
                      lib.UNHOOKED_SKILLS, lib.STANDALONE_RUN_SKILLS):
            self.assertNotIn(SKILL, other)

    def test_no_step_of_ship(self):
        wf = lib.validate_workflow_file(lib.default_workflow_path())
        self.assertFalse(lib.workflow.has_step(wf, SKILL))
        self.assertFalse(lib.workflow.has_step(wf, "create-ticket"))

    def test_its_hook_scripts_mirror_create_tickets(self):
        for kind in ("pre", "post"):
            path = os.path.join(SCRIPTS, "%s-%s.py" % (kind, SKILL))
            self.assertTrue(os.path.isfile(path), path)
            body = read(path)
            self.assertIn('run_%s("%s")' % (kind, SKILL), body)
            self.assertTrue(os.access(path, os.X_OK), "%s must be executable" % path)

    def test_its_commit_layer_is_the_ticket_docs(self):
        self.assertEqual(commit_plan.SKILL_LAYER[SKILL], "ticket-docs")
        self.assertEqual(commit_plan.SKILL_LAYER["create-ticket"], "ticket-docs")

    def test_the_clarification_ledger_names_it(self):
        schema = json.loads(read(os.path.join(PLUGIN, "schemas", "clarifications.schema.json")))
        self.assertIn(SKILL, json.dumps(schema))
        enum = schema["properties"]["clarifications"]["items"]["properties"]["skill"]["enum"]
        self.assertIn(SKILL, enum)

    def test_its_subject_gate_is_registered(self):
        self.assertIs(gates.SUBJECT_GATES[SKILL], gates.gate_breakdown_ticket)

    def test_it_owns_no_agents(self):
        self.assertNotIn(SKILL, models.inventory())


class EpicBrakeMessageTest(unittest.TestCase):

    def test_the_epic_brake_points_at_breakdown_ticket(self):
        src = inspect.getsource(lib._refuse_epic)
        self.assertIn("/acs:breakdown-ticket %s", src)
        self.assertNotIn("fan-out", src)
        self.assertNotIn("/acs:create-ticket", src)


class RolesTest(unittest.TestCase):

    def test_the_authors_are_write_roles_and_the_reviewer_a_judge(self):
        for role in AUTHORS:
            self.assertEqual(skills.ROLE_KINDS[role], "write", role)
        self.assertEqual(skills.ROLE_KINDS["reviewer"], "judge")

    def test_the_authors_are_scaffolded_like_the_other_writers(self):
        for role in AUTHORS:
            self.assertEqual(models.recommended(role),
                             {"model": models.SONNET, "effort": "medium"}, role)

    def test_create_ticket_owns_the_five_roles(self):
        self.assertEqual(models.inventory().get("create-ticket"),
                         ["bug-author", "epic-author", "reviewer", "story-author",
                          "task-author"])

    def test_each_agent_name_splits_to_create_ticket(self):
        for role in AUTHORS + ("reviewer",):
            self.assertEqual(lib.split_agent_name("create-ticket-" + role),
                             ("create-ticket", role))

    def test_the_settings_schema_and_scaffold_carry_them(self):
        schema = json.loads(read(os.path.join(PLUGIN, "schemas", "settings.schema.json")))
        props = schema["properties"]["models"]["properties"]["create-ticket"]["properties"]
        self.assertEqual(sorted(props), sorted(AUTHORS + ("reviewer",)))
        settings = json.loads(read(os.path.join(REPO_ROOT, ".acs", "settings.json")))
        block = settings["models"]["create-ticket"]
        for role in AUTHORS + ("reviewer",):
            self.assertEqual(block[role], models.recommended(role), role)


class GateTest(AcsWorkspaceCase):

    def mint(self, tid, ttype, status="open", archived=False):
        base = (os.path.join(lib.archive_dir(self.ws, "acme-shop"), tid) if archived
                else lib.ticket_dir(self.ws, "acme-shop", tid))
        os.makedirs(base, exist_ok=True)
        ticket = lib.new_ticket_doc(tid, "T " + tid, ttype, status=status)
        lib.save_ticket(base, ticket)
        lib.update_index(self.ws, "acme-shop", ticket, archived=archived)

    def test_an_epic_passes(self):
        self.mint("SHOP-10", "epic")
        out = self.pre(SKILL, "SHOP-10")
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_a_story_and_a_task_pass(self):
        for tid, ttype in (("SHOP-11", "story"), ("SHOP-12", "task")):
            self.mint(tid, ttype)
            out = self.pre(SKILL, tid)
            self.assertEqual(out.returncode, 0, "%s: %s" % (ttype, out.stderr))

    def test_the_gate_opens_no_run(self):
        self.mint("SHOP-10", "epic")
        self.pre(SKILL, "SHOP-10")
        self.assertIsNone(lib.load_run(self.rdir("SHOP-10")))

    def test_a_bug_is_refused(self):
        self.mint("SHOP-13", "bug")
        out = self.pre(SKILL, "SHOP-13")
        self.assertEqual(out.returncode, 2)
        self.assertIn("is a bug", out.stderr)
        self.assertIn("/acs:create-ticket", out.stderr)

    def test_a_done_ticket_is_refused(self):
        self.mint("SHOP-14", "story", status="done")
        out = self.pre(SKILL, "SHOP-14")
        self.assertEqual(out.returncode, 2)
        self.assertIn("done", out.stderr)

    def test_an_archived_ticket_is_refused(self):
        self.mint("SHOP-15", "epic", status="done", archived=True)
        out = self.pre(SKILL, "SHOP-15")
        self.assertEqual(out.returncode, 2)
        self.assertIn("archived", out.stderr)

    def test_an_unknown_ticket_is_refused(self):
        out = self.pre(SKILL, "SHOP-99")
        self.assertEqual(out.returncode, 2)
        self.assertIn("SHOP-99", out.stderr)

    def test_nothing_to_break_down_is_refused(self):
        out = self.pre(SKILL, "")
        self.assertEqual(out.returncode, 2)
        self.assertIn("/acs:breakdown-ticket SHOP-123", out.stderr)

    def test_two_tickets_are_refused(self):
        self.mint("SHOP-10", "epic")
        self.mint("SHOP-11", "epic")
        out = self.pre(SKILL, "SHOP-10 SHOP-11")
        self.assertEqual(out.returncode, 2)
        self.assertIn("one ticket", out.stderr)

    def test_a_prompt_alone_is_refused_toward_create_ticket(self):
        out = self.pre(SKILL, "the wishlist work")
        self.assertEqual(out.returncode, 2)
        self.assertIn("/acs:create-ticket", out.stderr)

    def test_the_session_pointer_names_the_parent_when_the_args_do_not(self):
        self.mint("SHOP-10", "epic")
        self.ensure_run("SHOP-10")
        out = self.pre(SKILL, "")
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_step_start_takes_the_invocation_args(self):
        """SKILLS' Start: `step start --step breakdown-ticket --args "$ARGUMENTS"`."""
        self.mint("SHOP-17", "story")
        out = self.run_script("acs.py", "step", "start", "--step", SKILL,
                              "--args", "SHOP-17")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIsNotNone(lib.load_run(self.rdir("SHOP-17")))
        self.mint("SHOP-18", "bug")
        out = self.run_script("acs.py", "step", "start", "--step", SKILL,
                              "--args", "SHOP-18")
        self.assertEqual(out.returncode, 2)
        self.assertIn("is a bug", out.stderr)

    def test_the_split_signal_document_rides_along(self):
        self.mint("SHOP-16", "story")
        plan = os.path.join(self.repo, "plan.md")
        with open(plan, "w", encoding="utf-8") as fh:
            fh.write("# plan\n")
        out = self.pre(SKILL, "SHOP-16 plan.md")
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_step_start_reapplies_the_gate(self):
        self.mint("SHOP-13", "bug")
        out = self.run_script("acs.py", "step", "start", "--step", SKILL,
                              "--ticket", "SHOP-13")
        self.assertEqual(out.returncode, 2)
        self.assertIn("is a bug", out.stderr)
        self.assertIsNone(lib.load_run(self.rdir("SHOP-13")))

    def test_step_start_and_the_post_hook_run_over_the_parent(self):
        self.mint("SHOP-10", "epic")
        out = self.run_script("acs.py", "step", "start", "--step", SKILL,
                              "--ticket", "SHOP-10")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIsNotNone(lib.load_run(self.rdir("SHOP-10")))
        out = self.post(SKILL, "SHOP-10", {"status": "completed",
                                           "states": {"children": []}})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(lib.last_status(self.rdir("SHOP-10"), SKILL), "completed")


if __name__ == "__main__":
    unittest.main()
