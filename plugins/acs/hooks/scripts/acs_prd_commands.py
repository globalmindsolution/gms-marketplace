"""acs_prd_commands — the PRD doc set's templates (ADR-0147) and whether each
feature PRD is implemented, derived from its tickets (ADR-0146).

    acs.py prd template [--kind prd|feature]
        {"ok", "templates": [{kind, name, path, source, sections, joined, problems}]}

The template a document is written from: the repo's `.acs/templates/<name>.md`
when it has one (`source: repo`), else the plugin's built-in (`builtin`). Its
`## ` headings are the document's required sections (`joined` is the `A; B; C`
form /acs:create-prd passes as required_sections / feature_required_sections).
A template with `problems` (no section, a duplicate, a feature template without
Goals served or Requirements) exits 2.

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
from acs_lib import prd_delivery, prd_template  # noqa: E402


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


def cmd_prd_template(args):
    ctx = context_or_die("prd template")
    kinds = [args.kind] if args.kind else ["prd", "feature"]
    found = [prd_template.load(k, ctx["checkout_root"], lib.plugin_root()) for k in kinds]
    for t in found:  # the repo's copy repo-relative; the built-in absolute, readable as is
        if t["source"] == "repo":
            t["path"] = os.path.relpath(t["path"], ctx["checkout_root"]).replace(os.sep, "/")
    bad = ["%s (%s): %s" % (t["name"], t["path"], "; ".join(t["problems"]))
           for t in found if t["problems"]]
    if bad:
        die("prd template", "unusable PRD template: " + " | ".join(bad))
    emit({"ok": True, "templates": found})


def add_parser(group):
    prd = group("prd", help="whether each feature PRD is implemented, from its tickets (ADR-0146)")
    sub = prd.add_subparsers(dest="cmd")
    status = sub.add_parser("status", help="derive each feature PRD's delivery from its tickets")
    status.add_argument("--feature", help="only this feature slug")
    status.add_argument("--no-git", dest="no_git", action="store_true",
                        help="do not read the default branch's history")
    status.set_defaults(func=cmd_prd_status)
    template = sub.add_parser("template", help="the template each PRD document is written "
                                               "from, and its required sections (ADR-0147)")
    template.add_argument("--kind", choices=("prd", "feature"),
                          help="the hub (prd) or a feature PRD (feature); default both")
    template.set_defaults(func=cmd_prd_template)
