"""ADR-0136: acs state stays in the main checkout, and is written through `acs.py write`.

The workspace is `<main-checkout>/.acs/state-machine/<repo-id>/` -- one folder
at the main checkout's root that every linked worktree resolves to, never a
worktree's own folder. A Claude Code session in a worktree is refused any
Edit/Write whose target is in the main checkout, so every state file a skill or
an agent writes goes through `acs.py write` -- Python run from the worktree --
instead of the Write tool. (When the Bash sandbox is on, /acs:setup offers the
`sandbox.filesystem.allowWrite` rule for that folder: tests/acs/test_claude_permissions.py.)

Pinned here:
  * root derivation -- main checkout, subdirectory, linked worktree, a worktree
    nested in the checkout (`.claude/worktrees/x`), all to the main checkout's
    `.acs/state-machine`; the unchanged refusals; doctor's `state_root`;
  * `acs.py write` -- inside/outside/`..`/symlink/append/atomic, the run-relative
    default, `--run`, the machine-owned ledgers it refuses, and a first write
    that leaves the checkout clean.
"""

import errno
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


def _root(repo):
    """The one state root: the MAIN checkout's .acs/state-machine."""
    return os.path.join(repo, ".acs", "state-machine")


class _TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)


# ---------------------------------------------------------------------------
# root derivation
# ---------------------------------------------------------------------------

class TestRootDerivation(_TmpCase):

    def test_main_checkout_resolves_to_its_acs_state_machine(self):
        repo = _mkrepo(self.tmp)
        self.assertEqual(_real(lib.default_state_root(repo)), _real(_root(repo)))

    def test_subdirectory_resolves_to_the_same_root(self):
        repo = _mkrepo(self.tmp)
        sub = os.path.join(repo, "a", "b")
        os.makedirs(sub)
        self.assertEqual(_real(lib.default_state_root(sub)), _real(_root(repo)))

    def test_linked_worktree_resolves_to_the_main_checkouts_root(self):
        repo = _mkrepo(self.tmp)
        wt = os.path.join(self.tmp, "wt")
        _git("-C", repo, "worktree", "add", "-q", "-b", "wt-branch", wt)
        self.assertEqual(_real(lib.default_state_root(wt)), _real(_root(repo)))
        self.assertNotEqual(_real(lib.default_state_root(wt)), _real(_root(wt)))

    def test_nested_claude_worktree_resolves_to_the_main_checkouts_root(self):
        repo = _mkrepo(self.tmp)
        nested = os.path.join(repo, ".claude", "worktrees", "x")
        _git("-C", repo, "worktree", "add", "-q", "-b", "nested", nested)
        self.assertEqual(_real(lib.default_state_root(nested)), _real(_root(repo)))
        self.assertEqual(_real(lib.default_state_root(nested)),
                         _real(lib.default_state_root(repo)))

    def test_nothing_lives_in_the_git_dir(self):
        repo = _mkrepo(self.tmp)
        root = lib.default_state_root(repo)
        lib.write_json(os.path.join(root, "acme-shop", "counters.json"), {"next": 1})
        self.assertFalse(os.path.exists(os.path.join(repo, ".git", "acs")))

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

    def test_the_checkout_stays_clean_after_a_state_write(self):
        repo = _mkrepo(self.tmp)
        root = lib.default_state_root(repo)
        lib.write_json(os.path.join(root, "acme-shop", "counters.json"), {"next": 1})
        status = _git("-C", repo, "status", "--porcelain", "-uall").stdout
        self.assertEqual(status.strip(), "")

    def test_doctor_reports_the_state_root(self):
        repo = _mkrepo(self.tmp)
        proc = subprocess.run([sys.executable, ACS, "doctor"], cwd=repo,
                              capture_output=True, text=True)
        out = json.loads(proc.stdout)
        self.assertEqual(_real(out["state_root"]["path"]), _real(_root(repo)))
        self.assertIsNone(out["state_root"]["error"])
        self.assertEqual(sorted(out["state_root"]), ["error", "path"])

    def test_doctor_from_a_worktree_reports_the_main_checkouts_root(self):
        repo = _mkrepo(self.tmp)
        wt = os.path.join(self.tmp, "wt")
        _git("-C", repo, "worktree", "add", "-q", "-b", "wt-branch", wt)
        proc = subprocess.run([sys.executable, ACS, "doctor"], cwd=wt,
                              capture_output=True, text=True)
        self.assertEqual(_real(json.loads(proc.stdout)["state_root"]["path"]),
                         _real(_root(repo)))

    def test_doctor_outside_a_repo_reports_why_there_is_no_root(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        proc = subprocess.run([sys.executable, ACS, "doctor"], cwd=plain,
                              capture_output=True, text=True)
        report = json.loads(proc.stdout)["state_root"]
        self.assertIsNone(report["path"])
        self.assertIn("not a git repository", report["error"])

    def test_a_worktrees_context_names_the_main_checkouts_workspace_and_run(self):
        repo = _mkrepo(self.tmp)
        repo_dir = lib.repo_dir(lib.default_state_root(repo), "acme-shop")
        wf_path = lib.default_workflow_path()
        wf = lib.validate_workflow_file(wf_path)
        lib.create_run(repo_dir, {"kind": "ticket", "ticket_id": "SHOP-1"}, wf, wf_path,
                       run_id="SHOP-1")
        wt = os.path.join(self.tmp, "wt")
        _git("-C", repo, "worktree", "add", "-q", "-b", "wt-branch", wt)
        lib.save_pointer(repo_dir, lib.checkout_id(wt), run_id="SHOP-1", checkout_path=wt)
        proc = subprocess.run([sys.executable, ACS, "context"], cwd=wt,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(_real(out["workspace"]), _real(_root(repo)))
        self.assertEqual(out["run_id"], "SHOP-1")
        self.assertEqual(_real(out["run_dir"]),
                         _real(os.path.join(_root(repo), "acme-shop", "runs", "SHOP-1")))


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

    def test_a_first_write_leaves_the_checkout_clean(self):
        """The workspace sits in the main checkout: a write through the CLI
        ignores it exactly as write_json does, before anything lands there
        (ADR-0105 -- a repo may run acs without setup's ignore entry)."""
        os.unlink(os.path.join(self.ws, ".gitignore"))
        proc = self.write("steps/code/iter-1/notes.md", stdin="# Notes\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(os.path.join(self.ws, ".gitignore")) as fh:
            self.assertEqual(fh.read(), "*\n")
        status = _git("-C", self.repo, "status", "--porcelain", "-uall").stdout
        self.assertEqual(status.strip(), "")

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
