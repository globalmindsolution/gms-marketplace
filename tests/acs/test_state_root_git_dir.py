"""ADR-0136: acs state lives in the git common dir, and is written through `acs.py write`.

A Claude Code session in a worktree is refused any Edit/Write whose target is in
the main checkout, and the Bash sandbox lets Bash write only the working
directory, $TMPDIR and -- from a linked worktree -- the main repo's shared `.git`
directory. The workspace used to be `<main-checkout>/.acs/state-machine`, which
both rules refuse. It is now `<git-common-dir>/acs/state-machine`, migrated on
first derivation, and every state file a skill or an agent writes goes through
`acs.py write` instead of the Write tool.

Pinned here:
  * root derivation -- main checkout, subdirectory, linked worktree, a worktree
    nested in the checkout (`.claude/worktrees/x`), the unchanged refusals, and
    `git clean -fdx` leaving the state alone;
  * migration -- move, both-exist, idempotent, stored absolute paths, the
    cross-device fallback, a removal that fails, and doctor's leftover report;
  * `acs.py write` -- inside/outside/`..`/symlink/append/atomic, the run-relative
    default, `--run`, the machine-owned ledgers it refuses.
"""

import errno
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import SCRIPTS, load_module, run_main, pushd  # noqa: E402

import acs_lib as lib  # noqa: E402
from acs_lib import state_root as state_root_mod  # noqa: E402

ACS = os.path.join(SCRIPTS, "acs.py")


def _git(*args, cwd=None):
    return subprocess.run(["git"] + list(args), cwd=cwd, check=True,
                          capture_output=True, text=True)


def _mkrepo(parent, name="repo", remote="https://github.com/acme/shop.git", commit=True):
    path = os.path.join(parent, name)
    os.makedirs(path)
    _git("init", "-q", path)
    if remote:
        _git("-C", path, "remote", "add", "origin", remote)
    _git("-C", path, "config", "user.email", "acs-test@example.com")
    _git("-C", path, "config", "user.name", "acs-test")
    if commit:
        _git("-C", path, "commit", "--allow-empty", "-q", "-m", "init")
    return path


def _real(path):
    return os.path.realpath(path)


def _legacy(repo):
    return os.path.join(repo, ".acs", "state-machine")


def _new(repo):
    return os.path.join(repo, ".git", "acs", "state-machine")


class _TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)


# ---------------------------------------------------------------------------
# root derivation
# ---------------------------------------------------------------------------

class TestRootDerivation(_TmpCase):

    def test_main_checkout_resolves_under_the_git_dir(self):
        repo = _mkrepo(self.tmp)
        self.assertEqual(_real(lib.default_state_root(repo)), _real(_new(repo)))

    def test_subdirectory_resolves_to_the_same_root(self):
        repo = _mkrepo(self.tmp)
        sub = os.path.join(repo, "a", "b")
        os.makedirs(sub)
        self.assertEqual(_real(lib.default_state_root(sub)), _real(_new(repo)))

    def test_linked_worktree_shares_the_main_repos_root(self):
        repo = _mkrepo(self.tmp)
        wt = os.path.join(self.tmp, "wt")
        _git("-C", repo, "worktree", "add", "-q", "-b", "wt-branch", wt)
        self.assertEqual(_real(lib.default_state_root(wt)), _real(_new(repo)))

    def test_nested_claude_worktree_shares_the_main_repos_root(self):
        repo = _mkrepo(self.tmp)
        nested = os.path.join(repo, ".claude", "worktrees", "x")
        _git("-C", repo, "worktree", "add", "-q", "-b", "nested", nested)
        self.assertEqual(_real(lib.default_state_root(nested)), _real(_new(repo)))
        self.assertEqual(_real(lib.default_state_root(nested)),
                         _real(lib.default_state_root(repo)))

    def test_deriving_the_root_creates_nothing(self):
        repo = _mkrepo(self.tmp)
        lib.default_state_root(repo)
        self.assertFalse(os.path.exists(os.path.join(repo, ".git", "acs")))
        self.assertFalse(os.path.exists(os.path.join(repo, ".acs")))

    def test_bare_repo_is_still_refused(self):
        bare = os.path.join(self.tmp, "bare.git")
        _git("init", "-q", "--bare", bare)
        with self.assertRaises(lib.GateError) as ctx:
            lib.default_state_root(bare)
        self.assertIn("bare git repository", str(ctx.exception))

    def test_non_git_directory_is_still_refused(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        with self.assertRaises(lib.GateError) as ctx:
            lib.default_state_root(plain)
        self.assertIn("not a git repository", str(ctx.exception))

    def test_submodule_is_still_refused(self):
        upstream = _mkrepo(self.tmp, "upstream", remote=None)
        superp = _mkrepo(self.tmp, "super", remote=None)
        subprocess.run(["git", "-C", superp, "-c", "protocol.file.allow=always",
                        "submodule", "add", "-q", upstream, "mod"],
                       check=True, capture_output=True)
        with self.assertRaises(lib.GateError) as ctx:
            lib.default_state_root(os.path.join(superp, "mod"))
        self.assertIn("submodule", str(ctx.exception))

    def test_git_clean_fdx_leaves_the_state_alone(self):
        repo = _mkrepo(self.tmp)
        root = lib.default_state_root(repo)
        os.makedirs(os.path.join(root, "acme-shop"))
        marker = os.path.join(root, "acme-shop", "counters.json")
        with open(marker, "w") as fh:
            fh.write("{}\n")
        _git("-C", repo, "clean", "-fdxq")
        self.assertTrue(os.path.isfile(marker))

    def test_the_checkout_stays_clean_after_a_state_write(self):
        repo = _mkrepo(self.tmp)
        root = lib.default_state_root(repo)
        lib.write_json(os.path.join(root, "acme-shop", "counters.json"), {"next": 1})
        status = _git("-C", repo, "status", "--porcelain", "--ignored").stdout
        self.assertEqual(status.strip(), "")


# ---------------------------------------------------------------------------
# migration
# ---------------------------------------------------------------------------

def _seed_legacy(repo):
    """An un-migrated workspace with absolute paths stored in it, as the
    analysis loop (`draft.dir`) and a run's ledger store them."""
    old = _legacy(repo)
    rdir = os.path.join(old, "acme-shop", "runs", "SHOP-1")
    os.makedirs(os.path.join(rdir, "steps", "code"))
    with open(os.path.join(old, ".gitignore"), "w") as fh:
        fh.write("*\n")
    with open(os.path.join(rdir, "steps", "code", "result.json"), "w") as fh:
        json.dump({"status": "completed"}, fh)
    with open(os.path.join(rdir, "analysis.json"), "w") as fh:
        json.dump({"draft": {"dir": os.path.join(rdir, "steps", "a", "iter-1", "draft"),
                             "files": [os.path.join(old, "acme-shop", "x.md"),
                                       "/elsewhere/keep.md"]},
                   "workspace": old, "unrelated": old + "-not-under-it",
                   "count": 3}, fh)
    with open(os.path.join(rdir, "notes.md"), "w") as fh:
        fh.write("prose stays as written\n")
    return old, rdir


class TestMigration(_TmpCase):

    def setUp(self):
        super().setUp()
        self.repo = _mkrepo(self.tmp)

    def test_the_legacy_root_is_moved_and_a_note_left_behind(self):
        old, _ = _seed_legacy(self.repo)
        root = lib.default_state_root(self.repo)
        self.assertEqual(_real(root), _real(_new(self.repo)))
        self.assertFalse(os.path.exists(old))
        moved = os.path.join(root, "acme-shop", "runs", "SHOP-1", "steps", "code",
                             "result.json")
        self.assertEqual(lib.read_json(moved), {"status": "completed"})
        note = old + ".MOVED"
        with open(note, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(text.count("\n"), 1)
        self.assertIn(root, text)

    def test_stored_absolute_paths_are_rewritten_to_the_new_root(self):
        old, _ = _seed_legacy(self.repo)
        root = lib.default_state_root(self.repo)
        new_rdir = os.path.join(root, "acme-shop", "runs", "SHOP-1")
        doc = lib.read_json(os.path.join(new_rdir, "analysis.json"))
        self.assertEqual(doc["draft"]["dir"],
                         os.path.join(new_rdir, "steps", "a", "iter-1", "draft"))
        self.assertEqual(doc["draft"]["files"],
                         [os.path.join(root, "acme-shop", "x.md"), "/elsewhere/keep.md"])
        self.assertEqual(doc["workspace"], root)
        self.assertEqual(doc["unrelated"], old + "-not-under-it")
        self.assertEqual(doc["count"], 3)
        with open(os.path.join(new_rdir, "notes.md")) as fh:
            self.assertEqual(fh.read(), "prose stays as written\n")

    def test_a_migrated_run_still_resolves_through_the_cli(self):
        old = _legacy(self.repo)
        repo_dir = lib.repo_dir(old, "acme-shop")
        wf_path = lib.default_workflow_path()
        wf = lib.validate_workflow_file(wf_path)
        lib.create_run(repo_dir, {"kind": "ticket", "ticket_id": "SHOP-1"}, wf, wf_path,
                       run_id="SHOP-1")
        lib.save_pointer(repo_dir, lib.checkout_id(self.repo), run_id="SHOP-1",
                         checkout_path=self.repo)
        proc = subprocess.run([sys.executable, ACS, "context"], cwd=self.repo,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(_real(out["workspace"]), _real(_new(self.repo)))
        self.assertEqual(out["run_id"], "SHOP-1")
        self.assertEqual(_real(out["run_dir"]),
                         _real(os.path.join(_new(self.repo), "acme-shop", "runs", "SHOP-1")))
        proc = subprocess.run([sys.executable, ACS, "run", "show"], cwd=self.repo,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(old))

    def test_migration_is_idempotent(self):
        _seed_legacy(self.repo)
        first = lib.default_state_root(self.repo)
        note = _legacy(self.repo) + ".MOVED"
        with open(note) as fh:
            before = fh.read()
        snapshot = sorted(os.listdir(os.path.join(first, "acme-shop", "runs", "SHOP-1")))
        second = lib.default_state_root(self.repo)
        self.assertEqual(first, second)
        with open(note) as fh:
            self.assertEqual(fh.read(), before)
        self.assertEqual(sorted(os.listdir(os.path.join(second, "acme-shop", "runs",
                                                        "SHOP-1"))), snapshot)

    def test_both_roots_present_uses_the_new_one_and_leaves_the_old(self):
        old, _ = _seed_legacy(self.repo)
        new = _new(self.repo)
        os.makedirs(os.path.join(new, "acme-shop"))
        with open(os.path.join(new, "acme-shop", "counters.json"), "w") as fh:
            fh.write('{"next": 7}\n')
        root = lib.default_state_root(self.repo)
        self.assertEqual(_real(root), _real(new))
        self.assertTrue(os.path.isdir(old), "a leftover is reported, never deleted")
        self.assertFalse(os.path.exists(os.path.join(new, "acme-shop", "runs")))
        report = lib.state_root_report(self.repo)
        self.assertTrue(report["legacy_leftover"])
        self.assertEqual(_real(report["legacy"]), _real(old))
        self.assertEqual(_real(report["path"]), _real(new))

    def test_doctor_reports_the_leftover(self):
        _seed_legacy(self.repo)
        os.makedirs(_new(self.repo))
        proc = subprocess.run([sys.executable, ACS, "doctor"], cwd=self.repo,
                              capture_output=True, text=True)
        out = json.loads(proc.stdout)
        self.assertTrue(out["state_root"]["legacy_leftover"])
        self.assertEqual(_real(out["state_root"]["legacy"]), _real(_legacy(self.repo)))
        self.assertIn("leftover", out["state_root"]["message"])

    def test_doctor_reports_no_leftover_on_a_clean_repo(self):
        proc = subprocess.run([sys.executable, ACS, "doctor"], cwd=self.repo,
                              capture_output=True, text=True)
        out = json.loads(proc.stdout)
        self.assertFalse(out["state_root"]["legacy_leftover"])
        self.assertEqual(_real(out["state_root"]["path"]), _real(_new(self.repo)))

    def test_no_legacy_root_means_no_note(self):
        lib.default_state_root(self.repo)
        self.assertFalse(os.path.exists(_legacy(self.repo) + ".MOVED"))

    def test_a_worktree_migrates_the_main_checkouts_legacy_root(self):
        _seed_legacy(self.repo)
        wt = os.path.join(self.tmp, "wt")
        _git("-C", self.repo, "worktree", "add", "-q", "-b", "wt-branch", wt)
        root = lib.default_state_root(wt)
        self.assertEqual(_real(root), _real(_new(self.repo)))
        self.assertTrue(os.path.isdir(os.path.join(root, "acme-shop", "runs", "SHOP-1")))
        self.assertFalse(os.path.exists(_legacy(self.repo)))

    def test_cross_device_move_falls_back_to_copy_then_remove(self):
        old, _ = _seed_legacy(self.repo)
        real_rename = os.rename

        def rename(src, dst):
            if os.path.abspath(src) == os.path.abspath(old):
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            return real_rename(src, dst)

        with mock.patch.object(state_root_mod.os, "rename", side_effect=rename):
            root = lib.default_state_root(self.repo)
        self.assertFalse(os.path.exists(old))
        doc = lib.read_json(os.path.join(root, "acme-shop", "runs", "SHOP-1", "analysis.json"))
        self.assertEqual(doc["workspace"], root)
        parent = os.path.dirname(root)
        self.assertEqual(sorted(n for n in os.listdir(parent) if n.startswith(".")), [],
                         "no temp directory or guard file is left behind")

    def test_a_removal_that_fails_leaves_both_and_uses_the_new_one(self):
        old, _ = _seed_legacy(self.repo)

        def refuse_rename(src, dst):
            raise OSError(errno.EPERM, "Operation not permitted")

        def refuse_rmtree(path, *a, **k):
            raise OSError(errno.EPERM, "Operation not permitted")

        with mock.patch.object(state_root_mod.os, "rename", side_effect=refuse_rename), \
                mock.patch.object(state_root_mod.shutil, "rmtree", side_effect=refuse_rmtree), \
                mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            # os.rename refused for the tree; the staging->final step is os.replace.
            root = lib.default_state_root(self.repo)
        self.assertIn("could not be removed", err.getvalue())
        self.assertTrue(os.path.isdir(old))
        self.assertTrue(os.path.isfile(os.path.join(root, "acme-shop", "runs", "SHOP-1",
                                                    "steps", "code", "result.json")))
        self.assertTrue(lib.state_root_report(self.repo)["legacy_leftover"])

    def test_a_migration_that_cannot_complete_is_a_gate_error(self):
        _seed_legacy(self.repo)

        def refuse(*a, **k):
            raise OSError(errno.EACCES, "Permission denied")

        with mock.patch.object(state_root_mod.os, "rename", side_effect=refuse), \
                mock.patch.object(state_root_mod.shutil, "copytree", side_effect=refuse):
            with self.assertRaises(lib.GateError) as ctx:
                lib.default_state_root(self.repo)
        self.assertIn(_legacy(self.repo), str(ctx.exception))
        self.assertTrue(os.path.isdir(_legacy(self.repo)))
        self.assertFalse(os.path.exists(_new(self.repo)))

    def test_a_move_interrupted_after_the_rename_is_finished(self):
        """The old tree was renamed into staging, then the process died."""
        old, _ = _seed_legacy(self.repo)
        staging = os.path.join(self.repo, ".git", "acs", ".state-machine.migrating")
        os.makedirs(os.path.dirname(staging))
        os.rename(old, staging)
        root = lib.default_state_root(self.repo)
        self.assertFalse(os.path.exists(staging))
        doc = lib.read_json(os.path.join(root, "acme-shop", "runs", "SHOP-1", "analysis.json"))
        self.assertEqual(doc["workspace"], root)

    def test_a_partial_copy_is_discarded_and_redone(self):
        old, _ = _seed_legacy(self.repo)
        staging = os.path.join(self.repo, ".git", "acs", ".state-machine.migrating")
        os.makedirs(os.path.join(staging, "half"))
        root = lib.default_state_root(self.repo)
        self.assertFalse(os.path.exists(os.path.join(root, "half")))
        self.assertTrue(os.path.isdir(os.path.join(root, "acme-shop", "runs", "SHOP-1")))
        self.assertFalse(os.path.exists(old))

    def test_a_concurrent_migrator_that_won_is_respected(self):
        """The loser of a race finds the new root already there: it uses it."""
        old, _ = _seed_legacy(self.repo)
        new = _new(self.repo)
        real_rename = os.rename

        def lose(src, dst):
            if os.path.abspath(src) == os.path.abspath(old):
                os.makedirs(new)              # the winner landed first
                raise OSError(errno.ENOTEMPTY, "Directory not empty")
            return real_rename(src, dst)

        with mock.patch.object(state_root_mod.os, "rename", side_effect=lose):
            root = lib.default_state_root(self.repo)
        self.assertEqual(_real(root), _real(new))
        self.assertTrue(os.path.isdir(old))


# ---------------------------------------------------------------------------
# acs.py write
# ---------------------------------------------------------------------------

class TestWriteVerb(_TmpCase):

    def setUp(self):
        super().setUp()
        self.repo = _mkrepo(self.tmp)
        self.ws = lib.default_state_root(self.repo)
        self.repo_dir = lib.repo_dir(self.ws, "acme-shop")
        wf_path = lib.default_workflow_path()
        wf = lib.validate_workflow_file(wf_path)
        for run_id in ("SHOP-1", "SHOP-2"):
            lib.create_run(self.repo_dir, {"kind": "ticket", "ticket_id": run_id}, wf,
                           wf_path, run_id=run_id)
        lib.save_pointer(self.repo_dir, lib.checkout_id(self.repo), run_id="SHOP-1",
                         checkout_path=self.repo)
        self.rdir = lib.run_dir(self.repo_dir, "SHOP-1")

    def write(self, *args, stdin="hello\n", cwd=None):
        return subprocess.run([sys.executable, ACS, "write"] + list(args), input=stdin,
                              capture_output=True, text=True, cwd=cwd or self.repo)

    def assert_refused(self, proc, *needles):
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("acs write: "), proc.stderr)
        for needle in needles:
            self.assertIn(needle, proc.stderr)

    def test_a_relative_path_lands_in_the_current_run(self):
        proc = self.write("steps/code/iter-1/notes.md", stdin="# Notes\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        target = os.path.join(self.rdir, "steps", "code", "iter-1", "notes.md")
        self.assertEqual(out, {"ok": True, "path": _real(target), "bytes": 8,
                               "appended": False, "total_bytes": 8})
        with open(target, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# Notes\n")

    def test_content_is_written_verbatim(self):
        body = "no trailing newline — ünïcode"
        proc = self.write("steps/code/x.txt", stdin=body)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["bytes"], len(body.encode("utf-8")))
        with open(os.path.join(self.rdir, "steps", "code", "x.txt"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), body)

    def test_an_empty_stdin_writes_an_empty_file(self):
        proc = self.write("steps/code/empty.md", stdin="")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(os.path.getsize(os.path.join(self.rdir, "steps", "code",
                                                      "empty.md")), 0)

    def test_run_names_another_run(self):
        proc = self.write("--run", "SHOP-2", "steps/code/result.json", stdin="{}\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(lib.run_dir(self.repo_dir, "SHOP-2"),
                                                    "steps", "code", "result.json")))
        self.assertFalse(os.path.exists(os.path.join(self.rdir, "steps", "code",
                                                     "result.json")))

    def test_an_unknown_run_is_refused(self):
        self.assert_refused(self.write("--run", "SHOP-99", "x.md"), "SHOP-99")

    def test_a_relative_path_with_no_current_run_is_refused(self):
        lib.save_pointer(self.repo_dir, lib.checkout_id(self.repo), run_id=None,
                         checkout_path=self.repo)
        self.assert_refused(self.write("x.md"), "no current run")

    def test_an_absolute_path_inside_the_workspace_is_written(self):
        target = os.path.join(self.repo_dir, "SHOP-1", "clarifications.json")
        proc = self.write(target, stdin='{"items": []}\n')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(lib.read_json(target), {"items": []})

    def test_an_absolute_path_works_from_a_worktree_with_no_run(self):
        wt = os.path.join(self.tmp, "wt")
        _git("-C", self.repo, "worktree", "add", "-q", "-b", "wt-branch", wt)
        target = os.path.join(self.rdir, "steps", "code", "iter-1", "slice-a.md")
        proc = self.write(target, stdin="a\n", cwd=wt)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(target))
        # ...and a relative one names the worktree's own (absent) run.
        self.assert_refused(self.write("steps/code/x.md", cwd=wt), "no current run")
        proc = self.write("--run", "SHOP-1", "steps/code/y.md", cwd=wt)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_an_absolute_path_outside_the_workspace_is_refused(self):
        target = os.path.join(self.repo, "src", "app.py")
        self.assert_refused(self.write(target), "outside the workspace")
        self.assertFalse(os.path.exists(target))

    def test_a_dotdot_escape_is_refused(self):
        self.assert_refused(self.write("../../../../../../escape.md"), "outside the workspace")
        self.assert_refused(self.write(os.path.join(self.ws, "..", "escape.md")),
                            "outside the workspace")
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.ws), "escape.md")))

    def test_a_dotdot_that_stays_inside_is_allowed(self):
        proc = self.write("steps/code/../code/ok.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.rdir, "steps", "code", "ok.md")))

    def test_a_symlinked_directory_escape_is_refused(self):
        outside = os.path.join(self.tmp, "outside")
        os.makedirs(outside)
        os.makedirs(os.path.join(self.rdir, "steps"), exist_ok=True)
        os.symlink(outside, os.path.join(self.rdir, "steps", "link"))
        self.assert_refused(self.write("steps/link/pwned.md"), "outside the workspace")
        self.assertEqual(os.listdir(outside), [])

    def test_a_symlinked_file_escape_is_refused(self):
        outside = os.path.join(self.tmp, "victim.txt")
        with open(outside, "w") as fh:
            fh.write("original\n")
        os.makedirs(os.path.join(self.rdir, "steps", "code"), exist_ok=True)
        os.symlink(outside, os.path.join(self.rdir, "steps", "code", "result.json"))
        self.assert_refused(self.write("steps/code/result.json"), "outside the workspace")
        with open(outside) as fh:
            self.assertEqual(fh.read(), "original\n")

    def test_append_adds_to_the_file(self):
        self.assertEqual(self.write("steps/code/log.md", stdin="one\n").returncode, 0)
        proc = self.write("--append", "steps/code/log.md", stdin="two\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual((out["bytes"], out["appended"], out["total_bytes"]), (4, True, 8))
        with open(os.path.join(self.rdir, "steps", "code", "log.md")) as fh:
            self.assertEqual(fh.read(), "one\ntwo\n")

    def test_parallel_appends_lose_nothing(self):
        """review-code's adjudicators append to one file side by side."""
        procs = [subprocess.Popen([sys.executable, ACS, "write", "--append",
                                   "steps/review-code/iter-1/adjudication.md"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, cwd=self.repo, text=True)
                 for _ in range(8)]
        for i, proc in enumerate(procs):
            proc.stdin.write("ruling %d\n" % i)
            proc.stdin.close()
        for proc in procs:
            self.assertEqual(proc.wait(), 0, proc.stderr.read())
            proc.stdout.close()
            proc.stderr.close()
        folder = os.path.join(self.rdir, "steps", "review-code", "iter-1")
        with open(os.path.join(folder, "adjudication.md")) as fh:
            lines = sorted(fh.read().splitlines())
        self.assertEqual(lines, sorted("ruling %d" % i for i in range(8)))
        self.assertEqual(os.listdir(folder), ["adjudication.md"], "no guard or temp left")

    def test_append_creates_a_missing_file(self):
        proc = self.write("--append", "steps/code/new.md", stdin="first\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(os.path.join(self.rdir, "steps", "code", "new.md")) as fh:
            self.assertEqual(fh.read(), "first\n")

    def test_overwrite_replaces_the_file(self):
        self.write("steps/code/r.md", stdin="old content that is longer\n")
        self.write("steps/code/r.md", stdin="new\n")
        with open(os.path.join(self.rdir, "steps", "code", "r.md")) as fh:
            self.assertEqual(fh.read(), "new\n")

    def test_the_machine_owned_ledgers_are_refused(self):
        for rel in ("run.json", "steps/code/state.json", "lock.json",
                    "active-agents/abc.json", "steps/code/iter-1/filemap.json"):
            with self.subTest(rel=rel):
                self.assert_refused(self.write(rel, stdin="{}\n"), "acs.py")
        for path in (os.path.join(self.repo_dir, "runs-index.json"),
                     os.path.join(self.repo_dir, "tickets-index.json"),
                     os.path.join(self.repo_dir, "sessions", "x", "pointer.json")):
            with self.subTest(path=path):
                self.assert_refused(self.write(path, stdin="{}\n"), "acs.py")
        self.assertEqual(lib.load_run(self.rdir)["run_id"], "SHOP-1")

    def test_a_directory_target_is_refused(self):
        os.makedirs(os.path.join(self.rdir, "steps", "code", "dir"))
        self.assert_refused(self.write("steps/code/dir"), "directory")

    def test_the_write_is_atomic_when_the_rename_fails(self):
        target = os.path.join(self.rdir, "steps", "code", "result.json")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as fh:
            fh.write("before\n")
        mod = load_module("acs.py", "acs_write_atomic_probe")
        import acs_write_commands as wc
        with pushd(self.repo), \
                mock.patch.object(wc.os, "replace", side_effect=OSError(errno.EIO, "boom")):
            code, out, err = run_main(mod, ["write", "steps/code/result.json"],
                                      stdin="after\n")
        self.assertEqual(code, 2, err)
        with open(target) as fh:
            self.assertEqual(fh.read(), "before\n")
        self.assertEqual([n for n in os.listdir(os.path.dirname(target))
                          if n != "result.json"], [], "no temp file left behind")

    def test_context_reports_the_current_run(self):
        proc = subprocess.run([sys.executable, ACS, "context"], cwd=self.repo,
                              capture_output=True, text=True)
        out = json.loads(proc.stdout)
        self.assertEqual(out["run_id"], "SHOP-1")
        self.assertEqual(_real(out["run_dir"]), _real(self.rdir))
        lib.save_pointer(self.repo_dir, lib.checkout_id(self.repo), run_id=None,
                         checkout_path=self.repo)
        out = json.loads(subprocess.run([sys.executable, ACS, "context"], cwd=self.repo,
                                        capture_output=True, text=True).stdout)
        self.assertIsNone(out["run_id"])
        self.assertIsNone(out["run_dir"])


if __name__ == "__main__":
    unittest.main()
