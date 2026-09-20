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

    # The step this checkout is on, from the run's own ledger. There is at most
    # one in_progress step (I1), so there is nothing to scan and nothing to
    # guess: the ledger either names it or there is nothing to hand off.
    step = lib.in_progress_step(doc)

    handed = None
    metrics_error = None
    # Releasing the lock IS the handoff (see this file's docstring): the next
    # session cannot pick the run up while it is held. update_metrics is
    # repo-guarded and refuses rather than writing unguarded, so it runs inside
    # a try -- a refused metrics write must not interrupt the step and then
    # strand the lock, which is the one outcome that makes the handoff
    # undeliverable.
    try:
        if step:
            _state, entry = lib.finalize_invocation(rdir, step, run_id, {
                "status": "interrupted",
                "stop_reason": args.stop_reason,
                "handoff_summary": summary,
            })
            lib.write_handoff_context(rdir, step, summary)
            wf = lib.validate_workflow_file(
                lib.resolve_workflow(ctx["checkout_root"])["path"])
            lib.finish_step(rdir, step, wf, status="interrupted",
                            stop_reason=args.stop_reason, summary=summary)
            # a handed-off invocation still spent time and tokens -- keep repo
            # metrics consistent with the run ledger
            lib.update_metrics(ctx["workspace"], ctx["repo_id"], run_entry=entry)
            handed = step
    except lib.GuardTimeout as exc:
        metrics_error = str(exc)
        handed = handed or step
    finally:
        lib.point_checkout_at(ctx, run_id, None)
        lib.release_lock(rdir, cwd)

    # The command that resumes. A step that was in flight is re-run by name; a
    # run with nothing in flight resumes through the workflow, which knows
    # where its cursor is.
    resume = "/acs:%s %s" % (handed, run_id) if handed else "/acs:ship %s" % run_id
    out = {
        "ok": True,
        "run_id": run_id,
        "step": handed,
        "stop_reason": args.stop_reason if handed else None,
        "lock_released": True,
        "continue_with": resume,
    }
    if metrics_error:
        out.update({"metrics_updated": False, "error": metrics_error})
    print(json.dumps(out, indent=2))
    if metrics_error:
        sys.stderr.write(
            "acs handoff: %s\nThe step is finalized as interrupted and the lock IS "
            "released, so %s can be resumed; only metrics.json was not updated, "
            "so this invocation's tokens and cost are lost from it.\n"
            % (metrics_error, run_id))
        sys.exit(2)


if __name__ == "__main__":
    main()
