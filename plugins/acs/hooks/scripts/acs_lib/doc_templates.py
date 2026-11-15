"""acs_lib.doc_templates — the repo's own copies of acs's templates (ADR-0148).

Every built-in template in the plugin's `templates/` (not `templates/ci/`, the
CI runners setup installs separately) shapes something a skill writes: the PR
body, the ticket descriptions, the tech design, the audit reports and the PRD
documents. A repo's `.acs/templates/<name>.md` replaces the built-in of that
name. /acs:setup scaffolds a copy of every one, so a team edits its templates
in place, in its own repo, without first finding them in the plugin.

A copy must not freeze the built-in it came from. `.acs/templates/
templates.lock.json` records, per template, the sha256 of the built-in it was
copied from. On every setup re-run:

  absent      copied, its hash recorded (`added`)
  untouched   the copy still equals what was copied: refreshed to the current
              built-in when that moved on (`refreshed`), else left (`unchanged`)
  edited      the copy differs from what was copied: never overwritten
              (`customised`); when the built-in has also moved on since, the
              team is told to review it (`drift`)
  unrecorded  a copy the repo had before any lock entry (hand-made): kept as
              `customised`, with no base to compare

So an edit is the team's for good, and an unedited copy keeps following the
plugin.
"""

import hashlib
import json
import os

LOCK_NAME = "templates.lock.json"


def builtin_dir(plugin_root):
    return os.path.join(plugin_root, "templates")


def repo_dir(root):
    return os.path.join(root, ".acs", "templates")


def builtin_names(plugin_root):
    """Every built-in template's name (its file name without `.md`), sorted."""
    folder = builtin_dir(plugin_root)
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(n[:-3] for n in names
                  if n.endswith(".md") and os.path.isfile(os.path.join(folder, n)))


def _sha(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _read_lock(root):
    try:
        with open(os.path.join(repo_dir(root), LOCK_NAME), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    templates = doc.get("templates") if isinstance(doc, dict) else None
    return templates if isinstance(templates, dict) else {}


def status(root, plugin_root):
    """[{name, path, state, builtin_changed}] for every built-in template, read-only.

    `state` is `missing`, `untouched`, `customised` or `unrecorded`;
    `builtin_changed` says the built-in differs from the one the copy came from."""
    lock, out = _read_lock(root), []
    for name in builtin_names(plugin_root):
        rel = "/".join((".acs", "templates", name + ".md"))
        copy = _sha(os.path.join(root, rel))
        builtin = _sha(os.path.join(builtin_dir(plugin_root), name + ".md"))
        base = (lock.get(name) or {}).get("sha256")
        if copy is None:
            state = "missing"
        elif base is None:
            state = "unrecorded"
        elif copy == base:
            state = "untouched"
        else:
            state = "customised"
        out.append({"name": name, "path": rel, "state": state,
                    "builtin_changed": bool(base) and builtin != base})
    return out


def scaffold(root, plugin_root, dry_run=False):
    """Copy, refresh or keep each template per the module docstring.

    Returns {added, refreshed, unchanged, customised, drift, written} -- lists of
    repo-relative paths; `written` is every file this call wrote (the lock
    included), for setup to stage."""
    lock = _read_lock(root)
    result = {k: [] for k in ("added", "refreshed", "unchanged", "customised", "drift",
                              "written")}
    new_lock = dict(lock)
    for entry in status(root, plugin_root):
        name, rel, state = entry["name"], entry["path"], entry["state"]
        src = os.path.join(builtin_dir(plugin_root), name + ".md")
        if state in ("missing", "untouched") and (state == "missing" or entry["builtin_changed"]):
            if not dry_run:
                os.makedirs(repo_dir(root), exist_ok=True)
                with open(src, "rb") as fh, open(os.path.join(root, rel), "wb") as out:
                    out.write(fh.read())
            new_lock[name] = {"sha256": _sha(src)}
            result["added" if state == "missing" else "refreshed"].append(rel)
            result["written"].append(rel)
        elif state == "untouched":
            result["unchanged"].append(rel)
        else:
            result["customised"].append(rel)
            if entry["builtin_changed"]:
                result["drift"].append(rel)
    if new_lock != lock:
        lock_rel = "/".join((".acs", "templates", LOCK_NAME))
        if not dry_run:
            os.makedirs(repo_dir(root), exist_ok=True)
            with open(os.path.join(root, lock_rel), "w", encoding="utf-8") as fh:
                json.dump({"templates": dict(sorted(new_lock.items()))}, fh, indent=2)
                fh.write("\n")
        result["written"].append(lock_rel)
    return result


def apply_for_setup(root, plugin_root, wanted, changes, staged, dry_run=False):
    """`setup apply`'s step: `wanted` True scaffolds every template; None (the
    answer absent) still refreshes a repo that already has copies; False skips.
    Notes each change on `changes` and extends `staged` with what it wrote."""
    if wanted is False or (wanted is None and not os.path.isdir(repo_dir(root))):
        return None
    done = scaffold(root, plugin_root, dry_run=dry_run)
    for key, verb in (("added", "scaffolded"), ("refreshed", "refreshed")):
        for rel in done[key]:
            changes.note(True, "%s %s" % (verb, rel))
    changes.note(False, "%d document templates already current, %d customised"
                 % (len(done["unchanged"]), len(done["customised"])))
    for rel in done["drift"]:
        changes.warn("%s is customised and its built-in changed since it was copied; "
                     "compare it with the plugin's templates/%s" % (rel, os.path.basename(rel)))
    staged.extend(done["written"])
    return done
