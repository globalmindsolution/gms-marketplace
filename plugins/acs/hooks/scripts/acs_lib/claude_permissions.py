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

With either answer it also writes the Bash sandbox write rule for acs's state
folder -- `{"sandbox": {"filesystem": {"allowWrite": ["<abs main
checkout>/.acs/state-machine"]}}}` -- to the main checkout's
`.claude/settings.local.json`, never the team file (ADR-0136). A worktree
session's Bash sandbox writes only its working directory, $TMPDIR, added dirs
and `allowWrite` paths, and the state folder sits in the MAIN checkout, which
every worktree resolves to. Settings path rules anchor at the session's own
working directory, so the rule must be absolute -- which makes it
machine-specific, hence the local file.

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


#: Where the sandbox write rule lives inside a settings document.
SANDBOX_KEYS = ("sandbox", "filesystem", "allowWrite")


def sandbox_rule(root):
    """The absolute path the sandbox rule allows: the MAIN checkout's
    `.acs/state-machine`, the folder `default_state_root` derives from any
    worktree of the repo."""
    return os.path.join(_base(root), ".acs", "state-machine")


def ignore_entries(scope):
    """The ignore entries an answer needs: the user's local file is machine-
    specific, so it is ignored the way `.acs/settings.local.json` is -- and
    both answers write it, since the sandbox rule always goes there."""
    return (FILES["user"],) if scope in ("team", "user") else ()


def _ignored(rel, cwd):
    try:
        return subprocess.run(["git", "check-ignore", "-q", rel], cwd=cwd,
                              capture_output=True).returncode == 0
    except OSError:
        return False


def _nested_list(path, doc, keys):
    """The list at `keys` in `doc` ([] when absent); GateError when a level on
    the way is not what a merge needs."""
    node = doc
    for i, key in enumerate(keys):
        last = i == len(keys) - 1
        node = node.get(key, [] if last else {})
        if not isinstance(node, list if last else dict):
            raise GateError("%s: `%s` is not %s" % (path, ".".join(keys[:i + 1]),
                                                     "a list" if last else "an object"))
    return node


def _set_nested(doc, keys, value):
    node = doc
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    node[keys[-1]] = value


def _load(path):
    """The document of a settings file; {} when absent. GateError when it
    cannot be merged into without losing something."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        raise GateError("%s is not valid JSON (%s) -- fix or remove it, then re-run"
                        % (path, exc))
    if not isinstance(doc, dict):
        raise GateError("%s is not a JSON object" % path)
    _nested_list(path, doc, ("permissions", "allow"))
    _nested_list(path, doc, SANDBOX_KEYS)
    return doc


def detect(root):
    """What the setup question needs: the rules, verbatim, and per scope the
    file's path, whether it exists, which rules it already carries and which it
    lacks, and an `error` when it could not be read; and `sandbox_rule`, the
    state folder's absolute path, the local file it goes to and whether it is
    already there."""
    out = {"rules": list(RULES)}
    for scope, path in paths(root).items():
        try:
            allow, error = _nested_list(path, _load(path), ("permissions", "allow")), None
        except GateError as exc:
            allow, error = [], str(exc)
        out[scope] = {"path": path, "exists": os.path.exists(path), "error": error,
                      "present": [r for r in RULES if r in allow],
                      "missing": [r for r in RULES if r not in allow]}
    out["user"]["ignored"] = _ignored(FILES["user"], _base(root))
    rule, local = sandbox_rule(root), paths(root)["user"]
    try:
        present, error = rule in _nested_list(local, _load(local), SANDBOX_KEYS), None
    except GateError as exc:
        present, error = False, str(exc)
    out["sandbox_rule"] = {"path": rule, "file": local, "present": present, "error": error}
    return out


def errors(root, scope):
    """Why applying `scope` must write nothing, or []."""
    if not isinstance(scope, str) or scope not in ANSWERS:
        return ["claude_permissions must be one of team, user or skip, got %r" % (scope,)]
    if scope == "skip":
        return []
    try:
        for path in sorted({paths(root)[scope], paths(root)["user"]}):
            _load(path)
    except GateError as exc:
        return [str(exc)]
    return []


def _merge(path, keys, items, dry_run):
    """Append the `items` missing from the list at `keys` in `path`'s document;
    returns those added. Writes only when something was added."""
    doc = _load(path)
    current = _nested_list(path, doc, keys)
    added = [item for item in items if item not in current]
    if added and not dry_run:
        _set_nested(doc, keys, list(current) + added)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return added


def apply(root, scope, dry_run=False):
    """Merge the missing rules into `permissions.allow` of the scope's file and
    the sandbox rule into `sandbox.filesystem.allowWrite` of the main
    checkout's local file (each created when absent, JSON with 2-space indent).
    Returns {"scope", "path", "added", "sandbox": {"path", "rule", "added"}};
    an `added` is empty, and nothing is written for it, when all is there."""
    problems = errors(root, scope)
    if problems or scope == "skip":
        if problems:
            raise GateError(problems[0])
        return {"scope": scope, "path": None, "added": [], "sandbox": None}
    path, local, rule = paths(root)[scope], paths(root)["user"], sandbox_rule(root)
    added = _merge(path, ("permissions", "allow"), RULES, dry_run)
    sandbox_added = _merge(local, SANDBOX_KEYS, (rule,), dry_run)
    return {"scope": scope, "path": path, "added": added,
            "sandbox": {"path": local, "rule": rule, "added": sandbox_added}}
