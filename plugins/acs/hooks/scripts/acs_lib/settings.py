"""acs_lib.settings — extracted from acs_lib.py by MAR-522."""


import fnmatch
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
import claude_code_adapter as cc  # noqa: E402

from ._common import GateError, deep_merge, read_json
from .models import validate_models
from .repo import checkout_root, default_state_root, main_repo_root



BUILTIN_TEMPLATES = {"pr-default", "epic-default", "story-default", "task-default"}


#: The ticket id prefix when a repo sets none (ADR-0105): tickets are ACS-1,
#: ACS-2, ... A repo that wants its own sets `ticket_prefix` by hand. Mirrored
#: by templates/ci/check-conventions.py, which runs without the plugin.
DEFAULT_TICKET_PREFIX = "ACS"

DEFAULT_SETTINGS = {
    "ticket_prefix": DEFAULT_TICKET_PREFIX,
    "test_coverage_percent": 90,
    "merge_strategy": "squash",
    "suites": {},
    "workflow": {"advisories": True},
    "tracker": {"provider": "local"},
}

#: Keys an older acs read and this one ignores (ADR-0102): no setting locates a
#: document or the workspace. Still legal in a settings file -- unknown keys
#: are -- and named by `/acs:setup detect` so a stale one is not mistaken for a
#: live one.
RETIRED_SETTINGS_KEYS = (
    "workspace_path", "prd_path", "architecture_path", "requirements_path",
    "requirements_layout", "adr_path", "quality_path", "operations_path",
    "principles_path", "standards_path", "artifacts", "contracts_path",
    # ADR-0115 and the conventions removal: the model follows the repo's own
    # style, and the few fixed conventions live in acs_lib.conventions.
    "formats", "enforcement", "hook_gates",
)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def settings_files(cwd):
    """Candidate settings files, least -> most specific. settings.local.json is
    machine-specific and gitignored; a linked worktree may not have its own copy,
    so the main checkout's local settings are also consulted."""
    candidates = []
    user = os.path.join(os.path.expanduser("~"), ".acs", "settings.json")
    candidates.append(user)
    main_root = main_repo_root(cwd)
    top = checkout_root(cwd)
    roots = []
    for root in (main_root, top):
        if root and root not in roots:
            roots.append(root)
    for root in roots:
        candidates.append(os.path.join(root, ".acs", "settings.json"))
    for root in roots:
        candidates.append(os.path.join(root, ".acs", "settings.local.json"))
    return candidates


def load_settings(cwd):
    """Per-key merge across scopes: settings.local.json -> project settings.json -> user."""
    merged = dict(DEFAULT_SETTINGS)
    found = []
    for path in settings_files(cwd):
        data = read_json(path)
        if isinstance(data, dict):
            merged = deep_merge(merged, data)
            found.append(path)
    _normalize_e2e_into_suites(merged)
    return merged, found


def _normalize_e2e_into_suites(merged):
    """Upsert a configured e2e into suites['e2e'] (e2e wins on collision, non-fatally warned)."""
    e2e = merged.get("e2e")
    if not isinstance(e2e, dict) or not e2e:
        return
    suites = dict(merged.get("suites") or {})
    existing = suites.get("e2e")
    if isinstance(existing, dict) and existing.get("command") != e2e.get("command"):
        merged.setdefault("_settings_warnings", []).append(
            "settings.e2e and settings.suites.e2e are both configured with different commands; "
            "e2e (the deprecated alias) wins and overwrites suites.e2e at load time."
        )
    suites["e2e"] = e2e
    merged["suites"] = suites


def validate_settings(settings, cwd, require_workspace=True):
    """Shared baseline validation used by every pre-hook. Raises GateError.

    The workspace is always <main-checkout>/.acs/state-machine (ADR-0086). No
    setting locates it, and none locates a document either (ADR-0102): a skill
    finds the repo's docs the way any session does, through CLAUDE.md and the
    repo itself."""
    workspace = default_state_root(cwd) if require_workspace else None  # may raise GateError
    prefix = settings.get("ticket_prefix")
    if require_workspace:
        if not prefix or not re.fullmatch(r"[A-Z][A-Z0-9]*", str(prefix)):
            raise GateError(
                "ticket_prefix %r is invalid (must be an uppercase identifier, e.g. SHOP). "
                "Fix it in .acs/settings.json, or remove it to use the default %s."
                % (prefix, DEFAULT_TICKET_PREFIX)
            )
    coverage = settings.get("test_coverage_percent", 90)
    if not isinstance(coverage, (int, float)) or not (0 < coverage <= 100):
        raise GateError("test_coverage_percent must be a number in (0, 100]; got %r." % (coverage,))
    strategy = settings.get("merge_strategy", "squash")
    if strategy not in ("squash", "merge", "rebase"):
        raise GateError("merge_strategy must be one of squash|merge|rebase; got %r." % (strategy,))
    e2e = settings.get("e2e")
    if e2e is not None:
        if not isinstance(e2e, dict) or not isinstance(e2e.get("command"), str) or not e2e["command"].strip():
            raise GateError("e2e must be an object with a non-empty 'command' (plus optional setup/teardown/per_iteration).")
        for key in ("setup", "teardown"):
            if key in e2e and (not isinstance(e2e[key], str) or not e2e[key].strip()):
                raise GateError("e2e.%s must be a non-empty string when set." % key)
        if "per_iteration" in e2e and not isinstance(e2e["per_iteration"], bool):
            raise GateError("e2e.per_iteration must be a boolean.")
    suites = settings.get("suites", {})
    if not isinstance(suites, dict):
        raise GateError("suites must be an object mapping suite names to suite definitions; got %r." % (suites,))
    for name, suite in suites.items():
        if not isinstance(suite, dict) or not isinstance(suite.get("command"), str) or not suite["command"].strip():
            raise GateError("suites.%s must be an object with a non-empty 'command' (plus optional setup/teardown/per_iteration)." % name)
        for key in ("setup", "teardown"):
            if key in suite and (not isinstance(suite[key], str) or not suite[key].strip()):
                raise GateError("suites.%s.%s must be a non-empty string when set." % (name, key))
        if "per_iteration" in suite and not isinstance(suite["per_iteration"], bool):
            raise GateError("suites.%s.per_iteration must be a boolean." % name)
    validate_models(settings.get("models", {}))
    return workspace if require_workspace else None


def resolve_template(value, repo_root, plugin_root):
    """Built-in name -> plugin templates/; else <repo>/.acs/templates/<value>.md; else absolute path."""
    if value in BUILTIN_TEMPLATES:
        return os.path.join(plugin_root, "templates", "%s.md" % value)
    candidate = os.path.join(repo_root or "", ".acs", "templates", "%s.md" % value)
    if repo_root and os.path.isfile(candidate):
        return candidate
    if os.path.isabs(value) and os.path.isfile(value):
        return value
    return None
