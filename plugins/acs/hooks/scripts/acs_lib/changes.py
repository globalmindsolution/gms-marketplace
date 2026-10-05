"""acs_lib.changes — the working-tree changeset a run produced (ADR-0127).

Only `/acs:create-pr` stages, commits and pushes. Every other skill leaves its
output as uncommitted changes in the working tree and records the paths it
wrote. That moves the question "what did this run change?" off the commit log
(`git diff <default>...HEAD`, which is empty while nothing is committed) and on
to the working tree itself, and this module is the one answer to it:

  * **Baseline** -- `<run>/baseline.json`, written once per run by the first
    `acs.py step start`: the HEAD the run started from, the branch, and the
    paths that were ALREADY dirty or untracked at that moment, with their blob
    ids. A file the user was editing before the run began is not the run's.
  * **Snapshot** -- a git tree id of the whole working tree, untracked
    non-ignored files included, built in a throwaway index so the real index
    and the tree are never touched. A tree id is a value a later step can diff
    against: it is what a review records as `reviewed_sha`.
  * **Changeset** -- `<since>` -> a fresh snapshot, minus the baseline's dirty
    paths that have not changed again since the baseline.

Everything here shells out to git and nothing else; no function stages,
commits or moves HEAD.
"""

import os
import shutil
import subprocess
import tempfile

from ._common import GateError, now_iso, read_json, write_json

BASELINE_FILENAME = "baseline.json"

#: `git diff --name-status` letters, spelled out for the JSON a skill reads.
STATUS_NAMES = {"A": "added", "M": "modified", "D": "deleted", "T": "type_changed",
                "U": "unmerged", "X": "unknown"}


def _run_git(root, args, env=None, check=True):
    full_env = dict(os.environ)
    # A path is a path: never let a file called `*.py` act as a glob.
    full_env["GIT_LITERAL_PATHSPECS"] = "1"
    if env:
        full_env.update(env)
    try:
        proc = subprocess.run(["git"] + list(args), cwd=root, capture_output=True,
                              env=full_env, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateError("git %s could not run: %s" % (" ".join(args[:2]), exc))
    if check and proc.returncode != 0:
        raise GateError("git %s failed: %s" % (
            " ".join(args[:3]), proc.stderr.decode("utf-8", "replace").strip()))
    return proc


def _out(root, args, **kw):
    return _run_git(root, args, **kw).stdout.decode("utf-8", "replace").strip()


def head_sha(root):
    """HEAD's commit sha, or None on an unborn branch."""
    proc = _run_git(root, ["rev-parse", "--verify", "--quiet", "HEAD^{commit}"], check=False)
    return (proc.stdout.decode().strip() or None) if proc.returncode == 0 else None


def current_branch(root):
    """The checked-out branch name, or None when HEAD is detached."""
    proc = _run_git(root, ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    return (proc.stdout.decode().strip() or None) if proc.returncode == 0 else None


def default_branches(root):
    """The repo's default branch names: origin/HEAD's target when the remote
    records one, plus the conventional `main` and `master` either way."""
    names = {"main", "master"}
    proc = _run_git(root, ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], check=False)
    if proc.returncode == 0:
        names.add(proc.stdout.decode().strip().rsplit("/", 1)[-1])
    return names


def empty_tree(root):
    """The empty tree's id in this repo's hash (sha1 or sha256)."""
    proc = subprocess.run(["git", "hash-object", "-t", "tree", "--stdin"], cwd=root,
                          input=b"", capture_output=True)
    if proc.returncode != 0:
        raise GateError("git hash-object failed: %s" % proc.stderr.decode("utf-8", "replace"))
    return proc.stdout.decode().strip()


def resolve_tree(root, rev):
    """The tree id `rev` (a commit, a tree, or any rev) names, or GateError."""
    proc = _run_git(root, ["rev-parse", "--verify", "--quiet", "%s^{tree}" % rev], check=False)
    tree = proc.stdout.decode().strip()
    if proc.returncode != 0 or not tree:
        raise GateError("%r names no commit or tree in this repository" % rev)
    return tree


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def snapshot(root):
    """A tree id of the full working tree -- tracked changes, deletions and
    untracked non-ignored files -- written through a TEMPORARY index.

    The temporary index starts as a copy of the real one (so git reuses its
    stat data rather than re-hashing every file) or, with none, from HEAD;
    `git add -A` then makes it match the working tree. The real index is never
    written: `GIT_INDEX_FILE` points every command at the copy."""
    git_index = os.path.join(root, _out(root, ["rev-parse", "--git-path", "index"]))
    tmpdir = tempfile.mkdtemp(prefix="acs-snapshot-")
    try:
        tmp_index = os.path.join(tmpdir, "index")
        env = {"GIT_INDEX_FILE": tmp_index}
        if os.path.isfile(git_index):
            # copy2, not copyfile: git re-reads an entry whose mtime is not
            # older than the index FILE's ("racy"); a copy stamped with a newer
            # mtime would make git trust stale stat data and miss a same-size
            # edit made in the same second the index was written.
            shutil.copy2(git_index, tmp_index)
        elif head_sha(root):
            _run_git(root, ["read-tree", "HEAD"], env=env)
        _run_git(root, ["add", "-A", "--", "."], env=env)
        return _out(root, ["write-tree"], env=env)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Diffs between two tree-ish values
# ---------------------------------------------------------------------------

def name_status(root, old, new):
    """[{"path", "status"}] for every path that differs between two tree-ish
    values, renames reported as a delete plus an add (a commit plan groups
    paths, and a rename's two halves are two paths)."""
    raw = _run_git(root, ["diff", "--name-status", "--no-renames", "-z", old, new, "--"]).stdout
    parts = raw.decode("utf-8", "surrogateescape").split("\0")
    out = []
    for i in range(0, len(parts) - 1, 2):
        letter = parts[i][:1]
        out.append({"path": parts[i + 1], "status": STATUS_NAMES.get(letter, letter)})
    return out


def blobs(root, tree, paths):
    """{path: blob id or None} for `paths` in `tree` (None: absent there)."""
    found = {p: None for p in paths}
    if not paths:
        return found
    raw = _run_git(root, ["ls-tree", "-r", "-z", "--full-tree", tree]).stdout
    wanted = set(paths)
    for record in raw.decode("utf-8", "surrogateescape").split("\0"):
        if "\t" not in record:
            continue
        meta, path = record.split("\t", 1)
        if path in wanted:
            found[path] = meta.split()[2]
    return found


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

def baseline_path(rdir):
    return os.path.join(rdir, BASELINE_FILENAME)


def load_baseline(rdir):
    doc = read_json(baseline_path(rdir)) if rdir else None
    return doc if isinstance(doc, dict) else None


#: A run whose FIRST step is one of these reads work that already exists --
#: hand-written changes to review, document, ship or test. The paths dirty at
#: its baseline are its subject, not someone else's work in progress, so the
#: changeset keeps them. A run that starts by writing (analysis, plan, code)
#: leaves them out instead: they were there before it and are not its output.
ADOPTING_FIRST_STEPS = ("review-code", "docs-sync", "create-pr", "run-e2e-tests")


def record_baseline(rdir, checkout_root, first_step=None):
    """Write `<run>/baseline.json` once per run, never overwriting it. Returns
    the baseline (the existing one when already recorded)."""
    existing = load_baseline(rdir)
    if existing is not None:
        return existing
    base = head_sha(checkout_root)
    tree = snapshot(checkout_root)
    dirty = [entry["path"] for entry in
             name_status(checkout_root, base or empty_tree(checkout_root), tree)]
    doc = {
        "base_sha": base,
        "branch": current_branch(checkout_root),
        "tree": tree,
        "dirty": dirty,
        "dirty_blobs": blobs(checkout_root, tree, dirty),
        "first_step": first_step,
        "adopts_dirty": first_step in ADOPTING_FIRST_STEPS,
        "recorded_at": now_iso(),
    }
    os.makedirs(rdir, exist_ok=True)
    write_json(baseline_path(rdir), doc)
    return doc


def _base_of(root, baseline):
    return (baseline or {}).get("base_sha") or empty_tree(root)


def changeset(root, since=None, baseline=None, tree=None):
    """What changed from `since` to the working tree now.

    `since` defaults to the baseline's `base_sha` (the empty tree on a run that
    began on an unborn branch). A path the baseline found already dirty is
    left out -- reported under `excluded` -- unless its content changed again
    since the baseline, or the run adopted it (`adopts_dirty`: its first step
    reads existing work, ADOPTING_FIRST_STEPS). Returns {"since", "tree",
    "files", "excluded"}."""
    if since is None:
        if baseline is None:
            raise GateError("no baseline recorded for this run and no --since given -- "
                            "pass --since <commit-or-tree>")
        since = _base_of(root, baseline)
    resolve_tree(root, since)
    tree = tree or snapshot(root)
    entries = name_status(root, since, tree)
    adopted = bool((baseline or {}).get("adopts_dirty"))
    dirty = set() if adopted else set((baseline or {}).get("dirty") or [])
    recorded_blobs = (baseline or {}).get("dirty_blobs") or {}
    candidates = [e["path"] for e in entries if e["path"] in dirty]
    now_blobs = blobs(root, tree, candidates)
    files, excluded = [], []
    for entry in entries:
        path = entry["path"]
        if path in dirty and now_blobs.get(path) == recorded_blobs.get(path):
            excluded.append(entry)
        else:
            files.append(entry)
    return {"since": since, "tree": tree, "files": files, "excluded": excluded}


def render(root, since, tree, paths, mode):
    """`git diff --stat` or `--patch` text of `since` -> `tree`, limited to
    `paths` (so the baseline's excluded paths never show)."""
    if not paths:
        return ""
    flag = "--stat" if mode == "stat" else "--patch"
    out = []
    # Chunked: a changeset of thousands of paths must not overflow argv.
    for i in range(0, len(paths), 500):
        chunk = paths[i:i + 500]
        out.append(_run_git(root, ["diff", flag, "--no-renames", since, tree, "--"] + chunk)
                   .stdout.decode("utf-8", "replace"))
    return "".join(out)
