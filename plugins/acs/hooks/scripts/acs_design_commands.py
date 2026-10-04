"""acs_design_commands — `acs.py design ...`, the version front matter of design docs (ADR-0122).

    acs.py design check  <doc>...                         status, version and problems per doc
    acs.py design init   --status S [--ticket ID] [--feature F] <doc>...
                                                          first front matter (a doc that has one is left alone)
    acs.py design bump   [--ticket ID] <doc>...           a change: version + 1, re-opened as proposed
    acs.py design status --set S [--ticket ID] <doc>...   a legal status transition

Every verb prints one JSON object. `check` exits 0 whatever it finds (`ok` says
whether every document is clean); a write verb that is refused exits 2 and
writes nothing for the document it refused.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import emit  # noqa: E402

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


def cmd_design_status(args):
    emit({"ok": True, "files": [dict(D.set_status(p, args.set, args.ticket), path=p)
                                for p in _existing(args.docs)]})


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
    status.add_argument("docs", nargs="+")
    status.set_defaults(func=cmd_design_status)
