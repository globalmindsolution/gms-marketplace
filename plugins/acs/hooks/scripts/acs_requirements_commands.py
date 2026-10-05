"""acs_requirements_commands — `acs.py requirements <verb>` and `acs.py artifacts
show`, the run's requirements and its documents (ADR-0128).

    acs.py requirements show [--run R]          the run's requirements, as JSON
    acs.py requirements add --args "<text>"     record a later invocation's sources
    acs.py requirements refine --from FILE|-    analyze-requirements' write-back
    acs.py artifacts show [--run R | --ticket T] where the run's documents live

Every verb defaults to this checkout's current run (the pointer); `--run`
names another. A ticket id, documents and a prompt are only the containers the
requirements came in: none of these verbs needs a ticket.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import context_or_die, die, emit, read_json_arg, run_or_die  # noqa: E402

reqs = lib.requirements


def _ensure(rdir, ctx):
    """requirements.md exists for the run (a run recorded before ADR-0128, or
    on a host where the write failed, is materialised on first read)."""
    if not os.path.isfile(reqs.sources_path(rdir)):
        reqs.materialise(rdir, ctx)


def cmd_requirements_show(args):
    """The run's requirements: {path, sources, acceptance_criteria, features,
    feature, needs_design, phase, feature_analysis, refined}."""
    run_id, rdir, ctx = run_or_die("requirements show", args.run)
    try:
        _ensure(rdir, ctx)
    except lib.GateError as exc:
        die("requirements show", str(exc))
    emit(dict(reqs.summary(rdir, ctx), ok=True, run_id=run_id))


def cmd_requirements_add(args):
    """Append a later invocation's sources (deduplicated) and regenerate."""
    run_id, rdir, ctx = run_or_die("requirements add", args.run)
    if not (args.args or "").strip():
        die("requirements add", "--args is required: the ticket ids, documents and "
                                "prompt to add")
    try:
        result = reqs.add_sources(rdir, ctx, args.args)
    except lib.GateError as exc:
        die("requirements add", str(exc))
    emit(dict(reqs.summary(rdir, ctx), ok=True, run_id=run_id,
              added=[{"kind": e.get("kind"), "ref": e.get("ref")} for e in result["added"]]))


def cmd_requirements_refine(args):
    """Store refined acceptance criteria / needs_design / features / feature /
    phase; regenerate `## Refined`; patch the ticket when the run has one."""
    run_id, rdir, ctx = run_or_die("requirements refine", args.run)
    data = read_json_arg("requirements refine", args.source)
    try:
        report = reqs.refine(rdir, ctx, data)
    except lib.GateError as exc:
        die("requirements refine", str(exc))
    emit(dict(reqs.summary(rdir, ctx), ok=True, run_id=run_id,
              ticket_patched=report["ticket_patched"],
              ticket_fields=report["ticket_fields"]))


def _artifacts_target(args, ctx):
    """(rdir or None, ticket_id or None) for `artifacts show`."""
    repo = lib.repo_dir(ctx["workspace"], ctx["repo_id"])
    if args.run:
        _run_id, rdir, _ctx = run_or_die("artifacts show", args.run)
        return rdir, None
    if args.ticket:
        try:
            ticket_id, _tdir, _archived = lib.resolve_active_partition(
                os.getcwd(), ctx, explicit=args.ticket, allow_archived=True)
        except lib.GateError as exc:
            die("artifacts show", str(exc))
        return lib.run_docs.latest_run_for_ticket(repo, ticket_id), ticket_id
    run_id = lib.current_run_id(ctx)
    if run_id:
        rdir = lib.run_dir(repo, run_id)
        if lib.load_run(rdir) is not None:
            return rdir, None
    try:
        ticket_id, _tdir, _archived = lib.resolve_active_partition(
            os.getcwd(), ctx, allow_archived=True)
    except lib.GateError:
        die("artifacts show", "no current run for this checkout and no ticket resolves: "
                              "pass --run <run-id> or --ticket <id>")
    return lib.run_docs.latest_run_for_ticket(repo, ticket_id), ticket_id


def cmd_artifacts_show(args):
    """Where one run's documents live -- the phase folders, each document's
    existing file (legacy docs/tickets/<ID>/ read as a fallback) and the path a
    new one is written to -- plus the ticket and its derived status when the run
    has one. Read-only, so an archived ticket is answered too."""
    ctx = context_or_die("artifacts show")
    rdir, ticket_id = _artifacts_target(args, ctx)
    try:
        out = lib.run_docs.describe(ctx, rdir=rdir, ticket_id=ticket_id)
    except lib.GateError as exc:
        die("artifacts show", str(exc))
    emit(dict(out, ok=True))


def add_parser(group):
    """Register `requirements` and its verbs on acs.py's top-level subparsers."""
    requirements = group("requirements",
                         help="the run's requirements from any container (ADR-0128)")
    sub = requirements.add_subparsers(dest="cmd")

    show = sub.add_parser("show", help="the run's requirements, as JSON")
    show.add_argument("--run")
    show.set_defaults(func=cmd_requirements_show)

    add = sub.add_parser("add", help="record a later invocation's sources")
    add.add_argument("--run")
    add.add_argument("--args", help="ticket ids, documents and a prompt, as typed")
    add.set_defaults(func=cmd_requirements_add)

    refine = sub.add_parser("refine", help="analyze-requirements' refined requirements")
    refine.add_argument("--run")
    refine.add_argument("--from", dest="source", metavar="FILE",
                        help="a JSON object ('-' or omitted reads stdin): "
                             "acceptance_criteria, needs_design, features, feature, phase")
    refine.set_defaults(func=cmd_requirements_refine)
    return requirements
