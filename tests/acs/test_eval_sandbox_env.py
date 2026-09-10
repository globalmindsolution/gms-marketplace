"""MAR-574 -- the eval Sandbox's git isolation must be scoped to its own git
calls, not applied process-wide via HOME.

`claude` resolves its plugin cache from `$HOME/.claude/plugins/cache`, so a
sandbox that rewrites HOME in the env it hands to `claude -p` hides every
installed plugin from the session under test. These tests pin the split: the
sandbox's own git subprocesses run under an isolated env; `self.env` -- what
`trigger()` and `run_skill()` inherit -- keeps the operator's real HOME.

Every fixture is a local temp dir; no network, no `claude` process, no cost.

Run:  python3 -m unittest tests.acs.test_eval_sandbox_env -v
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.join(REPO_ROOT, "evals", "acs"))
import harness  # noqa: E402  (path-inserted, same resolution run_evals.py uses)

ISOLATION_KEYS = ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_ATTR_NOSYSTEM")


def make_operator_home(tmp):
    """A fake operator HOME whose global git config excludes `.acs/` -- the
    condition the harness's HOME override was originally added to dodge."""
    home = os.path.join(tmp, "operator-home")
    os.makedirs(home, exist_ok=True)
    excludes = os.path.join(home, "global-gitignore")
    with open(excludes, "w") as fh:
        fh.write(".acs/\n")
    with open(os.path.join(home, ".gitconfig"), "w") as fh:
        fh.write("[core]\n\texcludesFile = %s\n" % excludes)
    return home


def operator_env(home):
    """The env an operator's shell would hand the harness, GIT_* scrubbed the
    same way Sandbox.__init__ scrubs it."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["HOME"] = home
    env["XDG_CONFIG_HOME"] = home
    return env


def add_is_blocked(tmp, env):
    """True when `git add .acs/settings.json` is refused under `env` -- the
    control that proves the excludes fixture actually bites."""
    repo = os.path.join(tmp, "control-repo")
    os.makedirs(os.path.join(repo, ".acs"))
    with open(os.path.join(repo, ".acs", "settings.json"), "w") as fh:
        fh.write("{}\n")
    subprocess.run(["git", "init", "-q", repo], check=True,
                   capture_output=True, env=env)
    proc = subprocess.run(["git", "-C", repo, "add", ".acs/settings.json"],
                          capture_output=True, text=True, env=env)
    return proc.returncode != 0


class _SubprocessRecorder:
    """Records the argv and env of every subprocess call, then delegates to the
    real callable it replaces."""

    def __init__(self, real):
        self._real = real
        self.calls = []

    def __call__(self, cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd:
            self.calls.append((list(cmd), dict(kwargs.get("env") or {})))
        return self._real(cmd, *args, **kwargs)

    def argv0s(self):
        return [os.path.basename(str(cmd[0])) for cmd, _ in self.calls]

    def envs_for(self, program):
        return [env for cmd, env in self.calls
                if os.path.basename(str(cmd[0])) == program]


class _FakeClaudeProc:
    """Stand-in for the `claude` Popen in trigger(): yields no events."""

    def __init__(self):
        self.stdout = iter(())

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


class EvalSandboxEnvTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-eval-envtest-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = make_operator_home(self.tmp)
        patch = mock.patch.dict(
            os.environ, {"HOME": self.home, "XDG_CONFIG_HOME": self.home,
                         "ACS_EVAL_KEEP": "0"})
        patch.start()
        self.addCleanup(patch.stop)

    # -- AC-1 -------------------------------------------------------------- #

    def test_sandbox_env_does_not_override_home(self):
        """The env `claude -p` inherits keeps the operator's real HOME, so the
        session resolves the operator's own plugin cache."""
        with harness.Sandbox(prefix="EVAL", slug="shop") as sb:
            self.assertEqual(
                sb.env["HOME"], self.home,
                "Sandbox.env['HOME'] must stay the operator's HOME; a rewritten "
                "HOME hides $HOME/.claude/plugins/cache from every claude -p")
            self.assertNotEqual(sb.env["HOME"], sb.tmp)

    # -- AC-2 -------------------------------------------------------------- #

    def test_git_calls_use_an_isolated_env(self):
        """Every git subprocess the sandbox runs gets the isolated env, and the
        isolation lives only in that per-call copy -- never in self.env."""
        recorder = _SubprocessRecorder(subprocess.run)
        with mock.patch.object(harness.subprocess, "run", recorder):
            with harness.Sandbox(prefix="EVAL", slug="shop") as sb:
                sb.changed_lines()
                self.assertTrue(
                    hasattr(sb, "_isolated_git_env"),
                    "Sandbox has no per-call isolated git env, so its git "
                    "isolation can only be coming from a process-wide override")
                isolated = sb._isolated_git_env()

                config = isolated["GIT_CONFIG_GLOBAL"]
                self.assertEqual(config, isolated["GIT_CONFIG_SYSTEM"])
                self.assertTrue(os.path.isfile(config))
                self.assertEqual(os.path.getsize(config), 0)
                git_home = isolated["HOME"]
                self.assertEqual(git_home, isolated["XDG_CONFIG_HOME"])
                self.assertTrue(os.path.isdir(git_home))
                self.assertNotEqual(git_home, self.home)
                self.assertEqual(isolated["GIT_ATTR_NOSYSTEM"], "1")
                for path in (config, git_home):
                    self.assertTrue(path.startswith(sb.tmp + os.sep),
                                    "%s must live under the sandbox tmp so it "
                                    "is cleaned up with it" % path)

                self.assertEqual(sb.env["HOME"], self.home)
                for key in ISOLATION_KEYS:
                    self.assertNotIn(key, sb.env)
                self.assertNotEqual(sb.env.get("XDG_CONFIG_HOME"), git_home)

                git_envs = recorder.envs_for("git")
                self.assertTrue(git_envs, "no git call was recorded")
                for env in git_envs:
                    self.assertEqual(env.get("HOME"), git_home)
                    self.assertEqual(env.get("GIT_CONFIG_GLOBAL"), config)
                    self.assertEqual(env.get("GIT_CONFIG_SYSTEM"), config)
                    self.assertEqual(env.get("GIT_ATTR_NOSYSTEM"), "1")

        self.assertFalse(os.path.exists(config))
        self.assertFalse(os.path.exists(git_home))

    # -- AC-3 -------------------------------------------------------------- #

    def test_seeding_survives_a_global_excludes_file_ignoring_acs(self):
        """A global core.excludesFile ignoring `.acs/` still cannot stop the
        sandbox from tracking .acs/settings.json."""
        self.assertTrue(
            add_is_blocked(self.tmp, operator_env(self.home)),
            "fixture is inert: the global excludesFile did not block "
            "`git add .acs/settings.json`, so this test proves nothing")

        with harness.Sandbox(prefix="EVAL", slug="shop") as sb:
            tracked = subprocess.run(
                ["git", "-C", sb.repo, "ls-files", ".acs/settings.json"],
                capture_output=True, text=True).stdout.strip()
        self.assertEqual(tracked, ".acs/settings.json")

    # -- AC-4 -------------------------------------------------------------- #

    def test_sandbox_build_spawns_no_paid_claude_session(self):
        """The whole regression surface is free: building and measuring a
        sandbox spawns git, never `claude`."""
        run_rec = _SubprocessRecorder(subprocess.run)
        popen_rec = _SubprocessRecorder(subprocess.Popen)
        with mock.patch.object(harness.subprocess, "run", run_rec), \
             mock.patch.object(harness.subprocess, "Popen", popen_rec):
            with harness.Sandbox(prefix="EVAL", slug="shop") as sb:
                sb.changed_lines()

        spawned = run_rec.argv0s() + popen_rec.argv0s()
        self.assertIn("git", spawned)
        self.assertNotIn("claude", spawned)

    # -- AC-5 -------------------------------------------------------------- #

    def test_run_skill_inherits_the_unoverridden_env(self):
        """run_skill() and trigger() -- the two paid call sites -- hand `claude`
        the operator's HOME, so the AC-1 fix reaches them and none of the git
        isolation leaks into the session."""
        with harness.Sandbox(prefix="EVAL", slug="shop") as sb:
            completed = mock.Mock(returncode=0, stderr="",
                                  stdout='{"is_error": false, "result": "ok"}')
            run_rec = _SubprocessRecorder(mock.Mock(return_value=completed))
            popen_rec = _SubprocessRecorder(mock.Mock(return_value=_FakeClaudeProc()))
            with mock.patch.object(harness.subprocess, "run", run_rec), \
                 mock.patch.object(harness.subprocess, "Popen", popen_rec):
                sb.run_skill("/acs:create-ticket Add X")
                sb.trigger("add a ticket")

            claude_envs = run_rec.envs_for("claude") + popen_rec.envs_for("claude")
            self.assertEqual(len(claude_envs), 2,
                             "expected one claude spawn from run_skill and one "
                             "from trigger")
            for env in claude_envs:
                self.assertEqual(env.get("HOME"), self.home)
                self.assertNotEqual(env.get("HOME"), sb.tmp)
                for key in ISOLATION_KEYS:
                    self.assertNotIn(key, env)


if __name__ == "__main__":
    unittest.main()
