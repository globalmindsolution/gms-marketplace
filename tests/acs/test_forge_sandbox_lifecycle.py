"""MAR-67 (Task 2) -- ForgeSandbox lifecycle: clone, run branch, teardown,
workspace-partition wipe, throwaway ticket prefix (AC-1, AC-3, AC-4, AC-5).

Every fixture is a local `git init --bare` "target" repo; `gh` is never
invoked -- PR-close behavior is asserted via a `_gh`-overriding subclass.
Stdlib-only; no network, no `claude` process.

Run:  python3 -m unittest tests.acs.test_forge_sandbox_lifecycle -v
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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


def remote_head_sha(bare, branch="main"):
    out = _run(["git", "ls-remote", bare, "refs/heads/%s" % branch]).stdout.strip()
    sha, _, _ = out.partition("\t")
    return sha


def remote_branches(bare):
    out = _run(["git", "ls-remote", "--heads", bare]).stdout
    names = []
    for line in out.splitlines():
        _, _, ref = line.partition("\t")
        if ref.startswith("refs/heads/"):
            names.append(ref[len("refs/heads/"):])
    return names


def delete_remote_branch(bare, branch="main"):
    """Simulate the default branch being deleted from the target mid-run."""
    _run(["git", "-C", bare, "config", "receive.denyDeleteCurrent", "ignore"])
    tmp = tempfile.mkdtemp(prefix="acs-forge-branchdelete-")
    try:
        clone = os.path.join(tmp, "delete")
        _run(["git", "clone", "-q", bare, clone])
        _run(["git", "-C", clone, "push", "-q", "origin", "--delete", branch])
    finally:
        _run(["rm", "-rf", tmp], check=False)


def push_drift_commit(bare, branch="main"):
    """Simulate an external write to the target's default branch mid-run."""
    tmp = tempfile.mkdtemp(prefix="acs-forge-drift-")
    try:
        clone = os.path.join(tmp, "drift")
        _run(["git", "clone", "-q", bare, clone])
        _run(["git", "-C", clone, "config", "user.email", "drift@example.com"])
        _run(["git", "-C", clone, "config", "user.name", "drift"])
        with open(os.path.join(clone, "DRIFT.md"), "w") as fh:
            fh.write("unexpected external write\n")
        _run(["git", "-C", clone, "add", "-A"])
        _run(["git", "-C", clone, "commit", "-q", "-m", "drift"])
        _run(["git", "-C", clone, "push", "-q", "origin", branch])
    finally:
        _run(["rm", "-rf", tmp], check=False)


def _hazard_cases(cfg_root):
    """(label, apply(sb)) for every real-world git hazard known to have
    crashed the seeding `add`/`commit` calls or bypassed config-only
    isolation: excludesFile hiding .acs/, gpgsign with no working signer, a
    failing hooksPath hook, autocrlf+safecrlf rejecting the LF payload, a
    templateDir hook copied into .git/hooks at clone time (config isolation
    cannot un-install an already-copied hook file), a templateDir
    info/exclude copied at clone time (repo-local, unreachable by any
    GIT_CONFIG_*/HOME/XDG isolation), a templateDir prepare-commit-msg hook
    (a hook `--no-verify` never covered), the XDG_CONFIG_HOME/git/ignore
    excludes fallback (resolved from HOME, not from any config key), and its
    HOME-only variant (no XDG_CONFIG_HOME set at all)."""
    excludes_file = os.path.join(cfg_root, "excludes")
    with open(excludes_file, "w") as fh:
        fh.write(".acs/\n")
    excludes_cfg = os.path.join(cfg_root, "excludesFile.gitconfig")
    with open(excludes_cfg, "w") as fh:
        fh.write("[core]\n\texcludesFile = %s\n" % excludes_file)

    gpgsign_cfg = os.path.join(cfg_root, "gpgsign.gitconfig")
    with open(gpgsign_cfg, "w") as fh:
        fh.write("[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = false\n")

    hooks_dir = os.path.join(cfg_root, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    hook_path = os.path.join(hooks_dir, "pre-commit")
    with open(hook_path, "w") as fh:
        fh.write("#!/bin/sh\nexit 1\n")
    os.chmod(hook_path, 0o755)
    hookspath_cfg = os.path.join(cfg_root, "hooksPath.gitconfig")
    with open(hookspath_cfg, "w") as fh:
        fh.write("[core]\n\thooksPath = %s\n" % hooks_dir)

    autocrlf_cfg = os.path.join(cfg_root, "autocrlf.gitconfig")
    with open(autocrlf_cfg, "w") as fh:
        fh.write("[core]\n\tautocrlf = true\n\tsafecrlf = true\n")

    template_dir = os.path.join(cfg_root, "template")
    template_hooks_dir = os.path.join(template_dir, "hooks")
    os.makedirs(template_hooks_dir, exist_ok=True)
    template_hook_path = os.path.join(template_hooks_dir, "pre-commit")
    with open(template_hook_path, "w") as fh:
        fh.write("#!/bin/sh\nexit 1\n")
    os.chmod(template_hook_path, 0o755)
    templatedir_cfg = os.path.join(cfg_root, "templateDir.gitconfig")
    with open(templatedir_cfg, "w") as fh:
        fh.write("[init]\n\ttemplateDir = %s\n" % template_dir)

    # A templateDir whose info/exclude (not a hook) lists .acs/ -- copied
    # into .git/info/exclude at clone time, repo-local so no GIT_CONFIG_*/
    # HOME/XDG isolation can reach it; only an empty-template clone can.
    template_exclude_dir = os.path.join(cfg_root, "template-exclude")
    os.makedirs(os.path.join(template_exclude_dir, "info"), exist_ok=True)
    with open(os.path.join(template_exclude_dir, "info", "exclude"), "w") as fh:
        fh.write(".acs/\n")
    template_exclude_cfg = os.path.join(cfg_root, "templateDirExclude.gitconfig")
    with open(template_exclude_cfg, "w") as fh:
        fh.write("[init]\n\ttemplateDir = %s\n" % template_exclude_dir)

    # A templateDir whose hooks/prepare-commit-msg fails -- a hook
    # `--no-verify` never covered (it only skips pre-commit/commit-msg).
    template_prepare_dir = os.path.join(cfg_root, "template-prepare-commit-msg")
    template_prepare_hooks_dir = os.path.join(template_prepare_dir, "hooks")
    os.makedirs(template_prepare_hooks_dir, exist_ok=True)
    template_prepare_hook_path = os.path.join(template_prepare_hooks_dir,
                                              "prepare-commit-msg")
    with open(template_prepare_hook_path, "w") as fh:
        fh.write("#!/bin/sh\nexit 1\n")
    os.chmod(template_prepare_hook_path, 0o755)
    template_prepare_cfg = os.path.join(cfg_root, "templateDirPrepareCommitMsg.gitconfig")
    with open(template_prepare_cfg, "w") as fh:
        fh.write("[init]\n\ttemplateDir = %s\n" % template_prepare_dir)

    def _global_config(path):
        def apply(sb):
            sb.env["GIT_CONFIG_GLOBAL"] = path
        return apply

    cases = [
        ("core.excludesFile ignoring .acs/", _global_config(excludes_cfg)),
        ("commit.gpgsign with no working signer", _global_config(gpgsign_cfg)),
        ("core.hooksPath with a failing hook", _global_config(hookspath_cfg)),
        ("core.autocrlf + core.safecrlf rejecting LF", _global_config(autocrlf_cfg)),
        ("init.templateDir installing a failing pre-commit hook",
         _global_config(templatedir_cfg)),
        ("init.templateDir installing a hostile info/exclude for .acs/",
         _global_config(template_exclude_cfg)),
        ("init.templateDir installing a failing prepare-commit-msg hook",
         _global_config(template_prepare_cfg)),
    ]

    empty_cfg = os.path.join(cfg_root, "empty.gitconfig")
    open(empty_cfg, "a").close()
    xdg_home = os.path.join(cfg_root, "xdg-config-home")
    os.makedirs(os.path.join(xdg_home, "git"), exist_ok=True)
    with open(os.path.join(xdg_home, "git", "ignore"), "w") as fh:
        fh.write(".acs/\n")

    def _xdg_config_home(sb):
        sb.env["GIT_CONFIG_GLOBAL"] = empty_cfg
        sb.env["XDG_CONFIG_HOME"] = xdg_home

    cases.append(("XDG_CONFIG_HOME/git/ignore excludes fallback ignoring .acs/",
                 _xdg_config_home))

    # HOME-only variant: no XDG_CONFIG_HOME at all, so git falls back to the
    # HOME-derived default (~/.config/git/ignore).
    home_only_dir = os.path.join(cfg_root, "home-only-config")
    os.makedirs(os.path.join(home_only_dir, ".config", "git"), exist_ok=True)
    with open(os.path.join(home_only_dir, ".config", "git", "ignore"), "w") as fh:
        fh.write(".acs/\n")

    def _home_only_git_ignore(sb):
        sb.env["GIT_CONFIG_GLOBAL"] = empty_cfg
        sb.env.pop("XDG_CONFIG_HOME", None)
        sb.env["HOME"] = home_only_dir

    cases.append(("HOME-only ~/.config/git/ignore excludes fallback "
                 "(no XDG_CONFIG_HOME) ignoring .acs/", _home_only_git_ignore))
    return cases


class FakeGh:
    """Records every argv passed to the `_gh` seam; replies from a small script
    so `_close_open_prs` can be driven without any real `gh` process."""

    def __init__(self, prs=None, fail_list=False, fail_close=False):
        self.calls = []
        self.prs = prs if prs is not None else []
        self.fail_list = fail_list
        self.fail_close = fail_close

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("pr", "list"):
            if self.fail_list:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="gh: not authenticated")
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps(self.prs), stderr="")
        if args[:2] == ("pr", "close"):
            rc = 1 if self.fail_close else 0
            return subprocess.CompletedProcess(args, rc, stdout="", stderr="gh: close failed" if self.fail_close else "")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


def stubbed(gh=None):
    """A ForgeSandbox subclass whose `_gh` seam is replaced by a FakeGh."""
    gh = gh if gh is not None else FakeGh()

    class _Stubbed(harness.ForgeSandbox):
        def _gh(self, *args):
            return gh(*args)

    _Stubbed.fake_gh = gh
    return _Stubbed


class ForgeSandboxLifecycleTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-forge-lifecycle-test-")
        self.addCleanup(subprocess.run, ["rm", "-rf", self.tmp])
        self.bare = make_target_repo(self.tmp)

    # -- AC-1: clone + run branch ---------------------------------------- #

    def test_enter_clones_target_into_temp_checkout(self):
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            self.assertTrue(os.path.isdir(sb.repo))
            self.assertTrue(os.path.isfile(os.path.join(sb.repo, "README.md")))
            origin = _run(["git", "-C", sb.repo, "config", "--get", "remote.origin.url"]).stdout.strip()
            self.assertEqual(origin, self.bare)

    def test_run_branch_is_created_off_default_branch(self):
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            branch = _run(["git", "-C", sb.repo, "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
            self.assertEqual(branch, sb.run_branch)
            self.assertTrue(sb.run_branch.startswith("acs-eval/"))
            ancestor = subprocess.run(
                ["git", "-C", sb.repo, "merge-base", "--is-ancestor", sb.baseline_sha, "HEAD"])
            self.assertEqual(ancestor.returncode, 0)

    def test_run_branch_name_is_unique_across_two_sandboxes(self):
        with harness.ForgeSandbox(remote_url=self.bare) as sb1:
            run_branch1, run_id1 = sb1.run_branch, sb1.run_id
        with harness.ForgeSandbox(remote_url=self.bare) as sb2:
            run_branch2, run_id2 = sb2.run_branch, sb2.run_id
        self.assertNotEqual(run_id1, run_id2)
        self.assertNotEqual(run_branch1, run_branch2)

    def test_env_preserves_real_home_and_scrubs_git_vars(self):
        with mock.patch.dict(os.environ, {"GIT_DIR": "/should/not/leak"}):
            real_home = os.environ.get("HOME")
            with harness.ForgeSandbox(remote_url=self.bare) as sb:
                self.assertEqual(sb.env.get("HOME"), real_home)
                self.assertNotIn("GIT_DIR", sb.env)

    def test_enter_succeeds_despite_hostile_global_git_config(self):
        # Isolated "global" configs (via GIT_CONFIG_GLOBAL, never the real
        # gitconfig) reproducing every operator setting known to have crashed
        # the seeding `add`/`commit` calls with an unhandled CalledProcessError
        # and a leaked checkout. Structural isolation (GIT_CONFIG_GLOBAL/
        # GIT_CONFIG_SYSTEM pointed at an empty temp config for just those two
        # calls) closes the whole class at once, not key-by-key.
        cfg_root = tempfile.mkdtemp(prefix="acs-forge-globalcfg-", dir=self.tmp)
        for label, apply_hazard in _hazard_cases(cfg_root):
            with self.subTest(hazard=label):
                sb = harness.ForgeSandbox(remote_url=self.bare)
                # Set directly on sb.env (post-construction, after the GIT_*
                # scrub) so this instance's git calls see the hostile config.
                apply_hazard(sb)
                with sb:
                    settings_path = os.path.join(sb.repo, ".acs", "settings.json")
                    self.assertTrue(os.path.isfile(settings_path))
                    log = _run(["git", "-C", sb.repo, "log", "--name-only", "-1"]).stdout
                    self.assertIn(".acs/settings.json", log)

    def test_isolated_git_env_sets_git_attr_nosystem(self):
        # K-2: closes the system /etc/gitattributes vector for the seeding
        # calls (e.g. a `*.json working-tree-encoding=UTF-16` system
        # attribute breaking `git add` with "fatal: BOM is required").
        #
        # Git gives GIT_CONFIG_SYSTEM an override path for testing config,
        # but there is no equivalent for the *attributes* system file: git
        # resolves it from a compile-time path with no env-settable redirect
        # (verified empirically -- setting GIT_ATTR_SYSTEM has zero effect on
        # attribute resolution, unlike GIT_CONFIG_SYSTEM). Reproducing the
        # hazard live would require writing to (or depending on the content
        # of) the real /etc/gitattributes on the machine running this suite,
        # which the hard constraints for this test file rule out. So this
        # case is validated at the unit level -- the fix is a single,
        # well-documented git flag (GIT_ATTR_NOSYSTEM) whose semantics are
        # not in question, only its presence in the isolated seeding env is
        # -- and the live hazard itself was independently reproduced and
        # confirmed by two verify lenses (see iter-5-verify.md, finding K-2).
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            env = sb._isolated_git_env()
        self.assertEqual(env.get("GIT_ATTR_NOSYSTEM"), "1")

    def test_remote_url_target_matching_self_owner_name_is_rejected(self):
        owner_name = harness._owner_name_from_remote_url(self.bare)
        with mock.patch.object(harness, "_self_owner_name", return_value=owner_name):
            with self.assertRaises(harness.ForgeConfigError):
                with harness.ForgeSandbox(remote_url=self.bare):
                    pass

    def test_enter_raises_and_cleans_up_when_marker_missing(self):
        bare = make_target_repo(self.tmp, marker=False, name="acs-eval-nomarker")
        sb = harness.ForgeSandbox(remote_url=bare)
        with self.assertRaises(harness.ForgeConfigError):
            sb.__enter__()
        self.assertFalse(os.path.isdir(sb.tmp))

    def test_enter_wraps_post_clone_step_failure_in_forge_config_error_and_cleans_up(self):
        # Any post-clone __enter__ step (not just the marker guard) must be
        # covered by the same cleanup-then-typed-raise pattern.
        boom = RuntimeError("boom from a post-clone step")
        with mock.patch.object(harness.ForgeSandbox, "_wipe_partition", side_effect=boom):
            sb = harness.ForgeSandbox(remote_url=self.bare)
            with self.assertRaises(harness.ForgeConfigError) as ctx:
                sb.__enter__()
            self.assertIn("boom from a post-clone step", str(ctx.exception))
            self.assertFalse(os.path.isdir(sb.tmp))

    def test_default_branch_never_checked_out_for_writes(self):
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            self.assertEqual(sb.default_branch, "main")
            branch = _run(["git", "-C", sb.repo, "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
            self.assertNotEqual(branch, sb.default_branch)
            self.assertEqual(branch, sb.run_branch)

    # -- AC-3: teardown ---------------------------------------------------- #

    def test_exit_deletes_run_branch_from_remote(self):
        Stubbed = stubbed()
        with Stubbed(remote_url=self.bare) as sb:
            _run(["git", "-C", sb.repo, "push", "-q", "origin", sb.run_branch])
            self.assertIn(sb.run_branch, remote_branches(self.bare))
            run_branch = sb.run_branch
        self.assertNotIn(run_branch, remote_branches(self.bare))

    def test_exit_deletes_pipeline_created_branches_carrying_the_run_prefix(self):
        Stubbed = stubbed()
        with Stubbed(remote_url=self.bare) as sb:
            pipeline_branch = "story/FORGE%s-1-add-x" % sb.run_id
            _run(["git", "-C", sb.repo, "push", "-q", "origin",
                  "HEAD:refs/heads/%s" % pipeline_branch])
            self.assertIn(pipeline_branch, remote_branches(self.bare))
        self.assertNotIn(pipeline_branch, remote_branches(self.bare))

    def test_exit_closes_open_pr_via_gh_seam(self):
        gh = FakeGh()
        Stubbed = stubbed(gh)
        with Stubbed(remote_url=self.bare) as sb:
            head_ref = "acs-eval/%s" % sb.run_id
            gh.prs = [{"number": 42, "headRefName": head_ref}]
            owner_name = sb.owner_name
        close_calls = [c for c in gh.calls if c[:2] == ("pr", "close")]
        self.assertEqual(len(close_calls), 1)
        self.assertEqual(
            close_calls[0],
            ("pr", "close", "42", "--repo", owner_name, "--delete-branch"))

    def test_exit_leaves_unrelated_prs_alone(self):
        gh = FakeGh()
        Stubbed = stubbed(gh)
        with Stubbed(remote_url=self.bare) as sb:
            gh.prs = [{"number": 7, "headRefName": "story/UNRELATED-9-thing"}]
        close_calls = [c for c in gh.calls if c[:2] == ("pr", "close")]
        self.assertEqual(close_calls, [])

    def test_default_branch_sha_unchanged_is_verified_and_drift_is_reported(self):
        Stubbed = stubbed()
        with Stubbed(remote_url=self.bare) as sb:
            pass
        self.assertEqual(sb.teardown_errors, [])

        with Stubbed(remote_url=self.bare) as sb2:
            push_drift_commit(self.bare)
            drifted_sha = remote_head_sha(self.bare)
        self.assertTrue(sb2.teardown_errors)
        self.assertTrue(any("drifted" in e for e in sb2.teardown_errors))
        self.assertEqual(remote_head_sha(self.bare), drifted_sha)
        self.assertNotEqual(remote_head_sha(self.bare), sb2.baseline_sha)

    def test_default_branch_deleted_entirely_is_reported_as_drift(self):
        Stubbed = stubbed()
        with Stubbed(remote_url=self.bare) as sb:
            delete_remote_branch(self.bare)
        self.assertTrue(sb.teardown_errors)
        self.assertTrue(any("no longer exists" in e for e in sb.teardown_errors))

    def test_teardown_is_idempotent_and_survives_gh_failure(self):
        gh = FakeGh(fail_list=True)
        Stubbed = stubbed(gh)
        with Stubbed(remote_url=self.bare) as sb:
            pass
        self.assertTrue(any("gh pr list failed" in e for e in sb.teardown_errors))
        # A second, redundant teardown call must not raise either.
        sb.__exit__(None, None, None)

    def test_teardown_runs_even_when_the_body_raises(self):
        gh = FakeGh()
        Stubbed = stubbed(gh)
        holder = {}

        def body():
            with Stubbed(remote_url=self.bare) as sb:
                holder["sb"] = sb
                raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            body()
        self.assertTrue(gh.calls)  # teardown's gh seam still ran
        self.assertFalse(os.path.isdir(holder["sb"].tmp))  # and cleaned up

    def test_keep_flag_preserves_checkout_but_still_reports(self):
        gh = FakeGh(fail_list=True)
        Stubbed = stubbed(gh)
        with Stubbed(remote_url=self.bare, keep=True) as sb:
            pass
        try:
            self.assertTrue(os.path.isdir(sb.tmp))
            self.assertTrue(sb.teardown_errors)
        finally:
            subprocess.run(["rm", "-rf", sb.tmp])

    # -- AC-4: workspace-partition wipe ------------------------------------ #

    def test_enter_wipes_a_preexisting_workspace_partition(self):
        workspace = tempfile.mkdtemp(prefix="acs-forge-ws-test-", dir=self.tmp)
        partition_id = harness._partition_id_from_remote(self.bare)
        stale_dir = os.path.join(workspace, partition_id)
        os.makedirs(stale_dir)
        with open(os.path.join(stale_dir, "stale.json"), "w") as fh:
            fh.write("{}")
        with harness.ForgeSandbox(remote_url=self.bare, workspace=workspace) as sb:
            self.assertEqual(sb.partition_id, partition_id)
            self.assertFalse(os.path.exists(stale_dir))

    def test_wipe_is_a_noop_when_no_partition_exists(self):
        workspace = tempfile.mkdtemp(prefix="acs-forge-ws-empty-test-", dir=self.tmp)
        with harness.ForgeSandbox(remote_url=self.bare, workspace=workspace) as sb:
            self.assertTrue(os.path.isdir(sb.ws))

    def test_partition_id_matches_acs_lib_repo_partition_id(self):
        sys.path.insert(0, harness.SOURCE_SCRIPTS)
        import acs_lib  # noqa: E402  (path-inserted, mirrors the runner's own resolution)
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            remote = _run(["git", "-C", sb.repo, "config", "--get", "remote.origin.url"]).stdout.strip()
            expected = harness._partition_id_from_remote(remote)
            got = acs_lib.repo_partition_id(sb.repo)
        self.assertEqual(got, expected)

    # -- AC-5: throwaway ticket prefix -------------------------------------- #

    def test_forge_prefix_matches_acs_ticket_prefix_pattern(self):
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            self.assertRegex(sb.prefix, r"^[A-Z][A-Z0-9]*$")

    def test_forge_prefix_is_unique_per_run(self):
        with harness.ForgeSandbox(remote_url=self.bare) as sb1:
            prefix1 = sb1.prefix
        with harness.ForgeSandbox(remote_url=self.bare) as sb2:
            prefix2 = sb2.prefix
        self.assertNotEqual(prefix1, prefix2)

    def test_forge_prefix_differs_from_this_repos_ticket_prefix(self):
        with open(os.path.join(REPO_ROOT, ".acs", "settings.json"), encoding="utf-8") as fh:
            this_repo_prefix = json.load(fh)["ticket_prefix"]
        self.assertEqual(this_repo_prefix, "MAR")
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            self.assertNotEqual(sb.prefix, this_repo_prefix)
            self.assertTrue(sb.prefix.startswith("FORGE"))

    def test_seeded_settings_use_the_forge_prefix_and_temp_workspace(self):
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            with open(os.path.join(sb.repo, ".acs", "settings.json"), encoding="utf-8") as fh:
                settings = json.load(fh)
            with open(os.path.join(sb.repo, ".acs", "settings.local.json"), encoding="utf-8") as fh:
                local = json.load(fh)
        self.assertEqual(settings["ticket_prefix"], sb.prefix)
        self.assertEqual(settings["test_coverage_percent"], sb.coverage)
        self.assertEqual(local["workspace_path"], sb.ws)

    def test_first_allocated_ticket_id_is_forge_prefix_dash_one(self):
        with harness.ForgeSandbox(remote_url=self.bare) as sb:
            proc = subprocess.run(
                [sys.executable, os.path.join(harness.SOURCE_SCRIPTS, "new-ticket.py"),
                 "--title", "forge smoke", "--type", "task"],
                cwd=sb.repo, capture_output=True, text=True, env=sb.env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            ticket_id = json.loads(proc.stdout)["ticket_id"]
        self.assertEqual(ticket_id, "%s-1" % sb.prefix)

    # -- full lifecycle (AC-1, AC-3, AC-4, AC-5, AC-6) ---------------------- #

    def test_full_lifecycle_against_a_local_bare_target_repo(self):
        baseline_sha = remote_head_sha(self.bare)
        gh = FakeGh()
        Stubbed = stubbed(gh)

        # This is ordinary post-seeding pipeline activity, outside the
        # seeding calls' own isolation (by design -- see _isolated_git_env's
        # docstring); GIT_ATTR_NOSYSTEM here only keeps this local test
        # independent of whatever system gitattributes the test-running
        # machine happens to carry, not part of the code under test.
        pipeline_env = dict(os.environ, GIT_ATTR_NOSYSTEM="1")
        with Stubbed(remote_url=self.bare) as sb:
            with open(os.path.join(sb.repo, "CHANGES.md"), "w") as fh:
                fh.write("forge run change\n")
            _run(["git", "-C", sb.repo, "add", "-A"], env=pipeline_env)
            _run(["git", "-C", sb.repo, "commit", "-q", "-m", "forge run change"],
                 env=pipeline_env)
            _run(["git", "-C", sb.repo, "push", "-q", "origin", sb.run_branch],
                 env=pipeline_env)
            gh.prs = [{"number": 1, "headRefName": sb.run_branch}]
            run_branch = sb.run_branch

        self.assertEqual(remote_head_sha(self.bare), baseline_sha)
        self.assertNotIn(run_branch, remote_branches(self.bare))
        self.assertEqual(sb.teardown_errors, [])


if __name__ == "__main__":
    unittest.main()
