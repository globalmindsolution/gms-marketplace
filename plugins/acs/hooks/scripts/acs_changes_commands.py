"""acs_changes_commands — the working-tree changeset and the commits made from it (ADR-0127).

    acs.py changes snapshot                         {"ok", "tree"}: a tree id of the working tree
    acs.py changes diff [--since REV] [--run R]
                        [--name-only | --stat | --patch]
                                                    what changed since the run's baseline
    acs.py pr plan-commits [--ticket ID] [--run R] [--out FILE]
                                                    the commit groups /acs:create-pr previews,
                                                    for a run of any subject
    acs.py pr commit --plan FILE                    commit a (possibly edited) plan; never pushes

Only /acs:create-pr commits; every other step leaves its output uncommitted
and records the paths it wrote. `changes diff` replaces every
`git diff <default>...HEAD` changeset read, because a working tree nobody has
committed has an empty commit range. Every verb prints one JSON object; a
refusal exits 2.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import context_or_die, die, emit, read_json_arg  # noqa: E402
from acs_lib import changes, commit_plan  # noqa: E402


def _root_or_die(command):
    root = lib.checkout_root(os.getcwd())
    if not root:
        die(command, "%s is not inside a git checkout" % os.getcwd())
    return root


def _run_dir(command, ctx, run_id):
    """The run directory for `run_id` (else this checkout's current run), or
    None when there is none to name. An explicit --run must exist."""
    run_id = run_id or lib.current_run_id(ctx)
    if not run_id:
        return None, None
    rdir = lib.run_dir(lib.repo_dir(ctx["workspace"], ctx["repo_id"]), run_id)
    if lib.load_run(rdir) is None:
        die(command, "no run %r (expected %s)" % (run_id, rdir))
    return run_id, rdir


def cmd_changes_snapshot(args):
    emit({"ok": True, "tree": changes.snapshot(_root_or_die("changes snapshot"))})


def cmd_changes_diff(args):
    root = _root_or_die("changes diff")
    ctx = context_or_die("changes diff")
    run_id, rdir = _run_dir("changes diff", ctx, args.run)
    baseline = changes.load_baseline(rdir)
    if not args.since and baseline is None:
        die("changes diff", "no baseline recorded for %s and no --since given -- a run "
                            "records one at its first `acs.py step start`; pass "
                            "--since <commit-or-tree> to diff from somewhere else"
            % ("run %s" % run_id if run_id else "this checkout (no current run)"))
    cs = changes.changeset(root, since=args.since, baseline=baseline)
    out = {"ok": True, "run_id": run_id, "since": cs["since"], "tree": cs["tree"],
           "files": cs["files"], "excluded": [e["path"] for e in cs["excluded"]]}
    paths = [e["path"] for e in cs["files"]]
    if args.mode in ("stat", "patch"):
        out[args.mode] = changes.render(root, cs["since"], cs["tree"], paths, args.mode)
    emit(out)


def cmd_pr_plan_commits(args):
    """The plan for this checkout's run (or --run, or --ticket's runs), of any
    subject: a ticket's run reads all of that ticket's runs, a prompt's or a
    document's run reads itself, and either falls back to every uncommitted
    change when nothing was recorded (acs_lib.commit_plan.plan)."""
    command = "pr plan-commits"
    ctx = context_or_die(command)
    root = ctx.get("checkout_root") or _root_or_die(command)
    repo = lib.repo_dir(ctx["workspace"], ctx["repo_id"])
    ticket_id, run_doc = (args.ticket or "").strip() or None, None
    rdir = None
    if args.run or not ticket_id:
        _run_id, rdir = _run_dir(command, ctx, args.run)
        if rdir is None:
            die(command, "no current run for this checkout, and no --run or --ticket given. "
                         "Start /acs:create-pr with a ticket id, a prompt or a document.")
        run_doc = lib.load_run(rdir)
        ticket_id = ticket_id or ((run_doc.get("subject") or {}).get("ticket_id"))
    ticket = None
    if ticket_id:
        tdir, _archived = lib.find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
        ticket = lib.load_ticket(tdir) if os.path.isdir(tdir) else None
        if not isinstance(ticket, dict):
            die(command, "no ticket %s in this repo's workspace" % ticket_id)
    if rdir and args.run:
        rdirs = [rdir]
    elif ticket_id:
        rdirs = [d for d in lib.gates._run_dirs_for_ticket(repo, ticket_id) if os.path.isdir(d)]
    else:
        rdirs = [rdir]
    if run_doc is None and rdirs:
        run_doc = lib.load_run(rdirs[0])
    # The OLDEST baseline: the subject's first step recorded it, before any
    # step of any later re-run wrote a file.
    baseline = next((b for b in (changes.load_baseline(d) for d in reversed(rdirs)) if b),
                    None)
    mine = {os.path.realpath(d) for d in rdirs}
    others = []
    for run_id in lib.existing_run_ids(repo):
        other = lib.run_dir(repo, run_id)
        if os.path.realpath(other) in mine:
            continue
        if (lib.load_run(other) or {}).get("status") != "abandoned":
            others.append(other)
    plan = commit_plan.plan(root, rdirs, commit_plan.subject_of(run_doc, ticket),
                            baseline, others)
    if args.out:
        lib.write_json(args.out, plan)
    emit(dict(plan, ok=True, plan_file=os.path.abspath(args.out) if args.out else None))


def cmd_pr_commit(args):
    root = _root_or_die("pr commit")
    plan = read_json_arg("pr commit", args.plan)
    emit(dict(commit_plan.execute(root, plan), ok=True))


def add_parser(group):
    chg = group("changes", help="the working-tree changeset a run produced (ADR-0127)")
    sub = chg.add_subparsers(dest="cmd")

    snap = sub.add_parser("snapshot", help="a git tree id of the working tree, untracked "
                                           "files included; the real index is untouched")
    snap.set_defaults(func=cmd_changes_snapshot)

    diff = sub.add_parser("diff", help="what changed since the run's baseline (or --since)")
    diff.add_argument("--since", help="a commit or tree id (default: the baseline's base_sha)")
    diff.add_argument("--run", help="a run other than this checkout's current one")
    mode = diff.add_mutually_exclusive_group()
    mode.add_argument("--name-only", dest="mode", action="store_const", const="name-only",
                      help="the changed paths and their status (the default)")
    mode.add_argument("--stat", dest="mode", action="store_const", const="stat",
                      help="also `git diff --stat` text")
    mode.add_argument("--patch", dest="mode", action="store_const", const="patch",
                      help="also the full patch text")
    diff.set_defaults(func=cmd_changes_diff, mode="name-only")


def add_pr_parsers(pr_sub):
    """`pr plan-commits` and `pr commit`, beside `pr metadata` in acs.py's `pr` group."""
    plan = pr_sub.add_parser("plan-commits", help="the commit groups /acs:create-pr previews")
    plan.add_argument("--ticket", help="a ticket's runs (default: this checkout's run, "
                                       "whatever its subject)")
    plan.add_argument("--run", help="this run instead of the checkout's current one")
    plan.add_argument("--out", metavar="FILE", help="also write the plan to FILE")
    plan.add_argument("--docs", action="store_true", help=argparse.SUPPRESS)  # deprecated no-op
    plan.set_defaults(func=cmd_pr_plan_commits)

    commit = pr_sub.add_parser("commit", help="commit a plan's groups in order; never pushes")
    commit.add_argument("--plan", required=True, metavar="FILE",
                        help="the plan (as plan-commits printed it, possibly edited); '-' reads stdin")
    commit.set_defaults(func=cmd_pr_commit)
