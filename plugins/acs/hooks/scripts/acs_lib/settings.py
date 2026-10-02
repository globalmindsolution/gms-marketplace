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

from ._common import GateError, TICKET_TYPES, deep_merge, read_json
from .models import validate_models
from .repo import checkout_root, default_state_root, main_repo_root



# Placeholder vocabulary per inline format field (docs/requirements/functional/configuration.md).
FORMAT_PLACEHOLDERS = {
    "branch_name": {"ticket_id", "type", "slug", "external_key"},
    "commit_message": {"ticket_id", "type", "summary", "external_key"},
    "pr_title": {"ticket_id", "type", "title", "summary", "external_key", "ticket_ref"},
    "ticket_title": {"ticket_id", "type", "title", "external_key"},
}

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
    "formats": {
        "branch_name": "{type}/{ticket_id}-{slug}",
        "commit_message": "{ticket_id} {summary}",
        "pr_title": "{title}",
        "pr_description_template": "pr-default",
        "tickets": {
            "epic": {"title": "[EPIC] {title}", "description_template": "epic-default"},
            "story": {"title": "{title}", "description_template": "story-default"},
            "task": {"title": "{title}", "description_template": "task-default"},
        },
    },
}

#: Keys an older acs read and this one ignores (ADR-0102): no setting locates a
#: document or the workspace. Still legal in a settings file -- unknown keys
#: are -- and named by `/acs:setup detect` so a stale one is not mistaken for a
#: live one.
RETIRED_SETTINGS_KEYS = (
    "workspace_path", "prd_path", "architecture_path", "requirements_path",
    "requirements_layout", "adr_path", "quality_path", "operations_path",
    "principles_path", "standards_path", "artifacts", "contracts_path",
)

# Enforcement defaults — mirror schemas/settings.schema.json + the consumer-side
# templates/ci/check-conventions.py, used only when a key is absent from settings
# so /acs:merge-pr --pr behaves predictably on a repo with no enforcement block.
ENFORCEMENT_DEFAULTS = {
    "exempt_branches": ["release/*", "dependabot/*", "renovate/*"],
    "exempt_label": "acs-exempt",
    "require_label": "ACS",
}


def enforcement_value(settings, key):
    """Resolve enforcement.<key> from settings, defaulting per ENFORCEMENT_DEFAULTS."""
    return ((settings or {}).get("enforcement") or {}).get(key, ENFORCEMENT_DEFAULTS[key])


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
    validate_formats(settings.get("formats", {}))
    validate_models(settings.get("models", {}))
    return workspace if require_workspace else None


def validate_formats(formats):
    def check(field, template, vocab_key):
        if not isinstance(template, str) or not template.strip():
            raise GateError("formats.%s must be a non-empty string." % field)
        used = set(re.findall(r"\{([a-z_]+)\}", template))
        unknown = used - FORMAT_PLACEHOLDERS[vocab_key]
        if unknown:
            raise GateError(
                "formats.%s uses unknown placeholder(s) %s; allowed: %s."
                % (field, ", ".join("{%s}" % p for p in sorted(unknown)),
                   ", ".join("{%s}" % p for p in sorted(FORMAT_PLACEHOLDERS[vocab_key])))
            )

    if "branch_name" in formats:
        check("branch_name", formats["branch_name"], "branch_name")
        if "{ticket_id}" not in formats["branch_name"]:
            raise GateError("formats.branch_name must embed {ticket_id} — ticket detection from branch names depends on it.")
    if "commit_message" in formats:
        check("commit_message", formats["commit_message"], "commit_message")
    if "pr_title" in formats:
        check("pr_title", formats["pr_title"], "pr_title")
    tickets = formats.get("tickets", {})
    if not isinstance(tickets, dict):
        raise GateError("formats.tickets must be an object keyed by ticket type.")
    for ttype, conf in tickets.items():
        if ttype not in TICKET_TYPES:
            raise GateError("formats.tickets.%s: unknown ticket type (epic|story|task)." % ttype)
        if isinstance(conf, dict) and "title" in conf:
            check("tickets.%s.title" % ttype, conf["title"], "ticket_title")


def render_format(template, mapping):
    return re.sub(r"\{([a-z_]+)\}", lambda m: str(mapping.get(m.group(1), "")), template)


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
