"""/acs:create-pr takes a ticket id, a prompt or a document, like every skill (ADR-0127).

There is no docs-only mode: create-pr's subject is whatever the run machine
resolves -- this checkout's current run, or a new run over the prompt, ticket
or document it was given. The review brake holds only a run whose /acs:code
produced a result; a prompt's run with no code is a PR of whatever its steps
(or the user) left uncommitted. The post-hook finishes it like any step and
moves no ticket when there is none.

Run:  python3 -m unittest tests.acs.test_any_subject_create_pr -v
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib, load_module  # noqa: E402


class ArgsValueBindingTest(unittest.TestCase):
    """`--args "$ARGUMENTS"` must survive arguments that start with a dash."""

    def test_binding(self):
        acs = load_module("acs.py", "acs_entry_for_binding_test")
        self.assertEqual(acs._bind_args_values(["step", "start", "--args", "--x", "--run", "R"]),
                         ["step", "start", "--args=--x", "--run", "R"])
        self.assertEqual(acs._bind_args_values(["--args"]), ["--args"])


class CommitSubjectTest(unittest.TestCase):

    def test_a_ticket_leads_otherwise_the_summary_alone(self):
        C = lib.conventions
        self.assertEqual(C.commit_subject("SHOP-1", "Add tests"), "SHOP-1 Add tests")
        self.assertEqual(C.commit_subject(None, "Update PRD"), "Update PRD")
        self.assertEqual(C.COMMIT_SUBJECT_NO_TICKET.format(summary="x"), "x")


class PromptSubjectCreatePrTest(AcsWorkspaceCase):

    PROMPT = "ship the roadmap edits"

    def setUp(self):
        super().setUp()
        for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
            subprocess.run(["git", "-C", self.repo, "config", key, value], check=True)
        with open(os.path.join(self.repo, "README.md"), "w") as fh:
            fh.write("shop\n")
        subprocess.run(["git", "-C", self.repo, "add", "README.md"], check=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-qm", "init"], check=True)

    def write(self, rel, text="x\n"):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def start(self, *extra):
        out = self.run_script("acs.py", "step", "start", "--step", "create-pr", *extra)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_the_pre_hook_and_start_open_a_prompt_run(self):
        pre = self.pre("create-pr", self.PROMPT)
        self.assertEqual(pre.returncode, 0, pre.stderr)
        out = self.start("--args", self.PROMPT)
        self.assertIsNone(out["ticket_id"])
        self.assertEqual(out["subject"], {"kind": "prompt", "text": self.PROMPT})
        self.assertTrue(out["in_workflow"])

    def test_plan_commits_for_a_prompt_run_takes_every_uncommitted_change(self):
        self.write("docs/product/prd.md")
        self.write("src/app.py")
        self.write("tests/test_app.py")
        run_id = self.start("--args", self.PROMPT)["run_id"]
        out = self.run_script("acs.py", "pr", "plan-commits")
        self.assertEqual(out.returncode, 0, out.stderr)
        plan = json.loads(out.stdout)
        self.assertEqual(plan["mode"], "uncommitted")
        self.assertEqual((plan["run_id"], plan["ticket_id"]), (run_id, None))
        self.assertEqual([(g["subject"], g["paths"]) for g in plan["groups"]], [
            ("Update PRD", ["docs/product/prd.md"]),
            ("Add tests", ["tests/test_app.py"]),
            ("Update code", [".acs/settings.json", "src/app.py"]),
        ])
        self.assertEqual(plan["branch"], "task/%s-%s" % (run_id, lib.slugify(self.PROMPT)))

    def test_the_review_brake_holds_only_a_run_with_a_code_result(self):
        run_id = self.start("--args", self.PROMPT)["run_id"]
        rdir = lib.run_dir(lib.repo_dir(self.ws, "acme-shop"), run_id)
        lib.save_state(rdir, "review-code", dict(lib.empty_state("review-code", run_id),
                                                 states={"verifier_passed": False}))
        self.assertIsNone(lib.brakes._brake_create_pr({}, rdir, lib.load_run(rdir), None))
        lib.write_json(lib.result_path(rdir, "code"), {"status": "completed"})
        with self.assertRaises(lib.GateError):
            lib.brakes._brake_create_pr({}, rdir, lib.load_run(rdir), None)

    def test_post_create_pr_finishes_a_prompt_run_and_moves_no_ticket(self):
        run_id = self.start("--args", self.PROMPT)["run_id"]
        out = self.post("create-pr", run_id, {
            "status": "completed", "summary": "PR opened",
            "states": {"pr": {"number": 9, "url": "https://example.invalid/pull/9"}}})
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = lib.load_run(lib.run_dir(lib.repo_dir(self.ws, "acme-shop"), run_id))
        self.assertEqual(lib.step_entry(doc, "create-pr")["status"], "completed")

    def test_with_no_argument_it_continues_the_current_run(self):
        ticket = self.new_ticket("Wishlist API", "task")
        self.ensure_run(ticket)
        self.assertEqual(self.start()["run_id"], ticket)
        plan = json.loads(self.run_script("acs.py", "pr", "plan-commits").stdout)
        self.assertEqual(plan["ticket_id"], ticket)

    def test_plan_commits_with_no_run_is_refused(self):
        out = self.run_script("acs.py", "pr", "plan-commits")
        self.assertEqual(out.returncode, 2)
        self.assertIn("no current run", out.stderr)


class StandaloneRunAdoptionTest(AcsWorkspaceCase):

    def test_another_ticketless_skills_run_is_never_adopted(self):
        prd = self.run_script("acs.py", "step", "start", "--step", "create-prd")
        self.assertEqual(prd.returncode, 0, prd.stderr)
        prd_run = json.loads(prd.stdout)["run_id"]
        arch = self.run_script("acs.py", "step", "start", "--step", "create-architecture")
        self.assertEqual(arch.returncode, 0, arch.stderr)
        self.assertNotEqual(json.loads(arch.stdout)["run_id"], prd_run)


if __name__ == "__main__":
    unittest.main()
