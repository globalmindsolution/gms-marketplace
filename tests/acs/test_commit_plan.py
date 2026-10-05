"""acs_lib.commit_plan and `acs.py pr plan-commits | commit` (ADR-0127).

Only /acs:create-pr commits. It proposes small commits -- ticket docs, design
docs, per slice its tests then its code, docs-sync, e2e -- built from what the
run's steps RECORDED intersected with the working-tree changeset, previews
them, and commits the confirmed plan with pathspecs only. Every test drives
real git in a temp repo.

Run:  python3 -m unittest tests.acs.test_commit_plan -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib  # noqa: E402

P = lib.commit_plan


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True,
                          check=check).stdout


def write(root, rel, text="x\n"):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


class ClassificationTest(unittest.TestCase):

    def test_test_paths(self):
        for path in ("tests/test_a.py", "src/__tests__/a.js", "spec/models/user_spec.rb",
                     "pkg/a_test.go", "test_a.py", "web/a.spec.ts", "web/a.test.tsx",
                     "lib/test/thing.py"):
            with self.subTest(path=path):
                self.assertTrue(P.is_test_path(path))
        for path in ("src/a.py", "src/testing.py", "docs/test-strategy.md", "contest.py",
                     "src/specs.py"):
            with self.subTest(path=path):
                self.assertFalse(P.is_test_path(path))

    def test_doc_paths(self):
        for path in ("README.md", "docs/arch/flow.mmd", "docs/img/c4.png", "doc/x.txt"):
            self.assertTrue(P.is_doc_path(path), path)
        for path in ("src/a.py", "package.json", "docsify.config.js"):
            self.assertFalse(P.is_doc_path(path), path)

    def test_doc_sets(self):
        self.assertEqual(P.doc_set("docs/product/prd.md")[0], "prd")
        self.assertEqual(P.doc_set("docs/roadmap.md")[0], "prd")
        self.assertEqual(P.doc_set("docs/architecture/hld/context.md")[0], "hld")
        self.assertEqual(P.doc_set("docs/architecture/lld/checkout/flows.md"),
                         ("lld/checkout", "LLD checkout"))
        self.assertEqual(P.doc_set("docs/architecture/lld/index.md")[0], "lld")
        self.assertEqual(P.doc_set("docs/architecture/adr/0001-x.md")[0], "adr")
        self.assertEqual(P.doc_set("docs/requirements/functional/f1.md")[0], "requirements")
        self.assertEqual(P.doc_set("README.md")[0], "other")
        self.assertEqual(P.doc_set("docs/tickets/SHOP-7/plan.md")[0], "tickets/SHOP-7")

    def test_rel_rejects_paths_outside_the_checkout(self):
        self.assertIsNone(P._rel("/repo", "/elsewhere/x.py"))
        self.assertIsNone(P._rel("/repo", ""))
        self.assertIsNone(P._rel("/repo", None))
        self.assertEqual(P._rel("/repo", "./src/a.py"), "src/a.py")

    def test_spec_titles(self):
        self.assertEqual(P._spec_title("02-import-endpoint.md"), "import endpoint")
        self.assertIsNone(P._spec_title(None))


class CommitPlanCase(AcsWorkspaceCase):
    """A ticket on a committed repo, the run's baseline taken by `step start`."""

    def setUp(self):
        super().setUp()
        for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
            git(self.repo, "config", key, value)
        write(self.repo, "README.md", "shop\n")
        write(self.repo, "src/old.py", "old = 1\n")
        write(self.repo, "cfg.ini", "a=1\n")
        git(self.repo, "add", "README.md", "src/old.py", "cfg.ini")
        git(self.repo, "commit", "-qm", "init")
        self.ticket = self.new_ticket("Bulk import API", "task")
        self.docs = "docs/tickets/%s" % self.ticket

    def baseline(self):
        out = self.start("analyze-requirements", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.r = self.rdir(self.ticket)
        return lib.changes.load_baseline(self.r)

    def states(self, skill, states, where="state.json"):
        write_json(os.path.join(self.r, "steps", skill, where), {"states": states})

    def report(self, skill, name, doc, iteration=1):
        write_json(os.path.join(self.r, "steps", skill, "iter-%d" % iteration, name), doc)

    def plan(self, *extra, code=0):
        out = self.run_script("acs.py", "pr", "plan-commits", *extra)
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None


class PlanTicketTest(CommitPlanCase):

    def build(self):
        write(self.repo, "scratch/notes.txt", "user's own\n")  # dirty before the run
        write(self.repo, "cfg.ini", "a=2\n")                     # dirty, changed again later
        write(self.repo, "todo.md", "recorded later\n")          # dirty, a step records it
        self.baseline()
        write(self.repo, "cfg.ini", "a=3\n")
        write(self.repo, self.docs + "/analysis.md")
        write(self.repo, self.docs + "/design.md")
        write(self.repo, "docs/architecture/hld/overview.md")
        write(self.repo, "src/api.py")
        write(self.repo, "tests/test_api.py")
        write(self.repo, "docs/api/import.md")
        write(self.repo, "src/export.py")
        write(self.repo, "src/c/extra.py")
        write(self.repo, "src/glue.py")
        write(self.repo, "README.md", "shop, now with import\n")
        write(self.repo, "e2e/flow.spec.ts")
        write(self.repo, "stray.txt")
        os.remove(os.path.join(self.repo, "src/old.py"))
        self.states("create-design", {"design_path": self.docs + "/design.md",
                                      "files": ["docs/architecture/hld/overview.md"]})
        self.states("create-impl-plan", {"file_map": {"1": ["src/api.py"]}})
        self.report("code", "implementer-1.json", {
            "spec": "01-import-endpoint.md",
            "files_changed": ["src/api.py", "tests/test_api.py", "docs/api/import.md"]})
        self.report("code", "implementer-2.json", {"spec": "02-export.md",
                                                   "files_changed": ["src/export.py"]})
        self.report("code", "implementer-integration.json", {"files_changed": ["src/glue.py"]})
        write_json(os.path.join(self.r, "steps", "code", "iter-1", "filemap.json"),
                   {"skill": "code", "iteration": "1",
                    "tasks": {"1": ["src/api.py", "tests/test_api.py", "docs/api/import.md"],
                              "2": ["src/export.py", "src/c/", "src/old.py"]}})
        self.states("docs-sync", {"files": ["README.md", "docs/api/import.md"]},
                    where="result.json")
        self.states("create-e2e-tests", {"suites_written": ["e2e/flow.spec.ts"]})
        self.states("run-e2e-tests", {"files": ["stray.txt"]})  # read-only: ignored
        self.states("create-test-docs", {"files": ["todo.md"]})

    def test_the_layers_in_order_with_tests_before_code(self):
        self.build()
        plan = self.plan("--ticket", self.ticket)
        t = self.ticket
        self.assertEqual([(g["id"], g["subject"]) for g in plan["groups"]], [
            ("ticket-docs", "%s Add ticket docs" % t),
            ("design", "%s Add design docs" % t),
            ("slice-1-tests", "%s Add tests for import endpoint" % t),
            ("slice-1-code", "%s Implement import endpoint" % t),
            ("slice-2-code", "%s Implement export" % t),
            ("slice-integration-code", "%s Implement the integration seams" % t),
            ("docs-sync", "%s Sync docs with the change" % t),
            ("e2e", "%s Add e2e suites" % t),
        ])
        paths = {g["id"]: g["paths"] for g in plan["groups"]}
        self.assertEqual(paths["ticket-docs"], sorted([
            self.docs + "/analysis.md", self.docs + "/design.md", "todo.md"]))
        self.assertEqual(paths["design"], ["docs/architecture/hld/overview.md"])
        self.assertEqual(paths["slice-1-tests"], ["tests/test_api.py"])
        # A file the slice and docs-sync both touched lands once, in the slice.
        self.assertEqual(paths["slice-1-code"], ["docs/api/import.md", "src/api.py"])
        # The declared map attributes what no report listed, deletions included.
        self.assertEqual(paths["slice-2-code"], ["src/c/extra.py", "src/export.py", "src/old.py"])
        self.assertEqual(paths["slice-integration-code"], ["src/glue.py"])
        self.assertEqual(paths["docs-sync"], ["README.md"])
        self.assertEqual(paths["e2e"], ["e2e/flow.spec.ts"])
        self.assertEqual(plan["left_out"], ["cfg.ini", "stray.txt"])
        self.assertEqual(plan["excluded"], [".acs/settings.json", "scratch/notes.txt"])
        self.assertEqual(plan["base"], git(self.repo, "rev-parse", "HEAD").strip())
        self.assertEqual(plan["branch"], "task/%s-bulk-import-api" % t)
        self.assertEqual(plan["mode"], "recorded")
        self.assertTrue(plan["ok"])

    def test_deterministic(self):
        self.build()
        first, second = self.plan("--ticket", self.ticket), self.plan("--ticket", self.ticket)
        for doc in (first, second):
            doc.pop("tree")
        self.assertEqual(first, second)

    def test_the_ticket_defaults_to_the_checkouts_run_and_out_writes_the_plan(self):
        self.build()
        out_file = os.path.join(self.tmp, "plan.json")
        plan = self.plan("--out", out_file)
        self.assertEqual(plan["ticket_id"], self.ticket)
        self.assertEqual(plan["plan_file"], out_file)
        self.assertEqual(lib.read_json(out_file)["groups"], plan["groups"])

    def test_a_feature_branch_is_kept(self):
        git(self.repo, "checkout", "-qb", "feat/wishlist")
        self.build()
        self.assertEqual(self.plan("--ticket", self.ticket)["branch"], "feat/wishlist")

    def test_a_slice_with_only_tests_gets_one_group_and_code_states_fall_back(self):
        self.baseline()
        write(self.repo, "tests/test_only.py")
        write(self.repo, "lib/unmapped.py")
        self.report("code", "implementer.json", {"files_changed": ["tests/test_only.py"]})
        self.states("code", {"files": ["lib/unmapped.py"]})
        plan = self.plan("--ticket", self.ticket)
        self.assertEqual([(g["id"], g["paths"]) for g in plan["groups"]], [
            ("slice-main-tests", ["tests/test_only.py"]),
            ("slice-main-code", ["lib/unmapped.py"])])
        self.assertEqual(plan["groups"][0]["subject"], "%s Add tests for the plan" % self.ticket)

    def test_the_plans_file_map_attributes_code_files_without_a_guard_map(self):
        self.baseline()
        write(self.repo, "src/a.py")
        self.states("create-impl-plan", {"file_map": {"3": ["src/a.py"]}})
        self.states("code", {"files": ["src/a.py"]})
        plan = self.plan("--ticket", self.ticket)
        self.assertEqual(plan["groups"][0]["id"], "slice-3-code")
        self.assertEqual(plan["groups"][0]["subject"], "%s Implement slice 3" % self.ticket)

    def test_a_declared_map_without_a_code_step_claims_nothing(self):
        self.baseline()
        write(self.repo, "src/a.py")
        write(self.repo, self.docs + "/plan.md")
        self.states("create-impl-plan", {"file_map": {"1": ["src/a.py"]},
                                         "files": [self.docs + "/plan.md"]})
        plan = self.plan("--ticket", self.ticket)
        self.assertEqual([g["id"] for g in plan["groups"]], ["ticket-docs"])
        self.assertEqual(plan["left_out"], ["src/a.py"])

    def test_other_steps_recorded_paths_and_absolute_paths(self):
        self.baseline()
        write(self.repo, "out/report.html")
        write(self.repo, self.docs + "/plan.md")
        self.states("merge-pr", {"files": ["out/report.html", "/nowhere/else.txt"]})
        self.states("create-impl-plan", {"plan_path": os.path.join(self.repo, self.docs,
                                                                   "plan.md")})
        plan = self.plan("--ticket", self.ticket)
        self.assertEqual([(g["id"], g["paths"]) for g in plan["groups"]], [
            ("ticket-docs", [self.docs + "/plan.md"]), ("other", ["out/report.html"])])

    def test_the_api_contract_is_committed_with_the_design_docs(self):
        """ADR-0134: the API contract is a Design document -- the living
        `lld/<f>/api/<interface>.md` and the run record land in the `design`
        layer beside the data design, not with the ticket docs."""
        self.assertEqual(lib.commit_plan.SKILL_LAYER["create-api-contract"], "design")
        self.baseline()
        api = "docs/architecture/lld/import/api/imports.md"
        record = "docs/architecture/lld/import/%s/api-contract.md" % self.ticket
        erd = "docs/architecture/lld/import/data/logical-erd.md"
        for path in (api, record, erd):
            write(self.repo, path)
        self.states("create-api-contract", {"files": [api], "contract_path": record})
        self.states("create-data-design", {"files": [erd]})
        plan = self.plan("--ticket", self.ticket)
        self.assertEqual([(g["id"], g["paths"]) for g in plan["groups"]],
                         [("design", sorted([api, record, erd]))])

    def test_the_analysis_publication_is_read(self):
        self.baseline()
        write(self.repo, "docs/elsewhere/analysis.md")
        write_json(os.path.join(self.r, "steps", "analyze-requirements", "loop.json"),
                   {"publication": {"path": os.path.join(self.repo, "docs/elsewhere/analysis.md"),
                                    "files": []}})
        plan = self.plan("--ticket", self.ticket)
        self.assertEqual(plan["groups"][0]["paths"], ["docs/elsewhere/analysis.md"])

    def test_the_tickets_own_docs_folder_counts_even_when_dirty_at_the_baseline(self):
        """`--allocate` writes ticket.md before the first step's baseline."""
        write(self.repo, self.docs + "/early.md")
        self.baseline()
        write(self.repo, self.docs + "/analysis.md")
        self.states("analyze-requirements", {"files": [self.docs + "/analysis.md"]})
        plan = self.plan("--ticket", self.ticket)
        self.assertEqual([(g["id"], g["paths"]) for g in plan["groups"]],
                         [("ticket-docs", [self.docs + "/analysis.md", self.docs + "/early.md"])])
        self.assertNotIn(self.docs + "/early.md", plan["excluded"])

    def test_refusals(self):
        self.assertEqual(self.run_script("acs.py", "pr", "plan-commits", "--ticket",
                                         "SHOP-404").returncode, 2)
        self.assertEqual(self.run_script("acs.py", "pr", "plan-commits").returncode, 2)

    def test_a_named_run(self):
        self.baseline()
        write(self.repo, self.docs + "/analysis.md")
        plan = self.plan("--ticket", self.ticket, "--run", self.ticket)
        self.assertEqual(plan["groups"][0]["paths"], [self.docs + "/analysis.md"])


class PlanUncommittedTest(CommitPlanCase):
    """Nothing recorded (no baseline, or a run whose steps recorded no path):
    every uncommitted change against HEAD, documents by doc set, then slices
    other runs recorded, then tests and code -- nothing refused."""

    SUBJECT = {"run_id": "R-1", "ticket_id": None, "type": "task", "title": "tidy the docs"}

    def test_grouped_by_doc_set_then_tests_then_code(self):
        write(self.repo, "docs/architecture/adr/0009-queue.md")
        write(self.repo, "docs/architecture/lld/checkout/flows.mmd")
        write(self.repo, "docs/architecture/lld/billing/data.md")
        write(self.repo, "docs/architecture/hld/context.md")
        write(self.repo, "docs/product/prd.md")
        write(self.repo, "docs/requirements/f1.md")
        write(self.repo, "docs/tickets/SHOP-1/notes.md")
        write(self.repo, "README.md", "new readme\n")
        write(self.repo, "src/app.py")
        write(self.repo, "tests/test_app.py")
        plan = P.plan(self.repo, [], self.SUBJECT)
        self.assertEqual([(g["id"], g["subject"], g["paths"]) for g in plan["groups"]], [
            ("docs-prd", "Update PRD", ["docs/product/prd.md"]),
            ("docs-requirements", "Update requirements", ["docs/requirements/f1.md"]),
            ("docs-hld", "Update HLD", ["docs/architecture/hld/context.md"]),
            ("docs-lld-billing", "Update LLD billing", ["docs/architecture/lld/billing/data.md"]),
            ("docs-lld-checkout", "Update LLD checkout",
             ["docs/architecture/lld/checkout/flows.mmd"]),
            ("docs-adr", "Update ADRs", ["docs/architecture/adr/0009-queue.md"]),
            ("docs-tickets-SHOP-1", "Update ticket SHOP-1 docs", ["docs/tickets/SHOP-1/notes.md"]),
            ("docs-other", "Update docs", ["README.md"]),
            ("tests", "Add tests", ["tests/test_app.py"]),
            ("code", "Update code", [".acs/settings.json", "src/app.py"]),
        ])
        self.assertEqual(plan["mode"], "uncommitted")
        self.assertIsNone(plan["ticket_id"])
        self.assertEqual(plan["branch"], "task/R-1-tidy-the-docs")
        self.assertEqual((plan["left_out"], plan["excluded"]), ([], []))

    def test_other_runs_records_attribute_code_to_slices(self):
        self.baseline()  # the ticket's run: its code step is the "other" run here
        write(self.repo, "src/api.py")
        write(self.repo, "tests/test_api.py")
        write(self.repo, "e2e/flow.spec.ts")
        write(self.repo, "src/loose.py")
        self.report("code", "implementer-1.json", {
            "spec": "01-import.md", "files_changed": ["src/api.py", "tests/test_api.py"]})
        self.states("create-e2e-tests", {"files": ["e2e/flow.spec.ts"]})
        plan = P.plan(self.repo, [], self.SUBJECT, None, [self.r])
        self.assertEqual([(g["id"], g["paths"]) for g in plan["groups"]], [
            ("slice-1-tests", ["tests/test_api.py"]),
            ("slice-1-code", ["src/api.py"]),
            ("e2e", ["e2e/flow.spec.ts"]),
            ("code", [".acs/settings.json", "src/loose.py"]),
        ])

    def test_a_ticket_with_no_baseline_is_planned_uncommitted_with_its_id(self):
        write(self.repo, "docs/product/prd.md")
        plan = self.plan("--ticket", self.ticket)
        self.assertEqual(plan["mode"], "uncommitted")
        self.assertEqual(plan["groups"][0]["subject"], "%s Update PRD" % self.ticket)

    def test_a_run_that_recorded_nothing_is_planned_uncommitted(self):
        self.baseline()
        write(self.repo, "src/app.py")
        plan = self.plan("--run", self.ticket)
        self.assertEqual(plan["mode"], "uncommitted")
        self.assertEqual(plan["groups"][-1]["paths"], [".acs/settings.json", "src/app.py"])

    def test_the_checkouts_current_run_is_the_default(self):
        self.baseline()
        self.assertEqual(self.plan()["run_id"], self.ticket)

    def test_no_changes_plans_nothing(self):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "everything")
        plan = P.plan(self.repo, [], self.SUBJECT)
        self.assertEqual(plan["groups"], [])

    def test_subject_of(self):
        self.assertEqual(P.subject_of({"run_id": "R", "subject": {"kind": "document",
                                                                 "path": "spec.md"}}),
                         {"run_id": "R", "ticket_id": None, "type": "task", "title": "spec.md"})
        self.assertEqual(P.subject_of({"run_id": "SHOP-1"}, {"id": "SHOP-1", "type": "story",
                                                            "title": "T"})["type"], "story")


class ExecuteTest(CommitPlanCase):

    def ready(self):
        self.baseline()
        write(self.repo, self.docs + "/analysis.md")
        write(self.repo, "src/api.py")
        write(self.repo, "tests/test_api.py")
        write(self.repo, "stray.txt")
        os.remove(os.path.join(self.repo, "src/old.py"))
        self.report("code", "implementer.json", {
            "files_changed": ["src/api.py", "tests/test_api.py", "src/old.py"]})
        plan_file = os.path.join(self.tmp, "plan.json")
        return self.plan("--ticket", self.ticket, "--out", plan_file), plan_file

    def commit(self, plan_file, code=0):
        out = self.run_script("acs.py", "pr", "commit", "--plan", plan_file)
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return json.loads(out.stdout) if code == 0 else out

    def test_commits_each_group_with_its_paths_only_on_the_new_branch(self):
        bare = os.path.join(self.tmp, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        git(self.repo, "remote", "set-url", "--push", "origin", bare)
        plan, plan_file = self.ready()
        result = self.commit(plan_file)
        self.assertEqual(result["branch"], plan["branch"])
        self.assertEqual(result["branch_action"], "created")
        self.assertEqual(git(self.repo, "rev-parse", "--abbrev-ref", "HEAD").strip(),
                         plan["branch"])
        log = git(self.repo, "log", "--format=%s", "-3").splitlines()
        self.assertEqual(log, ["%s Implement the plan" % self.ticket,
                               "%s Add tests for the plan" % self.ticket,
                               "%s Add ticket docs" % self.ticket])
        for commit in result["commits"]:
            shown = git(self.repo, "show", "--name-only", "--format=", commit["sha"]).split()
            self.assertEqual(sorted(shown), commit["paths"])
        self.assertEqual(result["commits"][-1]["paths"], ["src/api.py", "src/old.py"])
        self.assertIn("stray.txt", result["remaining"])
        self.assertIn(".acs/settings.json", result["remaining"])
        self.assertEqual(subprocess.run(["git", "-C", bare, "for-each-ref"],
                                        capture_output=True, text=True).stdout, "",
                         "pr commit must never push")

    def test_already_on_the_branch_and_an_existing_branch_at_head(self):
        _plan, plan_file = self.ready()
        git(self.repo, "branch", "feat/x")
        plan = lib.read_json(plan_file)
        plan["branch"] = "feat/x"
        lib.write_json(plan_file, plan)
        self.assertEqual(self.commit(plan_file)["branch_action"], "switched")

    def test_an_edited_plan_is_honoured_from_stdin(self):
        plan, _plan_file = self.ready()
        git(self.repo, "checkout", "-qb", "feat/mine")
        plan["branch"] = "feat/mine"
        plan["groups"] = [{"id": "all", "subject": "SHOP-1 everything",
                           "paths": ["stray.txt", "src/api.py"]}]
        out = self.run_script("acs.py", "pr", "commit", "--plan", "-", stdin=json.dumps(plan))
        self.assertEqual(out.returncode, 0, out.stderr)
        result = json.loads(out.stdout)
        self.assertEqual(result["branch_action"], "already_on")
        self.assertEqual(result["commits"][0]["paths"], ["src/api.py", "stray.txt"])

    def test_refusals_commit_nothing(self):
        plan, plan_file = self.ready()
        head = git(self.repo, "rev-parse", "HEAD")
        cases = {
            "default branch": dict(plan, branch="master"),
            "not a valid branch name": dict(plan, branch="bad..name"),
            "names no branch": dict(plan, branch=""),
            "is empty": dict(plan, groups=[{"id": "g", "subject": "s", "paths": []}]),
            "no groups": dict(plan, groups=[]),
            "has no subject": dict(plan, groups=[{"id": "g", "paths": ["stray.txt"]}]),
            "not an uncommitted change": dict(plan, groups=[
                {"id": "g", "subject": "s", "paths": ["README.md"]}]),
            "in both group": dict(plan, groups=[
                {"id": "a", "subject": "s", "paths": ["stray.txt"]},
                {"id": "b", "subject": "s", "paths": ["stray.txt"]}]),
        }
        for reason, doc in cases.items():
            with self.subTest(reason=reason):
                lib.write_json(plan_file, doc)
                out = self.commit(plan_file, code=2)
                self.assertIn(reason, out.stderr)
                self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)
        self.assertEqual(P.validate_plan(self.repo, ["not", "an", "object"]),
                         ["the plan is not a JSON object"])

    def test_an_existing_branch_elsewhere_is_refused(self):
        _plan, plan_file = self.ready()
        git(self.repo, "branch", "feat/old", "HEAD")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "moved")
        plan = lib.read_json(plan_file)
        plan["branch"] = "feat/old"
        lib.write_json(plan_file, plan)
        self.assertIn("already exists", self.commit(plan_file, code=2).stderr)

    def test_a_failing_commit_names_what_was_committed(self):
        _plan, plan_file = self.ready()
        hook = os.path.join(self.repo, ".git", "hooks", "commit-msg")
        with open(hook, "w") as fh:
            fh.write("#!/bin/sh\ngrep -q 'Add ticket docs' \"$1\" && exit 0\n"
                     "echo rejected >&2\nexit 1\n")
        os.chmod(hook, 0o755)
        out = self.commit(plan_file, code=2)
        self.assertIn("committed so far", out.stderr)
        self.assertIn("ticket-docs", out.stderr)


class UnbornBranchTest(unittest.TestCase):

    def test_commits_onto_a_fresh_repo(self):
        tmp = tempfile.mkdtemp(prefix="acs-unborn-")
        self.addCleanup(shutil.rmtree, tmp, True)
        git(tmp, "init", "-q", "-b", "master")
        git(tmp, "config", "user.email", "t@example.com")
        git(tmp, "config", "user.name", "T")
        write(tmp, "docs/product/prd.md")
        plan = P.plan(tmp, [], {"run_id": "R-1", "ticket_id": None, "title": "the prd"})
        self.assertIsNone(plan["base"])
        result = P.execute(tmp, plan)
        self.assertEqual(result["branch"], "task/R-1-the-prd")
        self.assertEqual(git(tmp, "log", "--format=%s").strip(), "Update PRD")
        self.assertEqual(result["remaining"], [])


if __name__ == "__main__":
    unittest.main()
