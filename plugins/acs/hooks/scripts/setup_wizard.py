#!/usr/bin/env python3
"""setup_wizard.py — the deterministic half of /acs:setup (MAR-526).

setup/SKILL.md was 1,003 lines, most of them a recipe: four shell blocks to add
one `.gitignore` line, a heredoc to write a JSON dict, and three near-identical
"copy the workflow, chmod it" blocks. None of that is conversation. All of it
was being re-derived, in prose, on every setup run — the exact pattern ADR 0001
exists to prevent.

Setup configures conventions and the CI that enforces them, nothing else: the
ticket prefix, the branch/commit/PR formats, and the convention and tests
gates. Every other setting has a working default the user edits by hand, and no
setting locates a document or the workspace (ADR-0102).

Two commands:

  detect   Everything the conversation needs to know before it asks anything:
           which settings already exist and in which scope, what the git
           checkout looks like, what the toolchain has, which test commands are
           plausible, which CI installs are already in place, and which retired
           settings keys a settings file still carries. Reads only.

  apply    Everything the conversation decided, performed at once: the project
           settings, the ignore entries in both layers, the workspace
           create+probe, and the CI copies. Writes only what the answers ask
           for, and never a value equal to its built-in default.

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
import re
import shlex  # noqa: F401 -- used by setup_wizard_commands; part of the pre-split surface
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
    """The state root, resolved exactly as validate_settings does:
    `default_state_root`, always (no setting relocates it -- ADR-0102).
    Returned with the error rather than raising, so `detect` can report a
    repo layout acs cannot anchor to instead of crashing on it."""
    try:
        return lib.default_state_root(cwd), None
    except lib.GateError as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------

def scope_files(cwd, root=None):
    """The three settings scopes and what each currently holds.

    `root` is the directory apply will WRITE to (main_repo_root). Defaulting it
    to checkout_root made detect describe a different file from the one apply
    touched whenever the two differ -- i.e. in every linked worktree, which is
    how this repo runs its own pipeline."""
    root = root or lib.main_repo_root(cwd) or lib.checkout_root(cwd) or cwd
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


def default_branch(cwd):
    """The branch branch protection belongs on -- never simply the one checked
    out. `detect` used to report `git symbolic-ref HEAD` under this name, so
    setup run from a feature branch rendered a protection call for the feature
    branch. The remote's HEAD decides; failing that, a `main` or `master` that
    exists; failing that, None, and the skill asks rather than guesses."""
    ref = _git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd)
    if ref:
        return ref.split("/", 1)[1] if "/" in ref else ref
    for name in ("main", "master"):
        for candidate in ("refs/remotes/origin/%s" % name, "refs/heads/%s" % name):
            if _git(["rev-parse", "--verify", "--quiet", candidate], cwd):
                return name
    return None


def detect(cwd):
    # D2: detect roots on checkout_root while apply rooted on main_repo_root.
    # In a LINKED WORKTREE those differ, so apply wrote settings, .gitignore
    # and workflows into a checkout detect never showed -- and a
    # configured repo entered from a worktree read as a fresh init. Both now
    # report BOTH roots explicitly, and `settings_root` names the one apply
    # will actually write to, so the conversation and the writes agree.
    root = lib.checkout_root(cwd) or cwd
    settings_root = lib.main_repo_root(cwd) or root
    repo_id = lib.repo_partition_id(cwd)
    settings, sources = lib.load_settings(cwd)
    workspace, workspace_error = resolve_workspace(settings, cwd)
    return {
        # Computed, not hardcoded. It used to be a literal True on every path,
        # so `ok` meant "apply succeeded" for one command and nothing at all
        # for the other -- and SKILL.md's "No git repository, STOP" had no
        # field to read, since a non-repo directory still answered ok:true.
        "ok": bool(repo_id),
        "is_git_repo": bool(repo_id),
        "cwd": cwd,
        "checkout_root": root,
        "main_repo_root": lib.main_repo_root(cwd),
        "git_common_dir": _git(["rev-parse", "--git-common-dir"], cwd),
        "remote": _git(["remote", "get-url", "origin"], cwd),
        "repo_id": repo_id,
        "settings_root": settings_root,
        "in_linked_worktree": settings_root != root,
        "default_branch": default_branch(cwd),
        "current_branch": _git(["symbolic-ref", "--short", "HEAD"], cwd),
        "scopes": scope_files(cwd, settings_root),
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
        "retired_keys": retired_keys(scope_files(cwd, settings_root)),
    }


def retired_keys(scopes):
    """Retired settings keys a settings file still carries, per file.

    They are ignored (unknown keys are legal), which is exactly why they need
    naming: a `workspace_path` that pointed outside the repo means state the
    workspace no longer reads (ADR-0102)."""
    out = []
    for name in ("user", "project", "local"):
        data = lib.read_json(scopes[name]["path"])
        found = [k for k in lib.RETIRED_SETTINGS_KEYS
                 if isinstance(data, dict) and k in data]
        if found:
            out.append({"scope": name, "path": scopes[name]["path"], "keys": found})
    return out


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
        self.errors = []

    def note(self, changed, message):
        (self.changed if changed else self.unchanged).append(message)
        return changed

    def warn(self, message):
        self.warnings.append(message)

    def fail(self, message):
        """Something the wizard REFUSED to do. Distinct from a warning: it
        makes the whole run `ok: false`, because the skill's contract is to
        stop on a non-empty `errors`."""
        self.errors.append(message)

    def as_dict(self):
        return {"changed": self.changed, "unchanged": self.unchanged,
                "warnings": self.warnings}


class UnreadableSettings(Exception):
    """The file exists but is not readable JSON, so it cannot be merged into."""


def merge_json_file(path, updates, dry_run=False, remove=()):
    """Read-update-write so a re-run preserves untouched and unknown keys.

    Nested objects are merged one level down rather than replaced, because a
    run that sets `tracker.provider` must not drop the `tracker.github` block a
    previous run wrote.

    A file that EXISTS but does not parse raises rather than merging. read_json
    returns None for both "absent" and "corrupt", and collapsing that to {}
    turned the merge into a silent full overwrite: one stray comma in
    .acs/settings.json and every other key -- ticket_prefix, coverage target,
    the whole tracker block -- was destroyed, with no backup and ok:true. The
    caller has to decide, and `detect` already computes `readable: false` for
    exactly this.

    `remove` lists key paths (tuples) to delete: an answer equal to its default
    is not written, and when an earlier run wrote it, keeping the stale value
    would silently override the choice just made. An object emptied by a
    removal is dropped with it."""
    current = lib.read_json(path)
    if current is None and os.path.exists(path):
        raise UnreadableSettings(path)
    current = dict(current) if isinstance(current, dict) else {}
    merged = dict(current)
    for key, value in (updates or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    for key_path in remove:
        _delete_path(merged, key_path)
    if merged == current and os.path.exists(path):
        return False, merged
    if not dry_run:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
            fh.write("\n")
    return True, merged


def _delete_path(doc, key_path):
    """Delete doc[k1][k2]... when present; drop parents it leaves empty."""
    head, rest = key_path[0], tuple(key_path[1:])
    if head not in doc:
        return
    if rest:
        if isinstance(doc[head], dict):
            doc[head] = dict(doc[head])
            _delete_path(doc[head], rest)
            if not doc[head]:
                del doc[head]
        return
    del doc[head]


def split_defaults(values, defaults=None, prefix=()):
    """(to_write, defaulted): `values` without anything equal to its built-in
    default, and the key paths that were. Nested objects are compared key by
    key, so `{"formats": {"branch_name": <default>, "pr_title": "X"}}` writes
    only `pr_title`. The defaults are DEFAULT_SETTINGS plus the enforcement
    defaults, i.e. what every reader resolves an absent key to."""
    if defaults is None:
        defaults = dict(lib.DEFAULT_SETTINGS)
        defaults["enforcement"] = dict(lib.ENFORCEMENT_DEFAULTS)
    to_write, defaulted = {}, []
    for key, value in values.items():
        path = prefix + (key,)
        if key not in defaults:
            to_write[key] = value
        elif isinstance(value, dict) and isinstance(defaults[key], dict):
            sub, sub_defaulted = split_defaults(value, defaults[key], path)
            defaulted.extend(sub_defaulted)
            if sub:
                to_write[key] = sub
        elif value == defaults[key]:
            defaulted.append(path)
        else:
            to_write[key] = value
    return to_write, defaulted


def _same_ignore_rule(a, b):
    """Do these two ignore lines mean the same thing?

    `/.acs/state-machine/` and `.acs/state-machine/` are the same rule written
    two ways, and comparing the literals treated them as different -- so a file
    already carrying the rooted form got a second line for the same entry on
    every re-run, while .gitignore (guarded by git itself) stayed correct."""
    return a.strip().strip("/") == b.strip().strip("/")


def append_line_once(path, line, dry_run=False):
    """Append `line` unless the file already carries an EQUIVALENT rule,
    keeping the file newline-terminated so the entry cannot glue onto the
    last one."""
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            existing = fh.read()
    if any(_same_ignore_rule(line, present) for present in existing.splitlines()):
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
        # to commit an ignore-line change is still covered. It is NOT gated on
        # is_ignored(): that would skip exactly the case this layer exists for.
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


class MissingTemplate(Exception):
    """The template to install is not in the plugin. Distinct from "already
    identical", which _copy also reports as "nothing to do"."""


def apply_ci(root, installs, changes, dry_run=False):
    """Copy the shipped templates verbatim. Regenerated on every re-run, so
    changing a format later and re-running refreshes them.

    Returns (staged, installed): `installed` names only the CI installs whose
    every file actually landed. A missing template used to be filed under
    `unchanged` -- documented as "already the way it asked for" -- so a
    workflow that was never installed was reported as present AND its
    required-check context was still handed to Step 4, which would then wire a
    required status check for a workflow that does not exist, blocking every
    future PR on the repo."""
    templates = os.path.join(plugin_templates(), "ci")
    staged, installed = [], []
    for name in installs or ():
        if name not in CI_INSTALLS:
            changes.warn("unknown CI install %r — expected one of %s"
                         % (name, ", ".join(sorted(CI_INSTALLS))))
            continue
        files, workflow, _context = CI_INSTALLS[name]
        ok = True
        for filename in files:
            src = os.path.join(templates, filename)
            dst = os.path.join(root, ".acs", "ci", filename)
            try:
                changes.note(_copy(src, dst, executable=True, dry_run=dry_run),
                             "installed .acs/ci/%s" % filename)
            except MissingTemplate:
                changes.fail("the %s template %s is missing from the plugin; "
                             "nothing was installed for it" % (name, filename))
                ok = False
                continue
            staged.append(os.path.join(".acs", "ci", filename))
        src = os.path.join(templates, workflow)
        dst = os.path.join(root, ".github", "workflows", workflow)
        try:
            changes.note(_copy(src, dst, dry_run=dry_run),
                         "installed .github/workflows/%s" % workflow)
        except MissingTemplate:
            changes.fail("the %s workflow %s is missing from the plugin; "
                         "nothing was installed for it" % (name, workflow))
            ok = False
        else:
            staged.append(os.path.join(".github", "workflows", workflow))
        if ok:
            installed.append(name)
    return staged, installed


def _copy(src, dst, executable=False, dry_run=False):
    if not os.path.exists(src):
        raise MissingTemplate(src)
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


def refusals(cwd, settings_path, raw_settings, values, defaulted, installs):
    """Why apply must write NOTHING, or [] when it may go ahead.

    Checked before the first write, because each of these used to be found
    after it: an invalid format was written to .acs/settings.json and only then
    validated, so the run reported ok:false and left behind a file that made
    every other acs skill refuse to start. And a tests or e2e gate was
    installed with no command for it to run, reported ok:true, and had its
    required-check context handed to branch protection -- a check that then
    fails on every PR. The CI runners read only the committed project file, so
    the gate check reads what that file WILL hold, not the merged scopes."""
    errors = []
    resolved, _sources = lib.load_settings(cwd)
    candidate = lib.deep_merge(resolved, raw_settings)
    prefix = candidate.get("ticket_prefix")
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*", prefix):
        errors.append("ticket_prefix %r is invalid (must be an uppercase identifier, "
                      "e.g. SHOP)." % (prefix,))
    try:
        lib.validate_settings(candidate, cwd, require_workspace=False)
    except lib.GateError as exc:
        errors.append(str(exc))
    try:
        _wrote, project = merge_json_file(settings_path, values, dry_run=True, remove=defaulted)
    except UnreadableSettings:
        # Refusing is the whole point: a settings file we cannot parse is one
        # we cannot merge into, and overwriting it destroys every key the
        # wizard did not set.
        return errors + ["%s exists but is not valid JSON. The wizard will not "
                         "overwrite it -- fix or remove it, then re-run." % settings_path]
    command = (project.get("tests") or {}).get("command") if isinstance(project.get("tests"), dict) else None
    if "tests" in installs and not (isinstance(command, str) and command.strip()):
        errors.append("the tests gate needs tests.command in .acs/settings.json -- the "
                      "command that runs the suite and fails below $ACS_COVERAGE. CI reads "
                      "only that file, so without it the gate fails on every PR.")
    suites = project.get("suites") if isinstance(project.get("suites"), dict) else {}
    e2e = suites.get("e2e") or project.get("e2e")
    if "e2e" in installs and not (isinstance(e2e, dict) and e2e.get("command")):
        errors.append("the e2e gate needs an e2e suite (suites.e2e.command) in "
                      ".acs/settings.json. CI reads only that file, so without it the "
                      "gate fails on every PR.")
    return errors


def apply(cwd, answers, dry_run=False):
    root = lib.main_repo_root(cwd) or lib.checkout_root(cwd) or cwd
    changes = Changes()

    # Conventions are the team's, so they go to the committed project file.
    settings_path = os.path.join(root, ".acs", "settings.json")
    raw_settings = dict(answers.get("settings") or {})
    values, defaulted = split_defaults(raw_settings)
    refused = refusals(cwd, settings_path, raw_settings, values, defaulted,
                       list(answers.get("ci") or ()))
    if refused:
        out = changes.as_dict()
        out.update({"ok": False, "dry_run": dry_run, "settings_path": settings_path,
                    "workspace": None, "defaulted": [], "stage_for_commit": [],
                    "errors": refused + ["Nothing was written."],
                    "required_check_contexts": []})
        return out

    if values or (defaulted and os.path.exists(settings_path)):
        wrote, _merged = merge_json_file(settings_path, values, dry_run=dry_run,
                                         remove=defaulted)
        changes.note(wrote, "wrote %s" % settings_path)

    apply_ignores(root, cwd, changes, dry_run=dry_run)
    workspace = apply_workspace(cwd, changes, dry_run=dry_run)
    staged, installed_ci = apply_ci(root, answers.get("ci") or (), changes,
                                    dry_run=dry_run)

    settings, _sources = lib.load_settings(cwd)
    errors = list(changes.errors)
    try:
        lib.validate_settings(settings, cwd, require_workspace=False)
    except lib.GateError as exc:
        errors.append(str(exc))

    out = changes.as_dict()
    out.update({"ok": not errors, "dry_run": dry_run,
                "settings_path": settings_path, "workspace": workspace,
                "defaulted": [".".join(p) for p in defaulted],
                "stage_for_commit": staged, "errors": errors,
                # Only the installs that ACTUALLY landed: a required check for
                # a workflow that was never installed blocks every future PR.
                "required_check_contexts": [CI_INSTALLS[n][2] for n in installed_ci
                                            if n in CI_INSTALLS]})
    return out


from setup_wizard_commands import (PIPELINE_ORDER, SETUP_LABELS,  # noqa: E402,F401
                                   delivery_steps, render_labels,
                                   render_next_steps, render_protect)


#: The answers document's shape. Not a JSON Schema file, because this is the
#: only consumer and the whole point is a readable refusal -- but the same
#: contract its ten sibling artifacts get from plugins/acs/schemas/.
ANSWER_TYPES = {
    "settings": (dict, "an object of setting keys"),
    "ci": (list, "a list of any of %s" % ", ".join(sorted(CI_INSTALLS))),
}


def validate_answers(answers):
    """Errors in the answers document; [] when it is usable.

    Only the parse-to-a-dict check existed before, so `{"ci": "conventions"}`
    -- a string where a list is meant, the likeliest mistake for an agent
    hand-writing this from the SKILL.md example -- iterated the string CHARACTER
    BY CHARACTER, warned nine times, installed nothing, and still returned
    ok:true with errors:[]. Per the skill's contract that is a success report
    for a CI gate that was never installed."""
    if not isinstance(answers, dict):
        return ["the answers document must be a JSON object"]
    errors = []
    for key, value in answers.items():
        if key not in ANSWER_TYPES:
            continue  # unknown keys are ignored, as they always were
        expected, described = ANSWER_TYPES[key]
        if isinstance(value, expected) and not (expected is not bool
                                                and isinstance(value, bool)):
            continue
        errors.append("%r must be %s, got %s"
                      % (key, described, type(value).__name__))
    return errors


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
    pro = sub.add_parser("commands", help="the one-time gh calls, rendered and quoted")
    pro.add_argument("--cwd", default=None)
    pro.add_argument("--slug", default=None, help="owner/repo")
    pro.add_argument("--branch", default=None, help="the branch to protect")
    pro.add_argument("--context", action="append", default=[],
                     help="a required status-check context (repeatable)")
    args = parser.parse_args(argv)

    if not args.cmd:
        parser.print_help(sys.stderr)
        sys.exit(2)
    cwd = args.cwd or os.getcwd()

    if args.cmd == "commands":
        slug = args.slug or "<owner>/<repo>"
        branch = args.branch or "<default-branch>"
        root = lib.main_repo_root(cwd) or cwd
        tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True,
                                 text=True).stdout.split()
        greenfield = not [f for f in tracked
                          if not f.startswith(("docs/", ".acs/", ".github/"))
                          and not f.endswith((".md", ".txt"))]
        print(json.dumps({
            "ok": True,
            "protect": render_protect(slug, branch, args.context),
            "labels": render_labels(),
            "next_steps": render_next_steps(greenfield, lib.checkout_root(cwd)),
            "ready": bool(args.slug and args.branch and args.context),
        }, indent=2))
        sys.exit(0)

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
    answer_errors = validate_answers(answers)
    if answer_errors:
        sys.stderr.write("acs setup apply: %s\n" % "; ".join(answer_errors))
        sys.exit(2)

    # D5: seven write groups with no journal, and the result was printed only
    # AFTER apply returned -- so a raise mid-way left the earlier mutations in
    # place and produced EMPTY stdout with exit 1, which the skill's "read the
    # result, errors non-empty means stop" cannot parse and which is
    # indistinguishable from the documented settings-invalid exit. Now the
    # partial record is always emitted, and it names what did land.
    try:
        out = apply(cwd, answers, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001 - the report is the deliverable
        print(json.dumps({
            "ok": False, "dry_run": args.dry_run,
            "errors": ["the wizard stopped part-way: %r. The changes listed under "
                       "`changed` were already made; re-run once the cause is "
                       "fixed -- every step is idempotent." % exc],
            "changed": [], "unchanged": [], "warnings": [],
            "stage_for_commit": [], "required_check_contexts": [],
        }, indent=2, sort_keys=True))
        sys.exit(1)
    print(json.dumps(out, indent=2, sort_keys=True))
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
