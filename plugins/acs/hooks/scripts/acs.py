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
    context, gate, lane, stakes, ticket, phase, slug, fanout, doctor.
  * Delegated — the verbs an existing script already implements: `start`
    (skill-start.py), `finish` (pipeline-step.py), `plan check`
    (plan-approval.py). Those scripts stay the implementation and keep working
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
  acs.py stakes recommend --path plugins/acs/hooks/scripts/acs_lib.py
  acs.py stakes guard --current-size small --current-stakes normal --proposed-stakes high
  acs.py ticket show --ticket MAR-1
  acs.py ticket save --ticket MAR-1 --from ticket.json
  acs.py plan check --ticket MAR-1
  acs.py phase validate --skill code --result-file result.json
  acs.py slug --text "Introduce the acs CLI"
  acs.py doctor
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

#: Subcommands this CLI forwards to the script that already implements them.
#: The script remains the implementation and stays callable on its own; acs.py
#: is the documented front door. Values are argv[0] under SCRIPTS.
DELEGATED = {
    "start": "skill-start.py",
    "finish": "pipeline-step.py",
    "plan": "plan-approval.py",
}

SIZES = ("trivial", "small", "standard", "large")
STAKES = ("low", "normal", "high")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def emit(obj):
    """The one stdout contract: a single pretty JSON object."""
    print(json.dumps(obj, indent=2, sort_keys=True))


def die(command, reason, code=2):
    sys.stderr.write("acs %s: %s\n" % (command, reason))
    sys.exit(code)


def context_or_die(command):
    try:
        return lib.build_context(os.getcwd())
    except lib.GateError as exc:
        die(command, str(exc))


def partition_or_die(command, explicit):
    """Resolve (ticket_id, tdir, ctx) for an ACTIVE partition, or exit 2.

    Same resolution order as clarify.py / plan-approval.py: explicit --ticket
    wins, else the pointer/branch resolution in resolve_ticket_id."""
    ctx = context_or_die(command)
    ticket_id, _src = lib.resolve_ticket_id(
        os.getcwd(), ctx["settings"], ctx["workspace"], ctx["repo_id"], explicit=explicit)
    if not ticket_id:
        die(command, "could not resolve the ticket id (pass --ticket)")
    tdir, archived = lib.find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    if archived or not os.path.isdir(tdir):
        die(command, "no active partition for %s" % ticket_id)
    return ticket_id, tdir, ctx


def load_ticket_or_die(command, tdir, ticket_id):
    ticket = lib.load_ticket(tdir)
    if not isinstance(ticket, dict):
        die(command, "no readable ticket.json for %s" % ticket_id)
    return ticket


def read_json_arg(command, path):
    """A JSON object from `path`, or from stdin when path is absent or '-'."""
    if path and path != "-":
        data = lib.read_json(path)
        if not isinstance(data, dict):
            die(command, "%s is missing or not a JSON object" % path)
        return data
    if sys.stdin.isatty():
        die(command, "expected a JSON object on stdin (or pass a file)")
    raw = sys.stdin.read().strip()
    if not raw:
        die(command, "expected a JSON object on stdin, got nothing")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        die(command, "invalid JSON on stdin: %s" % exc)
    if not isinstance(data, dict):
        die(command, "expected a JSON object on stdin, got %s" % type(data).__name__)
    return data


# ---------------------------------------------------------------------------
# context / gate
# ---------------------------------------------------------------------------

def cmd_context(args):
    """The resolved workspace view: what checkout_root, main_repo_root,
    default_state_root, repo_dir, repo_partition_id, index_path and
    load_settings each answer, in one call."""
    ctx = context_or_die("context")
    out = {"ok": True, "checkout_root": ctx.get("checkout_root"),
           "workspace": ctx.get("workspace"), "repo_id": ctx.get("repo_id"),
           "settings": ctx.get("settings")}
    for key in ("main_repo_root", "worktree", "state_root"):
        if key in ctx:
            out[key] = ctx[key]
    out["index_path"] = lib.index_path(ctx["workspace"], ctx["repo_id"])
    if args.ticket:
        tdir, archived = lib.find_ticket_partition(ctx["workspace"], ctx["repo_id"], args.ticket)
        out["ticket_id"] = args.ticket
        out["partition"] = tdir
        out["archived"] = bool(archived)
    emit(out)


def cmd_gate(args):
    """Run one skill's pre-gate without running the skill. Exit code mirrors
    the gate's own (0 open, 2 blocked); the gate writes its reason to stderr."""
    if args.skill not in lib.GATES:
        die("gate", "unknown skill %r (expected one of %s)"
            % (args.skill, ", ".join(sorted(lib.GATES))))
    payload = {"cwd": os.getcwd(), "hook_event_name": "PreToolUse",
               "tool_input": {"skill": args.skill}}
    if args.ticket:
        payload["tool_input"]["args"] = args.ticket
    code = lib.run_pre_payload(args.skill, payload)
    emit({"ok": code == 0, "skill": args.skill, "exit_code": code})
    sys.exit(code)


# ---------------------------------------------------------------------------
# lane
# ---------------------------------------------------------------------------

def _lane_triple(lane, stakes):
    depth = lib.verify_depth(lane, stakes)
    return {"lane": lane, "depth": depth, "ceiling": lib.VERIFY_ITERATION_CAP[depth]}


def cmd_lane_derive(args):
    lane = lib.derive_lane(args.size, args.stakes, args.needs_design, args.type)
    out = _lane_triple(lane, args.stakes)
    out["rank"] = lib.lane_rank(lane)
    emit(out)


def cmd_lane_rank(args):
    emit({"lane": args.lane, "rank": lib.lane_rank(args.lane)})


def cmd_lane_escalate(args):
    """Pure computation — no write. `escalated` says whether the candidate beat
    the current lane; `lane apply` is what persists a raise."""
    lane, depth, ceiling = lib.escalate_lane(
        args.current_lane, args.size, args.stakes, args.needs_design, args.type)
    emit({"lane": lane, "depth": depth, "ceiling": ceiling,
          "escalated": lib.lane_rank(lane) > lib.lane_rank(args.current_lane),
          "from_lane": args.current_lane})


def cmd_lane_apply(args):
    """The on-trigger escalation sequence of code/SKILL.md, in its documented
    order: guard_axes, escalate_lane, then (only on a real raise) save_ticket,
    update_pipeline, update_index, and finally record_escalation_event.

    The audit event is written LAST on purpose: the axes and lane are durably
    applied first, so a failed event write leaves a lane change with no matching
    event — detectable — rather than an event for a persistence that never
    landed. A no-op raise writes nothing, which is what makes a resumed run
    idempotent."""
    ticket_id, tdir, ctx = partition_or_die("lane apply", args.ticket)
    ticket = load_ticket_or_die("lane apply", tdir, ticket_id)

    from_lane = ticket.get("lane")
    from_size, from_stakes = ticket.get("size"), ticket.get("stakes")
    eff_size, eff_stakes = lib.guard_axes(from_size, from_stakes,
                                          args.proposed_size, args.proposed_stakes)
    new_lane, depth, ceiling_after = lib.escalate_lane(
        from_lane, eff_size, eff_stakes, ticket.get("needs_design"), ticket.get("type"))

    ceiling_before = (args.ceiling_before if args.ceiling_before is not None
                      else lib.VERIFY_ITERATION_CAP[lib.verify_depth(from_lane, from_stakes)])
    result = {"ticket_id": ticket_id, "from_lane": from_lane, "lane": new_lane,
              "size": eff_size, "stakes": eff_stakes, "depth": depth,
              "ceiling_before": ceiling_before,
              "ceiling_after": max(ceiling_before, ceiling_after)}

    if lib.lane_rank(new_lane) <= lib.lane_rank(from_lane):
        result.update({"escalated": False, "event_recorded": False,
                       "reason": "candidate lane is not strictly higher — no write"})
        emit(result)
        return

    ticket["size"], ticket["stakes"], ticket["lane"] = eff_size, eff_stakes, new_lane
    lib.save_ticket(tdir, ticket)
    lib.update_pipeline(tdir, ticket_id, args.skill, "in_progress", lane=new_lane)
    lib.update_index(ctx["workspace"], ctx["repo_id"], ticket)
    result["escalated"] = True

    event = {"ts": lib.now_iso(), "from_lane": from_lane, "to_lane": new_lane,
             "from_size": from_size, "from_stakes": from_stakes,
             "to_size": eff_size, "to_stakes": eff_stakes,
             "trigger": args.trigger, "source": args.source or args.trigger,
             "ceiling_before": ceiling_before, "ceiling_after": result["ceiling_after"],
             "direction": "up", "confirmation_ref": None}
    try:
        lib.record_escalation_event(tdir, args.skill, event)
    except (ValueError, OSError) as exc:
        result.update({"event_recorded": False, "error": str(exc), "event": event})
        emit(result)
        die("lane apply",
            "axes and lane are applied but the escalation event was not recorded: %s" % exc)
    result.update({"event_recorded": True, "event": event})
    emit(result)


def cmd_lane_deescalate(args):
    """confirm_deescalation — the only sanctioned lane-lowering path, and it
    refuses without an answered clarify.py ledger id."""
    ticket_id, tdir, _ctx = partition_or_die("lane deescalate", args.ticket)
    ticket = load_ticket_or_die("lane deescalate", tdir, ticket_id)
    before = {"lane": ticket.get("lane"), "size": ticket.get("size"),
              "stakes": ticket.get("stakes")}
    try:
        updated = lib.confirm_deescalation(tdir, ticket, args.size, args.stakes,
                                           args.clarify_ref)
    except (ValueError, KeyError) as exc:
        die("lane deescalate", str(exc))
    emit({"ok": True, "ticket_id": ticket_id, "from": before,
          "lane": updated["lane"], "size": updated["size"], "stakes": updated["stakes"],
          "confirmation_ref": args.clarify_ref})


# ---------------------------------------------------------------------------
# stakes
# ---------------------------------------------------------------------------

def _paths_from(args, command):
    paths = list(args.path or [])
    if args.paths_from:
        if args.paths_from == "-":
            if sys.stdin.isatty():
                die(command, "--paths-from - expects paths on stdin, one per line")
            text = sys.stdin.read()
        else:
            try:
                with open(args.paths_from, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except OSError as exc:
                die(command, "cannot read %s: %s" % (args.paths_from, exc))
        paths.extend(line.strip() for line in text.splitlines() if line.strip())
    return paths


def cmd_stakes_recommend(args):
    """recommend_stakes over a changed-file set. A recommendation only — it
    never writes stakes; `lane apply` is what acts on it."""
    ctx = context_or_die("stakes recommend")
    paths = _paths_from(args, "stakes recommend")
    emit({"stakes": lib.recommend_stakes(paths, ctx["settings"]),
          "paths_considered": len(paths)})


def cmd_stakes_guard(args):
    """guard_axes — the higher of each axis, so no unattended path can lower a
    confirmed value. Call before escalate_lane."""
    size, stakes = lib.guard_axes(args.current_size, args.current_stakes,
                                  args.proposed_size, args.proposed_stakes)
    emit({"size": size, "stakes": stakes,
          "changed": (size, stakes) != (args.current_size, args.current_stakes)})


# ---------------------------------------------------------------------------
# ticket / phase / slug / fanout / doctor
# ---------------------------------------------------------------------------

def cmd_ticket_show(args):
    ticket_id, tdir, _ctx = partition_or_die("ticket show", args.ticket)
    emit({"ok": True, "ticket_id": ticket_id, "partition": tdir,
          "ticket": load_ticket_or_die("ticket show", tdir, ticket_id)})


def cmd_ticket_save(args):
    """save_ticket + update_index in one call — SKILL.md never pairs them any
    other way, and a save without the re-index leaves the index stale.

    Refuses to write axes or lane: those move only through `lane apply` /
    `lane deescalate`, which carry the guard and the audit event."""
    ticket_id, tdir, ctx = partition_or_die("ticket save", args.ticket)
    current = load_ticket_or_die("ticket save", tdir, ticket_id)
    incoming = read_json_arg("ticket save", args.source)

    if incoming.get("id") != current.get("id"):
        die("ticket save", "document id %r does not match the partition's %r"
            % (incoming.get("id"), current.get("id")))
    guarded = [k for k in ("size", "stakes", "lane") if incoming.get(k) != current.get(k)]
    if guarded:
        die("ticket save", "%s move only through `acs.py lane apply` / `lane deescalate`"
            % ", ".join(guarded))

    lib.save_ticket(tdir, incoming)
    lib.update_index(ctx["workspace"], ctx["repo_id"], incoming)
    emit({"ok": True, "ticket_id": ticket_id, "indexed": True})


def cmd_phase_validate(args):
    """Check a phase result document BEFORE the post-hook consumes it. The
    post-hook refuses a document with no status (it would otherwise finalize a
    run and open the next gate on nothing); this reports that verdict without
    writing anything."""
    result = read_json_arg("phase validate", args.result_file)
    errors = []
    status = result.get("status")
    if status is None:
        errors.append("status is absent — the post-hook refuses a result document without one")
    elif status not in lib.RUN_STATUSES:
        errors.append("status %r is not one of %s" % (status, ", ".join(lib.RUN_STATUSES)))
    elif status == "in_progress":
        errors.append("status 'in_progress' does not finalize a run")
    emit({"ok": not errors, "skill": args.skill, "status": status, "errors": errors})


def cmd_slug(args):
    emit({"text": args.text, "slug": lib.slugify(args.text, args.max_len)})


def cmd_fanout_batches(args):
    ctx = context_or_die("fanout batches")
    index = lib.read_json(lib.index_path(ctx["workspace"], ctx["repo_id"])) or {}
    emit({"batches": lib.fanout_batches(ctx["settings"], index, ctx["checkout_root"])})


def cmd_doctor(args):
    ctx = None
    try:
        ctx = lib.build_context(os.getcwd())
    except lib.GateError:
        pass  # the toolchain report is useful precisely when the context is not
    settings = ctx["settings"] if ctx else None
    emit({"ok": True, "context": ctx is not None,
          "toolchain": lib.check_toolchain(settings),
          "missing": lib.missing_tools(settings)})


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
    parser = argparse.ArgumentParser(prog="acs.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="group")

    ctx = sub.add_parser("context", help="resolved settings, workspace and paths")
    ctx.add_argument("--ticket", help="also resolve this ticket's partition")
    ctx.set_defaults(func=cmd_context)

    gate = sub.add_parser("gate", help="run a skill's pre-gate without the skill")
    gate.add_argument("--skill", required=True)
    gate.add_argument("--ticket")
    gate.set_defaults(func=cmd_gate)

    lane = sub.add_parser("lane", help="lane derivation, escalation and the audited apply")
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

    stakes = sub.add_parser("stakes", help="stakes recommendation and the axis guard")
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

    ticket = sub.add_parser("ticket", help="read and write ticket.json")
    ticket_sub = ticket.add_subparsers(dest="cmd")

    show = ticket_sub.add_parser("show", help="load_ticket")
    show.add_argument("--ticket")
    show.set_defaults(func=cmd_ticket_show)

    save = ticket_sub.add_parser("save", help="save_ticket + update_index")
    save.add_argument("--ticket")
    save.add_argument("--from", dest="source", metavar="FILE",
                      help="the ticket document ('-' or omitted reads stdin)")
    save.set_defaults(func=cmd_ticket_save)

    phase = sub.add_parser("phase", help="phase artifacts")
    phase_sub = phase.add_subparsers(dest="cmd")
    pval = phase_sub.add_parser("validate", help="check a result document before the post-hook")
    pval.add_argument("--skill", required=True)
    pval.add_argument("--result-file", dest="result_file", metavar="FILE")
    pval.set_defaults(func=cmd_phase_validate)

    slug = sub.add_parser("slug", help="slugify (branch and file naming)")
    slug.add_argument("--text", required=True)
    slug.add_argument("--max-len", dest="max_len", type=int, default=40)
    slug.set_defaults(func=cmd_slug)

    fanout = sub.add_parser("fanout", help="epic fan-out helpers")
    fanout_sub = fanout.add_subparsers(dest="cmd")
    batches = fanout_sub.add_parser("batches", help="fanout_batches")
    batches.set_defaults(func=cmd_fanout_batches)

    doctor = sub.add_parser("doctor", help="check_toolchain / missing_tools")
    doctor.set_defaults(func=cmd_doctor)

    for name in sorted(DELEGATED):
        sub.add_parser(name, add_help=False,
                       help="delegated to %s" % DELEGATED[name])
    return parser


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

    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        # A group with no subcommand ("acs.py lane") — show that group's usage.
        parser.print_help(sys.stderr)
        sys.exit(2)
    func(args)


if __name__ == "__main__":
    main()
