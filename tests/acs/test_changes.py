"""acs_lib.changes and `acs.py changes ...` -- the run's working-tree changeset (ADR-0127).

Only /acs:create-pr commits, so "what did this run change" is read off the
working tree: a baseline the first `step start` records, a snapshot tree built
in a throwaway index, and the diff between them. Every test drives real git in
a temp repo.

Run:  python3 -m unittest tests.acs.test_changes -v
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import SCRIPTS, AcsWorkspaceCase, lib  # noqa: E402

sys.path.insert(0, SCRIPTS)
import acs_state_commands  # noqa: E402

C = lib.changes


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True,
                          check=check).stdout


def write(root, rel, text="x\n"):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class GitRepoCase(unittest.TestCase):
    """A plain repo with one commit on `master`: a.txt, b.txt, .gitignore."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-changes-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(self.root)
        git(self.root, "init", "-q", "-b", "master")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "T")
        write(self.root, "a.txt", "a\n")
        write(self.root, "b.txt", "b\n")
        write(self.root, ".gitignore", "ignored/\n.run/\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        self.rdir = os.path.join(self.root, ".run")

    def paths(self, entries):
        return sorted(e["path"] for e in entries)


class SnapshotTest(GitRepoCase):

    def test_a_clean_tree_snapshots_to_heads_tree(self):
        self.assertEqual(C.snapshot(self.root), git(self.root, "rev-parse", "HEAD^{tree}").strip())

    def test_untracked_modified_and_deleted_files_are_in_the_tree_ignored_ones_are_not(self):
        write(self.root, "a.txt", "changed\n")
        os.remove(os.path.join(self.root, "b.txt"))
        write(self.root, "new dir/ünïcode file.py", "print(1)\n")
        write(self.root, "ignored/secret.txt")
        tree = C.snapshot(self.root)
        listed = git(self.root, "ls-tree", "-r", "--name-only", "-z", tree).split("\0")
        self.assertIn("new dir/ünïcode file.py", listed)
        self.assertIn("a.txt", listed)
        self.assertNotIn("b.txt", listed)
        self.assertNotIn("ignored/secret.txt", listed)
        self.assertEqual(git(self.root, "show", "%s:a.txt" % tree), "changed\n")

    def test_the_real_index_and_status_are_untouched(self):
        write(self.root, "a.txt", "staged\n")
        git(self.root, "add", "a.txt")
        write(self.root, "a.txt", "staged then edited\n")
        write(self.root, "u.txt")
        before = (git(self.root, "status", "--porcelain"), git(self.root, "diff", "--cached"))
        C.snapshot(self.root)
        self.assertEqual((git(self.root, "status", "--porcelain"),
                          git(self.root, "diff", "--cached")), before)

    def test_deterministic(self):
        write(self.root, "u.txt")
        self.assertEqual(C.snapshot(self.root), C.snapshot(self.root))

    def test_an_unborn_branch_snapshots_its_untracked_files(self):
        fresh = os.path.join(self.tmp, "fresh")
        os.makedirs(fresh)
        git(fresh, "init", "-q")
        write(fresh, "only.txt")
        self.assertIsNone(C.head_sha(fresh))
        tree = C.snapshot(fresh)
        self.assertEqual(git(fresh, "ls-tree", "--name-only", tree).split(), ["only.txt"])

    def test_with_no_index_file_it_starts_from_head(self):
        os.remove(os.path.join(self.root, ".git", "index"))
        write(self.root, "u.txt")
        listed = git(self.root, "ls-tree", "-r", "--name-only", C.snapshot(self.root)).split()
        self.assertEqual(sorted(listed), [".gitignore", "a.txt", "b.txt", "u.txt"])

    def test_outside_a_repository_is_a_gate_error(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        with self.assertRaises(lib.GateError):
            C.snapshot(plain)


class GitHelpersTest(GitRepoCase):

    def test_branch_and_detached_head(self):
        self.assertEqual(C.current_branch(self.root), "master")
        git(self.root, "checkout", "-q", "--detach")
        self.assertIsNone(C.current_branch(self.root))

    def test_default_branches_follow_origin_head(self):
        self.assertEqual(C.default_branches(self.root), {"main", "master"})
        git(self.root, "update-ref", "refs/remotes/origin/trunk", "HEAD")
        git(self.root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        self.assertIn("trunk", C.default_branches(self.root))

    def test_resolve_tree(self):
        head_tree = git(self.root, "rev-parse", "HEAD^{tree}").strip()
        self.assertEqual(C.resolve_tree(self.root, "HEAD"), head_tree)
        self.assertEqual(C.resolve_tree(self.root, head_tree), head_tree)
        with self.assertRaises(lib.GateError):
            C.resolve_tree(self.root, "no-such-rev")

    def test_empty_tree_matches_git(self):
        self.assertEqual(C.empty_tree(self.root), "4b825dc642cb6eb9a060e54bf8d69288fbee4904")

    def test_blobs_name_absent_paths_none(self):
        tree = C.snapshot(self.root)
        found = C.blobs(self.root, tree, ["a.txt", "missing.txt"])
        self.assertEqual(found["a.txt"], git(self.root, "rev-parse", "HEAD:a.txt").strip())
        self.assertIsNone(found["missing.txt"])
        self.assertEqual(C.blobs(self.root, tree, []), {})


class BaselineTest(GitRepoCase):

    def test_records_head_branch_and_what_was_already_dirty(self):
        write(self.root, "a.txt", "user edit\n")
        write(self.root, "notes.txt")
        doc = C.record_baseline(self.rdir, self.root)
        self.assertEqual(doc["base_sha"], git(self.root, "rev-parse", "HEAD").strip())
        self.assertEqual(doc["branch"], "master")
        self.assertEqual(sorted(doc["dirty"]), ["a.txt", "notes.txt"])
        self.assertEqual(set(doc["dirty_blobs"]), {"a.txt", "notes.txt"})
        self.assertTrue(doc["recorded_at"])
        self.assertEqual(C.load_baseline(self.rdir), doc)

    def test_never_overwritten(self):
        first = C.record_baseline(self.rdir, self.root)
        write(self.root, "later.txt")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "moved on")
        again = C.record_baseline(self.rdir, self.root)
        self.assertEqual(again, first)
        self.assertEqual(C.load_baseline(self.rdir), first)

    def test_unborn_branch_has_no_base_sha(self):
        fresh = os.path.join(self.tmp, "fresh")
        os.makedirs(fresh)
        git(fresh, "init", "-q")
        write(fresh, "x.txt")
        doc = C.record_baseline(os.path.join(self.tmp, "run"), fresh)
        self.assertIsNone(doc["base_sha"])
        self.assertEqual(doc["dirty"], ["x.txt"])
        write(fresh, "y.txt")
        cs = C.changeset(fresh, baseline=doc)
        self.assertEqual(cs["since"], C.empty_tree(fresh))
        self.assertEqual(self.paths(cs["files"]), ["y.txt"])

    def test_no_run_dir_means_no_baseline(self):
        self.assertIsNone(C.load_baseline(None))
        self.assertIsNone(C.load_baseline(os.path.join(self.tmp, "nowhere")))


class ChangesetTest(GitRepoCase):

    def test_the_run_changeset_leaves_baseline_dirt_out_unless_it_changed_again(self):
        write(self.root, "a.txt", "user edit\n")   # dirty, left alone
        write(self.root, "notes.txt", "mine\n")    # untracked, then changed again
        baseline = C.record_baseline(self.rdir, self.root)
        write(self.root, "notes.txt", "mine, then the run's\n")
        write(self.root, "src/new.py")
        os.remove(os.path.join(self.root, "b.txt"))
        cs = C.changeset(self.root, baseline=baseline)
        self.assertEqual(cs["since"], baseline["base_sha"])
        statuses = {e["path"]: e["status"] for e in cs["files"]}
        self.assertEqual(statuses, {"notes.txt": "added", "src/new.py": "added",
                                    "b.txt": "deleted"})
        self.assertEqual(self.paths(cs["excluded"]), ["a.txt"])

    def test_since_a_review_snapshot_shows_only_what_followed_it(self):
        baseline = C.record_baseline(self.rdir, self.root)
        write(self.root, "src/one.py")
        reviewed = C.snapshot(self.root)
        write(self.root, "src/two.py")
        write(self.root, "src/one.py", "fixed\n")
        cs = C.changeset(self.root, since=reviewed, baseline=baseline)
        self.assertEqual({e["path"]: e["status"] for e in cs["files"]},
                         {"src/one.py": "modified", "src/two.py": "added"})

    def test_since_without_a_baseline(self):
        write(self.root, "u.txt")
        cs = C.changeset(self.root, since="HEAD")
        self.assertEqual(self.paths(cs["files"]), ["u.txt"])
        self.assertEqual(cs["excluded"], [])

    def test_no_since_and_no_baseline_is_refused(self):
        with self.assertRaises(lib.GateError):
            C.changeset(self.root)

    def test_an_unknown_since_is_refused(self):
        with self.assertRaises(lib.GateError):
            C.changeset(self.root, since="deadbeef")

    def test_render_limits_the_text_to_the_listed_paths(self):
        baseline = C.record_baseline(self.rdir, self.root)
        write(self.root, "keep.py", "k = 1\n")
        write(self.root, "skip.py", "s = 1\n")
        tree = C.snapshot(self.root)
        stat = C.render(self.root, baseline["base_sha"], tree, ["keep.py"], "stat")
        self.assertIn("keep.py", stat)
        self.assertNotIn("skip.py", stat)
        patch = C.render(self.root, baseline["base_sha"], tree, ["keep.py"], "patch")
        self.assertIn("+k = 1", patch)
        self.assertEqual(C.render(self.root, baseline["base_sha"], tree, [], "patch"), "")


class ChangesCliTest(AcsWorkspaceCase):
    """`acs.py changes ...` and the baseline `step start` records."""

    def setUp(self):
        super().setUp()
        for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
            git(self.repo, "config", key, value)
        write(self.repo, "README.md", "shop\n")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-qm", "init")
        self.ticket = self.new_ticket("Wishlist API", "task")

    def cli(self, *args, code=0):
        out = self.run_script("acs.py", *args)
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def test_step_start_records_the_baseline_once(self):
        out = self.start("analyze-requirements", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        path = os.path.join(self.rdir(self.ticket), "baseline.json")
        first = lib.read_json(path)
        self.assertEqual(first["base_sha"], git(self.repo, "rev-parse", "HEAD").strip())
        self.assertIn(".acs/settings.json", first["dirty"])
        write(self.repo, "src/a.py")
        self.start("create-impl-plan", self.ticket)
        self.assertEqual(lib.read_json(path), first, "a later step must not move the baseline")

    def test_snapshot_verb(self):
        out = self.cli("changes", "snapshot")
        self.assertTrue(out["ok"])
        self.assertEqual(out["tree"], C.snapshot(self.repo))

    def test_diff_defaults_to_name_only_since_the_baseline(self):
        self.start("analyze-requirements", self.ticket)
        write(self.repo, "docs/tickets/%s/analysis.md" % self.ticket)
        out = self.cli("changes", "diff")
        self.assertEqual(out["run_id"], self.ticket)
        self.assertEqual(out["files"], [{"path": "docs/tickets/%s/analysis.md" % self.ticket,
                                         "status": "added"}])
        self.assertIn(".acs/settings.json", out["excluded"])
        self.assertNotIn("stat", out)

    def test_diff_stat_and_patch(self):
        self.start("analyze-requirements", self.ticket)
        write(self.repo, "src/a.py", "a = 1\n")
        self.assertIn("src/a.py", self.cli("changes", "diff", "--stat")["stat"])
        self.assertIn("+a = 1", self.cli("changes", "diff", "--patch", "--run", self.ticket)["patch"])

    def test_diff_since_a_snapshot(self):
        self.start("analyze-requirements", self.ticket)
        write(self.repo, "src/a.py")
        tree = self.cli("changes", "snapshot")["tree"]
        write(self.repo, "src/b.py")
        out = self.cli("changes", "diff", "--since", tree, "--name-only")
        self.assertEqual([f["path"] for f in out["files"]], ["src/b.py"])

    def test_diff_with_no_run_and_no_since_is_refused(self):
        out = self.run_script("acs.py", "changes", "diff")
        self.assertEqual(out.returncode, 2)
        self.assertIn("--since", out.stderr)
        self.assertEqual(self.cli("changes", "diff", "--since", "HEAD")["run_id"], None)

    def test_an_unknown_run_is_refused(self):
        out = self.run_script("acs.py", "changes", "diff", "--run", "SHOP-999")
        self.assertEqual(out.returncode, 2)
        self.assertIn("no run", out.stderr)

    def test_a_bad_since_is_refused(self):
        out = self.run_script("acs.py", "changes", "diff", "--since", "nope")
        self.assertEqual(out.returncode, 2)

    def test_snapshot_outside_a_checkout_is_refused(self):
        plain = tempfile.mkdtemp(prefix="acs-plain-")
        self.addCleanup(shutil.rmtree, plain, True)
        out = self.run_script("acs.py", "changes", "snapshot", cwd=plain)
        self.assertEqual(out.returncode, 2)

    def test_a_baseline_that_cannot_be_taken_never_refuses_the_start(self):
        """Fail-soft: a warning, never a refused step."""
        plain = tempfile.mkdtemp(prefix="acs-plain-")
        self.addCleanup(shutil.rmtree, plain, True)
        err = io.StringIO()
        with redirect_stderr(err):
            acs_state_commands._record_baseline(os.path.join(plain, "run"),
                                                {"checkout_root": plain})
        self.assertIn("no baseline recorded", err.getvalue())
        acs_state_commands._record_baseline(os.path.join(plain, "run"), {})


if __name__ == "__main__":
    unittest.main()
