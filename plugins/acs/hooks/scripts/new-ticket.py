#!/usr/bin/env python3
"""new-ticket.py — allocate a ticket id and create its workspace partition.

Used by /acs:create-ticket (a new ticket, remote imports), /acs:breakdown-ticket
(a parent's children) and anywhere else a ticket must be minted. Maintains both
directions of the epic <-> child link and the repo-level tickets-index.json.

Usage:
  new-ticket.py --title "Wishlist API" --type story [--parent SHOP-122]
                [--description "..."] [--priority high]
                [--external github:123] [--assignee jane] [--story-points 3]
                [--features wishlist,checkout] [--requirements wishlist/R1,wishlist/R2]
                [--require-prd-link]
  new-ticket.py --title "Cart doubles a line" --type bug [--severity high]
                [--reproduction "1. ..."] [--expected "..."] [--actual "..."]
                [--environment "v0.5.0, Firefox 140"]

A child minted with `--parent` traces to its parent's PRD features unless
`--features` says otherwise (`--features ""` = none) (ADR-0138). The parent must
be an epic. `--requirements` names the PRD requirements the ticket delivers
(`<slug>/R<n>`, ADR-0144); a given requirement must resolve against its
feature's PRD. `--require-prd-link` -- what /acs:create-ticket and
/acs:breakdown-ticket pass -- refuses to mint a ticket whose PRD link is not
sound: no PRD, no feature, a feature with no PRD of its own, a story naming no
requirement (`acs_lib.prd_link`). Without it (a regression bug /acs:run-e2e-tests
files, say) the link is optional. /acs:breakdown-ticket converts a story or task it splits into one
first (`acs.py ticket save`, type epic), so the id is kept. The bug flags apply
to `--type bug` only.

Prints {"ticket_id": ..., "partition": ..., "ticket_document": ...,
"features": [...], "features_inherited": true|false} on success. `ticket_document` is the file the ticket was written to:
`<partition>/ticket.json` in the workspace. Since ADR-0128 a ticket lives only
in the workspace and the tracker -- nothing is written into the consumer
repo's docs tree (no `docs/tickets/<ID>/ticket.md`), so minting a ticket
leaves the working tree untouched.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--type", dest="ttype", required=True, choices=lib.TICKET_TYPES)
    parser.add_argument("--description", default="")
    parser.add_argument("--priority", default="medium", choices=lib.PRIORITIES)
    parser.add_argument("--parent", help="parent epic ticket id")
    parser.add_argument("--docs-only", dest="docs_only", choices=["true", "false"], default="false",
                        help="user-confirmed docs-only flag (relaxes /code TDD/coverage gates)")
    parser.add_argument("--external", help="remote tracker mapping, e.g. github:123")
    parser.add_argument("--assignee")
    parser.add_argument("--story-points", dest="story_points", type=int)
    parser.add_argument("--due-date", dest="due_date",
                        help="Optional delivery target date, ISO-8601 YYYY-MM-DD.")
    parser.add_argument("--features",
                        help="PRD features it traces to, as comma-separated slugs (ADR-0120). "
                             "Omitted with --parent: the parent's features (ADR-0138); "
                             "\"\" = none.")
    parser.add_argument("--requirements",
                        help="PRD requirements it delivers, as comma-separated "
                             "`<feature-slug>/R<n>` ids (ADR-0144)")
    parser.add_argument("--require-prd-link", dest="require_prd_link", action="store_true",
                        help="refuse unless the ticket links the PRD soundly (ADR-0144); "
                             "/acs:create-ticket and /acs:breakdown-ticket pass it")
    # A bug's report (ADR-0138): --type bug only, each optional.
    parser.add_argument("--severity", choices=lib.BUG_SEVERITIES,
                        help="a bug's severity, separate from --priority")
    parser.add_argument("--reproduction", help="a bug's steps to reproduce (markdown)")
    parser.add_argument("--expected", help="what a bug's steps should produce")
    parser.add_argument("--actual", help="what they produce instead")
    parser.add_argument("--environment", help="where the bug was seen (version, OS, runtime)")
    parser.add_argument("--seed-next", dest="seed_next", type=int,
                        help="Confirm or repair the ticket-id reconciliation floor: "
                             "mint <PREFIX>-<n> and record it as the confirmed floor.")
    args = parser.parse_args()

    if args.due_date is not None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.due_date):
            sys.stderr.write(
                "acs new-ticket: --due-date must be YYYY-MM-DD, got: %r\n" % args.due_date
            )
            sys.exit(2)

    try:
        features = lib.parse_features(args.features)
        requirements = lib.prd_link.parse_requirements(args.requirements)
    except lib.GateError as exc:
        sys.stderr.write("acs new-ticket: --%s\n" % exc)
        sys.exit(2)

    bug = {field: getattr(args, field) for field in lib.BUG_FIELDS
           if getattr(args, field) is not None}
    if bug and args.ttype != "bug":
        sys.stderr.write("acs new-ticket: %s only apply to --type bug, not --type %s\n"
                         % (", ".join("--" + f for f in bug), args.ttype))
        sys.exit(2)

    if args.seed_next is not None and args.seed_next < 1:
        sys.stderr.write(
            "acs new-ticket: --seed-next must be >= 1, got: %d\n" % args.seed_next
        )
        sys.exit(2)

    cwd = os.getcwd()
    try:
        ctx = lib.build_context(cwd)
    except lib.GateError as exc:
        sys.stderr.write("acs new-ticket: %s\n" % exc)
        sys.exit(2)
    workspace, repo_id = ctx["workspace"], ctx["repo_id"]

    external = None
    if args.external:
        provider, _, key = args.external.partition(":")
        if not key:
            sys.stderr.write("acs new-ticket: --external must be <provider>:<key>\n")
            sys.exit(2)
        external = {"provider": provider, "key": key}

    parent_dir = None
    parent_ticket = None
    if args.parent:
        parent_dir, archived = lib.find_ticket_partition(workspace, repo_id, args.parent)
        parent_ticket = lib.load_ticket(parent_dir) if os.path.isdir(parent_dir) else None
        if archived or not parent_ticket:
            sys.stderr.write("acs new-ticket: parent ticket %s not found (or archived)\n" % args.parent)
            sys.exit(2)
        if parent_ticket.get("type") != "epic":
            sys.stderr.write("acs new-ticket: parent %s is a %s, not an epic\n" % (args.parent, parent_ticket.get("type")))
            sys.exit(2)

    # A child traces to its parent's PRD features unless the caller narrowed
    # them (ADR-0138): a child that silently traced to nothing would drop out
    # of every feature's LLD. An explicit --features, even "", is the answer.
    inherited = args.features is None and bool(parent_ticket and parent_ticket.get("features"))
    if inherited:
        features = list(parent_ticket["features"])

    # The PRD link, judged before an id is spent (ADR-0144): always when the
    # caller asks for it, and for any requirement given -- a link that names a
    # requirement must name a real one.
    if args.require_prd_link or requirements:
        try:
            lib.prd_link.ensure_link(ctx["checkout_root"], args.ttype, features,
                                     requirements, ctx["settings"])
        except lib.GateError as exc:
            sys.stderr.write("acs new-ticket: %s\nNo ticket id was minted.\n" % exc)
            sys.exit(2)

    repo_root = ctx.get("main_repo_root") or ctx["checkout_root"]
    try:
        ticket_id = lib.allocate_ticket_id(
            workspace, repo_id, ctx["settings"]["ticket_prefix"],
            repo_root=repo_root, seed_next=args.seed_next)
    except lib.ReconciliationRequired as exc:
        sys.stderr.write("acs new-ticket: " + exc.render("new-ticket.py --seed-next <n>") + "\n")
        sys.exit(2)
    except lib.GuardTimeout as exc:
        # A refused id allocation is the CLEAN failure: nothing is minted and
        # nothing is written, so a retry is safe and complete. It reached the
        # operator as a traceback and exit 1 -- which reads as a crash, and
        # which the CLI contract (`acs <command>: <reason>`, exit 2) forbids.
        sys.stderr.write(
            "acs new-ticket: %s\nNo ticket id was minted and no partition was "
            "written; re-run once the other writer finishes.\n" % exc)
        sys.exit(2)
    tdir = lib.ticket_dir(workspace, repo_id, ticket_id)
    os.makedirs(tdir, exist_ok=True)

    ticket = lib.new_ticket_doc(
        ticket_id, args.title, args.ttype,
        description=args.description,
        priority=args.priority,
        parent=args.parent,
        external=external,
        assignee=args.assignee,
        story_points=args.story_points,
        docs_only=args.docs_only == "true",
        due_date=args.due_date,
        features=features,
        requirements=requirements,
        **bug
    )
    lib.save_ticket(tdir, ticket)
    # Where the ticket landed: its partition's ticket.json, never the repo's
    # docs tree (ADR-0128). Reported so the caller sees the write.
    _kind, document = lib.ticket_source(tdir)
    document = document or os.path.join(tdir, lib.artifacts.TICKET_JSON_FILENAME)
    try:
        lib.update_index(workspace, repo_id, ticket, archived=False)
    except lib.GuardTimeout as exc:
        sys.stderr.write(
            "acs new-ticket: %s\nThe ticket %s IS created and its partition "
            "written, but tickets-index.json has no entry for it yet; the entry "
            "is rebuilt from ticket.json by the next write to the index. Do NOT "
            "re-run -- a second call mints a second id.\n" % (exc, ticket_id))
        sys.exit(2)

    # No run ledger is written here. Under the re-key a ticket is a SUBJECT a
    # run may later be started over (§4.2), not a run of its own, so
    # "create-ticket completed" is no longer a thing downstream gates read --
    # the ticket partition existing IS the ticket having been created, which
    # is what the gates checked all along.
    #
    # A child minted here therefore never re-runs /acs:create-ticket: its
    # pipeline starts at /acs:code (via /acs:ship <child-id>), reading the
    # EPIC's tech design when one exists (`context.design`, ADR-0139).

    if parent_ticket is not None:
        children = parent_ticket.setdefault("children", [])
        if ticket_id not in children:
            children.append(ticket_id)
        lib.save_ticket(parent_dir, parent_ticket)
        lib.update_index(workspace, repo_id, parent_ticket)

    print(json.dumps({"ticket_id": ticket_id, "partition": tdir,
                      "ticket_document": document, "features": features,
                      "requirements": requirements,
                      "features_inherited": inherited}, indent=2))


if __name__ == "__main__":
    main()
