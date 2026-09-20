#!/usr/bin/env python3
"""plan-approval.py — the sole writer of steps/create-impl-plan/plan-approval.json.

On a `standard`/`complex` delivery-path run, records the deterministic verdict
of acs_lib.plan_approval_eligible against the current plan, once per approved
plan digest, and mirrors the outcome into the step's states.plan_approved.
Never a subagent Write, never a gate.

The approval now lives beside the plan it approves, in
`steps/create-impl-plan/`, rather than in a mirror under the code step. There
is ONE plan (§4.2) and `plan_sha256` hashes it: the mirror existed only
because the plan had two homes, and an approval that hashes a copy is an
approval of the wrong bytes the moment the copy drifts.

It also answers the plan's OTHER machine-readable question, under a verb of
its own: `plan-approval.py path` prints the `## Contract` block's
`delivery_path` and `owes` flags and writes nothing. That read belongs here
because this script already resolves the run, the plan and the contract, and
because ADR 0001 says a skill reaches Python through a CLI — `/acs:code` used
to open-code the same three calls in a heredoc inside its SKILL.md, which is
the pattern the rule exists to prevent.

Reachable as `acs.py plan check` and `acs.py plan path` (MAR-521, §4.8) —
acs.py drops the `check` verb and forwards the rest here unchanged; this
script stays the implementation.

Usage:
  plan-approval.py [path] [--run <run-id>] [--plan <path>]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_lib import plan_contract  # noqa: E402

#: The delivery paths on which an approved plan is a precondition for /acs:code
#: (ADR-0095). The two cheap paths run against the plan without one, and their
#: legs say so; the plan-conformance review dimension then reports N/A.
APPROVAL_PATHS = ("standard", "complex")

RECORD_NAME = "plan-approval.json"


PLAN_STEP = "create-impl-plan"


def _step_dir(rdir):
    return os.path.join(rdir, "steps", PLAN_STEP)


def record_path(rdir):
    return os.path.join(_step_dir(rdir), RECORD_NAME)


def _resolve_plan_path(rdir, explicit):
    """--plan wins; else steps/create-impl-plan/plan.md -- the only name ever
    read or written for the plan artifact. There is ONE plan now (§4.2): the
    approval mirror is gone, and with it the chance of approving bytes that a
    later edit to the original left behind."""
    if explicit:
        return explicit
    return os.path.join(_step_dir(rdir), "plan.md")


def _plan_dir_contains(rdir, path):
    """True if path's realpath stays within the plan step's directory --
    guards against an escaping --plan describing bytes outside the run."""
    base = os.path.realpath(_step_dir(rdir))
    target = os.path.realpath(path)
    return target == base or target.startswith(base + os.sep)


def _emit_contract(rdir, plan_path):
    """`plan path` — the plan's Contract block, read and printed, nothing written.

    `/acs:code` dispatches to its leg from `delivery_path`, and the four
    always-run steps read `owes` to decide whether they owe anything (§2.2).
    Both are reads of a decision already made: the path was judged ONCE, by
    `/acs:create-impl-plan`, from the plan's own scope. Nothing here recomputes
    it, and a plan that has not been judged prints `null` rather than a
    guess — an unclassified plan is a plan that is not ready to dispatch, and
    saying so is the answer.

    `contract_errors` carries what `plan_contract.errors` found, so a caller
    that sees `delivery_path: null` can tell "no Contract block yet" from
    "a Contract block that does not parse"."""
    contract = plan_contract.read(plan_path)
    print(json.dumps({
        "ok": True,
        "run_dir": rdir,
        "plan": plan_path if os.path.isfile(plan_path) else None,
        "delivery_path": plan_contract.delivery_path(contract),
        "owes": {key: plan_contract.owes(contract, key)
                 for key in plan_contract.OWES_KEYS},
        "contract_errors": plan_contract.errors(contract),
    }, indent=2))


def main():
    parser = argparse.ArgumentParser()
    # `check` is the default so that `acs.py plan check`, which forwards an
    # empty argv after dropping the verb, keeps meaning what it always meant.
    parser.add_argument("verb", nargs="?", choices=("check", "path"), default="check",
                        help="check: record the approval verdict (default). "
                             "path: print the plan's Contract block, writing nothing.")
    parser.add_argument("--run", help="a run other than this checkout's current one")
    parser.add_argument("--plan")
    args = parser.parse_args()

    cwd = os.getcwd()
    try:
        ctx = lib.build_context(cwd)
    except lib.GateError as exc:
        sys.stderr.write("acs plan-approval: %s\n" % exc)
        sys.exit(2)

    repo = lib.repo_dir(ctx["workspace"], ctx["repo_id"])
    run_id = args.run or lib.current_run_id(ctx)
    if not run_id:
        sys.stderr.write("acs plan-approval: no current run for this checkout (pass --run).\n")
        sys.exit(2)
    rdir = lib.run_dir(repo, run_id)
    if lib.load_run(rdir) is None:
        sys.stderr.write("acs plan-approval: no run %s at %s\n" % (run_id, rdir))
        sys.exit(2)

    if args.verb == "path":
        # The same containment guard `check` applies below: a read is still a
        # read of bytes, and an escaping --plan would print a contract that
        # belongs to no run.
        plan_path = _resolve_plan_path(rdir, args.plan)
        if not _plan_dir_contains(rdir, plan_path):
            sys.stderr.write(
                "acs plan-approval: --plan must resolve within steps/%s/\n" % PLAN_STEP)
            sys.exit(2)
        _emit_contract(rdir, plan_path)
        sys.exit(0)

    # Approval binds on the two deep delivery paths only. The path is READ from
    # the plan's own ## Contract block, never derived here: it was judged once,
    # by the plan, from the plan's own scope (§3.2), and recomputing it would
    # be a second opinion about a decision already made and acted on.
    plan_path = _resolve_plan_path(rdir, args.plan)
    # The containment guard runs BEFORE the first read, as it does on `path`.
    # It used to sit after `plan_contract.read`, so an escaping --plan was
    # opened and parsed and only then refused -- the guard reported a refusal
    # for bytes it had already read.
    if not _plan_dir_contains(rdir, plan_path):
        sys.stderr.write(
            "acs plan-approval: --plan must resolve within steps/%s/\n" % PLAN_STEP)
        sys.exit(2)
    delivery_path = plan_contract.delivery_path(plan_contract.read(plan_path))
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

    try:
        with open(plan_path, "r", encoding="utf-8") as fh:
            plan_text = fh.read()
    except OSError:
        plan_text = None

    state = lib.load_step_state(rdir, PLAN_STEP, run_id)

    if plan_text is None:
        eligible, evaluation = False, {"inputs": {}, "checks": {},
                                       "failures": ["plan-artifact-missing"]}
    else:
        # No fold argument: `plan_approval_eligible` accepts and ignores one
        # (the spec fold has no separate section set any more), and computing
        # it meant listing and reading every specs/*.md on each check.
        eligible, evaluation = lib.plan_approval_eligible(plan_text, ctx["settings"])

    existing = lib.read_json(record_path(rdir))
    if (plan_text is not None and eligible and isinstance(existing, dict)
            and existing.get("eligible") is True
            and existing.get("plan_sha256") == evaluation["inputs"].get("plan_sha256")):
        state.setdefault("states", {})["plan_approved"] = True
        lib.save_step_state(rdir, PLAN_STEP, state)
        print(json.dumps({"ok": True, "skipped": "already-approved",
                          "eligible": True, "plan_approved": True}, indent=2))
        sys.exit(0)

    if eligible:
        record = {
            "run_id": run_id,
            "skill": PLAN_STEP,
            "delivery_path": delivery_path,
            "approved_at": lib.now_iso(),
            "eligible": True,
            "plan_path": os.path.relpath(plan_path, rdir),
            "plan_sha256": evaluation["inputs"]["plan_sha256"],
            "predicate": {
                "function": "acs_lib.plan_approval_eligible",
                "inputs": evaluation["inputs"],
                "checks": evaluation["checks"],
                "failures": evaluation["failures"],
            },
            "writer": "plan-approval.py",
        }
        lib.write_json(record_path(rdir), record)

    state.setdefault("states", {})["plan_approved"] = bool(eligible)
    lib.save_step_state(rdir, PLAN_STEP, state)

    print(json.dumps({"ok": True, "eligible": bool(eligible),
                      "plan_approved": bool(eligible), "delivery_path": delivery_path,
                      "failures": evaluation.get("failures", [])}, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
