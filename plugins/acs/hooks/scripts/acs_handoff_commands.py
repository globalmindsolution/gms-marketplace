"""acs_handoff_commands — member-to-member TICKET handoff over a hidden ref (ADR-0131).

    acs.py handoff send --ticket ID [--note TEXT | --note-file F] [--attach PATH ...]
                        [--replace] [--dry-run] [--remote NAME]
        package the ticket's uncommitted work and its run's resume set into one
        commit and push it to refs/acs/handoff/<ID>. The sender's workspace,
        index and refs are untouched. --dry-run reports the package (and the
        outside-repo attachments the run holds, for the sender to confirm)
        without building or pushing anything.
    acs.py handoff receive --ticket ID [--replace] [--keep-ref] [--remote NAME]
        fetch it, apply the work onto this (clean) checkout with a 3-way
        apply, restore the resume set, and print `continue_with`.
    acs.py handoff list [--details] [--remote NAME]
        the handoffs waiting on the remote.

Each verb prints one JSON object; a refusal exits 2 with `acs handoff <verb>:
<reason>` on stderr. This is NOT `handoff.py`, which pauses this session's own
run under context pressure and is unchanged.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import context_or_die, die, emit  # noqa: E402
from acs_lib import team_handoff, team_handoff_receive  # noqa: E402


def _note(command, args):
    if args.note is not None and args.note_file:
        die(command, "pass --note or --note-file, not both")
    if args.note_file:
        try:
            with open(args.note_file, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            die(command, "cannot read --note-file %s: %s" % (args.note_file, exc))
    return args.note or ""


def _call(command, fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except lib.GateError as exc:
        die(command, str(exc))


def cmd_handoff_send(args):
    command = "handoff send"
    ctx = context_or_die(command)
    note = _note(command, args)
    emit(_call(command, team_handoff.send, ctx, args.ticket.strip(), note=note,
               attach=args.attach, replace=args.replace, dry_run=args.dry_run,
               remote=args.remote))


def cmd_handoff_receive(args):
    command = "handoff receive"
    ctx = context_or_die(command)
    ticket = (args.ticket or args.ticket_pos or "").strip()
    if not ticket:
        die(command, "name the ticket to receive (--ticket ID)")
    emit(_call(command, team_handoff_receive.receive, ctx, ticket, replace=args.replace,
               keep_ref=args.keep_ref, remote=args.remote))


def cmd_handoff_list(args):
    command = "handoff list"
    ctx = context_or_die(command)
    emit(_call(command, team_handoff.list_waiting, ctx, remote=args.remote,
               details=args.details))


def add_parser(group):
    handoff = group("handoff", help="hand a ticket to a teammate's machine over "
                                    "refs/acs/handoff/<ID> (ADR-0131)")
    sub = handoff.add_subparsers(dest="cmd")

    send = sub.add_parser("send", help="package the ticket's work and run state; push it")
    send.add_argument("--ticket", required=True, help="the ticket to hand off")
    send.add_argument("--note", help="the handoff note (done / in flight / next / decisions)")
    send.add_argument("--note-file", dest="note_file", metavar="FILE",
                      help="read the note from a file")
    send.add_argument("--attach", action="append", default=[], metavar="PATH",
                      help="include this outside-repo attachment the run copied "
                           "(repeatable; none travel unless named)")
    send.add_argument("--replace", action="store_true",
                      help="overwrite a handoff of this ticket still waiting on the remote")
    send.add_argument("--dry-run", dest="dry_run", action="store_true",
                      help="report the package and the attachments; build and push nothing")
    send.add_argument("--remote", default="origin")
    send.set_defaults(func=cmd_handoff_send)

    receive = sub.add_parser("receive", help="fetch, apply and restore a waiting handoff")
    receive.add_argument("ticket_pos", nargs="?", metavar="ID", help="the ticket to receive")
    receive.add_argument("--ticket", help="the ticket to receive")
    receive.add_argument("--replace", action="store_true",
                         help="move this workspace's existing run/ticket to a backup first")
    receive.add_argument("--keep-ref", dest="keep_ref", action="store_true",
                         help="leave refs/acs/handoff/<ID> on the remote")
    receive.add_argument("--remote", default="origin")
    receive.set_defaults(func=cmd_handoff_receive)

    lst = sub.add_parser("list", help="the handoffs waiting on the remote")
    lst.add_argument("--details", action="store_true",
                     help="fetch each one to show its sender, time and note")
    lst.add_argument("--remote", default="origin")
    lst.set_defaults(func=cmd_handoff_list)
