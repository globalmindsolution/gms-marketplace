#!/usr/bin/env python3
"""The fixture app: a small, real codebase for behavioural scenarios to run on.

    python3 runner/fixture_app.py build <dir>     # materialise it with its history
    python3 runner/fixture_app.py hash            # the hash scenarios.json must carry
    python3 runner/fixture_app.py --check         # fail if scenarios.json's hash is stale
    python3 runner/fixture_app.py selftest        # build in a temp dir, run its tests

Why it exists: the two-line `app.py` the paid scenarios have run against
measures almost nothing — docs-sync has no docs to sync, the coverage gate
never bites, regression-risk has no history, and no path matches a
`high_stakes_paths` glob. `dataset/fixtures/app/tree/` is an order-management
service (14 modules, 43 tests at 99% coverage, a docs/ tree with two ADRs, a
`payments/` path for stakes escalation) and `history.json` is its 32-commit
history — including a feature commit and its revert — replayed with fixed
author, committer and dates, so every build has identical SHAs.

The fixture is part of the experiment. `hash()` covers every byte of the tree
and the history; `dataset/scenarios.json` records it as `fixture_hash`, and
`--check` (run by `make check`) fails when they disagree, so a changed fixture
forces a `scenario_set_version` bump instead of silently making older
baselines incomparable.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(REPO_ROOT, "dataset", "fixtures", "app")
TREE = os.path.join(FIXTURE, "tree")
HISTORY = os.path.join(FIXTURE, "history.json")
SCENARIOS = os.path.join(REPO_ROOT, "dataset", "scenarios.json")

_SKIP = ("__pycache__", ".coverage")


def tree_files():
    out = []
    for root, dirs, files in os.walk(TREE):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP)
        for name in sorted(files):
            if name.endswith(".pyc") or name in _SKIP:
                continue
            path = os.path.join(root, name)
            out.append(os.path.relpath(path, TREE))
    return out


def fixture_hash():
    """sha256 over every tree file's path and bytes, plus history.json."""
    h = hashlib.sha256()
    for rel in tree_files():
        h.update(rel.encode())
        with open(os.path.join(TREE, rel), "rb") as fh:
            h.update(fh.read())
    with open(HISTORY, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()[:16]


def _git(repo, *args, env=None):
    subprocess.run(("git",) + args, cwd=repo, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)


def _replace_once(text, old, new, where):
    if text.count(old) != 1:
        raise RuntimeError("%s: anchor found %d times, expected once:\n%s"
                           % (where, text.count(old), old[:120]))
    return text.replace(old, new)


def initial_version(rel, history, upto):
    """The file as it first entered history: the final tree with every later
    non-reverted patch undone, newest first."""
    with open(os.path.join(TREE, rel)) as fh:
        text = fh.read()
    later = [c for c in history["commits"][upto + 1:]
             if "patch" in c and not c.get("reverted")]
    for commit in reversed(later):
        for edit in reversed(commit["patch"]):
            if edit["file"] == rel:
                text = _replace_once(text, edit["after"], edit["before"],
                                     "%s (reverse of %r)" % (rel, commit["message"]))
    return text


def build(dest):
    """Materialise the fixture repo at `dest` with its full history; returns HEAD."""
    with open(HISTORY) as fh:
        history = json.load(fh)
    os.makedirs(dest, exist_ok=True)
    if os.listdir(dest):
        raise RuntimeError("%s is not empty" % dest)
    name, email = history["author"].rsplit(" <", 1)
    email = email.rstrip(">")
    base_env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                    GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email,
                    GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email)
    _git(dest, "init", "-q", "-b", "main", ".", env=base_env)
    when = datetime.fromisoformat(history["start"])
    step = timedelta(minutes=history["step_minutes"])
    seen = set()
    for i, commit in enumerate(history["commits"]):
        stamp = (when + step * i).isoformat()
        env = dict(base_env, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
        if commit.get("revert"):
            _git(dest, "revert", "--no-edit", "HEAD", env=env)
            message = commit["message"] + "\n\n" + commit.get("trailer", "")
            _git(dest, "commit", "-q", "--amend", "-m", message.rstrip(), env=env)
            continue
        for edit in commit.get("patch", []):
            target = os.path.join(dest, edit["file"])
            with open(target) as fh:
                text = fh.read()
            text = _replace_once(text, edit["before"], edit["after"],
                                 "%s (%r)" % (edit["file"], commit["message"]))
            with open(target, "w") as fh:
                fh.write(text)
        for rel in commit.get("files", []):
            if rel in seen:
                raise RuntimeError("%s is added twice; later edits must be patches" % rel)
            seen.add(rel)
            dst = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(dst) or dest, exist_ok=True)
            with open(dst, "w") as fh:
                fh.write(initial_version(rel, history, i))
        _git(dest, "add", "-A", env=env)
        _git(dest, "commit", "-q", "-m", commit["message"], env=env)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True,
                          text=True, env=base_env, check=True).stdout.strip()
    # The final tree must equal tree/ exactly: history that drifts from the
    # files it claims to build is the kind of fixture rot the hash exists for.
    missing = [rel for rel in tree_files() if rel not in seen]
    if missing:
        raise RuntimeError("history never adds: %s" % ", ".join(missing))
    for rel in tree_files():
        with open(os.path.join(TREE, rel), "rb") as a, open(os.path.join(dest, rel), "rb") as b:
            if a.read() != b.read():
                raise RuntimeError("history does not rebuild tree/: %s differs" % rel)
    return head


def recorded_hash():
    with open(SCENARIOS) as fh:
        return json.load(fh).get("fixture_hash")


def selftest():
    dest = tempfile.mkdtemp(prefix="acs-fixture-")
    try:
        head = build(dest)
        log = subprocess.run(["git", "log", "--format=%s", "--reverse"], cwd=dest,
                             capture_output=True, text=True, check=True).stdout.splitlines()
        tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                               cwd=dest, capture_output=True, text=True)
        ok = tests.returncode == 0
        print("built %s: %d commits, HEAD %s, tests %s"
              % (dest, len(log), head[:12], "OK" if ok else "FAILED"))
        if not ok:
            print(tests.stderr[-2000:])
        return 0 if ok else 1
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", choices=["build", "hash", "selftest"])
    ap.add_argument("dest", nargs="?")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if scenarios.json's fixture_hash is stale")
    args = ap.parse_args()
    if args.check:
        want, got = fixture_hash(), recorded_hash()
        if want != got:
            print("fixture_hash is stale: scenarios.json has %s, the fixture is %s — "
                  "bump scenario_set_version and record the new hash" % (got, want),
                  file=sys.stderr)
            return 1
        print("fixture_hash %s is current" % want)
        return 0
    if args.command == "hash":
        print(fixture_hash())
        return 0
    if args.command == "build":
        if not args.dest:
            ap.error("build needs a destination directory")
        print(build(args.dest))
        return 0
    if args.command == "selftest":
        return selftest()
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
