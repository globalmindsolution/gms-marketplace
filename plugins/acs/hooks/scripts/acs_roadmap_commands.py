"""acs_roadmap_commands — the roadmap's derived delivery status (ADR-0145).

    acs.py roadmap status [--roadmap PATH] [--write] [--no-git]
        {"ok", "roadmap", "milestones": [{name, version, status, was, tickets}],
         "changed", "written"}

Each milestone's status is derived from the tickets it tracks (its epics, and
every ticket linking one of its features) -- the tickets index, plus the ticket
ids that lead a commit subject on the default branch -- never asserted by an
agent. `--write` rewrites only each milestone's `Status:` line and the Release
versions Status cell; nothing else in the document moves, so a status refresh
is not a new version of the roadmap (it carries no front-matter bump).
`--no-git` skips the default-branch read (the index alone decides).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import context_or_die, die, emit  # noqa: E402
from acs_lib import doc_layout, roadmap  # noqa: E402


def _roadmap_path(ctx, explicit):
    root = ctx["checkout_root"]
    if explicit:
        return explicit if os.path.isabs(explicit) else os.path.join(root, explicit)
    prd_dir = doc_layout.prd_dir(root, ctx["settings"])
    return os.path.join(root, *prd_dir.split("/"), "roadmap.md")


def cmd_roadmap_status(args):
    ctx = context_or_die("roadmap status")
    path = _roadmap_path(ctx, args.roadmap)
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        die("roadmap status", "no roadmap to read at %s (%s); write it with "
                              "/acs:manage-roadmap" % (path, exc))
    index = (lib.read_json(lib.index_path(ctx["workspace"], ctx["repo_id"])) or {}).get(
        "tickets", {})
    merged = (set() if args.no_git
              else roadmap.merged_on_default_branch(ctx["checkout_root"], ctx["settings"]))
    derived = roadmap.derive(text, index, merged)
    updated = roadmap.render(text, derived)
    changed = updated != text
    if args.write and changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(updated)
    emit({"ok": True, "roadmap": os.path.relpath(path, ctx["checkout_root"]).replace(os.sep, "/"),
          "milestones": derived, "changed": changed, "written": bool(args.write and changed)})


def add_parser(group):
    rm = group("roadmap", help="the roadmap's derived delivery status (ADR-0145)")
    sub = rm.add_subparsers(dest="cmd")
    status = sub.add_parser("status", help="derive each milestone's status from its tickets")
    status.add_argument("--roadmap", help="the roadmap file (default: roadmap.md beside the PRD)")
    status.add_argument("--write", action="store_true",
                        help="rewrite the Status lines and cells in place")
    status.add_argument("--no-git", dest="no_git", action="store_true",
                        help="do not read the default branch's history")
    status.set_defaults(func=cmd_roadmap_status)
