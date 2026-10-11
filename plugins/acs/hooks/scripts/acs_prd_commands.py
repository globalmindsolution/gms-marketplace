"""acs_prd_commands — whether each feature PRD is implemented, derived from its tickets (ADR-0146).

    acs.py prd status [--feature SLUG] [--no-git]
        {"ok", "features": [{feature, path, doc_status, delivery, agreement,
                             requirements: [{id, state, tickets}], tickets}],
         "ready", "drift"}

Read-only. Each requirement `<slug>/R<n>` of a feature PRD is delivered when
every ticket naming it is done (the tickets index, or the ticket id leading a
commit subject on the default branch); a feature is `implemented` when every
requirement is delivered. `ready` lists the approved feature PRDs delivery
says are implemented -- the move /acs:set-doc-status may offer -- and `drift`
the ones marked implemented that delivery no longer bears out. `--no-git`
skips the default-branch read (the index alone decides).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import context_or_die, die, emit  # noqa: E402
from acs_lib import prd_delivery  # noqa: E402


def tickets_index(ctx):
    """The workspace's tickets index ({id: entry}); {} when there is none."""
    return (lib.read_json(lib.index_path(ctx["workspace"], ctx["repo_id"])) or {}).get(
        "tickets", {})


def cmd_prd_status(args):
    ctx = context_or_die("prd status")
    root = ctx["checkout_root"]
    if not lib.prd_link.prd_path(root, ctx["settings"]):
        die("prd status", "this repo has no PRD; write it with /acs:create-prd")
    if args.feature and args.feature not in prd_delivery.feature_slugs(root, ctx["settings"]):
        die("prd status", "feature %r has no PRD of its own" % args.feature)
    index, merged = prd_delivery.evidence(root, ctx["settings"], tickets_index(ctx),
                                          git=not args.no_git)
    features = prd_delivery.derive(root, index, merged, ctx["settings"], args.feature)
    emit({"ok": True, "features": features,
          "ready": [f["feature"] for f in features if f["agreement"] == "ready"],
          "drift": [f["feature"] for f in features if f["agreement"] == "drift"]})


def add_parser(group):
    prd = group("prd", help="whether each feature PRD is implemented, from its tickets (ADR-0146)")
    sub = prd.add_subparsers(dest="cmd")
    status = sub.add_parser("status", help="derive each feature PRD's delivery from its tickets")
    status.add_argument("--feature", help="only this feature slug")
    status.add_argument("--no-git", dest="no_git", action="store_true",
                        help="do not read the default branch's history")
    status.set_defaults(func=cmd_prd_status)
