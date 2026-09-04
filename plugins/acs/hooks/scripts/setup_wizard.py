#!/usr/bin/env python3
"""setup_wizard.py — the deterministic half of /acs:setup (MAR-526).

setup/SKILL.md was 1,003 lines, most of them a recipe: four shell blocks to add
one `.gitignore` line, a heredoc to write a JSON dict, three near-identical
"copy the workflow, chmod it" blocks, and a Python heredoc to upsert a managed
`CLAUDE.md` block. None of that is conversation. All of it was being re-derived,
in prose, on every setup run — the exact pattern ADR 0001 exists to prevent.

Two commands:

  detect   Everything the conversation needs to know before it asks anything:
           which settings already exist and in which scope, what the git
           checkout looks like, what the toolchain has, which test commands are
           plausible, and which of the optional installs are already in place.
           Reads only.

  apply    Everything the conversation decided, performed at once: the settings
           split across scopes, the ignore entries in both layers, the workspace
           create+probe, the CI copies, the CLAUDE.md managed block, and the
           status-line settings. Writes only what the answers ask for.

**Idempotence is the contract, not a nicety.** /acs:setup is re-run whenever a
format changes, and a repo initialised by an older acs is expected to be
repaired by a re-run. So every write here is a read-update-write merge, every
ignore entry is added only when `git check-ignore` says it is missing, and every
copy is a refresh. `apply` reports what it CHANGED versus what was already the
way it asked for, so a re-run is visibly a no-op rather than silently one.

Usage:
  setup_wizard.py detect [--cwd DIR]
  setup_wizard.py apply --answers FILE [--cwd DIR] [--dry-run]

Reachable as `acs.py setup detect` / `acs.py setup apply`. Stdlib-only.
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402

#: The ignore entries every repo gets, in both layers. Narrow directory entries
#: on purpose: a broad `.acs/` glob would swallow settings.json and .acs/ci/,
#: which CI has to read.
IGNORE_ENTRIES = (".acs/settings.local.json", ".acs/state-machine/")

#: Paths a broad ignore rule must NOT swallow. Warned about, never fixed for
#: the user: a `!.acs/` negation is their configuration to decide.
MUST_STAY_TRACKED = (".acs/settings.json", ".acs/ci/check-conventions.py")

#: install name -> (files copied into .acs/ci/, workflow copied into
#: .github/workflows/, the required-status-check context the gate uses).
CI_INSTALLS = {
    "conventions": (("check-conventions.py", "commit-msg", "pre-push", "install-hooks.sh"),
                    "acs-conventions.yml", "Branch / PR / commit conventions"),
    "tests": (("run-tests.py",), "acs-tests.yml", "Tests & coverage"),
    "e2e": (("run-e2e.py",), "acs-e2e.yml", "E2E suite"),
}

#: Keys that are machine-specific and therefore always land in
#: settings.local.json, whatever scope the user chose for the rest.
LOCAL_ONLY_KEYS = ("workspace_path",)

#: The two Claude Code status-line keys, and the script each points at.
STATUS_LINES = {"statusLine": "statusline.py",
                "subagentStatusLine": "subagent-statusline.py"}

#: Ordered probes for a plausible test command: (marker file, command).
TEST_COMMAND_CANDIDATES = (
    ("pyproject.toml", "python3 -m pytest -q"),
    ("setup.py", "python3 -m pytest -q"),
    ("tests", "python3 -m unittest discover -s tests"),
    ("package.json", "npm test"),
    ("go.mod", "go test ./..."),
    ("Cargo.toml", "cargo test"),
)


def _git(args, cwd):
    try:
        proc = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)
    except OSError:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def is_ignored(path, cwd):
    """`git check-ignore` on `path`, EXACTLY as written.

    The trailing slash matters and must not be stripped: a directory-only rule
    (`.acs/state-machine/`) does not match a bare `.acs/state-machine` that does
    not yet exist on disk, so probing without the slash reports a correctly
    ignored entry as missing and warns about a rule that is fine."""
    try:
        proc = subprocess.run(["git", "check-ignore", "-q", path],
                              cwd=cwd, capture_output=True, text=True)
    except OSError:
        return False
    return proc.returncode == 0


def plugin_templates():
    return os.path.join(lib.plugin_root(), "templates")


def resolve_workspace(settings, cwd):
    """The state root, resolved exactly as validate_settings does — an explicit
    `workspace_path` (expanded), else `default_state_root`.

    `validate_settings(..., require_workspace=False)` returns the RAW key, which
    is None on the common path where the repo takes the in-repo default, so what
    setup creates has to be resolved here or it would not be what every later
    run reads."""
    explicit = (settings or {}).get("workspace_path")
    if explicit:
        return os.path.abspath(os.path.expanduser(str(explicit))), None
    try:
        return lib.default_state_root(cwd), None
    except lib.GateError as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------

def scope_files(cwd):
    """The three settings scopes and what each currently holds."""
    root = lib.checkout_root(cwd) or cwd
    scopes = {
        "user": os.path.expanduser(os.path.join("~", ".acs", "settings.json")),
        "project": os.path.join(root, ".acs", "settings.json"),
        "local": os.path.join(root, ".acs", "settings.local.json"),
    }
    out = {}
    for name, path in scopes.items():
        data = lib.read_json(path)
        out[name] = {"path": path, "exists": os.path.exists(path),
                     "keys": sorted(data) if isinstance(data, dict) else [],
                     "readable": isinstance(data, dict) or not os.path.exists(path)}
    return out


def test_command_candidates(root):
    seen, out = set(), []
    for marker, command in TEST_COMMAND_CANDIDATES:
        if os.path.exists(os.path.join(root, marker)) and command not in seen:
            seen.add(command)
            out.append({"marker": marker, "command": command})
    return out


def installed_ci(root):
    out = {}
    for name, (files, workflow, context) in CI_INSTALLS.items():
        out[name] = {
            "workflow": os.path.exists(os.path.join(root, ".github", "workflows", workflow)),
            "files": {f: os.path.exists(os.path.join(root, ".acs", "ci", f)) for f in files},
            "required_check_context": context,
        }
    return out


def claude_md_state(root):
    path = os.path.join(root, "CLAUDE.md")
    if not os.path.exists(path):
        return {"path": path, "exists": False, "managed_block": False, "malformed": False}
    with open(path, encoding="utf-8") as fh:
        body = fh.read()
    return {"path": path, "exists": True,
            "managed_block": lib.ACS_BLOCK_BEGIN in body,
            "malformed": bool(lib.managed_block_is_malformed(body))}


def status_line_state():
    out = {}
    for scope, path in (("user", os.path.expanduser("~/.claude/settings.json")),
                        ("project", os.path.join(os.getcwd(), ".claude", "settings.json"))):
        data = lib.read_json(path)
        out[scope] = {"path": path,
                      "set": {key: bool(isinstance(data, dict) and data.get(key))
                              for key in STATUS_LINES}}
    return out


def detect(cwd):
    root = lib.checkout_root(cwd) or cwd
    settings, sources = lib.load_settings(cwd)
    workspace, workspace_error = resolve_workspace(settings, cwd)
    return {
        "ok": True,
        "cwd": cwd,
        "checkout_root": root,
        "main_repo_root": lib.main_repo_root(cwd),
        "git_common_dir": _git(["rev-parse", "--git-common-dir"], cwd),
        "remote": _git(["remote", "get-url", "origin"], cwd),
        "repo_id": lib.repo_partition_id(cwd),
        "default_branch": _git(["symbolic-ref", "--short", "HEAD"], cwd),
        "scopes": scope_files(cwd),
        "settings_sources": sources,
        "merged_settings": settings,
        "workspace": workspace,
        "workspace_error": workspace_error,
        "ignored": {entry: is_ignored(entry, root) for entry in IGNORE_ENTRIES},
        "swallowed_by_a_broad_rule": [p for p in MUST_STAY_TRACKED if is_ignored(p, root)],
        "toolchain": lib.check_toolchain(settings),
        "missing_tools": lib.missing_tools(settings),
        "test_command_candidates": test_command_candidates(root),
        "ci": installed_ci(root),
        "claude_md": claude_md_state(lib.main_repo_root(cwd) or root),
        "status_line": status_line_state(),
    }


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

class Changes(object):
    """What apply did, split into what CHANGED and what was already so.

    The split is the whole point: /acs:setup is re-run routinely, and a re-run
    that reports nothing changed is how idempotence is observed rather than
    asserted."""

    def __init__(self):
        self.changed = []
        self.unchanged = []
        self.warnings = []

    def note(self, changed, message):
        (self.changed if changed else self.unchanged).append(message)
        return changed

    def warn(self, message):
        self.warnings.append(message)

    def as_dict(self):
        return {"changed": self.changed, "unchanged": self.unchanged,
                "warnings": self.warnings}


def merge_json_file(path, updates, dry_run=False):
    """Read-update-write so a re-run preserves untouched and unknown keys.

    Nested objects are merged one level down rather than replaced, because a
    run that sets `tracker.provider` must not drop the `tracker.github` block a
    previous run wrote."""
    current = lib.read_json(path)
    current = dict(current) if isinstance(current, dict) else {}
    merged = dict(current)
    for key, value in (updates or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    if merged == current and os.path.exists(path):
        return False, merged
    if not dry_run:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
            fh.write("\n")
    return True, merged


def append_line_once(path, line, dry_run=False):
    """Append `line` unless the file already carries it, keeping the file
    newline-terminated so the entry cannot glue onto the last one."""
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            existing = fh.read()
    if line in existing.splitlines():
        return False
    if dry_run:
        return True
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(line + "\n")
    return True


def apply_ignores(root, cwd, changes, dry_run=False):
    """Both layers, on every run — fresh or re-run.

    A repo first initialised by an older acs may carry `settings.local.json`
    with no ignore rule, and this is the only step that retro-fixes it.
    `git check-ignore` decides, not a grep, so an existing broader rule already
    counts and no duplicate line is appended."""
    gitignore = os.path.join(root, ".gitignore")
    common = _git(["rev-parse", "--git-common-dir"], cwd) or os.path.join(root, ".git")
    if not os.path.isabs(common):
        common = os.path.join(root, common)
    exclude = os.path.join(common, "info", "exclude")

    for entry in IGNORE_ENTRIES:
        if is_ignored(entry, root):
            changes.note(False, "%s already ignored" % entry)
        else:
            changes.note(append_line_once(gitignore, entry, dry_run),
                         "gitignored %s" % entry)
        # The untracked layer, so a linked worktree or a repo that prefers not
        # to commit an ignore-line change is still covered.
        changes.note(append_line_once(exclude, entry, dry_run),
                     "%s excluded in %s" % (entry, exclude))

    for entry in IGNORE_ENTRIES:
        if not dry_run and not is_ignored(entry, root):
            changes.warn("%s is still not ignored by git — check for a conflicting "
                         "!.acs/ negation rule" % entry)
    for path in MUST_STAY_TRACKED:
        if is_ignored(path, root):
            changes.warn("%s is gitignored — add '!.acs/' or narrow the rule, or CI "
                         "cannot read it" % path)


def apply_ci(root, installs, changes, dry_run=False):
    """Copy the shipped templates verbatim. Regenerated on every re-run, so
    changing a format later and re-running refreshes them."""
    templates = os.path.join(plugin_templates(), "ci")
    staged = []
    for name in installs or ():
        if name not in CI_INSTALLS:
            changes.warn("unknown CI install %r — expected one of %s"
                         % (name, ", ".join(sorted(CI_INSTALLS))))
            continue
        files, workflow, _context = CI_INSTALLS[name]
        for filename in files:
            src = os.path.join(templates, filename)
            dst = os.path.join(root, ".acs", "ci", filename)
            changes.note(_copy(src, dst, executable=True, dry_run=dry_run),
                         "installed .acs/ci/%s" % filename)
            staged.append(os.path.join(".acs", "ci", filename))
        src = os.path.join(templates, workflow)
        dst = os.path.join(root, ".github", "workflows", workflow)
        changes.note(_copy(src, dst, dry_run=dry_run),
                     "installed .github/workflows/%s" % workflow)
        staged.append(os.path.join(".github", "workflows", workflow))
    return staged


def _copy(src, dst, executable=False, dry_run=False):
    if not os.path.exists(src):
        return False
    same = False
    if os.path.exists(dst):
        with open(src, "rb") as a, open(dst, "rb") as b:
            same = a.read() == b.read()
    if same:
        return False
    if dry_run:
        return True
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    if executable:
        os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def apply_claude_md(root, settings, changes, dry_run=False):
    """Upsert the marker-delimited managed block.

    Marker-delimited so a re-run replaces only that span and never touches the
    surrounding CLAUDE.md the user owns; self-healing, because an earlier buggy
    run may have left doubled or orphaned markers."""
    template = os.path.join(plugin_templates(), "CLAUDE.acs.md")
    if not os.path.exists(template):
        changes.warn("no CLAUDE.acs.md template at %s" % template)
        return
    with open(template, encoding="utf-8") as fh:
        body = lib.managed_body_from_template(
            fh.read(), (settings or {}).get("ticket_prefix", ""),
            lib.enforcement_value(settings, "exempt_label") or "acs-exempt")
    path = os.path.join(root, "CLAUDE.md")
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            existing = fh.read()
    had_markers = lib.ACS_BLOCK_BEGIN in existing or lib.ACS_BLOCK_END in existing
    repaired = had_markers and lib.managed_block_is_malformed(existing)
    result = lib.upsert_managed_block(existing, body)
    if result.count(lib.ACS_BLOCK_BEGIN) != 1 or result.count(lib.ACS_BLOCK_END) != 1:
        changes.warn("the acs-managed CLAUDE.md block did not resolve to exactly one "
                     "marker pair; left the file unchanged")
        return
    if result == existing:
        changes.note(False, "CLAUDE.md's acs-managed block is already current")
        return
    if not dry_run:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(result)
    changes.note(True, "repaired a malformed acs-managed CLAUDE.md block" if repaired
                 else "wrote CLAUDE.md's acs-managed block")


def apply_status_line(root, request, changes, dry_run=False):
    """Write the user's Claude Code status-line settings — never over an
    existing value.

    `statusLine` is the USER's setting: an existing one is shown, not replaced,
    because acs is a guest in that file."""
    scope = (request or {}).get("scope", "user")
    keys = [k for k in STATUS_LINES if (request or {}).get(k)]
    if not keys:
        return
    path = (os.path.expanduser("~/.claude/settings.json") if scope == "user"
            else os.path.join(root, ".claude", "settings.json"))
    current = lib.read_json(path)
    current = current if isinstance(current, dict) else {}
    scripts = os.path.join(lib.plugin_root(), "hooks", "scripts")
    updates = {}
    for key in keys:
        if current.get(key):
            changes.note(False, "%s is already set in %s; left as it is" % (key, path))
            continue
        updates[key] = {"type": "command",
                        "command": "python3 %s" % os.path.join(scripts, STATUS_LINES[key])}
    if not updates:
        return
    wrote, _merged = merge_json_file(path, updates, dry_run=dry_run)
    changes.note(wrote, "set %s in %s" % (", ".join(sorted(updates)), path))


def apply_workspace(cwd, changes, dry_run=False):
    """Create and probe the state root, resolved exactly as validate_settings
    does — so what setup creates is what every later run reads."""
    settings, _sources = lib.load_settings(cwd)
    workspace, error = resolve_workspace(settings, cwd)
    if error:
        changes.warn("could not resolve the workspace: %s" % error)
        return None
    repo_id = lib.repo_partition_id(cwd)
    if not workspace or not repo_id:
        changes.warn("no workspace or repo identity to create")
        return workspace
    target = lib.repo_dir(workspace, repo_id)
    if os.path.isdir(target):
        changes.note(False, "workspace partition already at %s" % target)
    elif not dry_run:
        os.makedirs(target, exist_ok=True)
        changes.note(True, "created the workspace partition at %s" % target)
    else:
        changes.note(True, "would create the workspace partition at %s" % target)
    if not dry_run and not os.access(target, os.W_OK):
        changes.warn("%s is not writable" % target)
    return workspace


def apply(cwd, answers, dry_run=False):
    root = lib.main_repo_root(cwd) or lib.checkout_root(cwd) or cwd
    changes = Changes()

    scope = answers.get("scope", "project")
    values = dict(answers.get("settings") or {})
    local = {k: values.pop(k) for k in LOCAL_ONLY_KEYS if k in values}
    if answers.get("workspace_path"):
        local["workspace_path"] = answers["workspace_path"]

    scope_path = (os.path.expanduser(os.path.join("~", ".acs", "settings.json"))
                  if scope == "user" else os.path.join(root, ".acs", "settings.json"))
    if values:
        wrote, _merged = merge_json_file(scope_path, values, dry_run=dry_run)
        changes.note(wrote, "wrote %s" % scope_path)
    if local:
        local_path = os.path.join(root, ".acs", "settings.local.json")
        wrote, _merged = merge_json_file(local_path, local, dry_run=dry_run)
        changes.note(wrote, "wrote %s" % local_path)

    apply_ignores(root, cwd, changes, dry_run=dry_run)
    workspace = apply_workspace(cwd, changes, dry_run=dry_run)
    staged = apply_ci(root, answers.get("ci") or (), changes, dry_run=dry_run)

    settings, _sources = lib.load_settings(cwd)
    if answers.get("claude_md"):
        apply_claude_md(root, settings, changes, dry_run=dry_run)
    apply_status_line(root, answers.get("status_line"), changes, dry_run=dry_run)

    errors = []
    try:
        lib.validate_settings(settings, cwd, require_workspace=False)
    except lib.GateError as exc:
        errors.append(str(exc))

    out = changes.as_dict()
    out.update({"ok": not errors, "dry_run": dry_run, "scope": scope,
                "settings_path": scope_path, "workspace": workspace,
                "stage_for_commit": staged, "errors": errors,
                "required_check_contexts": [CI_INSTALLS[n][2]
                                            for n in (answers.get("ci") or ())
                                            if n in CI_INSTALLS]})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="setup_wizard.py",
                                     description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd")
    det = sub.add_parser("detect", help="everything the conversation needs, read-only")
    det.add_argument("--cwd", default=None)
    app = sub.add_parser("apply", help="everything the conversation decided, at once")
    app.add_argument("--cwd", default=None)
    app.add_argument("--answers", required=True, metavar="FILE",
                     help="the answers document ('-' reads stdin)")
    app.add_argument("--dry-run", dest="dry_run", action="store_true",
                     help="report what would change and write nothing")
    args = parser.parse_args(argv)

    if not args.cmd:
        parser.print_help(sys.stderr)
        sys.exit(2)
    cwd = args.cwd or os.getcwd()

    if args.cmd == "detect":
        print(json.dumps(detect(cwd), indent=2, sort_keys=True))
        sys.exit(0)

    raw = sys.stdin.read() if args.answers == "-" else None
    if raw is None:
        answers = lib.read_json(args.answers)
        if not isinstance(answers, dict):
            sys.stderr.write("acs setup apply: %s is missing or not a JSON object\n"
                             % args.answers)
            sys.exit(2)
    else:
        try:
            answers = json.loads(raw)
        except json.JSONDecodeError as exc:
            sys.stderr.write("acs setup apply: invalid JSON on stdin: %s\n" % exc)
            sys.exit(2)
    out = apply(cwd, answers, dry_run=args.dry_run)
    print(json.dumps(out, indent=2, sort_keys=True))
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
