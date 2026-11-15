"""acs_design_commands — `acs.py design ...`, the version front matter of design docs (ADR-0122).

    acs.py design check  <doc>...                         status, version and problems per doc
    acs.py design init   --status S [--ticket ID] [--feature F] <doc>...
                                                          first front matter (a doc that has one is left alone)
    acs.py design bump   [--ticket ID] <doc>...           a change: version + 1, re-opened as proposed
    acs.py design status --set S [--by NAME] [--reason TEXT] [--ticket ID]
                         [--override-delivery] <doc>...
                                                          a legal status transition, recording
                                                          status_by / status_at / status_reason
    acs.py design list   [--phase discovery|design] [--feature F] [--root DIR]
                                                          the versionable documents, grouped by
                                                          phase and doc set, with their legal moves

Every verb prints one JSON object. `check` and `list` exit 0 whatever they find
(`ok` on check says whether every document is clean); a write verb that is
refused exits 2. `status` is atomic (ADR-0130): every document is checked
before any is written, and one refusal writes none -- the error names each
refused document and why. `--by` defaults to `git config user.name
<user.email>`, else `unknown`.

A feature PRD's `implemented` is derived, never asserted (ADR-0146): `list`
gives each feature PRD its `delivery` (acs_lib.prd_delivery), and `status
--set implemented` refuses one whose delivery is not `implemented` -- every
requirement delivered by done tickets -- naming the requirements still open.
`--override-delivery` moves it anyway, for work no acs ticket tracks; it
needs `--reason`, which records why.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import emit  # noqa: E402
from acs_lib import prd_delivery  # noqa: E402

D = lib.design_docs


def _existing(paths):
    missing = [p for p in paths if not os.path.isfile(p)]
    if missing:
        raise lib.GateError("no such document: %s" % ", ".join(missing))
    return paths


def cmd_design_check(args):
    files = [D.check(p) for p in _existing(args.docs)]
    emit({"ok": not any(f["problems"] for f in files), "files": files})


def cmd_design_init(args):
    done = {p: D.init(p, args.status, args.ticket, args.feature) for p in _existing(args.docs)}
    emit({"ok": True, "initialised": [p for p, made in done.items() if made],
          "already_versioned": [p for p, made in done.items() if not made]})


def cmd_design_bump(args):
    emit({"ok": True, "files": [dict(D.bump(p, args.ticket), path=p)
                                for p in _existing(args.docs)]})


def default_actor(cwd=None):
    """`<user.name> <<user.email>>` from git config, whichever half is set, else `unknown`."""
    cwd = cwd or os.getcwd()
    name = lib._git(["config", "user.name"], cwd)
    email = lib._git(["config", "user.email"], cwd)
    if name and email:
        return "%s <%s>" % (name, email)
    return name or email or "unknown"


def _delivery_evidence(root):
    """(settings, index, merged) for deriving feature PRD delivery; the
    index is empty when this checkout has no acs workspace."""
    try:
        ctx = lib.build_context(root)
    except lib.GateError:
        return None, {}, set()
    index = (lib.read_json(lib.index_path(ctx["workspace"], ctx["repo_id"])) or {}).get(
        "tickets", {})
    index, merged = prd_delivery.evidence(root, ctx["settings"], index)
    return ctx["settings"], index, merged


def _delivery_summary(found):
    return {"state": found["delivery"], "agreement": found["agreement"],
            "open": [r["id"] for r in found["requirements"] if r["state"] != "delivered"]}


def _check_delivery(docs, override, reason):
    """Refuse `implemented` for a feature PRD its tickets do not bear out."""
    root = lib.checkout_root(os.getcwd()) or os.getcwd()
    settings, index, merged = _delivery_evidence(root)
    refused = []
    for doc in docs:
        slug = prd_delivery.feature_of(root, doc, settings)
        if not slug:
            continue
        found = prd_delivery.derive_feature(root, slug, index, merged, settings)
        if found["delivery"] != "implemented":
            refused.append("%s: delivery is %s (%s)" % (
                doc, found["delivery"], ", ".join(
                    "%s %s" % (r["id"], r["state"]) for r in found["requirements"]
                    if r["state"] != "delivered") or "it declares no requirement"))
    if refused and not override:
        raise lib.GateError(
            "a feature PRD is implemented when every requirement is delivered by done "
            "tickets (ADR-0146); not yet: " + "; ".join(refused) + ". Deliver them, or "
            "pass --override-delivery with --reason for work no acs ticket tracks")
    if refused and not (reason and reason.strip()):
        raise lib.GateError("--override-delivery needs --reason: why the feature is "
                            "implemented though its tickets do not show it")


def cmd_design_status(args):
    if args.set == "implemented":
        _check_delivery(args.docs, args.override_delivery, args.reason)
    by = args.by if args.by and args.by.strip() else default_actor()
    emit({"ok": True, "files": D.set_status_many(args.docs, args.set, ticket=args.ticket,
                                                  by=by, reason=args.reason)})


def cmd_design_list(args):
    root = args.root or lib.checkout_root(os.getcwd()) or os.getcwd()
    if not os.path.isdir(root):
        raise lib.GateError("no such directory: %s" % root)
    root = os.path.abspath(root)
    listing = D.list_documents(root, phase=args.phase, feature=args.feature)
    settings, index, merged = _delivery_evidence(root)
    for group in listing.get("groups", []):
        for doc in group.get("docs", []):
            slug = prd_delivery.feature_of(root, doc["path"], settings)
            if slug:
                doc["delivery"] = _delivery_summary(
                    prd_delivery.derive_feature(root, slug, index, merged, settings))
    emit(listing)


def add_parser(group):
    design = group("design", help="the version front matter of HLD/LLD documents")
    sub = design.add_subparsers(dest="verb")

    check = sub.add_parser("check", help="status, version and problems per document")
    check.add_argument("docs", nargs="+")
    check.set_defaults(func=cmd_design_check)

    init = sub.add_parser("init", help="give documents their first front matter")
    init.add_argument("--status", required=True, choices=D.STATUSES)
    init.add_argument("--ticket")
    init.add_argument("--feature", help="the PRD feature slug (LLD documents)")
    init.add_argument("docs", nargs="+")
    init.set_defaults(func=cmd_design_init)

    bump = sub.add_parser("bump", help="record a change: version + 1, back to proposed")
    bump.add_argument("--ticket")
    bump.add_argument("docs", nargs="+")
    bump.set_defaults(func=cmd_design_bump)

    status = sub.add_parser("status", help="move documents to a status (legal transitions)")
    status.add_argument("--set", required=True, choices=D.STATUSES)
    status.add_argument("--ticket")
    status.add_argument("--by", help="who moves it (default: git user.name <user.email>)")
    status.add_argument("--reason", help="why (recorded as status_reason)")
    status.add_argument("--override-delivery", dest="override_delivery", action="store_true",
                        help="mark a feature PRD implemented though its tickets do not show "
                             "it delivered (needs --reason; ADR-0146)")
    status.add_argument("docs", nargs="+")
    status.set_defaults(func=cmd_design_status)

    listing = sub.add_parser("list", help="the versionable documents by phase and doc set")
    listing.add_argument("--phase", choices=D.PHASES)
    listing.add_argument("--feature", help="only this PRD feature's groups")
    listing.add_argument("--root", help="the checkout root (default: this checkout)")
    listing.set_defaults(func=cmd_design_list)
