"""acs_lib.claude_permissions — the Claude Code permission rules /acs:setup offers.

No acs skill sets `allowed-tools`, so every acs CLI call -- `python3
"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/<script>.py" ...`, which Claude Code sees
with the plugin root already expanded to the plugin cache (or, in a dev
checkout, to `.../plugins/acs`) -- and every read-only git call asks for
permission. /acs:setup offers, opt-in, a FIXED set of `permissions.allow`
rules for the team's `.claude/settings.json` or the user's own
`.claude/settings.local.json`.

The set pre-approves acs's own scripts and read-only git, and nothing that
writes: `git add/commit/push` and `gh` keep prompting by design. A shell
pattern is a convenience, not a sandbox -- `*` matches any text, spaces
included -- and the skill says so when it offers the rules.

Both files are written at the MAIN checkout, the root /acs:setup writes every
other file to: Claude Code saves a linked worktree's approvals in the main
checkout's `settings.local.json`. A merge keeps every other key and rule, adds
only what is missing, and never rewrites a file it has nothing to add to.

Stdlib only.
"""

import json
import os
import subprocess

from ._common import GateError
from .repo import checkout_root, main_repo_root

#: acs's own scripts, wherever the plugin root expands to: the plugin cache
#: (`.../acs/<version>/hooks/scripts/acs.py`) or a dev checkout
#: (`.../plugins/acs/hooks/scripts/acs.py`). The `*` between `acs/` and
#: `hooks/` is what lets one rule cover both.
ACS_SCRIPTS_RULE = "Bash(python3 *acs/*hooks/scripts/*.py*)"

#: The fixed set, in the order it is shown and written. Read-only git only.
RULES = (
    ACS_SCRIPTS_RULE,
    "Bash(git status*)",
    "Bash(git diff*)",
    "Bash(git log*)",
    "Bash(git rev-parse*)",
    "Bash(git ls-files*)",
    "Bash(git show*)",
    "Bash(git check-ignore*)",
)

#: scope -> the settings file, relative to the main checkout.
FILES = {"team": ".claude/settings.json", "user": ".claude/settings.local.json"}
ANSWERS = ("team", "user", "skip")


def _base(root):
    return main_repo_root(root) or checkout_root(root) or root


def paths(root):
    """{scope: absolute path} of the two settings files."""
    base = _base(root)
    return {scope: os.path.join(base, *rel.split("/")) for scope, rel in FILES.items()}


def ignore_entries(scope):
    """The ignore entries an answer needs: the user's local file is machine-
    specific, so it is ignored the way `.acs/settings.local.json` is."""
    return (FILES["user"],) if scope == "user" else ()


def _ignored(rel, cwd):
    try:
        return subprocess.run(["git", "check-ignore", "-q", rel], cwd=cwd,
                              capture_output=True).returncode == 0
    except OSError:
        return False


def _load(path):
    """(document, allow list) of a settings file; ({}, []) when absent.
    GateError when it cannot be merged into without losing something."""
    if not os.path.exists(path):
        return {}, []
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        raise GateError("%s is not valid JSON (%s) -- fix or remove it, then re-run"
                        % (path, exc))
    if not isinstance(doc, dict):
        raise GateError("%s is not a JSON object" % path)
    perms = doc.get("permissions", {})
    if not isinstance(perms, dict):
        raise GateError("%s: `permissions` is not an object" % path)
    allow = perms.get("allow", [])
    if not isinstance(allow, list):
        raise GateError("%s: `permissions.allow` is not a list" % path)
    return doc, allow


def detect(root):
    """What the setup question needs: the rules, verbatim, and per scope the
    file's path, whether it exists, which rules it already carries and which it
    lacks, and an `error` when it could not be read."""
    out = {"rules": list(RULES)}
    for scope, path in paths(root).items():
        try:
            _doc, allow = _load(path)
            error = None
        except GateError as exc:
            allow, error = [], str(exc)
        out[scope] = {"path": path, "exists": os.path.exists(path), "error": error,
                      "present": [r for r in RULES if r in allow],
                      "missing": [r for r in RULES if r not in allow]}
    out["user"]["ignored"] = _ignored(FILES["user"], _base(root))
    return out


def errors(root, scope):
    """Why applying `scope` must write nothing, or []."""
    if not isinstance(scope, str) or scope not in ANSWERS:
        return ["claude_permissions must be one of team, user or skip, got %r" % (scope,)]
    if scope == "skip":
        return []
    try:
        _load(paths(root)[scope])
    except GateError as exc:
        return [str(exc)]
    return []


def apply(root, scope, dry_run=False):
    """Merge the missing rules into `permissions.allow` of the scope's file
    (created when absent, JSON with 2-space indent). Returns {"scope", "path",
    "added"}; `added` is empty, and nothing is written, when all are there."""
    problems = errors(root, scope)
    if problems or scope == "skip":
        if problems:
            raise GateError(problems[0])
        return {"scope": scope, "path": None, "added": []}
    path = paths(root)[scope]
    doc, allow = _load(path)
    added = [rule for rule in RULES if rule not in allow]
    if added and not dry_run:
        perms = doc.setdefault("permissions", {})
        perms["allow"] = list(allow) + added
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return {"scope": scope, "path": path, "added": added}
