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

Each control is pinned by the shape where it ALONE changes the verdict, which
is not the shape that motivated it:
  * convergent change + self-revert -> the merge-base control. A plain
    self-revert (GAP 1) does NOT pin it: there the R gate independently
    reaches own_violations, so deleting the control changes no verdict. Only
    a branch that converges with the base AND reverts its own later work has
    an R to satisfy step B, and there the control alone decides.
  * convergent change (GAP 4) -> the R gate (the cumulative scan), which the
    merge-base control does not reach.
Neither control is redundant, and deleting either one turns this suite red --
which is the claim this paragraph used to make about a shape that did not.

Run:  python3 -m unittest discover -s tests
"""

import json
import os
import re
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

#: The third author-facing copy of the module's degraded-run and accepted-
#: limitations prose -- the file an author opens when the conventions gate is
#: already red.
CI_REFERENCE = os.path.join(acs_case.REPO_ROOT, "src", "acs", "skills", "create-pr",
                            "references", "ci-convention-check.md")


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def flatten(text):
    """Whitespace-collapsed, backtick-free body, so a re-wrapped or code-quoted
    copy of the same sentence still matches."""
    return " ".join(text.replace("`", "").split())


# ---------------------------------------------------------------------------
# Fixture plumbing
# ---------------------------------------------------------------------------

def _git(root, *args, **kwargs):
    """Run a git command in `root`, returning stdout; raise on a non-zero exit."""
    proc = subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True, text=True, input=kwargs.get("input"),
                          env=kwargs.get("env"))
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


def _commit_at(root, subject, rel, text, when):
    """`_commit` with both dates pinned, so `git log`'s date order is deterministic."""
    _write(root, rel, text)
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", subject, env=env)
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


def merged_sibling(case):
    """The incident shape on a branch that also merged a sibling forked at the
    old base tip, dated before the squashed commits.

    `git log` lists by commit DATE, so the sibling's own commit comes out after
    the replay target while ancestry puts it ahead of it -- the one shape where
    list position and `git rebase --onto` disagree about who owns what.
    """
    root = _new_repo(case)
    shas = {"A": _git(root, "rev-parse", "HEAD").strip()}
    _commit_at(root, "Reconcile the record one", "one.txt", "one\n", "2026-01-02T00:00:00+00:00")
    _commit_at(root, "Reconcile the record two", "two.txt", "two\n", "2026-01-03T00:00:00+00:00")
    shas["X3"] = _commit_at(root, "MAR-9 a conforming inherited commit", "three.txt",
                            "three\n", "2026-01-04T00:00:00+00:00")
    _git(root, "checkout", "-q", "-b", "side", shas["X3"][0])
    shas["SIDE"] = _commit_at(root, "oops side work of my own", "side.txt", "side\n",
                              "2026-01-01T00:00:00+00:00")
    _git(root, "checkout", "-q", "work")
    _git(root, "merge", "-q", "--no-ff", "-m", "Merge branch 'side' into work",
         shas["SIDE"][0],
         env=dict(os.environ, GIT_AUTHOR_DATE="2026-01-05T00:00:00+00:00",
                  GIT_COMMITTER_DATE="2026-01-05T00:00:00+00:00"))
    _commit_at(root, "MAR-2 dependent work", "dep.txt", "dep\n", "2026-01-09T00:00:00+00:00")
    _commit_at(root, "oops my own bad commit", "dep.txt", "dep\nmore\n",
               "2026-01-10T00:00:00+00:00")
    _squash_onto(root, shas["X3"][0], shas["A"])
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


def convergent_self_revert(case):
    """The shape where the merge-base control ALONE decides the verdict: the
    branch converges with the base and also reverts its own later work.

    The revert's post-image (no `scratch.txt`) is what the base holds, so the
    base-side test reads it as absorbed. The fork point holds it too, which is
    the only thing that says otherwise. The R gate does not reach this shape --
    the branch's cumulative content against the base IS in the base, thanks to
    the convergent edit, so an `R` exists and step B is satisfied.
    """
    root = _new_repo(case, "f.txt", "alpha\nbeta\n")
    _commit(root, "MAR-2 converge with the base", "f.txt", "alpha\nBETA\n")
    _commit(root, "MAR-3 add a scratch file", "scratch.txt", "scratch\n")
    os.remove(os.path.join(root, "scratch.txt"))
    _commit(root, "oops undo that scratch file")
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


class TestMergeInRange(unittest.TestCase):
    """AC-2 on a range containing a merge: `git log --no-merges` lists by commit
    DATE while `git rebase --onto R` keeps whatever descends from R, so only an
    ancestry-derived classification can agree with the command the same message
    prints. The oracle below is git's own answer, never the module's."""

    def kept(self, root, replay_onto_full):
        out = _git(root, "log", "--no-merges", "--format=%s",
                   "%s..HEAD" % replay_onto_full).strip()
        return set(out.splitlines())

    def test_the_classification_agrees_with_the_rebase_the_message_emits(self):
        root, shas = merged_sibling(self)
        _, result, _ = check_json(root)
        self.assertEqual(result["replay_onto"], shas["X3"][1])
        kept = self.kept(root, shas["X3"][0])
        self.assertEqual(set(subjects(result["own"])) - kept, set(),
                         "reported as this branch's own, but the replay discards it")
        self.assertEqual(set(subjects(result["stacked"])) & kept, set(),
                         "told the author renaming will not help, but the replay keeps it "
                         "and the gate stays red on it")

    def test_a_commit_the_replay_keeps_is_reported_as_the_branchs_own(self):
        # The sibling's commit is a descendant of R and is nobody else's work.
        root, _ = merged_sibling(self)
        _, result, _ = check_json(root)
        self.assertIn("oops side work of my own", subjects(result["own"]))

    def test_a_commit_the_replay_keeps_is_never_listed_under_the_replay_advice(self):
        root, _ = merged_sibling(self)
        _, result, _ = check_json(root)
        self.assertEqual(subjects(result["stacked"]),
                         ["Reconcile the record two", "Reconcile the record one"])

    def test_the_own_count_counts_the_survivors_not_the_list_positions(self):
        # Three commits descend from R here -- the sibling's, `MAR-2 dependent
        # work` and `oops my own bad commit` -- while R sits at list index 2.
        root, _ = merged_sibling(self)
        _, result, _ = check_json(root)
        self.assertIn("Your own 3 commits are unaffected and keep their subjects.",
                      result["message"])


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

    def test_the_message_reads_correctly_for_several_stacked_commits(self):
        # The sibling of the single-commit case above: the plural rendering is
        # the one an author almost always sees, and nothing held it.
        root, _ = incident(self)
        _, result, _ = check_json(root)
        self.assertEqual(len(result["stacked"]), 2)
        self.assertIn("2 of its commits\nare not yours to fix.", result["message"])

    def test_the_own_count_is_what_the_replay_keeps_not_what_it_discards(self):
        # The sentence sits under a --force-with-lease, so it must count the
        # commits the emitted rebase KEEPS: everything newer than replay_onto.
        # Here X3 is the replay target and BOTH `MAR-2 dependent work` and
        # `oops my own bad commit` are newer than it, so the answer is 2 --
        # a shape the adjacent convergent_minimal fixture cannot distinguish.
        root, _ = incident(self, own_bad_commit=True)
        _, result, _ = check_json(root)
        self.assertEqual(len(result["own"]), 1)
        self.assertIn("Your own 2 commits are unaffected and keep their subjects.",
                      result["message"])

    def test_the_own_count_reads_correctly_for_a_single_surviving_commit(self):
        # Only `MAR-2 dependent work` is newer than X3, and it conforms -- so
        # it never enters `own` at all, which is exactly the miscount.
        root, _ = incident(self)
        _, result, _ = check_json(root)
        self.assertEqual(result["own"], [])
        self.assertIn("Your own 1 commit is unaffected and keeps its subjects.",
                      result["message"])


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

    def test_does_not_fire_when_a_convergent_branch_reverts_its_own_later_work(self):
        # The shape the merge-base control exists for. On a PLAIN self-revert
        # the R gate independently reaches own_violations, so that shape pins
        # nothing; here the convergent edit gives step B an `R`, and control
        # one is the only thing left that keeps `oops undo that scratch file`
        # out of the candidate set. Without it this branch is told, above a
        # --force-with-lease, that its own revert belongs to a merged PR.
        root = convergent_self_revert(self)
        code, result, _ = check_json(root)
        self.assertEqual(result["verdict"], "own_violations")
        self.assertEqual(code, 0)
        self.assertEqual(result["stacked"], [])
        self.assertEqual(subjects(result["own"]), ["oops undo that scratch file"])
        self.assertNotIn("replay_onto", result)

    def test_the_merge_base_control_is_what_rejects_that_revert(self):
        # Measured on the commit the control decides, so the verdict above
        # cannot quietly start resting on some other mechanism.
        root = convergent_self_revert(self)
        tmpdir = tempfile.mkdtemp(prefix="acs-stacked-base-idx-")
        self.addCleanup(shutil.rmtree, tmpdir, True)
        merge_base = _git(root, "merge-base", "main", "HEAD").strip()
        base_env = mod.tree_index(root, "main", tmpdir, "base")
        fork_env = mod.tree_index(root, merge_base, tmpdir, "fork")
        revert = _git(root, "rev-parse", "HEAD").strip()
        self.assertTrue(mod.reverse_applies(root, mod.commit_patch(root, revert), base_env),
                        "the base-side test alone reads this revert as absorbed")
        self.assertFalse(mod.absorbed(root, revert, "revert", base_env, fork_env, []),
                         "the merge-base control is what keeps it out of the "
                         "candidate set, and nothing else does")

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


def _index_unusable(which):
    """A `tree_index` stand-in failing for exactly one of the two indexes."""
    real = mod.tree_index

    def fake(root, ref, tmpdir, name):
        return None if name == which else real(root, ref, tmpdir, name)
    return fake


class TestDegradedIndex(unittest.TestCase):
    """A throwaway index that could not be seeded makes every reverse-apply
    return False, so the detector finds nothing and its report is
    indistinguishable from a healthy branch -- while asserting that inherited
    commits "are this branch's own". The posture stays fail-open; the failure
    stops being silent."""

    #: Every factual claim the degraded-run and accepted-limitations prose
    #: makes, the surfaces that repeat it, and the wrong form it must stay
    #: clear of. One table for three copies of one sentence: restoring the
    #: earlier wording to any single copy used to leave the suite green,
    #: because only two of the three were ever read. Values in braces come from
    #: the run measured in the test, so the prose is pinned to what the tool
    #: does rather than to a literal.
    ALL_SURFACES = ("report message", "module docstring", "ci-convention-check.md")
    PROSE_SURFACES = ("module docstring", "ci-convention-check.md")
    DEGRADED_CLAIMS = (
        ("which commit of the revert pair reads as absorbed", ALL_SURFACES,
         "a commit that reverts this branch's own earlier work",
         "a commit this branch itself reverted"),
        ("which index going missing causes that read", ALL_SURFACES,
         "fork[- ]point|fork index", "base[- ]?index"),
        ("the warning is carried on either verdict", PROSE_SURFACES,
         "on either verdict", None),
        # Anchored to its own sentence: "reported as stacked" alone appears
        # twice in the docstring, so an unqualified pattern is satisfied by the
        # self-revert paragraph and stops noticing if this claim is deleted.
        ("the zero-net-content residual is reported as stacked", PROSE_SURFACES,
         "net content against the base is already in the base"
         ".{{0,60}}reported as {reported_as}", "reported as clean"),
        ("the exit code the stacked_base verdict gets", ("ci-convention-check.md",),
         "{code} for verdict {verdict}", None),
        # The qualification's own CONTENT, held to literal text written here.
        # The other assertion on this template renders its expectation from the
        # template itself, so both sides move together and the sentence can
        # invert -- "is not confirmed" to "is confirmed" -- with nothing red.
        ("the qualification names the note that raised it",
         ("qualified report message",), "{qualifying_note}", None),
        ("the qualification withholds the classification rather than "
         "reinforcing it", ("qualified report message",),
         "classification above is not confirmed for the commit",
         "classification above is confirmed"),
        ("nothing was tested when the base index is unusable",
         ("base-unusable report message",),
         "were never tested against the base",
         "were tested against the base anyway"),
        # Pre-existing clauses that survived mutation, pinned while the table
        # is open: which tree remained, and which half of a revert pair the
        # lost control leaves alone.
        ("only one of the two trees was consulted", ("report message",),
         "tested against {base_ref} only", None),
        ("the commit on the other side of the revert is unaffected",
         PROSE_SURFACES, "commit it reverted is unaffected", None),
    )

    def _a_qualified_report_message(self):
        """A report whose only note has no sentence of its own, so `QUALIFIED`
        is what carries it. Returns (message, the note it must name)."""
        root = clean_branch(self)
        _git(root, "commit", "-q", "--allow-empty", "-m", "oops trigger ci")
        short = _git(root, "rev-parse", "--short", "HEAD").strip()
        _, result, _ = check_json(root)
        return result["message"], "empty commit %s" % short

    def _a_base_unusable_report_message(self):
        """The report the author gets when the base index could not be built."""
        root, _ = incident(self)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("base")):
            return mod.check(root, "main", FORMAT, PREFIX)["message"]

    def test_an_unusable_index_is_noted_instead_of_read_as_a_healthy_branch(self):
        root, _ = incident(self)
        with mock.patch.object(mod, "tree_index", return_value=None):
            result = mod.check(root, "main", FORMAT, PREFIX)
        self.assertTrue(any("throwaway index" in note for note in result["notes"]),
                        result["notes"])
        self.assertNotIn("are this branch's own", result["message"])

    def test_an_unusable_index_still_exits_zero_rather_than_blocking_the_author(self):
        root, _ = incident(self)
        with mock.patch.object(mod, "tree_index", return_value=None):
            result = mod.check(root, "main", FORMAT, PREFIX)
        self.assertEqual(result["verdict"], "own_violations")
        self.assertEqual(result["stacked"], [])

    def test_a_base_index_failure_names_the_base_it_could_not_read(self):
        root, _ = incident(self)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("base")):
            result = mod.check(root, "main", FORMAT, PREFIX)
        self.assertEqual(result["verdict"], "own_violations")
        self.assertIn("no commit could be tested against the base", " ".join(result["notes"]))
        self.assertIn("index of %s was unusable" % result["base_ref"], result["message"])

    def test_a_fork_index_failure_names_itself_instead_of_claiming_nothing_was_tested(self):
        # Losing the FORK index leaves every base-side test running; saying
        # nothing was tested describes the other failure, not this one.
        root, _ = incident(self)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            result = mod.check(root, "main", FORMAT, PREFIX)
        note = " ".join(result["notes"])
        self.assertIn("fork point", note)
        self.assertNotIn("no commit could be tested", note)

    def test_a_fork_index_failure_is_surfaced_on_the_stacked_message_too(self):
        # find_replay_point needs only the base index, so this shape still
        # prints a force-push replay -- with a control silently switched off.
        root, _ = incident(self)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            result = mod.check(root, "main", FORMAT, PREFIX)
        self.assertEqual(result["verdict"], "stacked_base")
        self.assertIn("--force-with-lease", result["message"])
        self.assertIn("fork point", result["message"])

    def test_a_fork_index_failure_is_surfaced_on_the_exit_zero_message_too(self):
        # The mirror of the stacked case, and the path that actually prints the
        # bare ownership claim: without the caveat this message tells the author
        # its subjects are his own while the control that proves it is off.
        root = own_bad(self)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            result = mod.check(root, "main", FORMAT, PREFIX)
        self.assertEqual(result["verdict"], "own_violations")
        self.assertIn("are this branch's own", result["message"])
        self.assertIn("fork point", result["message"])

    def test_the_fork_warning_names_the_commit_that_does_the_reverting(self):
        # Which half of a revert pair the lost control actually mis-reads,
        # measured here rather than assumed: the REVERT restores content the
        # base already holds, so it is the one that flips to absorbed. The
        # commit it reverted reads False either way, and conforms, so it is
        # never patch-tested -- naming it points the author at the only commit
        # of the pair the missing control does not affect.
        root = self_revert(self)
        tmpdir = tempfile.mkdtemp(prefix="acs-stacked-base-idx-")
        self.addCleanup(shutil.rmtree, tmpdir, True)
        base_env = mod.tree_index(root, "main", tmpdir, "base")
        revert = _git(root, "rev-parse", "HEAD").strip()
        reverted = _git(root, "rev-parse", "HEAD~1").strip()
        self.assertTrue(mod.absorbed(root, revert, "revert", base_env, None, []))
        self.assertFalse(mod.absorbed(root, reverted, "reverted", base_env, None, []))
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            result = mod.check(root, "main", FORMAT, PREFIX)
        # The residual shape is measured in the same test, so the prose claims
        # about it below are held to what the tool does rather than to a
        # literal somebody typed into three files.
        code, residual, _ = check_json(convergent_minimal(self))
        qualified_message, qualifying_note = self._a_qualified_report_message()
        measured = {"code": code, "verdict": residual["verdict"],
                    "reported_as": residual["verdict"].split("_")[0],
                    "base_ref": result["base_ref"],
                    "qualifying_note": re.escape(qualifying_note)}
        surfaces = {"report message": result["message"],
                    "qualified report message": qualified_message,
                    "base-unusable report message": self._a_base_unusable_report_message(),
                    "module docstring": mod.__doc__,
                    "ci-convention-check.md": read_text(CI_REFERENCE)}
        for claim, names, required, forbidden in self.DEGRADED_CLAIMS:
            for name in names:
                with self.subTest(claim=claim, surface=name):
                    body = flatten(surfaces[name])
                    self.assertRegex(body, required.format(**measured),
                                     "%s: %s -- not stated" % (name, claim))
                    if forbidden:
                        self.assertNotRegex(body, forbidden,
                                            "%s: %s -- stated the wrong way round"
                                            % (name, claim))

    def test_the_degraded_note_never_contradicts_the_absorbed_note(self):
        # Without the fork index the merge-base control cannot run, so the
        # self-revert commit reads as absorbed -- the opposite of untested.
        root = self_revert(self)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            result = mod.check(root, "main", FORMAT, PREFIX)
        self.assertIn("1 commit(s) look absorbed but no lossless replay point exists",
                      result["notes"])
        self.assertFalse(any("no commit could be tested" in note for note in result["notes"]),
                         result["notes"])

    def test_neither_single_index_failure_blocks_the_author(self):
        root, _ = incident(self)
        for which in ("base", "fork"):
            with mock.patch.object(mod, "tree_index", side_effect=_index_unusable(which)):
                code, result, err = check_json(root)
            self.assertEqual(err, "", which)
            self.assertEqual(code, 1 if result["stacked"] else 0, which)

    def test_a_read_tree_failure_yields_no_index_env(self):
        root = clean_branch(self)
        tmpdir = tempfile.mkdtemp(prefix="acs-stacked-base-idx-")
        self.addCleanup(shutil.rmtree, tmpdir, True)
        self.assertIsNone(mod.tree_index(root, "no-such-ref", tmpdir, "base"))

    def test_a_write_tree_mismatch_yields_no_index_env(self):
        # The self-check the read-tree env comment relies on: the index seeded
        # fine as far as read-tree knew, but it does not hold the ref's tree.
        root = clean_branch(self)
        tmpdir = tempfile.mkdtemp(prefix="acs-stacked-base-idx-")
        self.addCleanup(shutil.rmtree, tmpdir, True)
        with mock.patch.object(mod, "_text", return_value="0" * 40):
            self.assertIsNone(mod.tree_index(root, "main", tmpdir, "base"))

    def test_a_missing_index_env_never_reports_content_as_present(self):
        root = clean_branch(self)
        self.assertFalse(mod.reverse_applies(root, b"any patch bytes", None))


class TestQualifiedReport(unittest.TestCase):
    """A non-empty `notes` never coexists with a settled claim in `message`.

    `notes` records what the run could not settle, and both reading surfaces
    hand `message` to the author verbatim -- so a note the message does not
    carry is a qualification nobody ever sees. Every site that appends to
    `notes` is built here on a real fixture and held to the qualification the
    module says that path emits; the count guard below turns a sixth site red
    rather than letting it ship unqualified.
    """

    BARE_CLAIM = "are this branch's own."

    #: The literal text that proves `message` carries a given note's fact. A
    #: note with no sentence of its own is carried verbatim, so the note itself
    #: is the proof; the two index failures are named by their own sentence
    #: instead, and that sentence is written out HERE rather than rendered from
    #: the template it is supposed to check -- an expectation rendered from its
    #: own source moves with it and cannot see it invert.
    NOTE_IS_NAMED_BY = (
        ("no commit could be tested against the base",
         "were never tested against the base"),
        ("the merge-base control could not run",
         "throwaway index of the fork point was unusable"),
    )

    @classmethod
    def identifying_text(cls, note):
        """The text `message` must carry for `note` to count as named."""
        for fragment, sentence in cls.NOTE_IS_NAMED_BY:
            if fragment in note:
                return sentence
        return note

    def assert_message_names_every_note(self, result, label):
        """Every entry in `notes` is identifiable in `message`, and stated once."""
        message = " ".join(result["message"].split())
        self.assertTrue(result["notes"],
                        "%s: the fixture reached no notes path at all" % label)
        for note in result["notes"]:
            named_by = self.identifying_text(note)
            self.assertIn(named_by, message,
                          "%s: `notes` says %r and `message` does not say so: %s"
                          % (label, note, message))
            if named_by != note:
                # Its own sentence already states this fact; carrying the note
                # verbatim in the general list as well would state it twice.
                self.assertNotIn(note, message,
                                 "%s: %r is stated twice over: %s"
                                 % (label, note, message))

    def _root_commit_skipped(self):
        root = clean_branch(self)
        orphan = _orphan_commit(root, "orphan.txt", "orphan\n", "oops orphan work")
        _git(root, "merge", "--allow-unrelated-histories", "-q", "-m",
             "Merge unrelated side", orphan)
        short = _git(root, "rev-parse", "--short", orphan).strip()
        _, result, _ = check_json(root)
        return result, "root commit %s skipped" % short

    def _empty_commit(self):
        # On the STACKED shape deliberately: the qualification is required of
        # both renderings, and an empty non-conforming commit rides along with
        # the inherited ones without ever becoming a candidate itself.
        root, _ = incident(self)
        _git(root, "commit", "-q", "--allow-empty", "-m", "oops trigger ci")
        short = _git(root, "rev-parse", "--short", "HEAD").strip()
        code, result, _ = check_json(root)
        self.assertEqual((code, result["verdict"]), (1, "stacked_base"))
        return result, "empty commit %s" % short

    def _no_lossless_replay_point(self):
        root = convergent(self)
        _, result, _ = check_json(root)
        return result, "1 commit(s) look absorbed but no lossless replay point exists"

    def _base_index_unusable(self):
        root, _ = incident(self)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("base")):
            result = mod.check(root, "main", FORMAT, PREFIX)
        return result, "no commit could be tested against the base"

    def _fork_index_unusable(self):
        root = own_bad(self)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            result = mod.check(root, "main", FORMAT, PREFIX)
        return result, "the merge-base control could not run"

    #: One entry per `notes.append` site in stacked-base.py: the fixture that
    #: reaches it, and the qualification the message must then carry, rendered
    #: from the module's own template rather than copied out of it.
    NOTES_PATHS = (
        ("root commit skipped", _root_commit_skipped,
         lambda result, note: mod.QUALIFIED % note),
        ("empty commit", _empty_commit,
         lambda result, note: mod.QUALIFIED % note),
        ("no lossless replay point", _no_lossless_replay_point,
         lambda result, note: mod.QUALIFIED % note),
        ("base index unusable", _base_index_unusable,
         lambda result, note: mod.BASE_UNUSABLE % (result["base_ref"],
                                                   len(result["own"]), result["range"])),
        ("fork index unusable", _fork_index_unusable,
         lambda result, note: mod.FORK_DEGRADED % result["base_ref"]),
    )

    def test_every_notes_path_carries_its_qualification_into_the_message(self):
        for name, build, qualification in self.NOTES_PATHS:
            with self.subTest(path=name):
                result, note = build(self)
                self.assertIn(note, " ".join(result["notes"]),
                              "%s: the fixture never reached this path" % name)
                message = " ".join(result["message"].split())
                self.assertIn(" ".join(qualification(result, note).split()), message,
                              "%s: `notes` says %r and `message` does not say so: %s"
                              % (name, note, message))
                # The line above proves the wiring and nothing about the words:
                # its expectation is rendered from the same template the
                # message is. This one is not, so the interpolation is real.
                self.assert_message_names_every_note(result, name)
                self.assertFalse(message.endswith(self.BARE_CLAIM),
                                 "%s: a qualified run still ends on the bare ownership "
                                 "claim: %s" % (name, message))

    def _root_commit_and_empty_commit(self):
        # Two notes with no index failure and no mocking at all -- the compound
        # shape a real branch reaches, and the one where `_qualify` has no
        # specific sentence to lead with.
        root = clean_branch(self)
        orphan = _orphan_commit(root, "orphan.txt", "orphan\n", "oops orphan work")
        _git(root, "merge", "--allow-unrelated-histories", "-q", "-m",
             "Merge unrelated side", orphan)
        _git(root, "commit", "-q", "--allow-empty", "-m", "oops trigger ci")
        _, result, _ = check_json(root)
        return result

    def _fork_index_and_no_replay_point(self):
        # Losing the control is itself what makes the revert read as absorbed,
        # so this shape raises its second note by way of the first.
        root = self_revert(self)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            return mod.check(root, "main", FORMAT, PREFIX)

    def _fork_index_and_root_commit_skipped(self):
        root = clean_branch(self)
        orphan = _orphan_commit(root, "orphan.txt", "orphan\n", "oops orphan work")
        _git(root, "merge", "--allow-unrelated-histories", "-q", "-m",
             "Merge unrelated side", orphan)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            return mod.check(root, "main", FORMAT, PREFIX)

    def _fork_index_and_empty_commit_while_stacked(self):
        # The STACKED rendering of a compound shape: a different separator and
        # a different branch of `build_message` reach the same helper.
        root, _ = incident(self)
        _git(root, "commit", "-q", "--allow-empty", "-m", "oops trigger ci")
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            result = mod.check(root, "main", FORMAT, PREFIX)
        self.assertEqual(result["verdict"], "stacked_base")
        return result

    def _fork_index_and_two_skipped_commits(self):
        # Three notes, so a message that names the degraded sentence and ONE
        # more is still short of the contract.
        root = clean_branch(self)
        orphan = _orphan_commit(root, "orphan.txt", "orphan\n", "oops orphan work")
        _git(root, "merge", "--allow-unrelated-histories", "-q", "-m",
             "Merge unrelated side", orphan)
        _git(root, "commit", "-q", "--allow-empty", "-m", "oops trigger ci")
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("fork")):
            return mod.check(root, "main", FORMAT, PREFIX)

    def _base_index_and_empty_commit(self):
        root = clean_branch(self)
        _git(root, "commit", "-q", "--allow-empty", "-m", "oops trigger ci")
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("base")):
            return mod.check(root, "main", FORMAT, PREFIX)

    def _base_index_and_root_commit_skipped(self):
        root = clean_branch(self)
        orphan = _orphan_commit(root, "orphan.txt", "orphan\n", "oops orphan work")
        _git(root, "merge", "--allow-unrelated-histories", "-q", "-m",
             "Merge unrelated side", orphan)
        with mock.patch.object(mod, "tree_index", side_effect=_index_unusable("base")):
            return mod.check(root, "main", FORMAT, PREFIX)

    #: Shapes that raise MORE THAN ONE note in a single run. The table above
    #: reaches exactly one path per fixture, so a message that names the first
    #: note and silently drops the rest satisfies every row of it -- which is
    #: why every defect in this family has lived in the combinations.
    COMPOUND_SHAPES = (
        ("root commit + empty commit, no index failure", _root_commit_and_empty_commit),
        ("fork index + no lossless replay point", _fork_index_and_no_replay_point),
        ("fork index + root commit skipped", _fork_index_and_root_commit_skipped),
        ("fork index + empty commit, stacked", _fork_index_and_empty_commit_while_stacked),
        ("fork index + root commit + empty commit", _fork_index_and_two_skipped_commits),
        ("base index + empty commit", _base_index_and_empty_commit),
        ("base index + root commit skipped", _base_index_and_root_commit_skipped),
    )

    def test_every_compound_shape_names_every_one_of_its_notes(self):
        # Asserted over `result["notes"]` itself rather than against a list of
        # expected sentences, so a combination nobody thought of is covered the
        # day the code can produce it.
        for name, build in self.COMPOUND_SHAPES:
            with self.subTest(shape=name):
                result = build(self)
                self.assertGreater(len(result["notes"]), 1,
                                   "%s: not a compound shape after all -- notes: %s"
                                   % (name, result["notes"]))
                self.assert_message_names_every_note(result, name)

    def test_every_path_that_appends_to_notes_is_pinned_above(self):
        # The class guard: a sixth append site is a sixth way to ship an
        # unqualified message, and the table above is what proves there is not
        # one.
        with open(mod.__file__, encoding="utf-8") as fh:
            source = fh.read()
        self.assertEqual(source.count("notes.append("), len(self.NOTES_PATHS),
                         "stacked-base.py appends to `notes` from a different number "
                         "of sites than this table builds a fixture for")


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
