#!/usr/bin/env python3
"""/acs:create-pr ships work in ANY git state, not only uncommitted changes.

The plan reports `ahead` (commits HEAD carries past the default branch) and
`pushed` (origin has the branch at HEAD), and `pr commit` with no groups cuts the
branch at HEAD when the work was committed on the default branch or on a
detached HEAD. Real git, a bare origin in a temp dir.

Run:  python3 -m unittest tests.acs.test_commit_plan_already_committed -v
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import lib  # noqa: E402

P = lib.commit_plan
SUBJECT = {"run_id": "r1", "ticket_id": None, "type": "task", "title": "Fix thing"}


def git(root, *args):
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True,
                          check=True).stdout.strip()


class AlreadyCommittedTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        origin = os.path.join(self.tmp, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", origin], check=True)
        self.repo = os.path.join(self.tmp, "repo")
        subprocess.run(["git", "clone", "-q", origin, self.repo], check=True,
                       capture_output=True)
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "T")
        git(self.repo, "checkout", "-q", "-b", "main")
        self.commit("base.txt")
        git(self.repo, "push", "-q", "-u", "origin", "main")

    def commit(self, name):
        with open(os.path.join(self.repo, name), "w") as fh:
            fh.write(name)
        git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", "add " + name)

    def plan(self):
        return P.plan(self.repo, [], SUBJECT, None, [])

    def test_committed_unpushed_on_a_feature_branch(self):
        git(self.repo, "checkout", "-q", "-b", "task/feature")
        self.commit("a.txt")
        plan = self.plan()
        self.assertEqual(plan["groups"], [])
        self.assertEqual(plan["branch"], "task/feature")
        self.assertEqual([c["subject"] for c in plan["ahead"]], ["add a.txt"])
        self.assertFalse(plan["pushed"])
        self.assertEqual(P.validate_plan(self.repo, plan), [])

    def test_pushed_feature_branch_is_marked_pushed(self):
        git(self.repo, "checkout", "-q", "-b", "task/feature")
        self.commit("a.txt")
        git(self.repo, "push", "-q", "-u", "origin", "task/feature")
        plan = self.plan()
        self.assertTrue(plan["pushed"])
        self.assertEqual(len(plan["ahead"]), 1)

    def test_a_new_commit_after_the_push_is_not_pushed(self):
        git(self.repo, "checkout", "-q", "-b", "task/feature")
        self.commit("a.txt")
        git(self.repo, "push", "-q", "-u", "origin", "task/feature")
        self.commit("b.txt")
        self.assertFalse(self.plan()["pushed"])
        self.assertEqual(len(self.plan()["ahead"]), 2)

    def test_committed_on_the_default_branch_gets_a_branch_at_head(self):
        self.commit("a.txt")
        plan = self.plan()
        self.assertEqual(plan["current_branch"], "main")
        self.assertNotEqual(plan["branch"], "main")
        out = P.execute(self.repo, plan)
        self.assertEqual(out["branch_action"], "created")
        self.assertEqual(out["commits"], [])
        self.assertEqual(git(self.repo, "branch", "--show-current"), plan["branch"])

    def test_detached_head_gets_a_branch_at_head(self):
        self.commit("a.txt")
        git(self.repo, "checkout", "-q", "--detach")
        plan = self.plan()
        self.assertIsNone(plan["current_branch"])
        P.execute(self.repo, plan)
        self.assertEqual(git(self.repo, "branch", "--show-current"), plan["branch"])

    def test_nothing_ahead_and_nothing_to_commit_is_refused(self):
        git(self.repo, "checkout", "-q", "-b", "task/feature")
        plan = self.plan()
        self.assertEqual(plan["ahead"], [])
        self.assertTrue(any("no groups" in e for e in P.validate_plan(self.repo, plan)))

    def test_uncommitted_changes_beside_ahead_commits_are_both_reported(self):
        git(self.repo, "checkout", "-q", "-b", "task/feature")
        self.commit("a.txt")
        with open(os.path.join(self.repo, "new.py"), "w") as fh:
            fh.write("x = 1\n")
        plan = self.plan()
        self.assertEqual(len(plan["ahead"]), 1)
        self.assertEqual([p for g in plan["groups"] for p in g["paths"]], ["new.py"])

    def test_no_default_branch_ref_means_no_ahead(self):
        shutil.rmtree(os.path.join(self.repo, ".git", "refs", "remotes"))
        git(self.repo, "branch", "-m", "work")
        self.assertEqual(P.ahead_commits(self.repo), [])


if __name__ == "__main__":
    unittest.main()
