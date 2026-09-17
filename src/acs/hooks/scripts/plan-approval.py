#!/usr/bin/env python3
"""plan-approval.py — the sole writer of <partition>/phases/code/plan-approval.json.

On a `standard`/`complex` delivery-path /acs:code run, records the deterministic verdict of
acs_lib.plan_approval_eligible against the current plan artifact, once per
approved plan digest, and mirrors the outcome into code-state.json's
states.plan_approved. Never a subagent Write, never a gate.

Reachable as `acs.py plan check` (MAR-521) — acs.py drops the verb and forwards
the flags here unchanged; this script stays the implementation.

Usage:
  plan-approval.py --ticket <ticket-id> [--plan <path>]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_lib import workflow  # noqa: E402

#: The delivery paths on which an approved plan is a precondition for /acs:code
#: (ADR-0095). The two cheap paths run against the plan without one, and their
#: legs say so; the plan-conformance review dimension then reports N/A.
APPROVAL_PATHS = ("standard", "complex")

RECORD_NAME = "plan-approval.json"


def record_path(tdir):
    return os.path.join(tdir, "phases", "code", RECORD_NAME)


def _resolve_plan_path(tdir, explicit):
    """--plan wins; else <partition>/phases/code/plan.md -- the only name
    ever read or written for the plan artifact."""
    if explicit:
        return explicit
    return os.path.join(tdir, "phases", "code", "plan.md")


def _plan_dir_contains(tdir, path):
    """True if path's realpath stays within <tdir>/phases/code/ -- guards
    against an escaping --plan describing bytes outside the ticket partition."""
    base = os.path.realpath(os.path.join(tdir, "phases", "code"))
    target = os.path.realpath(path)
    return target == base or target.startswith(base + os.sep)


def _fold_active(tdir):
    """Mirrors code/SKILL.md's fold trigger: specs/ absent, or present with no
    non-blank .md content."""
    specs_dir = os.path.join(tdir, "specs")
    if not os.path.isdir(specs_dir):
        return True
    for name in sorted(os.listdir(specs_dir)):
        if not name.endswith(".md"):
            continue
        try:
            with open(os.path.join(specs_dir, name), "r", encoding="utf-8") as fh:
                if fh.read().strip():
                    return False
        except OSError:
            continue
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticket")
    parser.add_argument("--plan")
    args = parser.parse_args()

    cwd = os.getcwd()
    try:
        ctx = lib.build_context(cwd)
    except lib.GateError as exc:
        sys.stderr.write("acs plan-approval: %s\n" % exc)
        sys.exit(2)

    # Shared resolution (MAR-521 review): one implementation of
    # resolve -> find -> refuse-if-archived, in acs_lib.resolve_active_partition.
    try:
        ticket_id, tdir, _archived = lib.resolve_active_partition(
            cwd, ctx, explicit=args.ticket)
    except lib.GateError as exc:
        sys.stderr.write("acs plan-approval: %s\n" % exc)
        sys.exit(2)

    ticket = lib.load_ticket(tdir)
    if not isinstance(ticket, dict):
        sys.stderr.write("acs plan-approval: no readable ticket.json for %s\n" % ticket_id)
        sys.exit(2)

    # Approval binds on the two deep delivery paths only (ADR-0095). The path is
    # READ, never derived here: /acs:ship judged it once from this very plan and
    # recorded it, so recomputing would be a second opinion about a decision that
    # has already been made and acted on.
    delivery_path = workflow.recorded_delivery_path(tdir, ticket_id)
    if delivery_path is None:
        # No path yet means the plan has not been judged, which means nothing
        # downstream is waiting on an approval. Not an error -- just not due.
        print(json.dumps({"ok": True, "skipped": "unclassified",
                          "delivery_path": None, "plan_approved": False}, indent=2))
        sys.exit(0)
    if delivery_path not in APPROVAL_PATHS:
        print(json.dumps({"ok": True, "skipped": "delivery_path",
                          "delivery_path": delivery_path,
                          "plan_approved": False}, indent=2))
        sys.exit(0)

    plan_path = _resolve_plan_path(tdir, args.plan)
    if not _plan_dir_contains(tdir, plan_path):
        sys.stderr.write(
            "acs plan-approval: --plan must resolve within <partition>/phases/code/\n")
        sys.exit(2)

    try:
        with open(plan_path, "r", encoding="utf-8") as fh:
            plan_text = fh.read()
    except OSError:
        plan_text = None

    state = lib.load_state(tdir, "code", ticket_id)

    if plan_text is None:
        eligible, evaluation = False, {"inputs": {}, "checks": {},
                                       "failures": ["plan-artifact-missing"]}
    else:
        eligible, evaluation = lib.plan_approval_eligible(
            plan_text, ctx["settings"], _fold_active(tdir))

    existing = lib.read_json(record_path(tdir))
    if (plan_text is not None and eligible and isinstance(existing, dict)
            and existing.get("eligible") is True
            and existing.get("plan_sha256") == evaluation["inputs"].get("plan_sha256")):
        state["states"]["plan_approved"] = True
        lib.write_json(lib.state_path(tdir, "code"), state)
        print(json.dumps({"ok": True, "skipped": "already-approved",
                          "eligible": True, "plan_approved": True}, indent=2))
        sys.exit(0)

    if eligible:
        record = {
            "ticket_id": ticket_id,
            "skill": "code",
            "delivery_path": delivery_path,
            "approved_at": lib.now_iso(),
            "eligible": True,
            "plan_path": os.path.relpath(plan_path, tdir),
            "plan_sha256": evaluation["inputs"]["plan_sha256"],
            "predicate": {
                "function": "acs_lib.plan_approval_eligible",
                "inputs": evaluation["inputs"],
                "checks": evaluation["checks"],
                "failures": evaluation["failures"],
            },
            "writer": "plan-approval.py",
        }
        lib.write_json(record_path(tdir), record)

    state["states"]["plan_approved"] = bool(eligible)
    lib.write_json(lib.state_path(tdir, "code"), state)

    print(json.dumps({"ok": True, "eligible": bool(eligible),
                      "plan_approved": bool(eligible), "delivery_path": delivery_path,
                      "failures": evaluation.get("failures", [])}, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
