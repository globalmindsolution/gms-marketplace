#!/usr/bin/env python3
"""clarify.py — the requirement-clarification ledger.

One append-only Q&A record per ticket at <partition>/clarifications.json, or,
for a run with no ticket (ADR-0128: a prompt's or documents' run), per run at
runs/<run-id>/clarifications.json — the single source of truth for every
requirement ambiguity resolved (or assumed) during the pipeline. Coordinators MUST read it before asking the
user anything (re-asking an answered question is a defect) and MUST record
every Q&A through this helper (atomic writes; no hand-edited JSON).

Usage:
  clarify.py add    --skill code --question "Overwrite or reject duplicates?"
                    [--answer "reject"] [--source user|assumption]
                    [--rationale "why this assumption is needed"]
                    [--ticket SHOP-123 | --run RUN-ID]
  clarify.py answer --id C-2 --answer "reject" [--source user] [--ticket ... | --run ...]
  clarify.py list   [--open] [--ticket SHOP-123 | --run RUN-ID]

The ledger: `--ticket`'s partition; else `--run`'s (or this checkout's
current run's) ticket partition when that run has a ticket, else that run's
own directory; with no run at all, the ticket the branch names.

Statuses: open (asked, unanswered — e.g. sent upward in a needs_input
handoff), answered (user decided), assumed (no user available/needed —
requires --rationale; assumptions surface in completion reports and the PR
body until a user confirms them).
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402


def ledger_path(tdir):
    return os.path.join(tdir, "clarifications.json")


def load_ledger(tdir, ticket_id, run_id=None):
    data = lib.read_json(ledger_path(tdir))
    if not isinstance(data, dict) or not isinstance(data.get("clarifications"), list):
        data = {"ticket_id": ticket_id, "clarifications": []}
        if run_id and not ticket_id:
            data["run_id"] = run_id
    return data


def _fail(message):
    sys.stderr.write("acs clarify: %s\n" % message)
    sys.exit(2)


def _run_ledger(ctx, run_id, explicit):
    """(ticket_id, ledger_dir, run_id) through a run: its ticket's partition
    when it has one, else the run's own directory. None when no run resolves
    and none was named."""
    if not run_id:
        return None
    rdir = lib.run_dir(lib.repo_dir(ctx["workspace"], ctx["repo_id"]), run_id)
    doc = lib.load_run(rdir)
    if doc is None:
        if explicit:
            _fail("no run %r (expected %s)" % (run_id, rdir))
        return None
    ticket_id = (doc.get("subject") or {}).get("ticket_id")
    if ticket_id:
        return None  # a ticket's run keeps the ticket's ledger: resolved below
    if doc.get("status") in lib.TERMINAL_RUN_STATUSES and not explicit:
        return None
    return None, rdir, run_id


def resolve(args):
    """(ticket_id, ledger_dir, run_id). A ticket's ledger as before; a run with
    no ticket keeps its own (ADR-0128)."""
    cwd = os.getcwd()
    try:
        ctx = lib.build_context(cwd)
    except lib.GateError as exc:
        _fail(exc)
    if not args.ticket:
        explicit = getattr(args, "run", None)
        found = _run_ledger(ctx, explicit or lib.current_run_id(ctx), bool(explicit))
        if found is not None:
            return found
        if explicit:
            doc = lib.load_run(lib.run_dir(lib.repo_dir(ctx["workspace"], ctx["repo_id"]),
                                           explicit)) or {}
            args.ticket = (doc.get("subject") or {}).get("ticket_id")
    # Shared resolution (MAR-521 review): `list` may read a finished ticket, so
    # it allows an archived partition; every writing subcommand does not.
    try:
        ticket_id, tdir, archived = lib.resolve_active_partition(
            cwd, ctx, explicit=args.ticket, allow_archived=True)
    except lib.GateError as exc:
        sys.stderr.write("acs clarify: %s\n" % exc)
        sys.exit(2)
    if archived and args.cmd != "list":
        sys.stderr.write("acs clarify: %s is archived — ledger is read-only\n" % ticket_id)
        sys.exit(2)
    return ticket_id, tdir, None


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--skill", required=True, choices=lib.HOOKED_SKILLS)
    p_add.add_argument("--question", required=True)
    p_add.add_argument("--answer")
    p_add.add_argument("--source", choices=["user", "assumption"], default="user")
    p_add.add_argument("--rationale", help="required when --source assumption")
    p_add.add_argument("--ticket")
    p_add.add_argument("--run", help="a run with no ticket: its own ledger")

    p_ans = sub.add_parser("answer")
    p_ans.add_argument("--id", required=True)
    p_ans.add_argument("--answer", required=True)
    p_ans.add_argument("--source", choices=["user", "assumption"], default="user")
    p_ans.add_argument("--rationale")
    p_ans.add_argument("--ticket")
    p_ans.add_argument("--run", help="a run with no ticket: its own ledger")

    p_list = sub.add_parser("list")
    p_list.add_argument("--open", action="store_true", help="only open questions")
    p_list.add_argument("--ticket")
    p_list.add_argument("--run", help="a run with no ticket: its own ledger")

    args = parser.parse_args()
    ticket_id, tdir, run_id = resolve(args)
    data = load_ledger(tdir, ticket_id, run_id)
    entries = data["clarifications"]

    if args.cmd == "add":
        if args.source == "assumption" and not (args.rationale or "").strip():
            sys.stderr.write("acs clarify: --source assumption requires --rationale\n")
            sys.exit(2)
        if args.source == "assumption" and not args.answer:
            sys.stderr.write("acs clarify: an assumption must state the assumed answer (--answer)\n")
            sys.exit(2)
        entry = {
            "id": "C-%d" % (len(entries) + 1),
            "skill": args.skill,
            "question": args.question.strip(),
            "answer": (args.answer or "").strip() or None,
            "source": args.source if args.answer else None,
            "rationale": (args.rationale or "").strip() or None,
            "status": ("assumed" if args.source == "assumption" else "answered") if args.answer else "open",
            "asked_at": lib.now_iso(),
            "answered_at": lib.now_iso() if args.answer else None,
        }
        entries.append(entry)
        lib.write_json(ledger_path(tdir), data)
        print(json.dumps(entry, indent=2))
        return

    if args.cmd == "answer":
        for entry in entries:
            if entry.get("id") == args.id:
                entry["answer"] = args.answer.strip()
                entry["source"] = args.source
                if args.rationale:
                    entry["rationale"] = args.rationale.strip()
                entry["status"] = "assumed" if args.source == "assumption" else "answered"
                entry["answered_at"] = lib.now_iso()
                lib.write_json(ledger_path(tdir), data)
                print(json.dumps(entry, indent=2))
                return
        sys.stderr.write("acs clarify: no entry %s in %s\n" % (args.id, ledger_path(tdir)))
        sys.exit(2)

    if args.cmd == "list":
        wanted = [e for e in entries if not args.open or e.get("status") == "open"]
        out = {"ticket_id": ticket_id, "count": len(wanted), "clarifications": wanted}
        if run_id:
            out.update(run_id=run_id, ledger=ledger_path(tdir))
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
