#!/usr/bin/env python3
"""handoff.py — graceful session handoff for this checkout's run.

Run by the /acs:handoff utility skill (or proactively by a coordinator under
context pressure) AFTER it has flushed all soft context to the run directory:

  * finalizes the open invocation and transitions the in-progress STEP to
    `interrupted` with the stop_reason that says which kind of ending it was;
  * releases the run's .lock so ANY session can take over;
  * prints the exact command to continue in a fresh session.

`handed_off` is gone as a status. It named a REASON wearing a status: a handoff
is an interruption, `interrupted` is the one resumable state, and `stop_reason`
carries why (§4.3). What used to be `status: handed_off` is now
`status: interrupted` + `stop_reason: context_pressure`.

Usage:
  handoff.py --summary "done: tasks 1-2; in flight: task 3; next: coverage"
  handoff.py --summary-file <path> [--run <run-id>]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402


def last_interrupted_step(rdir, run_id):
    """The skill whose latest invocation on this run ended `interrupted`, the
    most recent first; None when there is none."""
    base = os.path.join(rdir, "steps")
    best = None
    for skill in sorted(os.listdir(base)) if os.path.isdir(base) else ():
        if not os.path.isfile(lib.state_path(rdir, skill)):
            continue
        last = lib.last_invocation(lib.load_state(rdir, skill, run_id)) or {}
        if last.get("status") == "interrupted":
            key = last.get("ended_at") or ""
            if best is None or key >= best[0]:
                best = (key, skill)
    return best[1] if best else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", help="handoff summary text")
    parser.add_argument("--summary-file", help="file containing the handoff summary")
    parser.add_argument("--run", help="run id (defaults to this checkout's pointer)")
    parser.add_argument("--ticket", dest="run", help=argparse.SUPPRESS)
    parser.add_argument("--stop-reason", default="context_pressure",
                        choices=list(lib.STOP_REASONS),
                        help="why the session is stopping (default: context_pressure)")
    args = parser.parse_args()

    summary = args.summary
    if args.summary_file:
        with open(args.summary_file, "r", encoding="utf-8") as fh:
            summary = fh.read().strip()
    if not summary:
        sys.stderr.write("acs handoff: a handoff summary is required "
                         "(--summary or --summary-file)\n")
        sys.exit(2)

    cwd = os.getcwd()
    try:
        ctx = lib.build_context(cwd)
    except lib.GateError as exc:
        sys.stderr.write("acs handoff: %s\n" % exc)
        sys.exit(2)

    repo = lib.repo_dir(ctx["workspace"], ctx["repo_id"])
    run_id = args.run or lib.current_run_id(ctx)
    if not run_id:
        sys.stderr.write("acs handoff: no current run for this checkout "
                         "(nothing to hand off)\n")
        sys.exit(2)
    rdir = lib.run_dir(repo, run_id)
    doc = lib.load_run(rdir)
    if doc is None:
        sys.stderr.write("acs handoff: no run recorded at %s\n" % rdir)
        sys.exit(2)

    # The step this checkout is on: the pointer first, then the run ledger.
    # One resolution, shared with the Stop hook and PreCompact, so the three
    # cannot disagree -- and the pointer half is what makes a standalone skill
    # the workflow does not name (I5 keeps it out of the ledger) resumable.
    # Every step in flight: a parallel group's members all are, and each is
    # finalized, so none is left claiming to run in a session that is gone.
    steps = lib.in_flight_steps(rdir, ctx, run_id)

    handed = []
    # Releasing the lock IS the handoff (see this file's docstring): the next
    # session cannot pick the run up while it is held, so it is released
    # whatever the writes above it do.
    try:
        for step in steps:
            lib.finalize_invocation(rdir, step, run_id, {
                "status": "interrupted",
                "stop_reason": args.stop_reason,
                "handoff_summary": summary,
            })
        if steps:
            lib.write_handoff_context(rdir, run_id, steps[0])
            wf = lib.validate_workflow_file(
                lib.resolve_workflow(ctx["checkout_root"])["path"])
        for step in steps:
            # The RUN transition, only for a step the workflow names. A skill
            # invoked on its own has step state but no position in a run, and
            # I5 refuses a `steps` entry the workflow does not name -- the
            # invocation above is recorded either way.
            if lib.has_step(wf, step):
                lib.finish_step(rdir, step, wf, status="interrupted",
                                stop_reason=args.stop_reason, summary=summary)
            handed.append(step)
    finally:
        lib.point_checkout_at(ctx, run_id, None)
        lib.release_lock(rdir, cwd)

    # The command that resumes. A step that was in flight is re-run by name; a
    # run with nothing in flight resumes through the workflow, which knows
    # where its cursor is.
    # Several steps in flight means a parallel group, and only /acs:ship runs
    # a group's members together, so that is the command that resumes it.
    # A run with no workflow position -- a delivery ticket's, opened by a
    # product skill -- has no cursor for /acs:ship to follow, so a SECOND
    # handoff (nothing left in flight) named /acs:ship for a create-docs run.
    # Such a run resumes through the skill it last interrupted.
    if not handed and not doc.get("steps"):
        standalone = last_interrupted_step(rdir, run_id)
        handed_again = [standalone] if standalone else []
    else:
        handed_again = handed
    resume = ("/acs:%s %s" % (handed_again[0], run_id) if len(handed_again) == 1
              else "/acs:ship %s" % run_id)
    out = {
        "ok": True,
        "run_id": run_id,
        "step": handed[0] if handed else None,
        "steps": handed,
        "stop_reason": args.stop_reason if handed else None,
        "lock_released": True,
        "continue_with": resume,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
