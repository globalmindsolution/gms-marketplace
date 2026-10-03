"""acs_analysis_commands — `acs.py analysis <verb>`, the analyze-requirements
controller's front door (ADR-0114).

    acs.py analysis next [--run R]               read-only: the ONE next action
    acs.py analysis plan [--areas a,b] [--run R] declare the survey lanes once
    acs.py analysis record-survey | record-synthesis | record-draft |
                    record-review | record-publication [--run R]
    acs.py analysis record-clarify [--blocking-open] [--run R]
    acs.py analysis publish [--summary S] [--run R]

Every verb but `next` writes `steps/analyze-requirements/loop.json` and prints
`{"ok": true, ..., "next": <the action next would print>}`. A record verb
whose evidence is missing or malformed exits 0 with the loop `blocked` and the
reason in `next` -- it ran; the answer was "not yet". A verb called out of
order exits 2.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import die, emit, run_or_die  # noqa: E402
from acs_lib import analysis_loop as loop_lib  # noqa: E402
from acs_lib import analysis_publish  # noqa: E402


def _resolve(command, explicit):
    run_id, rdir, ctx = run_or_die(command, explicit)
    subject = (lib.load_run(rdir) or {}).get("subject") or {}
    ticket_id = subject.get("ticket_id")
    if not ticket_id:
        die(command, "run %s has no ticket subject; /acs:analyze-requirements analyzes "
                     "one ticket" % run_id)
    tdir, _archived = lib.find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    return run_id, rdir, ctx, ticket_id, tdir


def _next(rdir, loop, ctx):
    action = loop_lib.next_action(rdir, loop, loop_lib.invocations(rdir))
    return lib.agent_sync.with_spawn_names(action, ctx["settings"])


def cmd_analysis_next(args):
    run_id, rdir, _ctx, ticket_id, _tdir = _resolve("analysis next", args.run)
    out = _next(rdir, loop_lib.load_loop(rdir), _ctx)
    emit(dict(out, ok=True, run_id=run_id, ticket_id=ticket_id))


def cmd_analysis_plan(args):
    run_id, rdir, _ctx, ticket_id, _tdir = _resolve("analysis plan", args.run)
    areas = [a for a in (args.areas or "").split(",") if a.strip()]
    try:
        loop = loop_lib.plan(rdir, run_id, ticket_id, areas)
    except lib.GateError as exc:
        die("analysis plan", str(exc))
    emit({"ok": True, "run_id": run_id, "lanes": loop["lanes"], "next": _next(rdir, loop, _ctx)})


def _record(command, args, fn):
    run_id, rdir, ctx, ticket_id, tdir = _resolve(command, args.run)
    loop = loop_lib.load_loop(rdir)
    try:
        report = fn(rdir, loop, ctx, tdir) or {}
        loop_lib.save_loop(rdir, loop)
    except lib.GateError as exc:
        die(command, str(exc))
    out = {"ok": True, "run_id": run_id, "recorded": not loop.get("blocked"),
           "next": _next(rdir, loop, ctx)}
    out.update(report)
    emit(out)
    return out


def cmd_analysis_record_survey(args):
    _record("analysis record-survey", args,
            lambda rdir, loop, ctx, tdir: loop_lib.record_survey(rdir, loop) and None)


def cmd_analysis_record_synthesis(args):
    _record("analysis record-synthesis", args,
            lambda rdir, loop, ctx, tdir: loop_lib.record_synthesis(rdir, loop) and None)


def cmd_analysis_record_clarify(args):
    _record("analysis record-clarify", args,
            lambda rdir, loop, ctx, tdir: loop_lib.record_clarify(
                rdir, loop, tdir, blocking_open=args.blocking_open) and None)


def cmd_analysis_record_draft(args):
    _record("analysis record-draft", args,
            lambda rdir, loop, ctx, tdir: loop_lib.record_draft(rdir, loop) and None)


def cmd_analysis_record_review(args):
    def review(rdir, loop, ctx, tdir):
        loop_lib.record_review(rdir, loop)
        if loop.get("history") and not loop.get("blocked"):
            last = loop["history"][-1]
            return {"passed": last["passed"], "blocking": last["blocking"]}
        return None
    _record("analysis record-review", args, review)


def cmd_analysis_record_publication(args):
    _record("analysis record-publication", args,
            lambda rdir, loop, ctx, tdir: analysis_publish.record_publication(
                rdir, loop, ctx) and None)


def cmd_analysis_publish(args):
    def publish(rdir, loop, ctx, tdir):
        ticket = lib.load_ticket(tdir) or {"id": loop and loop.get("ticket_id")}
        return analysis_publish.publish(rdir, loop, ctx, tdir, ticket,
                                        summary=args.summary)[1]
    out = _record("analysis publish", args, publish)
    if not out.get("published"):
        sys.stderr.write("acs analysis publish: refused: %s\n" % out.get("reason"))
        sys.exit(2)


def add_parser(group):
    """Register `analysis` and its verbs on acs.py's top-level subparsers."""
    analysis = group("analysis", help="the /acs:analyze-requirements controller (ADR-0114)")
    sub = analysis.add_subparsers(dest="cmd")

    def verb(name, func, help_text):
        parser = sub.add_parser(name, help=help_text)
        parser.add_argument("--run")
        parser.set_defaults(func=func)
        return parser

    verb("next", cmd_analysis_next, "read-only: the one next action, as JSON")
    plan = verb("plan", cmd_analysis_plan, "declare the survey lanes once")
    plan.add_argument("--areas", default="",
                      help="comma-separated code areas, one impact lane each "
                           "(empty: one impact lane over the whole repository)")
    verb("record-survey", cmd_analysis_record_survey,
         "read every lane's snapshot and notes; join the notes")
    verb("record-synthesis", cmd_analysis_record_synthesis,
         "read the synthesis snapshot; join it last")
    clarify = verb("record-clarify", cmd_analysis_record_clarify,
                   "the user was asked (or nothing was open)")
    clarify.add_argument("--blocking-open", dest="blocking_open", action="store_true",
                         help="a question that blocks planning is still open")
    verb("record-draft", cmd_analysis_record_draft, "read the draft pass's snapshot and draft")
    verb("record-review", cmd_analysis_record_review,
         "derive the iteration's verdict from the judge slices' snapshots")
    publish = verb("publish", cmd_analysis_publish,
                   "checks, byte-for-byte copy, docs-folder-only commit; never pushes")
    publish.add_argument("--summary", help="the {summary} of the commit message")
    verb("record-publication", cmd_analysis_record_publication,
         "verify the published bytes and the commit")
    return analysis
