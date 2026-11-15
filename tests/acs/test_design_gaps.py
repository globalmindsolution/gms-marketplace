"""ADR-0122: design versions and design <-> code gap detection.

- acs_lib.design_docs and `acs.py design check|init|bump|status`: the version
  front matter every HLD/LLD document carries, set only through legal transitions.
- The gap-analyst role: create-architecture spawns it beside its survey; the
  standalone /acs:audit-design runs it over the whole architecture set.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib as lib  # noqa: E402
from acs_lib import design_docs as D  # noqa: E402


def write_report(partition, skill):
    """The built-in template with every section empty: a valid, all-zero report."""
    with open(os.path.join(PLUGIN, "templates", "%s-report.md" % skill), encoding="utf-8") as fh:
        text = fh.read()
    path = os.path.join(partition, "steps", skill, "iter-1", "report.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def flat(path):
    with open(path, encoding="utf-8") as fh:
        return " ".join(fh.read().split())


class DocCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-design-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def doc(self, rel, text="# Doc\n\nBody line.\n"):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path


class FrontMatterTest(DocCase):

    def test_a_document_without_front_matter_is_reported(self):
        out = D.check(self.doc("hld/overview.md"))
        self.assertEqual(out["status"], None)
        self.assertTrue(out["problems"])

    def test_init_writes_a_valid_block_and_keeps_the_body(self):
        path = self.doc("hld/overview.md")
        self.assertTrue(D.init(path, "implemented", "SHOP-1"))
        front, body = D.read(path)
        self.assertEqual(front, {"status": "implemented", "version": 1, "tickets": ["SHOP-1"]})
        self.assertIn("Body line.", body)
        self.assertEqual(D.check(path)["problems"], [])

    def test_init_leaves_a_versioned_document_alone(self):
        path = self.doc("hld/overview.md")
        D.init(path, "proposed", "SHOP-1")
        self.assertFalse(D.init(path, "implemented", "SHOP-2"))
        self.assertEqual(D.read(path)[0]["status"], "proposed")

    def test_an_lld_document_must_name_its_feature(self):
        path = self.doc("lld/wishlist/api/wishlist.md")
        with self.assertRaises(lib.GateError):
            D.init(path, "proposed", "SHOP-1")
        self.assertTrue(D.init(path, "proposed", "SHOP-1", feature="wishlist"))
        self.assertEqual(D.check(path)["problems"], [])

    def test_bad_values_are_named(self):
        path = self.doc("hld/x.md", "---\nstatus: done\nversion: 0\ntickets: [\"nope\"]\n---\n# X\n")
        problems = " ".join(D.check(path)["problems"])
        for needle in ("status", "version", "tickets"):
            self.assertIn(needle, problems)


class TransitionTest(DocCase):

    def versioned(self, status="proposed"):
        path = self.doc("hld/overview.md")
        D.init(path, status, "SHOP-1")
        return path

    def test_the_lifecycle(self):
        path = self.versioned()
        D.set_status(path, "approved", "SHOP-1")
        D.set_status(path, "implemented", "SHOP-2")
        front = D.read(path)[0]
        self.assertEqual(front["status"], "implemented")
        self.assertEqual(front["tickets"], ["SHOP-1", "SHOP-2"])

    def test_proposed_cannot_jump_to_implemented(self):
        path = self.versioned()
        with self.assertRaises(lib.GateError) as ctx:
            D.set_status(path, "implemented")
        self.assertIn("not a legal transition", str(ctx.exception))
        self.assertEqual(D.read(path)[0]["status"], "proposed")

    def test_deprecated_is_final(self):
        path = self.versioned()
        D.set_status(path, "deprecated")
        for status in ("proposed", "approved", "implemented"):
            with self.assertRaises(lib.GateError):
                D.set_status(path, status)
        with self.assertRaises(lib.GateError):
            D.bump(path, "SHOP-3")

    def test_a_change_bumps_and_reopens(self):
        path = self.versioned("implemented")
        front = D.bump(path, "SHOP-2")
        self.assertEqual((front["version"], front["status"]), (2, "proposed"))
        self.assertEqual(front["tickets"], ["SHOP-1", "SHOP-2"])

    def test_writes_refuse_an_unversioned_document(self):
        path = self.doc("hld/overview.md")
        for call in (lambda: D.bump(path), lambda: D.set_status(path, "approved")):
            with self.assertRaises(lib.GateError):
                call()


class CliTest(AcsWorkspaceCase):

    def doc(self, rel):
        path = os.path.join(self.repo, "docs", "architecture", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# Doc\n")
        return path

    def acs(self, *args):
        return self.run_script("acs.py", "design", *args)

    def test_check_init_bump_status(self):
        path = self.doc("hld/overview.md")
        out = self.acs("check", path)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(json.loads(out.stdout)["ok"])
        self.assertEqual(self.acs("init", "--status", "proposed", "--ticket", "ACS-1",
                                  path).returncode, 0)
        self.assertTrue(json.loads(self.acs("check", path).stdout)["ok"])
        self.assertEqual(self.acs("status", "--set", "approved", path).returncode, 0)
        bumped = json.loads(self.acs("bump", "--ticket", "ACS-2", path).stdout)
        self.assertEqual(bumped["files"][0]["version"], 2)

    def test_an_illegal_transition_exits_2(self):
        path = self.doc("hld/overview.md")
        self.acs("init", "--status", "proposed", path)
        out = self.acs("status", "--set", "implemented", path)
        self.assertEqual(out.returncode, 2)
        self.assertIn("not a legal transition", out.stderr)

    def test_a_missing_document_exits_2(self):
        out = self.acs("check", os.path.join(self.repo, "nope.md"))
        self.assertEqual(out.returncode, 2)


class AuditDesignRunsWithoutATicketTest(AcsWorkspaceCase):

    def start(self, *extra):
        start = self.run_script("acs.py", "step", "start", "--step", "audit-design", *extra)
        self.assertEqual(start.returncode, 0, start.stderr)
        return json.loads(start.stdout)

    def finish(self, ctx):
        write_report(ctx["partition"], "audit-design")
        result = {"status": "completed", "summary": "no gaps",
                  "states": {"audit": {"scope": "all", "drifted": 0}}}
        done = self.run_script("post-audit-design.py", stdin=json.dumps(result))
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_a_fresh_checkout_gets_a_run_that_the_post_hook_concludes(self):
        ctx = self.start("--args", "wishlist")
        self.assertEqual(ctx["agents"].get("gap-analyst"), "acs:audit-design-gap-analyst")
        out = self.finish(ctx)
        self.assertEqual((out["run_id"], out["run_status"]), (ctx["run_id"], "completed"))
        # Concluded and unpointed: the next audit opens a run of its own.
        self.assertNotEqual(self.start()["run_id"], ctx["run_id"])

    def test_a_run_opened_for_the_audit_is_resumed(self):
        new = self.run_script("acs.py", "run", "new", "--prompt", "audit the design: all")
        self.assertEqual(new.returncode, 0, new.stderr)
        run_id = json.loads(new.stdout)["run_id"]
        self.assertEqual(self.start()["run_id"], run_id)


class RegistryTest(unittest.TestCase):

    def test_gap_analyst_is_a_survey_role_with_a_model_default(self):
        self.assertEqual(lib.ROLE_KINDS["gap-analyst"], "survey")
        self.assertIn("gap-analyst", lib.models.covered_roles())

    def test_audit_design_is_hooked_and_owns_one_role(self):
        self.assertIn("audit-design", lib.HOOKED_SKILLS)
        self.assertEqual(lib.skills_registry.agent_roles_of("audit-design"), ["gap-analyst"])
        self.assertIn("gap-analyst", lib.skills_registry.agent_roles_of("create-architecture"))


class ProseContractTest(unittest.TestCase):

    def test_create_architecture_runs_the_gap_analysis_beside_the_survey(self):
        body = flat(os.path.join(PLUGIN, "skills", "create-architecture", "SKILL.md"))
        for phrase in ("### Gap analysis", "in the SAME message as the survey",
                       "iter-1/gaps.md", "every drifted gap", "acs.py design",
                       "design bump"):
            self.assertIn(phrase, body)
        # ADR-0127: the run is ticketless, so no `--ticket` is passed.
        self.assertNotIn("design bump --ticket", body)
        self.assertNotIn("design init --ticket", body)

    def test_the_architect_handles_every_gap_and_versions_every_file(self):
        body = flat(os.path.join(PLUGIN, "agents", "create-architecture-architect.md"))
        for phrase in ("## Gaps handled", "classDef planned", "design init --status",
                       "design bump", "acs.py design check", "pass no `--ticket`"):
            self.assertIn(phrase, body)

    def test_the_reviewer_checks_versions_and_gaps(self):
        body = flat(os.path.join(PLUGIN, "agents", "create-architecture-reviewer.md"))
        self.assertIn("acs.py design check", body)
        self.assertIn("an unhandled or silently dropped gap is a blocking finding", body)

    def test_gap_analysts_classify_three_ways_with_two_citations(self):
        for name in ("create-architecture-gap-analyst.md", "audit-design-gap-analyst.md"):
            body = flat(os.path.join(PLUGIN, "agents", name))
            for phrase in ("**unimplemented**", "**undocumented**", "**drifted**",
                           "A gap is a fact with two citations", "## Unverified"):
                self.assertIn(phrase, body, name)

    def test_audit_design_is_read_only(self):
        body = flat(os.path.join(PLUGIN, "skills", "audit-design", "SKILL.md"))
        self.assertIn("You never edit a design document, the code, or anything else", body)
        self.assertIn("is the design ahead of the code", body)


if __name__ == "__main__":
    unittest.main()
