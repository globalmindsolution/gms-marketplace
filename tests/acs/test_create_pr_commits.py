"""/acs:create-pr is the one skill that branches, commits and pushes (ADR-0127).

The skill is short, goal-level prose that leaves the mechanics to the model. These
tests pin only what is machinery -- the mandatory commands, the CLIs, the rules that
protect the user's history -- and that what the Finish example records is what
`acs.py pr commit` prints.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_DIR = os.path.join(PLUGIN, "skills", "create-pr")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from acs_lib import commit_plan  # noqa: E402
from skill_text import result_example  # noqa: E402


def read(*parts):
    with open(os.path.join(SKILL_DIR, *parts), encoding="utf-8") as fh:
        return fh.read()


def flat(text):
    return " ".join(text.split())


def skill():
    return read("SKILL.md")


def resume():
    return read("references", "resume.md")


class TheContractTheSystemDependsOn(unittest.TestCase):
    """The skill is goal-level prose; these are the few things around it that are
    machinery, not judgment: the mandatory commands, the CLIs it hands the
    mechanics to, and the rules that protect the user's history."""

    def test_it_says_it_is_the_one_skill_that_commits(self):
        text = flat(skill())
        self.assertIn("ONLY acs skill that creates a branch, stages, commits or pushes", text)
        self.assertIn("ADR-0127", text)

    def test_the_mandatory_commands_and_clis_are_named(self):
        body = skill()
        self.assertRegex(body, r'(?m)^argument-hint: "\[ticket-id\] \[documents…\] \[prompt\]"$')
        text = flat(body)
        for needle in ("acs.py\" step start --step create-pr", "pr plan-commits",
                       "pr commit --plan", "pr-conventions.py check", "pr metadata fill",
                       "post-create-pr.py", "acs.py\" write steps/create-pr/result.json",
                       "clarify.py list", "handoff.py"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertLess(text.index("pr plan-commits"), text.index("pr commit --plan"))

    def test_it_works_in_any_git_state(self):
        text = flat(skill())
        for state in ("uncommitted", "committed", "unpushed", "already pushed"):
            self.assertIn(state, text)
        for field in ("`ahead`", "`pushed`"):
            self.assertIn(field, text)

    def test_nothing_is_committed_without_the_users_say_so(self):
        text = flat(skill())
        self.assertIn("no commit without their confirm", text)
        self.assertIn("confirm / edit / cancel", text)
        self.assertIn("never add an `excluded` path", text)

    def test_the_safety_rules(self):
        text = flat(skill())
        self.assertIn("Never force-push; never push the default branch", text)
        self.assertIn("never a draft", text)
        self.assertIn("Never report a PR, label or comment that was not actually made", text)

    def test_a_ticketless_pr_is_exempt_by_label_because_ci_still_wants_a_ticket(self):
        ci = os.path.join(PLUGIN, "templates", "ci", "check-conventions.py")
        with open(ci, encoding="utf-8") as fh:
            self.assertIn('EXEMPT_LABEL = "acs-exempt"', fh.read())
        text = flat(skill())
        self.assertIn("a run with no ticket also gets `acs-exempt`", text)
        self.assertIn("/acs:merge-pr --pr <number>", text)

    def test_the_brake_applies_only_to_a_run_with_a_code_step(self):
        self.assertIn("does not require `/acs:code` or `/acs:docs-sync` to have run",
                      flat(skill()))

    def test_resume_resumes_from_the_first_uncommitted_group(self):
        text = flat(resume())
        self.assertIn("Resume from the first uncommitted group", text)
        self.assertIn("do not re-plan or ask again", text)
        self.assertIn("commit-plan.resume.json", text)

    def test_the_references_the_skill_names_exist(self):
        for name in re.findall(r"references/([\w.-]+\.md)", skill()):
            self.assertTrue(os.path.exists(os.path.join(SKILL_DIR, "references", name)), name)


class WhatIsRecordedIsWhatTheCliPrints(unittest.TestCase):
    """The Finish example's `states.commits` items carry only keys `acs.py pr
    commit` prints, and the state fragment admits `commits`."""

    def _finish_states(self):
        body = skill()
        block = result_example(body)
        self.assertIsNotNone(block, "the Finish result-document example")
        return json.loads(block)["states"]

    def test_states_pr_stays_first_and_commits_follow(self):
        states = self._finish_states()
        self.assertEqual(list(states)[0], "pr")
        self.assertEqual(set(states["pr"]), {"number", "url", "branch", "base"})
        self.assertTrue(states["commits"])

    def test_the_state_fragment_admits_commits(self):
        fragment = json.loads(read("state.schema.json"))
        props = fragment["properties"]["states"]["properties"]
        self.assertEqual(props["commits"]["type"], "array")
        self.assertIn("pr", props)

    def test_the_example_keys_are_the_cli_keys(self):
        root = tempfile.mkdtemp(prefix="cpr-")
        try:
            def git(*args):
                subprocess.run(["git"] + list(args), cwd=root, check=True,
                               capture_output=True)
            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "t")
            with open(os.path.join(root, "README.md"), "w") as fh:
                fh.write("x\n")
            git("add", "README.md")
            git("commit", "-qm", "init")
            os.makedirs(os.path.join(root, "tests"))
            with open(os.path.join(root, "tests", "test_a.py"), "w") as fh:
                fh.write("def test_a():\n    pass\n")
            with open(os.path.join(root, "a.py"), "w") as fh:
                fh.write("A = 1\n")
            out = commit_plan.execute(root, {
                "branch": "task/T-1-a",
                "groups": [{"id": "slice-main-tests", "subject": "T-1 Add tests",
                            "paths": ["tests/test_a.py"]},
                           {"id": "slice-main-code", "subject": "T-1 Implement",
                            "paths": ["a.py"]}]})
        finally:
            shutil.rmtree(root, ignore_errors=True)
        self.assertEqual(out["branch"], "task/T-1-a")
        printed = set(out["commits"][0])
        for commit in self._finish_states()["commits"]:
            self.assertLessEqual(set(commit), printed)


class TheReportStaysNormative(unittest.TestCase):

    def test_completion_report_labels_and_order(self):
        body = skill()
        self.assertIn("## Completion report (normative)", body)
        block = body[body.index("## Completion report (normative)"):]
        labels = re.findall(r"^- \*\*(\w+)\*\*:", block, re.M)
        self.assertEqual(labels, ["Ticket", "Status", "Results", "Findings", "Artifacts",
                                  "Metrics", "Next"])
        self.assertIn("commits made", block)


if __name__ == "__main__":
    unittest.main()
