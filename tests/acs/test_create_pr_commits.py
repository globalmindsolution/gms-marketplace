"""/acs:create-pr is the one skill that branches, commits and pushes (ADR-0127).

Every step before it leaves its output as uncommitted changes and records the
paths it wrote; create-pr splits them into the commits `acs.py pr
plan-commits` proposes, has the user confirm that plan, commits it with `acs.py
pr commit --plan`, and only then pushes and opens the PR. These tests pin that
contract where it lives -- the skill's SKILL.md and references -- and check
that what the prose tells the coordinator to record is what the CLI prints.

The retired rule they replace said the opposite: uncommitted changes were
/acs:code's job, and create-pr stopped on them.
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


def publish():
    return read("references", "publish.md")


def resume():
    return read("references", "resume.md")


class TheRetiredRuleIsGone(unittest.TestCase):
    """Uncommitted changes are now create-pr's input, not its stop condition."""

    def test_no_file_tells_the_coordinator_to_stop_on_uncommitted_work(self):
        for name, body in (("SKILL.md", skill()), ("publish.md", publish()),
                           ("resume.md", resume())):
            text = flat(body)
            with self.subTest(file=name):
                self.assertNotRegex(text, r"(?i)never commit new work")
                self.assertNotRegex(text, r"(?i)uncommitted (implementation )?changes "
                                          r"(exist|are) .{0,40}/acs:code's job")
                self.assertNotIn("Do not commit, do not merge", text)
                self.assertNotIn("do not create new branches", text)

    def test_it_says_it_is_the_one_skill_that_commits(self):
        text = flat(skill())
        self.assertIn("ONLY acs skill that creates a branch, stages, commits or pushes", text)
        self.assertIn("ADR-0127", text)


class TheCommitPhase(unittest.TestCase):

    def test_a_ticket_a_prompt_or_the_current_run_plan_through_the_cli(self):
        """No skill needs a ticket: a ticket id, documents, a prompt, a mix of
        them, or nothing (the current run) all plan through the same CLI call,
        and no `--docs` mode survives (ADR-0128)."""
        body = skill()
        self.assertRegex(body, r'(?m)^argument-hint: "\[ticket-id\] \[documents…\] \[prompt\]"$')
        text = flat(body)
        self.assertIn("acs.py\" pr plan-commits \\ --out", text)
        for invocation in ("`/acs:create-pr <ticket-id>`", "`/acs:create-pr` (no argument)",
                           "`/acs:create-pr \"<prompt>\"` with no current run"):
            self.assertIn(invocation, text)
        self.assertIn("every uncommitted change against HEAD", text)
        for name, other in (("SKILL.md", body), ("publish.md", publish()),
                            ("resume.md", resume())):
            with self.subTest(file=name):
                self.assertNotIn("--docs", other)
                self.assertNotRegex(other, r"(?i)docs mode")

    def test_the_brake_applies_only_to_a_run_with_a_code_step(self):
        self.assertIn("it applies only when the run has a code step", flat(skill()))

    def test_ticket_references_only_when_there_is_a_ticket(self):
        text = flat(skill())
        self.assertIn("with a ticket it keeps the configured commit-subject format, "
                      "`{ticket_id} {summary}`; without one the subject is the summary alone",
                      text)
        self.assertIn("with no ticket id and no `Closes #` line", text)
        self.assertIn("never without a ticket", text)

    def test_the_plan_is_previewed_in_one_grouped_question(self):
        text = flat(skill())
        self.assertIn("Preview and confirm — ONE grouped question", text)
        self.assertIn("AskUserQuestion", text)
        for choice in ("**confirm**", "**edit**", "**cancel**"):
            self.assertIn(choice, text)
        for listed in ("`left_out`", "`excluded`"):
            self.assertIn(listed, text)
        for edit in ("moves a path between groups", "drops a path from a group",
                     "adds a `left_out` path to a group", "rewords a subject"):
            self.assertIn(edit, text)

    def test_the_confirmed_plan_is_written_then_committed_by_the_cli(self):
        text = flat(skill())
        self.assertIn("steps/create-pr/iter-<n>/commit-plan.json", text)
        self.assertIn("acs.py\" pr commit --plan steps/create-pr/iter-<n>/commit-plan.json",
                      text)
        self.assertLess(text.index("pr plan-commits"), text.index("pr commit --plan"))

    def test_commits_come_before_the_push_and_the_base_detect_before_the_push(self):
        text = flat(skill())
        commit = text.index("pr commit --plan")
        base = text.index("gh api repos/{owner}/{repo} --jq .default_branch")
        push = text.index("git push -u origin <branch>")
        self.assertLess(commit, push)
        self.assertLess(base, push)
        self.assertIn("its failure now stops the run before the push", text)

    def test_nothing_is_committed_without_a_confirm(self):
        text = flat(skill())
        self.assertIn("Silence is not approval", text)
        self.assertIn("commits nothing and hands off `needs_input`", text)
        self.assertIn("never an assumption", text)

    def test_the_body_lists_the_commits(self):
        self.assertRegex(flat(skill()), r"Changes \(the plan's `ahead` commits and the commits made, "
                                        r"in order — one bullet per commit")
        self.assertIn("the Changes section lists every commit on the branch past the default branch", flat(publish()))


class TheSafetyRules(unittest.TestCase):

    def test_publish_keeps_every_hard_rule(self):
        text = flat(publish())
        self.assertIn("Commit ONLY through `acs.py pr commit --plan`", text)
        for rule in ("never `git add -A`, `git add .`, `git commit -a`",
                     "never commit to the default branch",
                     "never include a `left_out` path the user did not move into a group",
                     "no force-push, ever",
                     "Never stash, reset, restore, clean or check out over the user's work"):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)

    def test_skill_never_force_pushes_nor_pushes_the_default_branch(self):
        self.assertIn("Never force-push, never push the default branch", flat(skill()))

    def test_a_ticketless_pr_is_exempt_by_label_because_ci_still_wants_a_ticket(self):
        """The installed CI check still fails a PR naming no ticket unless it
        carries `acs-exempt`; a ticketless run applies that label, and only
        that run does."""
        ci = os.path.join(PLUGIN, "templates", "ci", "check-conventions.py")
        with open(ci, encoding="utf-8") as fh:
            self.assertIn('EXEMPT_LABEL = "acs-exempt"', fh.read())
        text = flat(skill())
        self.assertIn("(no ticket: also `acs-exempt`)", text)
        self.assertRegex(text, r"With no ticket a `ticket_link` error is expected")
        self.assertIn("/acs:merge-pr --pr <number>", text)


class Resume(unittest.TestCase):

    def test_a_partial_plan_resumes_from_its_first_uncommitted_group(self):
        text = flat(resume())
        self.assertIn("resume from the first uncommitted group", text)
        self.assertIn("do not re-plan and do not ask again", text)
        self.assertIn("commit-plan.resume.json", text)


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
        for commit in json.loads(re.search(r"```json\n(\{.*?)```", publish(), re.S)
                                 .group(1))["commits"]:
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
