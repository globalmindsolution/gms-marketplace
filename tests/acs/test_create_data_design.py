"""ADR-0126: /acs:create-data-design, the ticket's data low-level design.

- create-data-design is a hooked, ticket-scoped Design skill owning three roles: the
  designer (write), the gap-analyst (survey) and the reviewer (judge).
- Documents only: the logical ERD and the physical schema under
  lld/<feature>/data/, never migration code; only the enabled lld_types; every
  document versioned with `design init --feature`; the gap analysts run in the SAME
  message as the survey; every written path recorded in `states.files` and left as a local
  change for the user to review and commit (no branch, commit or PR).
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

SKILL = "create-data-design"
ROLES = ["designer", "gap-analyst", "reviewer"]


def flat(*parts):
    with open(os.path.join(PLUGIN, *parts), encoding="utf-8") as fh:
        return " ".join(fh.read().split())


def read_hint():
    with open(os.path.join(PLUGIN, "skills", SKILL, "SKILL.md"), encoding="utf-8") as fh:
        return next(line for line in fh if line.startswith("argument-hint:")).strip()


class RegistryTest(unittest.TestCase):

    def test_create_data_design_is_hooked_and_owns_three_roles(self):
        self.assertIn(SKILL, lib.HOOKED_SKILLS)
        self.assertIn(SKILL, lib.PLANNING_SKILLS)
        self.assertEqual(lib.skills_registry.agent_roles_of(SKILL), ROLES)

    def test_the_roles_are_reused_with_their_kinds_and_model_defaults(self):
        self.assertEqual(lib.ROLE_KINDS["designer"], "write")
        self.assertEqual(lib.ROLE_KINDS["gap-analyst"], "survey")
        self.assertEqual(lib.ROLE_KINDS["reviewer"], "judge")
        for role in ROLES:
            self.assertIn(role, lib.models.covered_roles())


class StartedWithATicketTest(AcsWorkspaceCase):

    def test_step_start_names_the_agents_and_the_post_hook_accepts_a_result(self):
        tid = self.new_ticket("Wishlist sharing", "story")
        start = self.run_script("acs.py", "step", "start", "--step", SKILL, "--ticket", tid)
        self.assertEqual(start.returncode, 0, start.stderr)
        ctx = json.loads(start.stdout)
        self.assertEqual(ctx["ticket_id"], tid)
        for role in ROLES:
            self.assertEqual(ctx["agents"].get(role), "acs:%s-%s" % (SKILL, role))
        self.assertIn("logical-erd", ctx["settings"]["design"]["lld_types"])
        self.assertIn("physical-schema", ctx["settings"]["design"]["lld_types"])

        rel = "docs/architecture/lld/wishlist/data/logical-erd.md"
        doc = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(doc))
        with open(doc, "w", encoding="utf-8") as fh:
            fh.write("# Logical ERD\n")
        init = self.run_script("acs.py", "design", "init", "--status", "proposed",
                               "--ticket", tid, "--feature", "wishlist", doc)
        self.assertEqual(init.returncode, 0, init.stderr)
        check = json.loads(self.run_script("acs.py", "design", "check", doc).stdout)
        self.assertTrue(check["ok"], check)

        result = {"status": "completed", "summary": "logical ERD for wishlist",
                  "states": {"feature": ["wishlist"], "files": [rel],
                             "types": ["logical-erd"], "entities": 2,
                             "gaps": {"undocumented": 0, "unimplemented": 0, "drifted": 0}},
                  "findings": [], "errors": []}
        path = os.path.join(ctx["partition"], "steps", SKILL, "result.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh)
        done = self.run_script("post-%s.py" % SKILL, "--result-file", path)
        self.assertEqual(done.returncode, 0, done.stderr)

        with open(os.path.join(ctx["partition"], "steps", SKILL, "result.json"),
                  encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["states"]["files"], result["states"]["files"])


class ProseContractTest(unittest.TestCase):

    def test_the_skill_writes_documents_only_never_migration_code(self):
        body = flat("skills", SKILL, "SKILL.md")
        for phrase in ("**Documents only**", "never write source code, migration code",
                       "**never migration code**", "`logical-erd.md`", "`physical-schema.md`",
                       "lld/<feature>/data/", "`erDiagram`", "Migration outline"):
            self.assertIn(phrase, body)

    def test_only_the_enabled_lld_types_are_written(self):
        body = flat("skills", SKILL, "SKILL.md")
        for phrase in ("Only the enabled `settings.design.lld_types` it owns are written",
                       "a disabled type is never written",
                       "no data types enabled in design.lld_types"):
            self.assertIn(phrase, body)

    def test_documents_are_versioned_with_their_feature(self):
        body = flat("skills", SKILL, "SKILL.md")
        self.assertIn("design init --status <proposed|implemented> --ticket <id> --feature <slug>",
                      body)
        self.assertIn("design bump --ticket <id>", body)
        self.assertIn("`%% planned` comment", body)
        self.assertIn("--feature <feature>", flat("agents", "%s-designer.md" % SKILL))
        # A ticketless run versions its documents without a ticket (ADR-0128).
        self.assertIn("On a run with no ticket drop `--ticket <id>`", body)

    def test_no_ticket_is_required_and_the_feature_has_three_sources(self):
        """ADR-0128: a feature slug, a prompt or a document is enough; the
        feature comes from the argument, the requirements, or the ticket."""
        body = flat("skills", SKILL, "SKILL.md")
        self.assertIn('step start --step create-data-design --args "$ARGUMENTS"', body)
        self.assertIn("No ticket is required", body)
        for phrase in ("**the argument**",
                       "`requirements.feature`, else `requirements.features`",
                       "`context.ticket.features`", "requirements refine --from -",
                       "never call `ticket save` on a run with no ticket",
                       "**Requirements: `context.requirements` / `acs.py requirements show`"):
            self.assertIn(phrase, body)
        self.assertNotIn("No ticket id → ask the user", body)
        self.assertNotIn("--ticket <ticket-id>", body)
        self.assertRegex(read_hint(), r'^argument-hint: "\[ticket-id\] \[feature-slug\] ')

    def test_gap_analysts_run_in_the_same_message_as_the_survey(self):
        body = flat("skills", SKILL, "SKILL.md")
        for phrase in ("In the SAME message as the survey", "one gap analyst per survey area",
                       "settings.parallel.max_agents", "run_in_background: false",
                       "acs.py notes merge", "iter-1/gaps.md"):
            self.assertIn(phrase, body)

    def test_one_writer_three_reviewer_slices_and_the_zero_cost_checks(self):
        body = flat("skills", SKILL, "SKILL.md")
        for phrase in ('ONE designer, `slice="write"`', "| `model` |", "| `conventions` |",
                       "| `form` |", "design check", "mermaid_lint.py", "structure_lint.py",
                       "--ordered", "never \"pass with a missing slice\""):
            self.assertIn(phrase, body)

    def test_documents_stay_local_and_every_path_is_recorded(self):
        body = flat("skills", SKILL, "SKILL.md")
        for phrase in ("Record EVERY written path, repo-relative, in result `states.files`",
                       "no branch, no commit, no PR", '"files": ['):
            self.assertIn(phrase, body)

    def test_the_designer_never_writes_migration_code(self):
        body = flat("agents", "%s-designer.md" % SKILL)
        for phrase in ("**documents only**", "Never write migration code",
                       "Migration outline", "## Grounding (anti-hallucination)"):
            self.assertIn(phrase, body)

    def test_the_gap_analyst_classifies_with_two_citations(self):
        body = flat("agents", "%s-gap-analyst.md" % SKILL)
        for phrase in ("A gap is a fact with two citations", "## Unverified",
                       "**unimplemented**", "**undocumented**", "**drifted**",
                       "never run a migration"):
            self.assertIn(phrase, body)

    def test_the_reviewer_judges_logical_physical_agreement_and_documents_only(self):
        body = flat("agents", "%s-reviewer.md" % SKILL)
        for phrase in ("**logical-physical-agreement**", "**hld-conformance**",
                       "**documents-only**", "baseline-status.txt", "police grounding",
                       "Precision is not the test; truth is."):
            self.assertIn(phrase, body)


if __name__ == "__main__":
    unittest.main()
