"""Scratch git repos must not race their own teardown.

`tests/acs/__init__.py` disables git's opportunistic maintenance for every
subprocess this suite spawns. Without it, `git commit` launches
`git maintenance run --auto --quiet`, which writes into `.git/objects` while
a `TemporaryDirectory` is deleting that same tree:

    OSError: [Errno 39] Directory not empty: '/tmp/.../repo/.git/objects'

That is a race, so it cannot be asserted directly -- a passing run proves
nothing about the next one. What CAN be asserted is that the writer is gone:
the config reaches git, and a commit launches no maintenance child.
"""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acs import _GIT_CONFIG, _install_git_config  # noqa: E402


def git(args, cwd, trace=False):
    env = os.environ.copy()
    if trace:
        env["GIT_TRACE"] = "1"
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                          text=True, env=env)


class GitConfigReachesEverySubprocessTest(unittest.TestCase):

    def test_each_key_is_visible_to_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            git(["init", "-q", "."], tmp)
            for key, value in _GIT_CONFIG:
                got = git(["config", "--get", key], tmp).stdout.strip()
                self.assertEqual(got, value,
                                 "git does not see %s=%s; a scratch repo can "
                                 "still spawn maintenance into a directory the "
                                 "test is deleting" % (key, value))

    def test_a_commit_launches_no_maintenance_child(self):
        """The failure mode itself: the child that writes into .git/objects."""
        with tempfile.TemporaryDirectory() as tmp:
            git(["init", "-q", "."], tmp)
            git(["config", "user.email", "t@example.com"], tmp)
            git(["config", "user.name", "Test"], tmp)
            with open(os.path.join(tmp, "a"), "w") as fh:
                fh.write("x")
            git(["add", "-A"], tmp)
            trace = git(["commit", "-q", "-m", "init"], tmp, trace=True).stderr
            spawned = [line for line in trace.splitlines()
                       if "run_command:" in line
                       and ("maintenance" in line or " gc" in line)]
            self.assertEqual(spawned, [], "git commit still launches %s" % spawned)


class AppendsRatherThanClobbersTest(unittest.TestCase):
    """This environment already sets GIT_CONFIG_COUNT; overwriting it would
    silently drop whatever the host configured."""

    def test_existing_entries_survive(self):
        env = {"GIT_CONFIG_COUNT": "1",
               "GIT_CONFIG_KEY_0": "http.sslVerify",
               "GIT_CONFIG_VALUE_0": "true"}
        _install_git_config(env)
        self.assertEqual(env["GIT_CONFIG_KEY_0"], "http.sslVerify")
        self.assertEqual(env["GIT_CONFIG_VALUE_0"], "true")
        self.assertEqual(int(env["GIT_CONFIG_COUNT"]), 1 + len(_GIT_CONFIG))
        added = {env["GIT_CONFIG_KEY_%d" % i]: env["GIT_CONFIG_VALUE_%d" % i]
                 for i in range(1, int(env["GIT_CONFIG_COUNT"]))}
        self.assertEqual(added, dict(_GIT_CONFIG))

    def test_a_garbage_count_does_not_raise(self):
        env = {"GIT_CONFIG_COUNT": "not-a-number"}
        _install_git_config(env)
        self.assertEqual(int(env["GIT_CONFIG_COUNT"]), len(_GIT_CONFIG))


if __name__ == "__main__":
    unittest.main()
