#!/usr/bin/env python3
"""migrate_workspace.py -- standalone, one-shot workspace migrator.

Originating ticket: MAR-3. Implements the design's Migrator contract
(MAR-1/design.md, Rollout/migration section): copies an existing external
workspace partition (<old>/<repo-id>/) into the new in-repo state root
(<new>/<repo-id>/), with a hard preflight, conflict-abort handling for
repo-level files, idempotent ticket-partition resume, and copy-then-
verify-then-remove ordering.

Usage:
  migrate_workspace.py --from <old-workspace-root> --to <new-state-root>
                        --repo-root <main-checkout-root> [--dry-run]
"""

import argparse
import filecmp
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402


def _fail(message):
    """Print a user-facing refusal to stderr and exit 2 -- no writes precede this."""
    sys.stderr.write("acs migrate-workspace: %s\n" % message)
    sys.exit(2)


def _iter_files(root):
    """Yield every regular file under root as a path relative to root."""
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            yield os.path.relpath(os.path.join(dirpath, fname), root)


def preflight(old_root):
    """Abort (exit 2, no writes) on any live .lock file, or any in_progress last
    run, found anywhere under old_root -- ticket partitions and archive/ alike."""
    for dirpath, _dirnames, filenames in os.walk(old_root):
        for fname in filenames:
            if fname == ".lock":
                _fail("refusing to migrate -- a lock is present at %s"
                      % os.path.join(dirpath, fname))
            if fname.endswith("-state.json"):
                skill = fname[: -len("-state.json")]
                if lib.last_run_status(dirpath, skill) == "in_progress":
                    _fail("refusing to migrate -- %s's %s run is in_progress (%s)"
                          % (os.path.basename(dirpath), skill, os.path.join(dirpath, fname)))


def _copy_ticket_partition(old_path, new_path, rel, dry_run, actions):
    """Copy a whole ticket (or archived ticket) partition tree; a partition already
    present at the destination is left as-is -- never overwritten, never re-copied."""
    if os.path.isdir(new_path):
        actions.append(("keep-existing", rel))
        return
    actions.append(("copy-ticket", rel))
    if not dry_run:
        shutil.copytree(old_path, new_path)


def _copy_repo_level_file(old_root, new_root, rel, dry_run, actions):
    """Copy one repo-level file when absent at the destination; skip a byte-identical
    match; abort naming the file on any other conflict -- no "newer wins" guess."""
    old_path = os.path.join(old_root, rel)
    new_path = os.path.join(new_root, rel)
    if not os.path.exists(new_path):
        actions.append(("copy-file", rel))
        if not dry_run:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.copy2(old_path, new_path)
        return
    if filecmp.cmp(old_path, new_path, shallow=False):
        actions.append(("skip-identical", rel))
        return
    _fail("repo-level file differs at source and destination -- %s" % rel)


def classify_and_copy(old_root, new_root, dry_run):
    """Classify every direct child of old_root (ticket partition / archive/ / repo-
    level file or directory) and apply its copy rule; returns the planned actions."""
    actions = []
    archive_path = lib.archive_dir(os.path.dirname(old_root), os.path.basename(old_root))
    for name in sorted(os.listdir(old_root)):
        path = os.path.join(old_root, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "ticket.json")):
            _copy_ticket_partition(path, os.path.join(new_root, name), name, dry_run, actions)
        elif path == archive_path and os.path.isdir(path):
            for child in sorted(os.listdir(path)):
                child_path = os.path.join(path, child)
                if not os.path.isdir(child_path):
                    continue
                rel = os.path.join(name, child)
                _copy_ticket_partition(child_path, os.path.join(new_root, name, child),
                                        rel, dry_run, actions)
        elif os.path.isfile(path):
            _copy_repo_level_file(old_root, new_root, name, dry_run, actions)
        else:
            for file_rel in _iter_files(path):
                _copy_repo_level_file(old_root, new_root, os.path.join(name, file_rel),
                                       dry_run, actions)
    return actions


def _verify(old_root, new_root):
    """Invariant check: every file under old_root also exists at the same relative
    path under new_root, before old_root is ever removed."""
    for rel in _iter_files(old_root):
        assert os.path.exists(os.path.join(new_root, rel)), (
            "verification failed -- missing at destination: %s" % rel)


def main():
    parser = argparse.ArgumentParser(prog="migrate_workspace.py")
    parser.add_argument("--from", dest="old_workspace", required=True)
    parser.add_argument("--to", dest="new_workspace", required=True)
    parser.add_argument("--repo-root", dest="repo_root", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_id = lib.repo_partition_id(args.repo_root)
    if not repo_id:
        _fail("could not resolve a repo id from --repo-root %s (not a git checkout?)"
              % args.repo_root)

    old_root = lib.repo_dir(args.old_workspace, repo_id)
    new_root = lib.repo_dir(args.new_workspace, repo_id)

    if not os.path.isdir(old_root):
        print("acs migrate-workspace: already migrated (%s not present)" % old_root)
        sys.exit(0)

    preflight(old_root)
    actions = classify_and_copy(old_root, new_root, args.dry_run)
    for kind, rel in actions:
        print("%s %s" % (kind, rel))

    if args.dry_run:
        print("acs migrate-workspace: dry run only -- nothing written")
        sys.exit(0)

    _verify(old_root, new_root)
    shutil.rmtree(old_root)
    print("acs migrate-workspace: migrated %s -> %s (%d item(s))"
          % (old_root, new_root, len(actions)))
    sys.exit(0)


if __name__ == "__main__":
    main()
