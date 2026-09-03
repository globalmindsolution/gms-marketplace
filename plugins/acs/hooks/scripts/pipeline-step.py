#!/usr/bin/env python3
"""pipeline-step.py — record a pipeline step transition from a skill's Bash step.

The unhooked skills have no post-hook to write `pipeline-state.json` for them,
so without this they would have to embed Python in their prose to reach
`acs_lib.update_pipeline` — the pattern ADR 0001 exists to prevent.

Usage:
  pipeline-step.py --ticket SHOP-123 --skill test --status completed
                   [--summary "..."] [--set fix_loops=2] [--unset fix_loops]
                   [--only-if-present]

`--set k=v` merges arbitrary fields into the step entry (integers and the JSON
literals true/false/null are parsed as such; everything else stays a string).
`--only-if-present` makes the write conditional on the step entry already
existing, so recording a failure can never newly create a gate that was not
already active.

`--ticket` and `--skill` are validated against pipeline-state.schema.json's
own ticket_id pattern and steps enum before anything is written: `--ticket`
becomes a path segment, and a step name outside the enum produces a ledger the
schema rejects.

Prints the resulting step entry as JSON.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402

#: pipeline-state.schema.json's ticket_id pattern, anchored. --ticket becomes a
#: path segment, so an unvalidated value ("../victim") escapes the partition.
TICKET_ID = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+$")

#: pipeline-state.schema.json's steps.propertyNames enum. Writing a step name
#: outside it produces a ledger the schema rejects -- four test modules load
#: that schema and assert against it.
PIPELINE_STEPS = (
    "create-prd", "create-architecture", "create-project", "create-quality",
    "create-operations", "create-principles", "create-standards",
    "create-requirements", "create-ticket", "create-design", "code", "test",
    "docs-sync", "create-pr", "merge-pr",
)


def parse_value(text):
    """v -> a JSON scalar when it reads as one, else the raw string."""
    for literal, value in (("true", True), ("false", False), ("null", None)):
        if text == literal:
            return value
    try:
        return int(text)
    except ValueError:
        return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--skill", required=True, choices=PIPELINE_STEPS)
    parser.add_argument("--status", required=True,
                        choices=["in_progress", "completed", "failed", "interrupted"])
    parser.add_argument("--summary")
    parser.add_argument("--set", dest="sets", action="append", default=[],
                        metavar="KEY=VALUE", help="merge a field into the step entry")
    parser.add_argument("--unset", dest="unsets", action="append", default=[],
                        metavar="KEY", help="remove a field from the step entry")
    parser.add_argument("--only-if-present", action="store_true",
                        help="write only when the step entry already exists")
    args = parser.parse_args()

    if not TICKET_ID.match(args.ticket):
        sys.stderr.write("acs pipeline-step: %r is not a ticket id (expected %s)\n"
                         % (args.ticket, TICKET_ID.pattern))
        sys.exit(2)

    extra = {}
    for item in args.sets:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            sys.stderr.write("acs pipeline-step: --set expects KEY=VALUE, got %r\n" % item)
            sys.exit(2)
        parsed = parse_value(value)
        if key.strip() == "fix_loops" and not (isinstance(parsed, int) and parsed >= 0):
            # pipeline-state.schema.json gives fix_loops minimum 0.
            sys.stderr.write("acs pipeline-step: fix_loops must be a non-negative "
                             "integer, got %r\n" % value)
            sys.exit(2)
        extra[key.strip()] = parsed
    for key in args.unsets:
        extra[key.strip()] = None

    try:
        ctx = lib.build_context(os.getcwd())
    except lib.GateError as exc:
        sys.stderr.write("acs pipeline-step: %s\n" % exc)
        sys.exit(2)

    tdir, archived = lib.find_ticket_partition(ctx["workspace"], ctx["repo_id"], args.ticket)
    if archived or not os.path.isdir(tdir):
        sys.stderr.write("acs pipeline-step: no active partition for %s\n" % args.ticket)
        sys.exit(2)

    pipeline = lib.load_pipeline(tdir, args.ticket)
    if args.only_if_present and args.skill not in pipeline.get("steps", {}):
        print(json.dumps({"skill": args.skill, "written": False,
                          "reason": "step entry absent and --only-if-present was given"}))
        return

    data = lib.update_pipeline(tdir, args.ticket, args.skill, args.status,
                               summary=args.summary, extra=extra or None)
    step = data["steps"].get(args.skill, {})
    print(json.dumps({"skill": args.skill, "written": True, "step": step}, indent=2))


if __name__ == "__main__":
    main()
