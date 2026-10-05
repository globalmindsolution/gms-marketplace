"""acs_lib.state_root -- where the workspace lives, and the one-time move there (ADR-0136).

The workspace is `<git-common-dir>/acs/state-machine`. It used to be
`<main-checkout>/.acs/state-machine` (ADR-0086), and two Claude Code rules made
that unwritable exactly where acs is meant to run: a session in a worktree is
refused any Edit/Write aimed at the main checkout, and the Bash sandbox lets
Bash write only the working directory, $TMPDIR and -- from a linked worktree --
the main repo's shared `.git` directory. The common dir is the one place every
worktree of a repo shares that both rules allow, and `git clean -fdx` never
touches it.

`repo.default_state_root` derives the paths and the refusals; this module owns
the migration it triggers:

  * the legacy root exists and the new one does not -> the tree is moved
    (`os.rename`; when that is refused -- another device, a sandbox -- it is
    copied into a temp directory beside the new root and that is renamed into
    place, then the old tree is removed), every absolute path a JSON state file
    stored under the old root is rewritten to the new one, and a one-line
    `<main>/.acs/state-machine.MOVED` note names where it went;
  * both exist -> the new one is used and the old one is left for a human:
    `acs.py doctor` reports it (`state_root_report`);
  * a temp directory left by a move that was interrupted after the old tree
    was renamed away is finished, not lost.

The whole move runs under an O_EXCL guard in the common dir, so two hooks that
derive the root at once cannot both migrate.
"""

import json
import os
import shutil
import sys

from ._common import GateError, write_json

#: Path segments below the git common dir.
STATE_ROOT_PARTS = ("acs", "state-machine")
#: Path segments below the main checkout, before ADR-0136.
LEGACY_ROOT_PARTS = (".acs", "state-machine")
#: The note left where the legacy root was.
MOVED_SUFFIX = ".MOVED"
#: The guard and the staging directory, both beside the new root.
GUARD_NAME = ".migrate.guard"
STAGING_NAME = ".state-machine.migrating"


def state_root_for(common_dir):
    return os.path.join(common_dir, *STATE_ROOT_PARTS)


def legacy_root_for(main_checkout):
    return os.path.join(main_checkout, *LEGACY_ROOT_PARTS)


def _staging(new):
    return os.path.join(os.path.dirname(new), STAGING_NAME)


def _warn(message):
    sys.stderr.write("acs: %s\n" % message)


def _rewrite_value(value, prefixes, new):
    if isinstance(value, str):
        for old in prefixes:
            if value == old or value.startswith(old + os.sep):
                return new + value[len(old):]
        return value
    if isinstance(value, list):
        return [_rewrite_value(v, prefixes, new) for v in value]
    if isinstance(value, dict):
        return dict((k, _rewrite_value(v, prefixes, new)) for k, v in value.items())
    return value


def rewrite_stored_paths(tree, old, new):
    """Rewrite every string in every `*.json` under `tree` that names `old` or a
    path below it, so it names the same place under `new`. Returns the files
    changed. Idempotent: a rewritten value no longer starts with `old`.

    JSON only, on purpose: markdown is prose a reader resolves, a draft folder's
    digest covers its markdown, and `lock-events.jsonl` is an append-only audit
    ledger -- history, not a pointer."""
    prefixes = []
    for form in (os.path.normpath(old), os.path.realpath(old)):
        if form not in prefixes:
            prefixes.append(form)
    changed = []
    for dirpath, _dirnames, filenames in os.walk(tree):
        for name in filenames:
            if not name.endswith(".json"):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    doc = json.load(fh)
            except (OSError, ValueError):
                continue  # unreadable state stays exactly as it was
            rewritten = _rewrite_value(doc, prefixes, new)
            if rewritten != doc:
                write_json(path, rewritten)
                changed.append(path)
    return changed


def _leave_note(old, new):
    try:
        with open(old + MOVED_SUFFIX, "w", encoding="utf-8") as fh:
            fh.write("acs state moved to %s (ADR-0136); this folder is no longer read.\n" % new)
    except OSError as exc:
        _warn("state root migrated to %s, but the note at %s could not be written (%s)"
              % (new, old + MOVED_SUFFIX, exc))


def _finish(staging, old, new):
    """staging holds the complete tree: fix its stored paths, land it."""
    rewrite_stored_paths(staging, old, new)
    os.replace(staging, new)


def _move(old, new):
    staging = _staging(new)
    if os.path.isdir(staging) and not os.path.exists(old):
        _finish(staging, old, new)          # an interrupted move, picked back up
        return
    if os.path.exists(staging):
        shutil.rmtree(staging)              # a partial copy: start it again
    try:
        os.rename(old, staging)
    except OSError:
        if os.path.exists(new):
            return                          # someone else migrated first
        try:
            shutil.copytree(old, staging, symlinks=True)
        except (OSError, shutil.Error) as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise GateError(
                "acs could not move its state from %s to %s (%s). Nothing was lost: "
                "the old folder is untouched. Move it yourself (`mv %s %s`) and retry."
                % (old, new, exc, old, new))
        _finish(staging, old, new)
        try:
            shutil.rmtree(old)
        except OSError as exc:
            _warn("state copied to %s, but the old folder %s could not be removed (%s); "
                  "it is no longer read -- delete it once you have checked the copy "
                  "(`acs.py doctor` reports it)." % (new, old, exc))
            return
        _leave_note(old, new)
        return
    _finish(staging, old, new)
    _leave_note(old, new)


def migrate_legacy_root(old, new):
    """Move `old` to `new` when only `old` exists. Idempotent; raises GateError
    when a move that was needed could not be made."""
    staging = _staging(new)
    if os.path.exists(new) or not (os.path.isdir(old) or os.path.isdir(staging)):
        return False
    from .repo import repo_guard  # repo imports this module lazily too
    try:
        with repo_guard(os.path.dirname(new), GUARD_NAME):
            if os.path.exists(new) or not (os.path.isdir(old) or os.path.isdir(staging)):
                return False
            _move(old, new)
    except OSError as exc:
        raise GateError("acs could not migrate its state from %s to %s (%s)."
                        % (old, new, exc))
    return True


def state_root_report(cwd):
    """{"path", "legacy", "legacy_leftover", "message"} for `acs.py doctor`.
    Derives the root (so it migrates, like every other caller) and then says
    whether a legacy folder is still sitting in the main checkout."""
    from .repo import default_state_root, main_repo_root
    try:
        path = default_state_root(cwd)
    except GateError as exc:
        return {"path": None, "legacy": None, "legacy_leftover": False, "message": str(exc)}
    main = main_repo_root(cwd)
    legacy = legacy_root_for(main) if main else None
    leftover = bool(legacy and os.path.isdir(legacy))
    if leftover:
        message = ("legacy state folder %s is a leftover: acs reads %s. Check it holds "
                   "nothing you need, then delete it." % (legacy, path))
    else:
        message = "state root %s" % path
    return {"path": path, "legacy": legacy if leftover else None,
            "legacy_leftover": leftover, "message": message}
