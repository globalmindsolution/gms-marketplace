#!/usr/bin/env python3
"""acs.py — the single deterministic entry point for the acs pipeline.

ADR 0001's rule is that a skill reaches Python through a CLI, never by naming a
function for the model to invoke however it sees fit. The SKILL.md files broke
that rule in one direction only: they name `acs_lib` functions — save_ticket,
update_pipeline, update_index, record_delivery_path, plan_approval_eligible — with no
command to reach them, so a coordinator had to improvise heredoc Python. Every
such function is reachable here as a subcommand that takes flags and prints one
JSON object.

Two kinds of subcommand live behind this front door:

  * Implemented here — the verbs that had NO entry point at all (the gap above):
    context, gate, run, step, result, ticket, pr, tracker, readiness, lock,
    filemap, guard, verdict, slug, fanout, doctor, workflow, artifacts.
  * Delegated — the verbs an existing script already implements: `plan check`
    (plan-approval.py), `setup detect|apply` (setup_wizard.py). Those scripts stay the implementation and keep working
    when called directly; acs.py forwards argv to them and returns their exit
    code unchanged. Nothing was reimplemented, so no behaviour could drift.

Conventions, uniform across every subcommand:

  * stdout is exactly one JSON object, pretty-printed (delegated subcommands
    pass their script's own stdout through).
  * A usage or precondition failure writes `acs <command>: <reason>` to stderr
    and exits 2 — the same shape and code the existing scripts use.
  * Exit 0 means the command ran; it does NOT mean the answer was yes. Read
    the JSON (`delivery_path`, `eligible`, `ok`) for the verdict.

Usage:
  acs.py context
  acs.py gate --skill code [--ticket MAR-1]
  acs.py start --skill code --args MAR-1
  acs.py finish --ticket MAR-1 --skill test --status completed
  acs.py path show --ticket MAR-1
  acs.py path set --ticket MAR-1 --path standard --reason "adds a public endpoint and migrates orders"
  acs.py ticket show --ticket MAR-1
  acs.py ticket save --ticket MAR-1 --from ticket.json
  acs.py pr metadata fill --ticket MAR-1 --pr 42
  acs.py tracker sync --ticket MAR-1 --ticket MAR-2
  acs.py readiness --pr 42
  acs.py readiness --from recorded-pr.json
  acs.py lock status --ticket MAR-1
  acs.py lock force-unlock --ticket MAR-1 --reason "the holding container died"
  acs.py filemap set --task 1 --file src/a.py --file tests/test_a.py
  acs.py filemap show
  acs.py guard events --ticket MAR-1
  acs.py verdict show --iteration 2
  acs.py verdict merge --iteration 2
  acs.py plan check --ticket MAR-1
  acs.py setup detect
  acs.py setup apply --answers answers.json
  acs.py result validate --skill code result.json
  acs.py slug --text "Introduce the acs CLI"
  acs.py doctor
  acs.py workflow show
  acs.py workflow validate [--file PATH]
  acs.py workflow next --ticket MAR-1 [--dry-run]
  acs.py artifacts migrate [--dry-run]
  acs.py artifacts show --ticket MAR-1
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402

# The handlers and the shared CLI helpers, split out by MAR-572 to keep this
# entry point under E1's 800-line budget. Re-exported below rather than merely
# imported: `acs.cmd_context` and `acs.emit` are how the tests and any caller
# that reached them by name already resolve them, and code motion must not
# change that.
from acs_cli import (context_or_die, die, emit, load_ticket_or_die,  # noqa: E402,F401
    partition_or_die, read_json_arg)
from acs_commands import (CONTEXT_KEYS, cmd_artifacts_show, cmd_context,  # noqa: E402,F401
    cmd_doctor, cmd_fanout_batches, cmd_filemap_set, cmd_filemap_show,
    cmd_gate, cmd_guard_events, cmd_lock_force_unlock, cmd_lock_status,
    cmd_pr_metadata_fill, cmd_readiness, cmd_result_validate, cmd_run_abandon,
    cmd_run_check, cmd_run_new, cmd_run_next, cmd_run_show, cmd_slug,
    cmd_step_finish, cmd_step_show, cmd_step_start, cmd_ticket_save,
    cmd_ticket_show, cmd_tracker_sync, cmd_verdict_show,
    cmd_workflow_show, cmd_workflow_validate)

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

#: Subcommands this CLI forwards to the script that already implements them.
#: The script remains the implementation and stays callable on its own; acs.py
#: is the documented front door. Values are argv[0] under SCRIPTS.
DELEGATED = {
    "plan": "plan-approval.py",
    "setup": "setup_wizard.py",
}



# ---------------------------------------------------------------------------
# Delegation
# ---------------------------------------------------------------------------

def delegate(command, argv):
    """Forward argv to the script that implements `command`, returning its exit
    code unchanged. stdout/stderr are inherited, so the script's own JSON and
    error text reach the caller untouched."""
    script = os.path.join(SCRIPTS, DELEGATED[command])
    if not os.path.isfile(script):
        die(command, "delegate %s is missing" % DELEGATED[command])
    proc = subprocess.run([sys.executable, script] + list(argv))
    return proc.returncode


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser():
    """Return (parser, groups) where `groups` maps a group name to its parser.

    That map is argparse's own `sub.choices` -- keeping a module-level copy
    would go stale the moment build_parser() ran twice, pointing at the newest
    parser's children while main() held an older one."""
    parser = argparse.ArgumentParser(prog="acs.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="group")
    group = sub.add_parser

    ctx = group("context", help="resolved settings, workspace and paths")
    ctx.add_argument("--ticket", help="also resolve this ticket's partition")
    ctx.set_defaults(func=cmd_context)

    gate = group("gate", help="run a skill's pre-gate without the skill")
    gate.add_argument("--skill", required=True)
    gate.add_argument("--ticket")
    gate.set_defaults(func=cmd_gate)

    run = group("run", help="the RUN machine: runs/<run-id>/run.json")
    run_sub = run.add_subparsers(dest="cmd")

    rnew = run_sub.add_parser("new", help="record a new run over a subject")
    rnew.add_argument("--ticket", help="subject: a ticket id")
    rnew.add_argument("--prompt", help="subject: free text")
    rnew.add_argument("--document", help="subject: a path to a document")
    rnew.set_defaults(func=cmd_run_new)

    rshow = run_sub.add_parser("show", help="the run ledger")
    rshow.add_argument("--run", help="a run other than this checkout's current one")
    rshow.set_defaults(func=cmd_run_show)

    rnext = run_sub.add_parser("next", help="the cursor: the first step not completed")
    rnext.add_argument("--run")
    rnext.set_defaults(func=cmd_run_next)

    rcheck = run_sub.add_parser("check", help="invariants I1-I5")
    rcheck.add_argument("--run")
    rcheck.set_defaults(func=cmd_run_check)

    rabandon = run_sub.add_parser("abandon", help="give up on a run (a human's call)")
    rabandon.add_argument("--run")
    rabandon.add_argument("--reason", help="why; required")
    rabandon.set_defaults(func=cmd_run_abandon)

    step = group("step", help="the STEP machine: steps/<skill>/state.json")
    step_sub = step.add_subparsers(dest="cmd")

    sstart = step_sub.add_parser("start", help="step -> in_progress")
    sstart.add_argument("--step", required=True,
                        help="validated against the resolved workflow, not an enum")
    sstart.add_argument("--run")
    sstart.add_argument("--pr", help="/acs:merge-pr's exempt-pr mode: N, #N or a PR "
                                     "URL. Resolves no run and writes nothing.")
    sstart.add_argument("--ticket", help="name the subject explicitly")
    sstart.add_argument("--args", help="the invocation's raw argument text")
    sstart.add_argument("--allocate", action="store_true",
                        help="mint the delivery ticket a product-level skill works "
                             "under, unless --ticket (or an --args value that IS an "
                             "id) names a live partition to resume")
    sstart.add_argument("--doc-set", dest="doc_set", choices=sorted(lib.DOC_SETS),
                        help="the doc set a /acs:create-docs run delivers (required "
                             "with --step create-docs --allocate)")
    sstart.add_argument("--title", help="the minted ticket's title")
    sstart.add_argument("--type", dest="ttype", default="task",
                        help="the minted ticket's type (create-ticket only)")
    sstart.add_argument("--seed-next", dest="seed_next", type=int,
                        help="repair the id counter for a newly minted ticket "
                             "(only valid together with --allocate)")
    sstart.set_defaults(func=cmd_step_start)

    sfinish = step_sub.add_parser("finish", help="step -> completed / failed / interrupted")
    sfinish.add_argument("--step", required=True)
    sfinish.add_argument("--run")
    sfinish.add_argument("--status", choices=["completed", "failed", "interrupted"],
                         help="override; normally read from result.json")
    sfinish.add_argument("--outcome", help="override; normally read from result.json")
    sfinish.add_argument("--summary")
    sfinish.add_argument("--stop-reason", dest="stop_reason",
                         choices=["session_end", "needs_input", "context_pressure"])
    sfinish.add_argument("--no-op", dest="no_op", action="store_true",
                         help="the pre-hook found nothing owed; no coordinator ran")
    sfinish.set_defaults(func=cmd_step_finish)

    sshow = step_sub.add_parser("show", help="one step's own state")
    sshow.add_argument("--step", required=True)
    sshow.add_argument("--run")
    sshow.set_defaults(func=cmd_step_show)

    result = group("result", help="the step result document")
    result_sub = result.add_subparsers(dest="cmd")
    rvalidate = result_sub.add_parser("validate",
                                      help="check a result before the post-hook consumes it")
    rvalidate.add_argument("--skill", required=True)
    rvalidate.add_argument("result_file", nargs="?", default="-",
                           help="a path, or '-'/omitted for stdin")
    rvalidate.set_defaults(func=cmd_result_validate)

    ticket = group("ticket", help="read and write ticket.json")
    ticket_sub = ticket.add_subparsers(dest="cmd")

    show = ticket_sub.add_parser("show", help="load_ticket")
    show.add_argument("--ticket")
    show.set_defaults(func=cmd_ticket_show)

    save = ticket_sub.add_parser("save", help="save_ticket + update_index")
    save.add_argument("--ticket")
    save.add_argument("--from", dest="source", metavar="FILE",
                      help="the ticket document ('-' or omitted reads stdin)")
    save.set_defaults(func=cmd_ticket_save)

    pr = group("pr", help="PR metadata the forge, not the model, decides")
    pr_sub = pr.add_subparsers(dest="cmd")
    metadata = pr_sub.add_parser("metadata", help="PR metadata fill")
    metadata_sub = metadata.add_subparsers(dest="subcmd")
    fill = metadata_sub.add_parser("fill", help="create-pr step 6a in one call")
    fill.add_argument("--ticket")
    fill.add_argument("--pr", required=True, help="the PR number")
    fill.add_argument("--url", help="the PR url (looked up through gh when omitted)")
    fill.add_argument("--author", help="the PR author's login, excluded from reviewers")
    fill.add_argument("--gh-replay", dest="gh_replay", metavar="FILE",
                      help="replay recorded gh output instead of calling gh")
    fill.set_defaults(func=cmd_pr_metadata_fill)

    tracker = group("tracker", help="tracker sync")
    tracker_sub = tracker.add_subparsers(dest="cmd")
    sync = tracker_sub.add_parser("sync", help="create-ticket step 5's batch in one call")
    sync.add_argument("--ticket", action="append", default=[], required=True,
                      help="a ticket to sync (repeatable); the batch order is preserved")
    sync.add_argument("--dry-run", dest="dry_run", action="store_true",
                      help="report which tickets the sync set covers, and write nothing")
    sync.add_argument("--gh-replay", dest="gh_replay", metavar="FILE",
                      help="replay recorded gh output instead of calling gh")
    sync.set_defaults(func=cmd_tracker_sync)
    ready = group("readiness", help="merge-pr's four readiness dimensions")
    ready.add_argument("--pr", help="PR number to read through gh")
    ready.add_argument("--from", dest="source", metavar="FILE",
                       help="replay a recorded document instead ('-' reads stdin)")
    ready.set_defaults(func=cmd_readiness)
    lock = group("lock", help="inspect and (audited) break a ticket lock")
    lock_sub = lock.add_subparsers(dest="cmd")

    lstatus = lock_sub.add_parser("status", help="who holds the lock, and on what evidence")
    lstatus.add_argument("--run")
    lstatus.set_defaults(func=cmd_lock_status)

    lforce = lock_sub.add_parser("force-unlock", help="break a lock, recording who and why")
    lforce.add_argument("--run")
    lforce.add_argument("--reason", required=True,
                        help="why the lock is being broken; recorded in the audit ledger")
    lforce.add_argument("--actor", help="who decided, when it was not the running checkout")
    lforce.add_argument("--force", action="store_true",
                        help="break the lock even when this checkout is its holder")
    lforce.set_defaults(func=cmd_lock_force_unlock)
    filemap = group("filemap", help="the executor file map the write guard enforces")
    filemap_sub = filemap.add_subparsers(dest="cmd")

    fmset = filemap_sub.add_parser("set", help="declare one executor task's file map")
    fmset.add_argument("--run")
    fmset.add_argument("--skill", default="code")
    fmset.add_argument("--iteration", type=int, default=1)
    fmset.add_argument("--task", type=int, required=True, help="the executor task index")
    fmset.add_argument("--file", action="append", default=[],
                       help="a repo-relative path the task may write (repeatable)")
    fmset.add_argument("--files-from", dest="files_from", metavar="FILE",
                       help="read paths one per line ('-' for stdin)")
    fmset.set_defaults(func=cmd_filemap_set)

    fmshow = filemap_sub.add_parser("show", help="the declared map and the enforced union")
    fmshow.add_argument("--run")
    fmshow.add_argument("--skill", default="code")
    fmshow.add_argument("--iteration", type=int, default=1)
    fmshow.set_defaults(func=cmd_filemap_show)

    guard = group("guard", help="what the executor file-map guard denied")
    guard_sub = guard.add_subparsers(dest="cmd")

    gevents = guard_sub.add_parser("events", help="the denials the latest run recorded")
    gevents.add_argument("--run")
    gevents.add_argument("--skill", default="code")
    gevents.set_defaults(func=cmd_guard_events)
    verdict = group("verdict", help="the review's verdict document")
    verdict_sub = verdict.add_subparsers(dest="cmd")

    # `verdict merge` went with the per-lens verdict documents it merged. The
    # lenses write prose reports and return candidate findings; adjudication is
    # per finding, and the coordinator writes one verdict (§3.6). There is no
    # arithmetic left to invoke.
    vshow = verdict_sub.add_parser("show", help="read and validate one verdict")
    vshow.add_argument("--run")
    vshow.add_argument("--skill", default="review-code")
    vshow.add_argument("--iteration", type=int, default=1)
    vshow.add_argument("--lens", choices=list(lib.LENSES))
    vshow.set_defaults(func=cmd_verdict_show)

    slug = group("slug", help="slugify (branch and file naming)")
    slug.add_argument("--text", required=True)
    slug.add_argument("--max-len", dest="max_len", type=int, default=40)
    slug.set_defaults(func=cmd_slug)

    fanout = group("fanout", help="epic fan-out helpers")
    fanout_sub = fanout.add_subparsers(dest="cmd")
    batches = fanout_sub.add_parser("batches", help="fanout_batches")
    batches.set_defaults(func=cmd_fanout_batches)

    doctor = group("doctor", help="check_toolchain / missing_tools")
    doctor.set_defaults(func=cmd_doctor)

    workflow = group("workflow", help="the declarative ship pipeline (workflows/ship.yaml)")
    workflow_sub = workflow.add_subparsers(dest="cmd")

    wshow = workflow_sub.add_parser("show", help="the resolved workflow: consumer override or plugin default")
    wshow.set_defaults(func=cmd_workflow_show)

    wvalidate = workflow_sub.add_parser("validate", help="schema + semantic checks; exit 2 names the line")
    wvalidate.add_argument("--file", metavar="PATH",
                           help="validate this file instead of the resolved workflow")
    wvalidate.set_defaults(func=cmd_workflow_validate)


    artifacts = group("artifacts", help="the ticket documents in the repo docs tree")
    artifacts_sub = artifacts.add_subparsers(dest="cmd")

    ashow = artifacts_sub.add_parser("show", help="where one ticket's documents live, and its derived status")
    ashow.add_argument("--ticket")
    ashow.set_defaults(func=cmd_artifacts_show)

    for name in sorted(DELEGATED):
        sub.add_parser(name, add_help=False,
                       help="delegated to %s" % DELEGATED[name])
    return parser, sub.choices


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in DELEGATED:
        rest = argv[1:]
        # `plan check` reads as a verb pair but plan-approval.py takes flags
        # only; drop the verb before forwarding. Everything else goes verbatim,
        # so the delegate owns its own flags and --help.
        if argv[0] == "plan" and rest[:1] == ["check"]:
            rest = rest[1:]
        sys.exit(delegate(argv[0], rest))

    parser, groups = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        # A group with no subcommand ("acs.py path") — show THAT group's usage,
        # which is what names its subcommands; the root help does not.
        (groups.get(getattr(args, "group", None)) or parser).print_help(sys.stderr)
        sys.exit(2)
    try:
        func(args)
    except lib.GateError as exc:
        # The documented contract of this CLI (see the module docstring) is
        # `acs <command>: <reason>` on stderr and exit 2 for a blocked command.
        # GuardTimeout is a GateError raised from deep inside a repo-level
        # write, and without this it reached the operator as a Python traceback
        # and exit 1 -- indistinguishable from a crash, at ten call sites.
        verbs = [a for a in argv[:2] if not a.startswith("-")]
        die(" ".join(verbs) or "command", str(exc))


if __name__ == "__main__":
    main()
