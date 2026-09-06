#!/usr/bin/env python3
"""plan-approval.py — the sole writer of <partition>/phases/code/plan-approval.json.

On a STANDARD/COMPLEX-lane /acs:code run, records the deterministic verdict of
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

    # Recomputed, never the cached ticket["lane"] (SKILL.md:67-70).
    lane = lib.derive_lane(ticket.get("size"), ticket.get("stakes"),
                           ticket.get("needs_design"), ticket.get("type"))

    if lane not in ("STANDARD", "COMPLEX"):
        print(json.dumps({"ok": True, "skipped": "lane", "lane": lane,
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
            "lane": lane,
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
                      "plan_approved": bool(eligible), "lane": lane,
                      "failures": evaluation.get("failures", [])}, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
