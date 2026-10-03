"""acs_model_commands — `acs.py agents sync` and `acs.py settings scaffold`.

    acs.py agents sync [--dry-run]       make .claude/agents/acs-*.md match settings.models
    acs.py settings scaffold [--write]   the full `models` block; --write adds the
                                         entries a project settings.json lacks and
                                         changes nothing it already has

`step start` runs the sync itself; the verb is for a person who wants to see or
force it. `scaffold` is for /acs:setup and /acs:update, and for anyone starting
a settings file by hand.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import context_or_die, die, emit  # noqa: E402


def cmd_agents_sync(args):
    ctx = context_or_die("agents sync")
    root = ctx.get("checkout_root") or os.getcwd()
    try:
        result = lib.agent_sync.sync(ctx["settings"], root, dry_run=args.dry_run)
    except OSError as exc:
        die("agents sync", "could not write %s: %s"
            % (lib.agent_sync.project_agents_dir(root), exc))
    emit(dict(result, ok=True, dry_run=bool(args.dry_run),
              directory=lib.agent_sync.project_agents_dir(root)))


def cmd_settings_scaffold(args):
    scaffold = lib.models.scaffold()
    if not args.write:
        emit({"ok": True, "models": scaffold})
        return
    ctx = context_or_die("settings scaffold")
    root = ctx.get("checkout_root") or os.getcwd()
    path = os.path.join(root, ".acs", "settings.json")
    data = lib.read_json(path) if os.path.isfile(path) else {}
    if not isinstance(data, dict):
        die("settings scaffold", "%s is not a JSON object; fix it by hand first" % path)
    merged, added = lib.models.merge_missing(data.get("models"))
    data["models"] = merged
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    emit({"ok": True, "path": path, "added": added, "kept": sum(
        len(v) for v in merged.values()) - len(added)})


def add_parser(group):
    agents = group("agents", help="the agents that run, from settings.models")
    agents_sub = agents.add_subparsers(dest="verb")
    sync = agents_sub.add_parser(
        "sync", help="write .claude/agents/acs-*.md for each models entry that sets a value")
    sync.add_argument("--dry-run", dest="dry_run", action="store_true",
                      help="list what would change without writing")
    sync.set_defaults(func=cmd_agents_sync)

    settings = group("settings", help="settings helpers")
    settings_sub = settings.add_subparsers(dest="verb")
    scaffold = settings_sub.add_parser(
        "scaffold", help="the full models block, every skill and role")
    scaffold.add_argument("--write", action="store_true",
                          help="add the missing entries to .acs/settings.json")
    scaffold.set_defaults(func=cmd_settings_scaffold)
