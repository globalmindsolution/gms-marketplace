#!/usr/bin/env python3
"""stacked-base.py — detect a branch stacked on a squash-merged base.

`.acs/ci/check-conventions.py` collects a PR's commits with
`git log --no-merges origin/<base>..HEAD` — pure SHA ancestry. A squash merge
replaces the base PR's commits with ONE new commit, so the originals never
become ancestors of the base. A branch stacked on that base still carries them,
the range still lists them, and the commit_message check fails on subjects the
author cannot fix by renaming them.

  check   Decide whether `<base_ref>..HEAD` is that shape and, if it is, name
          the offending subjects and emit a replay command proven lossless.
          One compact JSON object on stdout. Exit 0 = no stacked base (verdict
          `clean` or `own_violations`), 1 = `stacked_base`, 2 = unevaluable
          (base ref does not resolve, no merge base) with `acs stacked-base:
          <reason>` on stderr.

Read-only: every tree test runs against a throwaway `GIT_INDEX_FILE` under
`tempfile.mkdtemp()`, so nothing in `.git` is written and the check is safe to
run before a push. Stdlib-only and network-free — the caller does the fetch.

HOW IT DECIDES — two controls, both found by measurement, neither redundant.

  Step A, the pre-filter. For each NON-CONFORMING commit `C`:
  `git diff --binary C^ C` must be non-empty, must reverse-apply cleanly to
  `<base_ref>`'s tree, and must NOT reverse-apply cleanly to the merge-base's
  tree. That last leg is control one: without it, a branch that reverts its own
  earlier commit is reported as stacked, because the reverted post-image is
  exactly what the base holds.

  Step B, the R gate. `R` is the NEWEST commit in range whose CUMULATIVE patch
  `git diff --binary <merge_base> <R>` is non-empty and reverse-applies cleanly
  to `<base_ref>`'s tree. Control two, and the only safe replay target:
  `git rebase --onto <base_ref> R` discards everything at-or-before `R`, so `R`
  has to be proven cumulatively. A target chosen from one commit's own content
  says nothing about the commits OLDER than it, and was measured dropping the
  author's own earlier work on a convergent-change branch. No `R` means
  `own_violations`, whatever step A said. What the replay KEEPS is then read
  back from `R..HEAD` — the same set the rebase replays — never from a commit's
  position in the listing, which `git log`'s commit-date order does not keep in
  ancestry order once the range holds a merge.

REJECTED, WITH MEASURED EVIDENCE — DO NOT RE-ATTEMPT.

  `git log --cherry-pick --right-only` does NOT work here. Measured against the
  real pre-replay branch (PR #562 stacked on PR #561, squash-merged as
  d09c52f), it returned the SAME three non-conforming subjects as plain
  ancestry — "Reconcile the ADR record with what v0.5.0 actually shipped",
  "Stop the plugin naming carriers v0.5.0 removed" and "Regenerate the
  schema-constraint cases, …" — because --cherry-pick matches by patch-id, per
  commit, and a squash merge produces one combined patch whose patch-id matches
  none of the individual commits it replaced. The GitHub API is no better: it
  derives a PR's commit list from the merge base, which a squash does not move.
  No patch-id based detection can work for this condition, and none is
  implemented below.

KNOWN LIMITATIONS, ACCEPTED.

  * False negatives degrade to today's behaviour, never to a false alarm. A
    commit whose region the base edited again after the squash fails both
    reverse-apply tests, and step B never runs when step A finds no candidate.
    `git apply -3` would change that failure profile and is deliberately unused.
  * One accepted false positive: a branch whose ENTIRE net content against the
    base is already in the base (both sides made the same edit) acquires an `R`
    and is reported as stacked. The diagnosis is wrong, but such a branch has
    zero net content, so the replay is a no-op and cannot lose work.
  * A degraded run can add a second one, and says so rather than hiding it:
    with the fork index unusable control one cannot run, so a commit this
    branch itself reverted reads as absorbed. `notes` then names the index that
    failed and the message carries the same warning, on either verdict.

Usage:
  stacked-base.py check --base main \\
      --commit-message-format "{ticket_id} {summary}" --ticket-prefix MAR \\
      [--repo-root <path, default cwd>]
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# Load check-conventions.py by file path, exactly as pr-conventions.py:50-54
# does. The matcher and the ignorable rule are CI's; this module calls
# cc.format_to_regex / cc._is_ignorable_commit and re-implements neither.
# ---------------------------------------------------------------------------
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKER = os.path.join(_PLUGIN_ROOT, "templates", "ci", "check-conventions.py")
_cc_spec = importlib.util.spec_from_file_location("acs_check_conventions", CHECKER)
cc = importlib.util.module_from_spec(_cc_spec)
_cc_spec.loader.exec_module(cc)

_SEP = "\x1f"


class CheckError(Exception):
    """A precondition the check cannot evaluate against — exit 2, not a verdict."""


def _git(root, args, env=None, stdin=None):
    """Run git in `root`; return (returncode, stdout BYTES, stderr text)."""
    proc = subprocess.run(["git", "-C", root] + list(args), capture_output=True,
                          env=env, input=stdin)
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", "replace")


def _text(root, args):
    """A git command's stdout as stripped text, or None when the command failed."""
    rc, out, _ = _git(root, args)
    return out.decode("utf-8", "replace").strip() if rc == 0 else None


def resolve_base_ref(root, base):
    """Prefer `origin/<base>`, fall back to `<base>` — check-conventions.py:310-320."""
    for candidate in ("origin/%s" % base, base):
        if _text(root, ["rev-parse", "--verify", "--quiet", candidate + "^{commit}"]):
            return candidate
    return None


def range_commits(root, base_ref):
    """(full, short, subject) for `<base_ref>..HEAD`, newest first, merges excluded."""
    out = _text(root, ["log", "--no-merges",
                       "--format=%%H%s%%h%s%%s" % (_SEP, _SEP), "%s..HEAD" % base_ref])
    if out is None:
        raise CheckError("could not list commits in %s..HEAD" % base_ref)
    commits = []
    for line in out.splitlines():
        parts = line.split(_SEP, 2)
        if len(parts) == 3 and parts[0]:
            commits.append((parts[0], parts[1], parts[2]))
    return commits


def commit_patch(root, sha):
    """One commit's patch as BYTES; None for a root commit. `--binary` is mandatory."""
    # A text round-trip corrupts a binary hunk, and dropping --binary makes any
    # commit touching a binary file report a false "not in base".
    rc, out, _ = _git(root, ["diff", "--binary", sha + "^", sha])
    return out if rc == 0 else None


def cumulative_patch(root, merge_base, sha):
    """Everything the branch has added since the fork point, up to `sha`, as BYTES."""
    rc, out, _ = _git(root, ["diff", "--binary", merge_base, sha])
    return out if rc == 0 else None


def tree_index(root, ref, tmpdir, name):
    """An env whose GIT_INDEX_FILE is a throwaway index holding `ref`'s tree."""
    # read-tree MUST carry the same env as the later apply: without it git
    # writes the REPOSITORY's index and leaves this one empty, at which point
    # every check returns "not absorbed". The write-tree comparison below
    # catches that; returning None is what `check` turns into a `notes` entry,
    # which is what keeps the failure from being silent.
    env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tmpdir, name))
    if _git(root, ["read-tree", ref], env=env)[0] != 0:
        return None
    rc, written, _ = _git(root, ["write-tree"], env=env)
    if rc != 0 or written.decode().strip() != _text(root, ["rev-parse", "%s^{tree}" % ref]):
        return None
    return env


def reverse_applies(root, patch, env):
    """True when `patch`'s post-image is present in the tree `env`'s index holds."""
    if env is None:
        return False
    # Always pass the patch as bytes on stdin: `git apply … -` with no pipe
    # blocks forever.
    rc, _, _ = _git(root, ["apply", "--cached", "--reverse", "--check", "-"],
                    env=env, stdin=patch)
    return rc == 0


def absorbed(root, sha, short, base_env, fork_env, notes):
    """Step A: the commit's content is in the base AND was not at the fork point."""
    patch = commit_patch(root, sha)
    if patch is None:
        notes.append("root commit %s skipped" % short)
        return False
    if not patch.strip():
        # An empty patch is never evidence of absorption.
        notes.append("empty commit %s" % short)
        return False
    return (reverse_applies(root, patch, base_env)
            and not reverse_applies(root, patch, fork_env))


def find_replay_point(root, merge_base, commits, oldest_candidate, base_env):
    """Step B: the newest commit whose CUMULATIVE content is already in the base."""
    # Scanning past the oldest step-A candidate is pointless: no candidate could
    # then sit at-or-before R, so there is nothing left to classify as stacked.
    for index in range(oldest_candidate + 1):
        patch = cumulative_patch(root, merge_base, commits[index][0])
        if patch and patch.strip() and reverse_applies(root, patch, base_env):
            return index, commits[index][1]
    return None, None


#: A lost fork index disables control one, whatever shape the report takes, so
#: both message shapes carry this sentence rather than only the not-stacked one.
FORK_DEGRADED = ("One control did not run: the throwaway index of the fork point was "
                 "unusable, so each commit was tested against %s only — a commit this "
                 "branch itself reverted can read as absorbed that way.")


def build_message(base, base_ref, rng, stacked, replay_onto, own_count, degraded=None):
    """The author-facing text — the whole user-visible deliverable."""
    if not stacked:
        if degraded == "base":
            return ("Stacked-base check could not run: its throwaway index of %s was "
                    "unusable, so the %d non-conforming commit subject(s) in %s "
                    "were never tested against the base." % (base_ref, own_count, rng))
        text = ("No stacked-base condition: %d non-conforming commit subject(s) "
                "in %s are this branch's own." % (own_count, rng))
        return (text + " " + FORK_DEGRADED % base_ref) if degraded == "fork" else text
    listing = "\n".join("  %s  %s" % (e["sha"], e["subject"]) for e in stacked)
    text = (
        "This branch is stacked on a base that was squash-merged, and %d of its commits\n"
        "%s not yours to fix.\n"
        "\n"
        "%s has already absorbed the content of those commits, but a squash merge\n"
        "replaces a pull request's commits with one new commit — so the originals never\n"
        "became ancestors of %s. This branch still carries them, the PR's commit\n"
        "range still lists them, and the \"Branch / PR / commit conventions\" gate will fail\n"
        "on these subjects:\n"
        "\n"
        "%s\n"
        "\n"
        "Renaming them will not help: they belong to a pull request that is already\n"
        "merged. Replay this branch onto the current base instead:\n"
        "\n"
        "  git fetch origin %s\n"
        "  git rebase --onto %s %s\n"
        "  git push --force-with-lease\n"
        "\n"
        "%s is the tip of the branch that was squash-merged — everything up to\n"
        "and including it is already in %s, so replaying past it loses nothing.\n"
        "\n"
        "Every commit SHA on this branch changes when you replay it. Any SHA recorded\n"
        "elsewhere — ticket partition phase artifacts, result.json \"commits\" lists, PR or\n"
        "issue comments — will be stale afterwards and has to be updated by hand.\n"
        "\n"
        "Your own %d commit%s unaffected and keep%s subjects."
        % (len(stacked), "is" if len(stacked) == 1 else "are",
           base_ref, base_ref, listing,
           base, base_ref, replay_onto, replay_onto, base_ref,
           own_count,
           " is" if own_count == 1 else "s are",
           "s its" if own_count == 1 else " their"))
    return (text + "\n\n" + FORK_DEGRADED % base_ref) if degraded == "fork" else text


def check(repo_root, base, commit_message_format, ticket_prefix):
    """Classify `<base_ref>..HEAD` and build the report the skill surfaces."""
    base_ref = resolve_base_ref(repo_root, base)
    if not base_ref:
        raise CheckError("base ref '%s' does not resolve (tried origin/%s and %s)"
                         % (base, base, base))
    merge_base = _text(repo_root, ["merge-base", base_ref, "HEAD"])
    if not merge_base:
        raise CheckError("no merge base between %s and HEAD (unrelated histories)" % base_ref)
    commits = range_commits(repo_root, base_ref)
    pattern = cc.format_to_regex(commit_message_format, ticket_prefix)

    # Only NON-CONFORMING commits are ever patch-tested. That asymmetry is the
    # single most misreadable part of this design: on a branch that reverts its
    # own earlier commit, the conforming commit is never evaluated, and
    # measuring it by hand gives the opposite (wrong) result to the one the
    # detector acts on.
    ignored, offenders = [], []
    for index, (sha, short, subject) in enumerate(commits):
        if cc._is_ignorable_commit(subject):
            ignored.append(subject)
        elif not pattern.match(subject.strip()):
            offenders.append((index, sha, short, subject))

    notes, candidates = [], []
    replay_index, replay_onto, kept, degraded = None, None, None, None
    tmpdir = tempfile.mkdtemp(prefix="acs-stacked-base-")
    try:
        base_env = tree_index(repo_root, base_ref, tmpdir, "base")
        fork_env = tree_index(repo_root, merge_base, tmpdir, "fork")
        # Fail open, but never silently, and never with one sentence for two
        # opposite failures: without the base index nothing can be tested at
        # all, while without the fork index only control one is lost and every
        # commit then reads as MORE absorbed.
        if base_env is None:
            degraded = "base"
            notes.append("throwaway index of %s unusable; no commit could be "
                         "tested against the base" % base_ref)
        elif fork_env is None:
            degraded = "fork"
            notes.append("throwaway index of the fork point unusable; the "
                         "merge-base control could not run")
        for index, sha, short, subject in offenders:
            if absorbed(repo_root, sha, short, base_env, fork_env, notes):
                candidates.append(index)
        if candidates:
            replay_index, replay_onto = find_replay_point(
                repo_root, merge_base, commits, max(candidates), base_env)
    finally:
        shutil.rmtree(tmpdir, True)

    if replay_index is None:
        if candidates:
            notes.append("%d commit(s) look absorbed but no lossless replay point exists"
                         % len(candidates))
        stacked, own = [], offenders
    else:
        # Classify by ANCESTRY, never by list position: `git log` orders by
        # commit date, so a range holding a merge can list an own commit after
        # R, while `R..HEAD` is exactly what the emitted rebase replays.
        kept = {sha for sha, _, _ in range_commits(repo_root, commits[replay_index][0])}
        stacked = [o for o in offenders if o[1] not in kept]
        own = [o for o in offenders if o[1] in kept]

    stacked = [{"sha": short, "subject": subject} for _, _, short, subject in stacked]
    own = [{"sha": short, "subject": subject} for _, _, short, subject in own]
    rng = "%s..HEAD" % base_ref

    result = {
        "verdict": "stacked_base" if stacked else ("own_violations" if own else "clean"),
        "base_ref": base_ref,
        "merge_base": _text(repo_root, ["rev-parse", "--short", merge_base]),
        "range": rng,
        "checked": len(commits),
        "stacked": stacked,
        "own": own,
        "ignored": ignored,
        "notes": notes,
    }
    if stacked:
        result["replay_onto"] = replay_onto
    # <M> counts the commits the emitted rebase KEEPS — everything that
    # descends from replay_onto, conforming or not. Without a replay point the
    # other sentences instead count the branch's own non-conforming subjects.
    own_count = len(own) if kept is None else len(kept)
    result["message"] = build_message(base, base_ref, rng, stacked, replay_onto,
                                      own_count, degraded)
    return result


# ---------------------------------------------------------------------------
# argparse plumbing — the testable core above is callable without it.
# ---------------------------------------------------------------------------

def _add_check_parser(sub):
    p = sub.add_parser("check")
    p.add_argument("--base", required=True)
    p.add_argument("--commit-message-format", required=True)
    p.add_argument("--ticket-prefix", required=True)
    p.add_argument("--repo-root", default=None)
    return p


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_check_parser(sub)
    args = parser.parse_args(argv)

    try:
        result = check(args.repo_root or os.getcwd(), args.base,
                       args.commit_message_format, args.ticket_prefix)
    except CheckError as exc:
        sys.stderr.write("acs stacked-base: %s\n" % exc)
        sys.exit(2)
    print(json.dumps(result))
    sys.exit(1 if result["verdict"] == "stacked_base" else 0)


if __name__ == "__main__":
    main()
