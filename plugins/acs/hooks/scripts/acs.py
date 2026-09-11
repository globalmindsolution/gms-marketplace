#!/usr/bin/env python3
"""acs.py — the single deterministic entry point for the acs pipeline.

ADR 0001's rule is that a skill reaches Python through a CLI, never by naming a
function for the model to invoke however it sees fit. The SKILL.md files broke
that rule in one direction only: they name `acs_lib` functions — derive_lane,
guard_axes, escalate_lane, save_ticket, update_pipeline, update_index,
record_escalation_event, recommend_stakes, confirm_deescalation — with no
command to reach them, so a coordinator had to improvise heredoc Python. Every
such function is reachable here as a subcommand that takes flags and prints one
JSON object.

Two kinds of subcommand live behind this front door:

  * Implemented here — the verbs that had NO entry point at all (the gap above):
    context, gate, lane, stakes, ticket, pr, tracker, readiness, lock, filemap,
    verdict, phase, slug, fanout, doctor, workflow, artifacts.
  * Delegated — the verbs an existing script already implements: `start`
    (skill-start.py), `finish` (pipeline-step.py), `plan check`
    (plan-approval.py), `setup detect|apply` (setup_wizard.py). Those scripts stay the implementation and keep working
    when called directly; acs.py forwards argv to them and returns their exit
    code unchanged. Nothing was reimplemented, so no behaviour could drift.

Conventions, uniform across every subcommand:

  * stdout is exactly one JSON object, pretty-printed (delegated subcommands
    pass their script's own stdout through).
  * A usage or precondition failure writes `acs <command>: <reason>` to stderr
    and exits 2 — the same shape and code the existing scripts use.
  * Exit 0 means the command ran; it does NOT mean the answer was yes. Read
    the JSON (`escalated`, `eligible`, `ok`) for the verdict.

Usage:
  acs.py context
  acs.py gate --skill code [--ticket MAR-1]
  acs.py start --skill code --args MAR-1
  acs.py finish --ticket MAR-1 --skill test --status completed
  acs.py lane derive --size large --stakes high --type task
  acs.py lane escalate --current-lane SMALL --size large --stakes high --type task
  acs.py lane apply --ticket MAR-1 --proposed-stakes high --trigger high_stakes_paths
  acs.py lane deescalate --ticket MAR-1 --size small --stakes low --clarify-ref C-2
  acs.py stakes recommend --path plugins/acs/hooks/scripts/acs_lib/state.py
  acs.py stakes guard --current-size small --current-stakes normal --proposed-stakes high
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
  acs.py verdict show --iteration 2
  acs.py verdict merge --iteration 2
  acs.py plan check --ticket MAR-1
  acs.py setup detect
  acs.py setup apply --answers answers.json
  acs.py phase validate --skill code --result-file result.json
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
from acs_commands import (CONTEXT_KEYS, cmd_context, cmd_doctor,  # noqa: E402,F401
    cmd_fanout_batches, cmd_filemap_set, cmd_filemap_show, cmd_gate,
    cmd_lane_apply, cmd_lane_deescalate, cmd_lane_derive, cmd_lane_escalate,
    cmd_lane_rank, cmd_lock_force_unlock, cmd_lock_status, cmd_phase_validate,
    cmd_pr_metadata_fill, cmd_readiness, cmd_slug, cmd_stakes_guard,
    cmd_stakes_recommend, cmd_ticket_save, cmd_ticket_show, cmd_tracker_sync,
    cmd_verdict_merge, cmd_verdict_show, cmd_workflow_next, cmd_workflow_show,
    cmd_workflow_validate, cmd_artifacts_migrate, cmd_artifacts_show)

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

#: Subcommands this CLI forwards to the script that already implements them.
#: The script remains the implementation and stays callable on its own; acs.py
#: is the documented front door. Values are argv[0] under SCRIPTS.
DELEGATED = {
    "start": "skill-start.py",
    "finish": "pipeline-step.py",
    "plan": "plan-approval.py",
    "setup": "setup_wizard.py",
}

SIZES = ("trivial", "small", "standard", "large")
STAKES = ("low", "normal", "high")


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

    lane = group("lane", help="lane derivation, escalation and the audited apply")
    lane_sub = lane.add_subparsers(dest="cmd")

    derive = lane_sub.add_parser("derive", help="derive_lane")
    derive.add_argument("--size", choices=SIZES)
    derive.add_argument("--stakes", choices=STAKES)
    derive.add_argument("--needs-design", dest="needs_design", action="store_true")
    derive.add_argument("--type", dest="type", default="task")
    derive.set_defaults(func=cmd_lane_derive)

    rank = lane_sub.add_parser("rank", help="lane_rank")
    rank.add_argument("--lane", required=True)
    rank.set_defaults(func=cmd_lane_rank)

    esc = lane_sub.add_parser("escalate", help="escalate_lane (pure, no write)")
    esc.add_argument("--current-lane", dest="current_lane")
    esc.add_argument("--size", choices=SIZES)
    esc.add_argument("--stakes", choices=STAKES)
    esc.add_argument("--needs-design", dest="needs_design", action="store_true")
    esc.add_argument("--type", dest="type", default="task")
    esc.set_defaults(func=cmd_lane_escalate)

    apply_ = lane_sub.add_parser("apply", help="the audited on-trigger escalation sequence")
    apply_.add_argument("--ticket")
    apply_.add_argument("--proposed-size", dest="proposed_size", choices=SIZES)
    apply_.add_argument("--proposed-stakes", dest="proposed_stakes", choices=STAKES)
    apply_.add_argument("--trigger", required=True,
                        help="which trigger fired, recorded on the escalation event")
    apply_.add_argument("--source", help="free-text provenance (defaults to --trigger)")
    apply_.add_argument("--skill", default="code")
    apply_.add_argument("--ceiling-before", dest="ceiling_before", type=int,
                        help="the in-flight ceiling, when already raised this run")
    apply_.set_defaults(func=cmd_lane_apply)

    deesc = lane_sub.add_parser("deescalate", help="confirm_deescalation (needs --clarify-ref)")
    deesc.add_argument("--ticket")
    deesc.add_argument("--size", required=True, choices=SIZES)
    deesc.add_argument("--stakes", required=True, choices=STAKES)
    deesc.add_argument("--clarify-ref", dest="clarify_ref", required=True)
    deesc.set_defaults(func=cmd_lane_deescalate)

    stakes = group("stakes", help="stakes recommendation and the axis guard")
    stakes_sub = stakes.add_subparsers(dest="cmd")

    rec = stakes_sub.add_parser("recommend", help="recommend_stakes over changed paths")
    rec.add_argument("--path", action="append", default=[])
    rec.add_argument("--paths-from", dest="paths_from", metavar="FILE",
                     help="read paths one per line ('-' for stdin)")
    rec.set_defaults(func=cmd_stakes_recommend)

    guard = stakes_sub.add_parser("guard", help="guard_axes")
    guard.add_argument("--current-size", dest="current_size", choices=SIZES)
    guard.add_argument("--current-stakes", dest="current_stakes", choices=STAKES)
    guard.add_argument("--proposed-size", dest="proposed_size", choices=SIZES)
    guard.add_argument("--proposed-stakes", dest="proposed_stakes", choices=STAKES)
    guard.set_defaults(func=cmd_stakes_guard)

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
    lstatus.add_argument("--ticket")
    lstatus.set_defaults(func=cmd_lock_status)

    lforce = lock_sub.add_parser("force-unlock", help="break a lock, recording who and why")
    lforce.add_argument("--ticket")
    lforce.add_argument("--reason", required=True,
                        help="why the lock is being broken; recorded in the audit ledger")
    lforce.add_argument("--actor", help="who decided, when it was not the running checkout")
    lforce.add_argument("--force", action="store_true",
                        help="break the lock even when this checkout is its holder")
    lforce.set_defaults(func=cmd_lock_force_unlock)
    filemap = group("filemap", help="the executor file map the write guard enforces")
    filemap_sub = filemap.add_subparsers(dest="cmd")

    fmset = filemap_sub.add_parser("set", help="declare one executor task's file map")
    fmset.add_argument("--ticket")
    fmset.add_argument("--skill", default="code")
    fmset.add_argument("--iteration", type=int, default=1)
    fmset.add_argument("--task", type=int, required=True, help="the executor task index")
    fmset.add_argument("--file", action="append", default=[],
                       help="a repo-relative path the task may write (repeatable)")
    fmset.add_argument("--files-from", dest="files_from", metavar="FILE",
                       help="read paths one per line ('-' for stdin)")
    fmset.set_defaults(func=cmd_filemap_set)

    fmshow = filemap_sub.add_parser("show", help="the declared map and the enforced union")
    fmshow.add_argument("--ticket")
    fmshow.add_argument("--skill", default="code")
    fmshow.add_argument("--iteration", type=int, default=1)
    fmshow.set_defaults(func=cmd_filemap_show)
    verdict = group("verdict", help="the verifier's verdict document")
    verdict_sub = verdict.add_subparsers(dest="cmd")

    vshow = verdict_sub.add_parser("show", help="read and validate one verdict")
    vshow.add_argument("--ticket")
    vshow.add_argument("--skill", default="code")
    vshow.add_argument("--iteration", type=int, default=1)
    vshow.add_argument("--lens", choices=list(lib.LENSES))
    vshow.set_defaults(func=cmd_verdict_show)

    vmerge = verdict_sub.add_parser("merge", help="merge the full-depth lens verdicts")
    vmerge.add_argument("--ticket")
    vmerge.add_argument("--skill", default="code")
    vmerge.add_argument("--iteration", type=int, default=1)
    vmerge.add_argument("--lens", action="append", choices=list(lib.LENSES),
                        help="restrict the merge to these lenses (default: all four)")
    vmerge.set_defaults(func=cmd_verdict_merge)

    phase = group("phase", help="phase artifacts")
    phase_sub = phase.add_subparsers(dest="cmd")
    pval = phase_sub.add_parser("validate", help="check a result document before the post-hook")
    pval.add_argument("--skill", required=True)
    pval.add_argument("--result-file", dest="result_file", metavar="FILE")
    pval.set_defaults(func=cmd_phase_validate)

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

    wnext = workflow_sub.add_parser("next", help="the READY steps for a ticket, per pipeline-state.json")
    wnext.add_argument("--ticket")
    wnext.add_argument("--dry-run", dest="dry_run", action="store_true",
                       help="evaluate without recording skipped steps in the ledger")
    wnext.set_defaults(func=cmd_workflow_next)

    artifacts = group("artifacts", help="the ticket documents in the repo docs tree")
    artifacts_sub = artifacts.add_subparsers(dest="cmd")

    amigrate = artifacts_sub.add_parser(
        "migrate", help="move ticket.json, design.md and the legacy plan into <tickets_path>/<ID>/ once")
    amigrate.add_argument("--dry-run", dest="dry_run", action="store_true",
                          help="list the moves and write nothing")
    amigrate.set_defaults(func=cmd_artifacts_migrate)

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
        # A group with no subcommand ("acs.py lane") — show THAT group's usage,
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
