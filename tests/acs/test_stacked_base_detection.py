"""Behavior tests for stacked-base.py -- detecting a branch stacked on a
squash-merged base before /acs:create-pr pushes.

Originating ticket: MAR-590 (child A of epic MAR-589). The condition:
.acs/ci/check-conventions.py collects a PR's commits with
`git log --no-merges origin/<base>..HEAD`, pure SHA ancestry. A squash merge
replaces the base PR's commits with one new commit, so the originals never
become ancestors of the base; a branch stacked on that base still carries
them and the commit_message check fails on subjects the author cannot fix.

The fixtures build the incident shape with plumbing (`git commit-tree`), not
checkout games, so the squash is exactly what GitHub produces: one commit
whose tree is the merged head's tree, parented on the fork point.

Two negative shapes are load-bearing and each pins one control:
  * self-revert (GAP 1)  -> the merge-base control;
  * convergent change (GAP 4) -> the R gate (the cumulative scan).
Neither control is redundant: the convergent shape defeats the merge-base
control on its own, which is why both tests exist.

Run:  python3 -m unittest discover -s tests
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

MODULE_FILENAME = "stacked-base.py"

mod = acs_case.load_module(MODULE_FILENAME, "stacked_base")

FORMAT = "{ticket_id} {summary}"
PREFIX = "MAR"
BINARY = b"\x00\x01\x02\x03binary payload\x00\xff"


# ---------------------------------------------------------------------------
# Fixture plumbing
# ---------------------------------------------------------------------------

def _git(root, *args, **kwargs):
    """Run a git command in `root`, returning stdout; raise on a non-zero exit."""
    proc = subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True, text=True, input=kwargs.get("input"))
    if proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), proc.stderr))
    return proc.stdout


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(text, bytes):
        with open(path, "wb") as fh:
            fh.write(text)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)


def _commit(root, subject, rel=None, text=None):
    """Write an optional file and commit it with `subject`; return (full, short)."""
    if rel is not None:
        _write(root, rel, text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", subject)
    return _git(root, "rev-parse", "HEAD").strip(), _git(root, "rev-parse", "--short", "HEAD").strip()


def _new_repo(case, seed_rel="seed.txt", seed_text="seed\n"):
    """A throwaway repo on `main` with one conforming seed commit, then branch `work`."""
    root = tempfile.mkdtemp(prefix="acs-stacked-base-test-")
    case.addCleanup(shutil.rmtree, root, True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    _write(root, seed_rel, seed_text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "MAR-1 seed")
    _git(root, "branch", "-M", "main")
    _git(root, "checkout", "-q", "-b", "work")
    return root


def _advance_base(root, subject="MAR-8 unrelated base work",
                  rel="base_extra.txt", text="base extra\n"):
    """Add an unrelated commit on `main`, so base_ref != merge_base."""
    _git(root, "checkout", "-q", "main")
    _write(root, rel, text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", subject)
    _git(root, "checkout", "-q", "work")


def _squash_onto(root, head_ref, parent_ref, subject="Base PR (#1)"):
    """The squash GitHub produces: one commit carrying head's tree, parented on the fork point."""
    tree = _git(root, "rev-parse", "%s^{tree}" % head_ref).strip()
    squash = _git(root, "commit-tree", tree, "-p", parent_ref, "-m", subject).strip()
    _git(root, "branch", "-f", "main", squash)
    return squash


def _orphan_commit(root, rel, text, subject):
    """A parentless commit built with plumbing -- no checkout, no index churn."""
    blob = _git(root, "hash-object", "-w", "--stdin", input=text).strip()
    tree = _git(root, "mktree", input="100644 blob %s\t%s\n" % (blob, rel)).strip()
    return _git(root, "commit-tree", tree, "-m", subject).strip()


# ---------------------------------------------------------------------------
# The shapes
# ---------------------------------------------------------------------------

def incident(case, advance_base=False, own_bad_commit=False):
    """The real incident: three inherited commits, two non-conforming, then a squash.

    X3 CONFORMS, so it is never patch-tested -- it is nonetheless the true old
    base tip, which is the case a per-commit replay target gets wrong.
    """
    root = _new_repo(case)
    shas = {}
    shas["A"] = _git(root, "rev-parse", "HEAD").strip()
    shas["X1"] = _commit(root, "Reconcile the record one", "one.txt", "one\n")
    shas["X2"] = _commit(root, "Reconcile the record two", "two.txt", "two\n")
    _write(root, "bin.dat", BINARY)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--amend", "--no-edit")
    shas["X2"] = (_git(root, "rev-parse", "HEAD").strip(),
                  _git(root, "rev-parse", "--short", "HEAD").strip())
    shas["X3"] = _commit(root, "MAR-9 a conforming inherited commit", "three.txt", "three\n")
    shas["D1"] = _commit(root, "MAR-2 dependent work", "dep.txt", "dep\n")
    if own_bad_commit:
        shas["D2"] = _commit(root, "oops my own bad commit", "dep.txt", "dep\nmore\n")
    _squash_onto(root, shas["X3"][0], shas["A"])
    if advance_base:
        _advance_base(root)
    return root, shas


def self_revert(case, advance_base=False):
    """GAP 1: the branch reverts its own earlier commit, so the base holds the post-image."""
    root = _new_repo(case, "f.txt", "alpha\nbeta\ngamma\n")
    _commit(root, "MAR-2 shout beta", "f.txt", "alpha\nBETA\ngamma\n")
    _commit(root, "oops undo that", "f.txt", "alpha\nbeta\ngamma\n")
    if advance_base:
        _advance_base(root)
    return root


def convergent(case):
    """GAP 4: base and branch make the SAME edit, with the branch's own work either side."""
    root = _new_repo(case, "f.txt", "alpha\nbeta\n")
    _commit(root, "MAR-2 my own earlier work", "mine_early.txt", "early\n")
    _commit(root, "shout beta", "f.txt", "alpha\nBETA\n")
    _commit(root, "MAR-4 more own work", "mine_late.txt", "late\n")
    _git(root, "checkout", "-q", "main")
    _write(root, "f.txt", "alpha\nBETA\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "MAR-7 the base makes the same change")
    _git(root, "checkout", "-q", "work")
    return root


def convergent_minimal(case):
    """The documented residual: the branch's entire net content is already in the base."""
    root = _new_repo(case, "f.txt", "alpha\nbeta\n")
    _commit(root, "shout beta", "f.txt", "alpha\nBETA\n")
    _git(root, "checkout", "-q", "main")
    _write(root, "f.txt", "alpha\nBETA\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "MAR-7 the base makes the same change")
    _git(root, "checkout", "-q", "work")
    return root


def own_bad(case):
    """N1: an ordinary branch carrying a badly-named commit of its own."""
    root = _new_repo(case)
    _commit(root, "MAR-2 real work", "a.txt", "a\n")
    _commit(root, "oops fix typo", "a.txt", "a\nfixed\n")
    return root


def clean_branch(case):
    root = _new_repo(case)
    _commit(root, "MAR-2 real work", "a.txt", "a\n")
    return root


# ---------------------------------------------------------------------------
# Driving the CLI -- every run_main() call in this module goes through here,
# inside a pushd, because an unguarded run_main can act on the operator's real
# cwd (tests/acs/test_testing_conventions_guard.py, convention 2).
# ---------------------------------------------------------------------------

def run_check(root, base="main", fmt=FORMAT, prefix=PREFIX):
    argv = ["check", "--base", base,
            "--commit-message-format", fmt, "--ticket-prefix", prefix]
    with acs_case.pushd(root):
        code, out, err = acs_case.run_main(mod, argv)
    return code, out, err


def check_json(root, **kwargs):
    code, out, err = run_check(root, **kwargs)
    return code, json.loads(out), err


def subjects(entries):
    return [entry["subject"] for entry in entries]


class TestDetection(unittest.TestCase):

    def test_reports_the_stacked_base_condition_when_the_base_was_squash_merged(self):
        root, shas = incident(self)
        code, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "stacked_base")
        self.assertEqual(code, 1)
        self.assertEqual(subjects(result["stacked"]),
                         ["Reconcile the record two", "Reconcile the record one"])
        self.assertEqual(result["own"], [])
        self.assertEqual(result["replay_onto"], shas["X3"][1])

    def test_detection_survives_an_unrelated_later_commit_on_the_base(self):
        root, shas = incident(self, advance_base=True)
        code, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "stacked_base")
        self.assertEqual(code, 1)
        self.assertEqual(result["replay_onto"], shas["X3"][1])
        self.assertNotEqual(result["merge_base"], result["replay_onto"])

    def test_a_binary_change_in_a_squashed_commit_does_not_break_detection(self):
        # Regression guard for the measured `--binary` finding: without it the
        # patch carries no binary hunk and the reverse-apply reports a false
        # "not in base" for every commit touching a binary file.
        root, shas = incident(self)
        patch = mod.commit_patch(root, shas["X2"][0])
        self.assertIn(b"GIT binary patch", patch)
        tmpdir = tempfile.mkdtemp(prefix="acs-stacked-base-idx-")
        self.addCleanup(shutil.rmtree, tmpdir, True)
        env = mod.tree_index(root, "main", tmpdir, "base")
        self.assertTrue(mod.reverse_applies(root, patch, env))
        _, result, _ = check_json(root)
        self.assertIn("Reconcile the record two", subjects(result["stacked"]))

    def test_a_mixed_branch_separates_its_own_commits_from_the_stacked_ones(self):
        root, shas = incident(self, own_bad_commit=True)
        _, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "stacked_base")
        self.assertEqual(subjects(result["stacked"]),
                         ["Reconcile the record two", "Reconcile the record one"])
        self.assertEqual(subjects(result["own"]), ["oops my own bad commit"])
        self.assertEqual(result["replay_onto"], shas["X3"][1])
        every = subjects(result["stacked"]) + subjects(result["own"]) + result["ignored"]
        self.assertEqual(len(every), len(set(every)))

    def test_a_branch_whose_subjects_all_conform_is_clean(self):
        root = clean_branch(self)
        code, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "clean")
        self.assertEqual(code, 0)
        self.assertEqual(result["stacked"], [])
        self.assertEqual(result["own"], [])

    def test_an_ignorable_subject_is_never_patch_tested(self):
        root = clean_branch(self)
        _commit(root, "Merge branch 'main' into task/thing", "m.txt", "m\n")
        with mock.patch.object(mod, "commit_patch", wraps=mod.commit_patch) as spy:
            result = mod.check(root, "main", FORMAT, PREFIX)
        self.assertIn("Merge branch 'main' into task/thing", result["ignored"])
        self.assertEqual(result["own"], [])
        spy.assert_not_called()


class TestReplayTarget(unittest.TestCase):

    def test_the_replay_target_is_the_tip_of_the_squashed_branch_even_when_it_conforms(self):
        # X3 conforms, so step A never patch-tests it; only the cumulative scan
        # can find it. A per-commit replay target would emit X2 here and the
        # rebase would drop X3.
        root, shas = incident(self)
        _, result, _ = check_json(root)
        self.assertEqual(result["replay_onto"], shas["X3"][1])
        self.assertNotEqual(result["replay_onto"], shas["X2"][1])


class TestMessage(unittest.TestCase):

    def test_the_message_names_every_offending_subject(self):
        root, _ = incident(self)
        _, result, _ = check_json(root)
        for subject in subjects(result["stacked"]):
            self.assertIn(subject, result["message"])
        for entry in result["stacked"]:
            self.assertIn("%s  %s" % (entry["sha"], entry["subject"]), result["message"])

    def test_the_message_carries_a_rebase_command_with_real_shas_not_a_placeholder(self):
        root, shas = incident(self)
        _, result, _ = check_json(root)
        self.assertIn("git rebase --onto main %s" % shas["X3"][1], result["message"])
        self.assertIn("git fetch origin main", result["message"])
        self.assertIn("--force-with-lease", result["message"])
        self.assertNotIn("<", result["message"])
        self.assertIn("Every commit SHA on this branch changes", result["message"])

    def test_the_message_never_names_an_unimplemented_command(self):
        # MAR-591 owns the SHA-resync tooling; pointing an author at a command
        # this ticket does not ship would be worse than saying "by hand".
        root, _ = incident(self)
        _, result, _ = check_json(root)
        self.assertNotIn("resync-shas", result["message"])
        self.assertIn("has to be updated by hand", result["message"])

    def test_the_message_reads_correctly_for_a_single_stacked_commit(self):
        root = convergent_minimal(self)
        _, result, _ = check_json(root)
        self.assertEqual(len(result["stacked"]), 1)
        self.assertIn("1 of its commits\nis not yours to fix.", result["message"])


class TestNegativeCase(unittest.TestCase):

    def test_does_not_fire_when_the_bad_commit_is_the_branchs_own(self):
        root = own_bad(self)
        code, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "own_violations")
        self.assertEqual(code, 0)
        self.assertEqual(result["stacked"], [])
        self.assertEqual(subjects(result["own"]), ["oops fix typo"])
        self.assertNotIn("replay_onto", result)

    def test_does_not_fire_when_the_branch_reverts_its_own_earlier_commit(self):
        # GAP 1. The candidate here is the NON-CONFORMING `oops undo that`,
        # whose patch is -BETA +beta: its post-image `beta` IS what the base
        # holds, so the raw reverse-apply succeeds. The conforming
        # `MAR-2 shout beta` is never patch-tested -- measuring it instead
        # gives rc=1 and the opposite (wrong) conclusion.
        root = self_revert(self)
        code, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "own_violations")
        self.assertEqual(code, 0)
        self.assertEqual(result["stacked"], [])
        self.assertEqual(subjects(result["own"]), ["oops undo that"])

    def test_does_not_fire_on_a_self_revert_when_the_base_has_advanced(self):
        # Proves the control is the MERGE-BASE tree, not the base tree twice.
        root = self_revert(self, advance_base=True)
        _, result, _ = check_json(root)
        self.assertNotEqual(result["merge_base"], "")
        self.assertEqual(result["verdict"], "own_violations")
        self.assertEqual(result["stacked"], [])

    def test_does_not_fire_when_the_base_made_the_same_change_independently(self):
        # GAP 4. The merge-base control passes this shape: the content IS in
        # the base and was NOT at the fork point. Only the cumulative R gate
        # rejects it.
        root = convergent(self)
        code, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "own_violations")
        self.assertEqual(code, 0)
        self.assertEqual(result["stacked"], [])
        self.assertEqual(subjects(result["own"]), ["shout beta"])
        self.assertIn("1 commit(s) look absorbed but no lossless replay point exists",
                      result["notes"])

    def test_a_convergent_change_never_emits_a_replay_target_that_would_drop_own_work(self):
        # `MAR-2 my own earlier work` is OLDER than the convergent commit, so
        # any replay target chosen from that commit would delete it.
        root = convergent(self)
        _, result, _ = check_json(root)
        self.assertNotIn("replay_onto", result)
        self.assertNotIn("git rebase --onto", result["message"])

    def test_an_empty_commit_is_never_reported_as_stacked(self):
        root = clean_branch(self)
        _git(root, "commit", "-q", "--allow-empty", "-m", "oops trigger ci")
        short = _git(root, "rev-parse", "--short", "HEAD").strip()
        _, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "own_violations")
        self.assertEqual(result["stacked"], [])
        self.assertIn("empty commit %s" % short, result["notes"])

    def test_the_own_violations_message_carries_no_replay_advice(self):
        root = own_bad(self)
        _, result, _ = check_json(root)
        for forbidden in ("git rebase --onto", "--force-with-lease", "squash"):
            self.assertNotIn(forbidden, result["message"])
        self.assertIn("are this branch's own", result["message"])


class TestResidual(unittest.TestCase):
    """The convergent-minimal residual is ACCEPTED, and pinned so it is not
    'fixed' into a false negative.

    The branch's entire net content against the base is already in the base, so
    the emitted replay is a no-op and cannot lose work -- the safety property
    that matters is preserved even though the stated cause (a squash) is wrong.
    Discriminating it would need the base's commit history rather than its
    tree, which is materially more machinery for a shape that costs nothing
    when wrong.
    """

    def test_a_branch_with_zero_net_content_against_the_base_is_reported(self):
        root = convergent_minimal(self)
        code, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "stacked_base")
        self.assertEqual(code, 1)
        self.assertEqual(subjects(result["stacked"]), ["shout beta"])


class TestReadOnly(unittest.TestCase):

    def test_the_check_writes_nothing_to_the_repository(self):
        root, _ = incident(self)
        index = os.path.join(root, ".git", "index")
        before_head = _git(root, "rev-parse", "HEAD").strip()
        before_index = os.stat(index).st_mtime_ns
        run_check(root)
        self.assertEqual(os.stat(index).st_mtime_ns, before_index)
        self.assertEqual(_git(root, "rev-parse", "HEAD").strip(), before_head)
        self.assertEqual(_git(root, "status", "--porcelain").strip(), "")


class TestReuse(unittest.TestCase):
    """The convention rules stay CI's -- this module never re-implements them."""

    def test_the_matcher_is_the_conventions_checkers_format_to_regex(self):
        root = own_bad(self)
        with mock.patch.object(mod.cc, "format_to_regex", wraps=mod.cc.format_to_regex) as spy:
            mod.check(root, "main", FORMAT, PREFIX)
        spy.assert_called_once_with(FORMAT, PREFIX)

    def test_ignorable_subjects_use_the_checkers_own_rule(self):
        root = own_bad(self)
        with mock.patch.object(mod.cc, "_is_ignorable_commit",
                               wraps=mod.cc._is_ignorable_commit) as spy:
            mod.check(root, "main", FORMAT, PREFIX)
        self.assertTrue(spy.called)


class TestCost(unittest.TestCase):
    """Step A's only justification: it keeps step B off the common paths."""

    def test_the_cumulative_scan_does_not_run_without_a_candidate(self):
        for factory in (clean_branch, own_bad):
            root = factory(self)
            with mock.patch.object(mod, "cumulative_patch", wraps=mod.cumulative_patch) as spy:
                mod.check(root, "main", FORMAT, PREFIX)
            spy.assert_not_called()


class TestRobustness(unittest.TestCase):

    def test_an_unresolvable_base_ref_exits_two_with_a_reason(self):
        root = clean_branch(self)
        code, out, err = run_check(root, base="no-such-branch")
        self.assertEqual(code, 2)
        self.assertIn("acs stacked-base: ", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(out, "")

    def test_a_root_commit_in_range_is_noted_not_fatal(self):
        root = clean_branch(self)
        orphan = _orphan_commit(root, "orphan.txt", "orphan\n", "oops orphan work")
        _git(root, "merge", "--allow-unrelated-histories", "-q", "-m",
             "Merge unrelated side", orphan)
        short = _git(root, "rev-parse", "--short", orphan).strip()
        code, result, _ = check_json(root)
        self.assertEqual(code, 0)
        self.assertEqual(result["verdict"], "own_violations")
        self.assertIn("root commit %s skipped" % short, result["notes"])

    def test_unrelated_histories_exit_two_rather_than_crash(self):
        root = clean_branch(self)
        orphan = _orphan_commit(root, "orphan.txt", "orphan\n", "oops orphan work")
        _git(root, "checkout", "-q", "-B", "work", orphan)
        code, out, err = run_check(root)
        self.assertEqual(code, 2)
        self.assertIn("acs stacked-base: ", err)
        self.assertEqual(out, "")

    def test_the_base_ref_prefers_the_origin_remote_ref(self):
        # Mirrors check-conventions.py:310-320, so the pre-flight and CI agree
        # on which range they are discussing.
        root = clean_branch(self)
        bare = root + "-origin.git"
        self.addCleanup(shutil.rmtree, bare, True)
        _git(root, "init", "-q", "--bare", bare)
        _git(root, "remote", "add", "origin", bare)
        _git(root, "push", "-q", "-u", "origin", "main")
        _, result, _ = check_json(root)
        self.assertEqual(result["base_ref"], "origin/main")
        self.assertEqual(result["range"], "origin/main..HEAD")


if __name__ == "__main__":
    unittest.main()
