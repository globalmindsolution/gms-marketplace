"""MAR-68 -- ForgeSandbox driving/seeding surface: run_script, run_skill (+
the _claude seam), gh_json, commit_file (AC-2 driver, plus the git-isolation
regression guard for the seeded commit).

Every fixture is a local `git init --bare` "target" repo; `claude` and `gh`
are never invoked -- both seams are stubbed via subclassing, following
test_forge_sandbox_lifecycle.py's house style. Stdlib-only; no network, no
`claude` process.

Run:  python3 -m unittest tests.acs.test_forge_sandbox_skill_driver -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.join(REPO_ROOT, "evals", "acs"))
import harness  # noqa: E402  (path-inserted, same resolution run_evals.py uses)


def _run(args, cwd=None, check=True, env=None):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)
    if check and proc.returncode != 0:
        raise AssertionError("%r failed: %s" % (args, proc.stderr))
    return proc


def make_target_repo(tmp, marker=True, name="acs-eval-target"):
    """A bare target repo seeded with a minimal buildable baseline commit on
    `main`, optionally carrying the FORGE_MARKER opt-in file."""
    bare = os.path.join(tmp, name + ".git")
    _run(["git", "init", "-q", "--bare", "--initial-branch=main", bare])
    seed = os.path.join(tmp, name + "-seed")
    _run(["git", "clone", "-q", bare, seed])
    _run(["git", "-C", seed, "config", "user.email", "seed@example.com"])
    _run(["git", "-C", seed, "config", "user.name", "seed"])
    with open(os.path.join(seed, "README.md"), "w") as fh:
        fh.write("# %s\n\nminimal buildable baseline\n" % name)
    if marker:
        with open(os.path.join(seed, harness.FORGE_MARKER), "w") as fh:
            fh.write("never-production; safe to force-reset\n")
    _run(["git", "-C", seed, "add", "-A"])
    _run(["git", "-C", seed, "commit", "-q", "-m", "seed"])
    _run(["git", "-C", seed, "push", "-q", "origin", "main"])
    return bare


DEFAULT_ENVELOPE = subprocess.CompletedProcess(
    [], 0,
    stdout=json.dumps({"is_error": False, "result": "done",
                       "total_cost_usd": 0.5, "num_turns": 7}),
    stderr="")


class FakeClaude:
    """Records every (cmd, timeout, repo, env) the `_claude` seam is called
    with; replies with a canned CompletedProcess so no `claude` ever runs."""

    def __init__(self, completed=None):
        self.calls = []
        self.completed = completed if completed is not None else DEFAULT_ENVELOPE

    def __call__(self, cmd, timeout, repo, env):
        self.calls.append((cmd, timeout, repo, env))
        return self.completed


def stubbed_claude(fake=None):
    """A ForgeSandbox subclass whose `_claude` seam is replaced by a FakeClaude."""
    fake = fake if fake is not None else FakeClaude()

    class _Stubbed(harness.ForgeSandbox):
        def _claude(self, cmd, timeout):
            return fake(cmd, timeout, self.repo, self.env)

    _Stubbed.fake_claude = fake
    return _Stubbed


class FakeGh:
    """Records every argv passed to the `_gh` seam; replies from a canned
    CompletedProcess so no `gh` ever runs."""

    def __init__(self, completed=None):
        self.calls = []
        self.completed = completed if completed is not None else \
            subprocess.CompletedProcess([], 0, stdout="{}", stderr="")

    def __call__(self, *args):
        self.calls.append(args)
        return self.completed


def stubbed_gh(fake=None):
    """A ForgeSandbox subclass whose `_gh` seam is replaced by a FakeGh."""
    fake = fake if fake is not None else FakeGh()

    class _Stubbed(harness.ForgeSandbox):
        def _gh(self, *args):
            return fake(*args)

    _Stubbed.fake_gh = fake
    return _Stubbed


def raising_gh():
    """A ForgeSandbox subclass whose `_gh` seam raises, simulating `gh`
    missing from PATH (R-10)."""
    class _Stubbed(harness.ForgeSandbox):
        def _gh(self, *args):
            raise FileNotFoundError("[Errno 2] No such file or directory: 'gh'")

    return _Stubbed


class ForgeSandboxSkillDriverTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-forge-skilldriver-test-")
        self.addCleanup(subprocess.run, ["rm", "-rf", self.tmp])
        self.bare = make_target_repo(self.tmp)

    # -- run_skill / _claude (AC-2) ---------------------------------------- #

    def test_run_skill_launches_claude_p_in_the_forge_checkout(self):
        fake = FakeClaude()
        Stubbed = stubbed_claude(fake)
        with Stubbed(remote_url=self.bare) as sb:
            sb.run_skill("run the /acs:create-pr skill")
            repo, env = sb.repo, sb.env

        self.assertEqual(len(fake.calls), 1)
        cmd, timeout, called_repo, called_env = fake.calls[0]
        self.assertEqual(cmd, [
            "claude", "-p", "run the /acs:create-pr skill",
            "--output-format", "json",
            "--permission-mode", "acceptEdits",
            "--allowedTools",
            " ".join(("Bash", "Read", "Write", "Edit", "Glob", "Grep",
                      "Task", "TodoWrite", "Skill")),
        ])
        self.assertEqual(timeout, 1800)
        self.assertEqual(called_repo, repo)
        self.assertIs(called_env, env)

    def test_run_skill_parses_the_json_envelope(self):
        Stubbed = stubbed_claude(FakeClaude(DEFAULT_ENVELOPE))
        with Stubbed(remote_url=self.bare) as sb:
            out = sb.run_skill("do the thing")

        self.assertEqual(out, {
            "ok": True, "is_error": False, "result": "done",
            "cost_usd": 0.5, "num_turns": 7, "raw": DEFAULT_ENVELOPE.stdout,
            "stderr": "", "returncode": 0,
        })

    def test_run_skill_reports_not_ok_on_error_envelope_or_unparseable_output(self):
        cases = [
            ("is_error true envelope", subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({"is_error": True, "result": "boom"}),
                stderr="")),
            ("non-zero returncode", subprocess.CompletedProcess(
                [], 1, stdout=json.dumps({"is_error": False, "result": "ok"}),
                stderr="fatal error")),
            ("unparseable stdout", subprocess.CompletedProcess(
                [], 0, stdout="not json", stderr="")),
        ]
        for label, completed in cases:
            with self.subTest(case=label):
                Stubbed = stubbed_claude(FakeClaude(completed))
                with Stubbed(remote_url=self.bare) as sb:
                    out = sb.run_skill("do the thing")
                self.assertFalse(out["ok"])
                self.assertEqual(out["raw"], completed.stdout)

    # -- run_script (AC-2 seeding) ------------------------------------------ #

    def test_run_script_runs_an_installed_hook_script_in_the_checkout(self):
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            out = sb.run_script("new-ticket.py", "--title", "forge smoke",
                                "--type", "task")
            self.assertEqual(out.returncode, 0, out.stderr)
            ticket_id = json.loads(out.stdout)["ticket_id"]

        self.assertEqual(ticket_id, "%s-1" % sb.prefix)

    # -- gh_json (AC-3) ------------------------------------------------------ #

    def test_gh_json_parses_output_from_the_gh_seam(self):
        pr = {"number": 7, "title": "[MAR-68] add bulk import endpoint"}
        fake = FakeGh(subprocess.CompletedProcess(
            [], 0, stdout=json.dumps(pr), stderr=""))
        Stubbed = stubbed_gh(fake)
        with Stubbed(remote_url=self.bare) as sb:
            got = sb.gh_json("pr", "view", "some-branch", "--repo", "o/n",
                             "--json", "number,title")
            calls_during_call = list(fake.calls)  # before __exit__'s own gh calls

        self.assertEqual(got, pr)
        self.assertEqual(calls_during_call, [
            ("pr", "view", "some-branch", "--repo", "o/n", "--json", "number,title"),
        ])

    def test_gh_json_returns_none_when_gh_fails_or_returns_unparseable_json(self):
        cases = [
            ("non-zero returncode", stubbed_gh(FakeGh(subprocess.CompletedProcess(
                [], 1, stdout="", stderr="gh: not authenticated")))),
            ("unparseable stdout", stubbed_gh(FakeGh(subprocess.CompletedProcess(
                [], 0, stdout="not json", stderr="")))),
            ("gh absent from PATH", raising_gh()),
        ]
        for label, Stubbed in cases:
            with self.subTest(case=label):
                with Stubbed(remote_url=self.bare) as sb:
                    got = sb.gh_json("pr", "view")
                self.assertIsNone(got)

    # -- commit_file (R-2 isolation regression guard) ------------------------ #

    def test_commit_file_creates_the_branch_and_commits_under_isolated_git_env(self):
        cfg_root = tempfile.mkdtemp(prefix="acs-forge-skilldriver-globalcfg-",
                                    dir=self.tmp)
        gpgsign_cfg = os.path.join(cfg_root, "gpgsign.gitconfig")
        with open(gpgsign_cfg, "w") as fh:
            fh.write("[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = false\n")

        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            # A hostile "global" config applied AFTER __enter__'s own seeding,
            # via GIT_CONFIG_GLOBAL (never the real gitconfig): if commit_file
            # used self.env directly instead of self._isolated_git_env(), this
            # gpgsign=true with no working signer would raise
            # CalledProcessError on `git commit` (R-2).
            sb.env["GIT_CONFIG_GLOBAL"] = gpgsign_cfg

            branch = "task/%s-1-seed" % sb.prefix
            sb.commit_file("SEED.md", "seed content\n", "seed commit",
                           branch=branch)

            current = _run(["git", "-C", sb.repo, "rev-parse",
                            "--abbrev-ref", "HEAD"]).stdout.strip()
            log = _run(["git", "-C", sb.repo, "log", "--name-only",
                       "-1"]).stdout

        self.assertEqual(current, branch)
        self.assertIn("SEED.md", log)
        self.assertIn("seed commit", log)


if __name__ == "__main__":
    unittest.main()
