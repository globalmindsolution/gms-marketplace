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
from .design_types import defaults as design_defaults, validate_design
from .migrate_settings import legacy_problems
from .repo import checkout_root, default_state_root, main_repo_root



BUILTIN_TEMPLATES = {"pr-default", "epic-default", "story-default", "task-default"}


#: The ticket id prefix when a repo sets none (ADR-0105): tickets are ACS-1,
#: ACS-2, ... A repo that wants its own sets `ticket_prefix` by hand. Mirrored
#: by templates/ci/check-conventions.py, which runs without the plugin.
DEFAULT_TICKET_PREFIX = "ACS"

DEFAULT_SETTINGS = {
    "ticket_prefix": DEFAULT_TICKET_PREFIX,
    "merge_strategy": "squash",
    "tests": {"coverage": 90},
    "workflow": {"advisories": True},
    "tracker": {"provider": "local"},
    # Which HLD/LLD documents the Design skills write (ADR-0120); chosen at /acs:setup.
    "design": design_defaults(),
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
    return merged, found


def coverage_target(settings):
    """The coverage target the /code cycle and the CI tests gate hold to."""
    value = ((settings or {}).get("tests") or {}).get("coverage")
    return DEFAULT_SETTINGS["tests"]["coverage"] if value is None else value


def test_suites(settings):
    """{name: definition} of every named test suite: `tests` less `coverage`."""
    tests = (settings or {}).get("tests") or {}
    return {name: suite for name, suite in tests.items() if name != "coverage"}


def validate_tests(tests):
    """`tests` is {coverage?, <suite>: {command, setup?, teardown?}}."""
    if not isinstance(tests, dict):
        raise GateError("tests must be an object: {coverage?, <suite>: {command, setup?, teardown?}}.")
    coverage = tests.get("coverage", DEFAULT_SETTINGS["tests"]["coverage"])
    if isinstance(coverage, bool) or not isinstance(coverage, (int, float)) or not (0 < coverage <= 100):
        raise GateError("tests.coverage must be a number in (0, 100]; got %r." % (coverage,))
    for name, suite in test_suites({"tests": tests}).items():
        if not isinstance(suite, dict) or not isinstance(suite.get("command"), str) \
                or not suite["command"].strip():
            raise GateError("tests.%s must be an object with a non-empty 'command' "
                            "(plus optional setup/teardown)." % name)
        for key in ("setup", "teardown"):
            if key in suite and (not isinstance(suite[key], str) or not suite[key].strip()):
                raise GateError("tests.%s.%s must be a non-empty string when set." % (name, key))


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
    legacy = legacy_problems(settings)
    if legacy:
        raise GateError(
            "settings.json uses keys acs no longer reads: %s. Run "
            "`python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py\" settings migrate --write` "
            "to rewrite it." % "; ".join(legacy))
    validate_tests(settings.get("tests", {}))
    strategy = settings.get("merge_strategy", "squash")
    if strategy not in ("squash", "merge", "rebase"):
        raise GateError("merge_strategy must be one of squash|merge|rebase; got %r." % (strategy,))
    validate_models(settings.get("models", {}))
    validate_design(settings.get("design", {}))
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
