"""acs_commands — the acs.py subcommand handlers.

Split out of acs.py by MAR-572, which is code motion only: every handler is
byte-identical to the one acs.py carried, and acs.py re-exports the whole set
so `acs.cmd_context` and friends keep resolving for the tests and for anything
that reached them by name.

Sibling module rather than a package, matching what MAR-531 did for
metrics_render and its kin: three SKILL.md files invoke
`python3 .../acs.py` by path, and that has to keep working.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402

from acs_cli import (context_or_die, die, emit, load_ticket_or_die,
    partition_or_die, read_json_arg)  # noqa: E402


# ---------------------------------------------------------------------------
# context / gate
# ---------------------------------------------------------------------------

#: Keys build_context actually returns that a coordinator needs by name. Copied
#: explicitly rather than passing ctx through, so a new internal key never
#: leaks into this command's contract by accident.
CONTEXT_KEYS = ("checkout_root", "main_repo_root", "workspace", "repo_id",
                "checkout_id", "plugin_root", "settings", "settings_sources")


def cmd_context(args):
    """The resolved workspace view: what checkout_root, main_repo_root,
    repo_partition_id, index_path, repo_dir and load_settings each answer, in
    one call, plus checkout_id (which names this checkout's pointer and
    cost-sample files)."""
    ctx = context_or_die("context")
    out = {"ok": True}
    for key in CONTEXT_KEYS:
        if key in ctx:
            out[key] = ctx[key]
    out["index_path"] = lib.index_path(ctx["workspace"], ctx["repo_id"])
    out["repo_dir"] = lib.repo_dir(ctx["workspace"], ctx["repo_id"])
    if args.ticket:
        tdir, archived = lib.find_ticket_partition(ctx["workspace"], ctx["repo_id"], args.ticket)
        # find_ticket_partition returns the ACTIVE path for a ticket that exists
        # nowhere, so the path alone cannot be read as "this ticket exists" --
        # every other partition-taking subcommand refuses that case outright.
        out["ticket_id"] = args.ticket
        out["partition"] = tdir
        out["archived"] = bool(archived)
        out["exists"] = os.path.isdir(tdir)
    emit(out)


def cmd_gate(args):
    """Run one skill's pre-gate without running the skill. Exit code mirrors
    the gate's own (0 open, 2 blocked); the gate writes its reason to stderr."""
    if args.skill not in lib.GATES:
        die("gate", "unknown skill %r (expected one of %s)"
            % (args.skill, ", ".join(sorted(lib.GATES))))
    payload = {"cwd": os.getcwd(), "tool_input": {"skill": args.skill}}
    if args.ticket:
        payload["tool_input"]["args"] = args.ticket
    # record_marker=False: this is NOT a PreToolUse event. The payload has no
    # session_id or transcript_path, and record_session_marker persists those
    # faithfully as null -- overwriting the real marker and costing the next run
    # its cost/usage attribution. Asking "would this gate pass?" must not.
    code = lib.run_pre_payload(args.skill, payload, record_marker=False)
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
    # The lane is derived from the GUARDED axes, unchanged: guard_axes floors an
    # absent axis at the lowest rank, and derive_lane must see that floor. Null
    # them here instead and derive_lane(None, ...) returns its STANDARD default,
    # so a call carrying no signal at all would escalate and raise the ceiling.
    new_lane, depth, ceiling_after = lib.escalate_lane(
        from_lane, eff_size, eff_stakes, ticket.get("needs_design"), ticket.get("type"))

    # PERSISTENCE guard, applied after the derivation and only to what is
    # written: an axis nobody has stated must not be materialised at the guard's
    # floor by a rigor-RAISING path, where it would anchor every later
    # comparison. Computed here, so it cannot influence the lane above.
    write_size = None if (from_size is None and args.proposed_size is None) else eff_size
    write_stakes = None if (from_stakes is None and args.proposed_stakes is None) else eff_stakes

    ceiling_before = (args.ceiling_before if args.ceiling_before is not None
                      else lib.VERIFY_ITERATION_CAP[lib.verify_depth(from_lane, from_stakes)])
    result = {"ticket_id": ticket_id, "from_lane": from_lane, "lane": new_lane,
              "depth": depth, "ceiling_before": ceiling_before,
              "ceiling_after": max(ceiling_before, ceiling_after)}

    if lib.lane_rank(new_lane) <= lib.lane_rank(from_lane):
        # Report what is ON DISK, not the computed effective axes: nothing was
        # written, and a caller branching on out["stakes"] must not read a raise
        # that never happened. What was asked for is reported separately.
        result.update({"lane": from_lane, "size": from_size, "stakes": from_stakes,
                       "proposed_size": args.proposed_size,
                       "proposed_stakes": args.proposed_stakes,
                       "escalated": False, "event_recorded": False, "event": None,
                       "reason": "candidate lane is not strictly higher — no write"})
        emit(result)
        return

    result["size"], result["stakes"] = write_size, write_stakes

    if write_size is not None:
        ticket["size"] = write_size
    if write_stakes is not None:
        ticket["stakes"] = write_stakes
    ticket["lane"] = new_lane
    lib.save_ticket(tdir, ticket)
    lib.update_pipeline(tdir, ticket_id, args.skill, "in_progress", lane=new_lane)
    # The index is repo-level, so its guard can refuse. That must NOT skip the
    # escalation event below: the index entry is rebuilt from ticket.json by
    # the next write, while the audit event has no other source and the lane
    # raise is already durable. Report the gap after the event is safe.
    index_error = None
    try:
        lib.update_index(ctx["workspace"], ctx["repo_id"], ticket)
    except lib.GuardTimeout as exc:
        index_error = str(exc)
    result["escalated"] = True
    result["index_updated"] = index_error is None

    event = {"ts": lib.now_iso(), "from_lane": from_lane, "to_lane": new_lane,
             "from_size": from_size, "from_stakes": from_stakes,
             "to_size": write_size, "to_stakes": write_stakes,
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
    if index_error:
        result["error"] = index_error
        emit(result)
        die("lane apply",
            "the lane raise (%s -> %s) and its escalation event ARE recorded, but "
            "tickets-index.json was not updated: %s\nThe index entry is rebuilt "
            "from ticket.json by the next write to it, so this self-heals; "
            "re-running would be a no-op, since the raise is already applied."
            % (from_lane, new_lane, index_error))
    emit(result)


def cmd_lane_deescalate(args):
    """confirm_deescalation — the only sanctioned lane-lowering path, and it
    refuses without an answered clarify.py ledger id.

    confirm_deescalation persists ticket.json, pipeline-state.json and the index
    BEFORE recording its audit event, exactly like the upward path. So a failure
    is not automatically "nothing happened": on any error this re-reads the
    ticket and reports what actually landed, the way `lane apply` does. Exit 2
    with `applied: true` means a rigor-LOWERING write is durable with no
    matching event — the loudest case in the system, and previously reported as
    a bare refusal with empty stdout."""
    ticket_id, tdir, _ctx = partition_or_die("lane deescalate", args.ticket)
    ticket = load_ticket_or_die("lane deescalate", tdir, ticket_id)
    before = {"lane": ticket.get("lane"), "size": ticket.get("size"),
              "stakes": ticket.get("stakes")}
    try:
        updated = lib.confirm_deescalation(tdir, ticket, args.size, args.stakes,
                                           args.clarify_ref)
    except (ValueError, KeyError, OSError) as exc:
        # "Did anything actually change on disk?" -- NOT "does the ticket now
        # hold the requested values?", which is also true when the ticket
        # already sat at them and the call refused before writing a byte.
        # OSError is caught because the failure this handler exists for is the
        # audit write, which fails that way on a full or read-only disk.
        on_disk = lib.load_ticket(tdir) or {}
        applied = any(on_disk.get(k) != before[k] for k in ("lane", "size", "stakes"))
        if not applied:
            if isinstance(exc, KeyError):
                die("lane deescalate", "ticket.json for %s has no %s field to lower"
                    % (ticket_id, exc))
            die("lane deescalate", str(exc))
        emit({"ok": False, "ticket_id": ticket_id, "from": before,
              "lane": on_disk.get("lane"), "size": on_disk.get("size"),
              "stakes": on_disk.get("stakes"), "applied": True,
              "event_recorded": False, "error": str(exc),
              "confirmation_ref": args.clarify_ref})
        die("lane deescalate",
            "axes and lane are LOWERED but the de-escalation event was not "
            "recorded: %s" % exc)
    recorded = lib.last_run(lib.load_state(tdir, "code")) or {}
    events = recorded.get("escalations") or []
    emit({"ok": True, "ticket_id": ticket_id, "from": before,
          "lane": updated["lane"], "size": updated["size"], "stakes": updated["stakes"],
          "applied": True, "event_recorded": True,
          # Both audited lane-writing paths report `event`, so a coordinator can
          # branch on it uniformly instead of only on the upward one.
          "event": events[-1] if events else None,
          "confirmation_ref": args.clarify_ref})


# ---------------------------------------------------------------------------
# stakes
# ---------------------------------------------------------------------------

def read_lines_arg(command, path):
    """Lines from `path`, or from stdin when it is '-'.

    The isatty guard matches _paths_from below: without it, `--files-from -`
    typed at a terminal blocks forever on a read that will never end, instead
    of saying what it wanted."""
    if path == "-":
        if sys.stdin.isatty():
            die(command, "%s - expects one path per line on stdin" % command)
        return sys.stdin.read().splitlines()
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().splitlines()
    except OSError as exc:
        die(command, "could not read %s: %s" % (path, exc))


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

    The document is a PATCH, not a replacement: incoming keys are merged over
    the stored ticket. A caller that hand-builds a document — the model-driven
    caller this CLI exists to serve — would otherwise wipe every field it did
    not think to include, taking title, type, status, parent and children with
    it and blanking the index row, which `gate_code`, `_epic_auto_done` and
    `fanout_batches` all read.

    Refuses to write axes or lane: those move only through `lane apply` /
    `lane deescalate`, which carry the guard and the audit event."""
    ticket_id, tdir, ctx = partition_or_die("ticket save", args.ticket)
    current = load_ticket_or_die("ticket save", tdir, ticket_id)
    incoming = read_json_arg("ticket save", args.source)

    if not current.get("id"):
        die("ticket save", "the stored ticket.json for %s has no id" % ticket_id)
    if "id" in incoming and incoming["id"] != current["id"]:
        die("ticket save", "document id %r does not match the partition's %r"
            % (incoming.get("id"), current.get("id")))
    guarded = [k for k in ("size", "stakes", "lane")
               if k in incoming and incoming[k] != current.get(k)]
    if guarded:
        die("ticket save", "%s move only through `acs.py lane apply` / `lane deescalate`"
            % ", ".join(guarded))

    updated = dict(current)
    updated.update(incoming)
    lib.save_ticket(tdir, updated)
    lib.update_index(ctx["workspace"], ctx["repo_id"], updated)
    emit({"ok": True, "ticket_id": ticket_id, "indexed": True,
          "fields_written": sorted(incoming)})


def _gh_runner(args, cwd):
    """The gh runner a forge command uses: live, or a recorded fixture.

    `--gh-replay FILE` maps a command PREFIX to a [returncode, stdout, stderr]
    triple, so the whole flow -- including the arms that only fire when a board
    is missing a field -- is reproducible with no forge."""
    responses = None
    if args.gh_replay:
        recorded = read_json_arg("pr metadata fill", args.gh_replay)
        responses = {k: tuple(v) for k, v in recorded.items()}
    return lib.Gh(responses=responses, cwd=cwd)


def cmd_pr_metadata_fill(args):
    """create-pr step 6a as one command: assignee, type label, CODEOWNERS
    reviewers, and the Project item with its Status and Group-B fields.

    Non-critical throughout — the PR is already created, so every failure is an
    `info` finding carrying the command, and exit 0 means the pass RAN, not
    that every field landed. Read `findings`."""
    ticket_id, tdir, ctx = partition_or_die("pr metadata fill", args.ticket)
    ticket = load_ticket_or_die("pr metadata fill", tdir, ticket_id)
    provider = ((ctx["settings"].get("tracker") or {}).get("provider") or "local")
    if provider != "github" or not (ticket.get("external") or {}).get("key"):
        emit({"ok": True, "ticket_id": ticket_id, "skipped": True,
              "reason": "tracker.provider is %r and ticket.external.key is %r — the "
                        "metadata-fill block does not apply"
                        % (provider, (ticket.get("external") or {}).get("key")),
              "findings": [], "applied": []})
        return
    gh = _gh_runner(args, ctx["checkout_root"])
    pr = {"number": args.pr, "url": args.url or ""}
    if not pr["url"]:
        code, out, _err = gh(["gh", "pr", "view", str(args.pr), "--json", "url", "-q", ".url"])
        pr["url"] = (out or "").strip() if code == 0 else ""
    out = lib.pr_metadata_fill(gh, ctx["settings"], ticket, pr, ctx["checkout_root"],
                               author=args.author)
    out.update({"ok": True, "ticket_id": ticket_id, "pr": args.pr, "skipped": False})
    emit(out)


def cmd_tracker_sync(args):
    """create-ticket step 5's batch as one command.

    Critical per ticket, soft per batch: a ticket whose `gh issue create` fails
    gets an `error` finding with the canonical hint and keeps `external` unset,
    and the batch continues so the failure can be retried alone. Exit 0 means
    the batch ran; read `failed`."""
    ctx = context_or_die("tracker sync")
    provider = ((ctx["settings"].get("tracker") or {}).get("provider") or "local")
    if provider == "local":
        emit({"ok": True, "skipped": True, "reason": "tracker.provider is 'local'",
              "synced": {}, "failed": [], "findings": []})
        return
    tickets, bodies = [], {}
    for ticket_id in args.ticket:
        tdir, archived = lib.find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
        if archived or not os.path.isdir(tdir):
            die("tracker sync", "no active partition for %s" % ticket_id)
        ticket = lib.load_ticket(tdir)
        if not isinstance(ticket, dict):
            die("tracker sync", "no readable ticket.json for %s" % ticket_id)
        tickets.append(ticket)
        bodies[ticket_id] = os.path.join(tdir, "tracker-body.md")

    candidates = lib.sync_candidates(tickets, tuple(lib.PRODUCT_TICKET_TITLES.values()))
    excluded = [t["id"] for t in tickets if t not in candidates]
    if args.dry_run:
        emit({"ok": True, "dry_run": True, "would_sync": [t["id"] for t in candidates],
              "excluded": excluded, "synced": {}, "failed": [], "findings": []})
        return
    gh = _gh_runner(args, ctx["checkout_root"])
    out = lib.tracker_sync(gh, ctx["settings"], candidates, bodies)
    out.update({"ok": True, "excluded": excluded, "dry_run": False})
    emit(out)
def cmd_readiness(args):
    """merge-pr's four readiness dimensions and one verdict, as JSON.

    Two input modes, deliberately interchangeable: `--pr N` reads GitHub
    through gh, and `--from FILE` replays a recorded document of the same
    shape. The decision itself is a pure function of that document
    (lib.merge_readiness), so a verdict is reproducible offline — which is what
    makes it reviewable, and what lets the tests cover every failing dimension
    without a network.

    Exit 0 means the check RAN. Read `verdict`: "ready" (merge), "update-branch"
    (only the base is ahead — the BEHIND carve-out), or "blocked" (a
    REPORT-ONLY stop, with `stop_reason` ready to drop into the result
    document)."""
    if bool(args.pr) == bool(args.source):
        die("readiness", "pass exactly one of --pr N or --from FILE")
    if args.source:
        recorded = read_json_arg("readiness", args.source)
        pr = recorded.get("pr_view", recorded)
        required_ok = recorded.get("required_checks_ok")
        if not isinstance(pr, dict):
            die("readiness", "the recorded document has no `pr_view` object")
    else:
        try:
            # Normalised the same way skill-start.py normalises the same
            # user input: `#42` and a PR URL both reach gh as `42`. Unnormalised,
            # `readiness --pr '#42'` reached `gh pr view '#42'`, which gh
            # resolves as a BRANCH NAME.
            pr = lib.gh_pr_view(lib.classify_merge_pr_arg(args.pr)[1] or args.pr,
                                ",".join(lib.PR_VIEW_FIELDS))
        except lib.GateError as exc:
            die("readiness", "%s\n%s" % (exc, lib.gh_failure_hint(str(exc))))
        required_ok = lib.gh_pr_required_checks_ok(args.pr)
        # ADR-0088 classifies this read as CRITICAL: an unevaluable gate is
        # never treated as passed. "No required checks configured" is NOT
        # unevaluable -- it is a supported repo shape (/acs:setup documents
        # enforcement as advisory until an admin enables it) -- so only a real
        # failure to read stops here, with gh's own words and the canonical
        # hint rather than a bare "exited non-zero".
        if isinstance(required_ok, tuple):
            _ok, detail = required_ok
            if lib.gh_read_is_unevaluable(detail):
                die("readiness", "gh pr checks --required could not be evaluated "
                                 "for PR %s:\n%s\n%s"
                    % (args.pr, detail or "(no output)", lib.gh_failure_hint(detail)))

    out = lib.merge_readiness(pr, required_ok)
    out["ok"] = True
    out["pr"] = pr.get("number", args.pr)
    out["required_checks_ok"] = (required_ok[0] if isinstance(required_ok, tuple)
                                 else required_ok)
    emit(out)
def _lock_view(tdir, ticket_id, ctx):
    lock = lib.read_lock(tdir)
    if not isinstance(lock, dict):
        return {"ok": True, "ticket_id": ticket_id, "held": False, "lock": None,
                "stale": None, "basis": None, "basis_detail": None, "held_by_me": False}
    stale, basis = lib.lock_staleness(lock)
    return {"ok": True, "ticket_id": ticket_id, "held": True, "lock": lock,
            "stale": stale, "basis": basis,
            "basis_detail": lib.LOCK_STALENESS_REASONS[basis],
            "held_by_me": lock.get("checkout_id") == ctx["checkout_id"]}


def cmd_lock_status(args):
    """What holds this ticket's lock, and on what evidence.

    `stale` is a verdict, `basis` is how it was reached — a lock held on
    another host has no liveness signal at all and degrades to an age timeout
    (lib.lock_staleness). Read both before breaking anything."""
    ticket_id, tdir, ctx = partition_or_die("lock status", args.ticket)
    view = _lock_view(tdir, ticket_id, ctx)
    view["lock_path"] = lib.lock_path(tdir)
    view["audit_path"] = lib.lock_audit_path(tdir)
    emit(view)


def cmd_lock_force_unlock(args):
    """Break a lock this checkout does not hold, recording who and why.

    The audited escape hatch for the case release_lock refuses by design: the
    holding session is gone but its lock is not (and, cross-host, will not read
    as stale for 24 hours). --reason is required and lands in the ticket's
    append-only lock-events.jsonl before the lock file is removed."""
    ticket_id, tdir, ctx = partition_or_die("lock force-unlock", args.ticket)
    before = _lock_view(tdir, ticket_id, ctx)
    if not before["held"]:
        emit({"ok": True, "ticket_id": ticket_id, "forced": False,
              "detail": "no lock file at %s" % lib.lock_path(tdir)})
        return
    if before["held_by_me"] and not args.force:
        die("lock force-unlock",
            "this checkout holds the lock — the post hook releases it; pass --force "
            "to break your own lock anyway")
    try:
        result = lib.force_release_lock(tdir, os.getcwd(), args.reason, actor=args.actor)
    except (ValueError, lib.GateError) as exc:
        die("lock force-unlock", str(exc))
    emit({"ok": True, "ticket_id": ticket_id, "forced": result["forced"],
          "detail": result["detail"], "audit_path": result["audit_path"],
          "broken_lock": result["lock"], "was_stale": before["stale"],
          "staleness_basis": before["basis"]})
def cmd_filemap_set(args):
    """Declare one executor task's file map, so the PreToolUse guard can enforce
    the executor charter's "mutate ONLY the files in your task's file map".

    Per task and additive: the coordinator declares them one at a time as it
    decomposes the plan, and declaring task 2 must not erase task 1."""
    ticket_id, tdir, _ctx = partition_or_die("filemap set", args.ticket)
    files = list(args.file)
    if args.files_from:
        files += [line.strip() for line in
                  read_lines_arg("filemap set", args.files_from) if line.strip()]
    if not files:
        die("filemap set", "declare at least one file (--file, or --files-from FILE)")
    tasks = lib.save_filemap_task(tdir, args.skill, args.iteration, args.task, files)
    emit({"ok": True, "ticket_id": ticket_id, "skill": args.skill,
          "iteration": str(args.iteration), "task": str(args.task),
          "files": tasks[str(args.task)],
          "path": lib.filemap_path(tdir, args.skill, args.iteration),
          "tasks": tasks})


def cmd_filemap_show(args):
    """The declared map for an iteration, plus the union the guard enforces."""
    ticket_id, tdir, _ctx = partition_or_die("filemap show", args.ticket)
    tasks = lib.load_filemap(tdir, args.skill, args.iteration) or {}
    emit({"ok": True, "ticket_id": ticket_id, "skill": args.skill,
          "iteration": str(args.iteration), "declared": bool(tasks), "tasks": tasks,
          "union": sorted({f for files in tasks.values() for f in files}),
          "path": lib.filemap_path(tdir, args.skill, args.iteration)})
def cmd_guard_events(args):
    """The file-map guard denials the latest run recorded.

    The audit trail /acs:metrics and external tooling read without knowing the
    state-file layout: one object, `events` in the order they were denied."""
    ticket_id, tdir, _ctx = partition_or_die("guard events", args.ticket)
    path = lib.state_path(tdir, args.skill)
    if not os.path.exists(path):
        die("guard events", "no %s state file at %s" % (args.skill, path))
    entry = lib.last_run(lib.load_state(tdir, args.skill, ticket_id)) or {}
    events = entry.get("guard_events") or []
    emit({"ok": True, "ticket_id": ticket_id, "skill": args.skill,
          "count": len(events), "events": events, "path": path})


def cmd_verdict_show(args):
    """The verifier's verdict for one iteration — validated, not just printed.

    `passed` in the output is DERIVED from the findings, so a document that
    claims otherwise shows up as an error here rather than as a pass."""
    ticket_id, tdir, _ctx = partition_or_die("verdict show", args.ticket)
    doc = lib.load_verdict(tdir, args.skill, args.iteration, args.lens)
    path = lib.verdict_path(tdir, args.skill, args.iteration, args.lens)
    if doc is None:
        die("verdict show", "no verdict at %s" % path)
    errors = lib.validate_verdict(doc, lens=args.lens, skill=args.skill,
                                  ticket_id=ticket_id, iteration=args.iteration)
    if errors:
        # `passed` is DERIVED from the findings, and an absent findings list
        # derives True -- so emitting it beside ok:false told the coordinator
        # (whose instructions say to copy `passed`, and never mention `ok`)
        # that an unusable document was a pass. A document we cannot validate
        # has no verdict to report.
        die("verdict show", "the verdict at %s is not usable: %s"
            % (path, "; ".join(errors)))
    emit({"ok": True, "ticket_id": ticket_id, "path": path,
          "passed": lib.derived_passed(doc), "claimed_passed": doc.get("passed"),
          "blocking": len(lib.blocking_findings(doc)), "errors": [],
          "verdict": doc})


def cmd_verdict_merge(args):
    """Merge the four full-depth lens verdicts into the iteration's verdict.

    Mechanical — passed is the conjunction, findings the union, each dimension
    the worst result any lens reported — so the coordinator INVOKES the merge
    rather than authoring a verdict it did not reach."""
    ticket_id, tdir, _ctx = partition_or_die("verdict merge", args.ticket)
    lenses = args.lens or list(lib.LENSES)
    # All four, always. --lens was an append flag with no completeness rule, so
    # `--lens A --lens C` merged a SUBSET and dropped lens B's blocking
    # findings while reporting ok/passed -- a coordinator-run command that
    # silently discards a verifier's verdict, which is what AC-3 forbids.
    if sorted(set(lenses)) != sorted(lib.LENSES):
        die("verdict merge",
            "a merge covers all four lenses (%s); got %s. A subset drops the "
            "findings of the lenses left out."
            % (", ".join(lib.LENSES), ", ".join(sorted(set(lenses)))))
    docs, missing = [], []
    for lens in lenses:
        doc = lib.load_verdict(tdir, args.skill, args.iteration, lens)
        if doc is None:
            missing.append(lens)
        else:
            docs.append(doc)
    if missing:
        die("verdict merge", "no verdict for lens %s (iteration %s)"
            % (", ".join(missing), args.iteration))
    merged = lib.merge_lens_verdicts(docs)
    merged["written_at"] = lib.now_iso()
    errors = lib.validate_verdict(merged)
    if errors:
        die("verdict merge", "the merged verdict is not well formed: %s" % "; ".join(errors))
    existing = lib.load_verdict(tdir, args.skill, args.iteration)
    if existing is not None and lib.blocking_findings(existing) and merged["passed"]:
        die("verdict merge",
            "%s already holds a verdict with %d blocking finding(s); refusing to "
            "replace it with a passing one. Fix the findings and re-run the "
            "verifier rather than overwriting its verdict."
            % (lib.verdict_path(tdir, args.skill, args.iteration),
               len(lib.blocking_findings(existing))))
    path = lib.write_verdict(tdir, args.skill, args.iteration, merged)
    emit({"ok": True, "ticket_id": ticket_id, "path": path, "passed": merged["passed"],
          "merged_from": merged["merged_from"], "blocking": len(lib.blocking_findings(merged)),
          "verdict": merged})


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
    # Probed ONCE: missing_tools() re-runs check_toolchain internally, so calling
    # both spawned every `<tool> --version` subprocess twice, each with a 5s
    # timeout.
    rows = lib.check_toolchain(settings)
    missing = lib.missing_tools(settings, rows=rows)
    required_missing = lib.missing_tools(settings, kinds=("required",), rows=rows)
    # `ok` is the verdict the module contract tells callers to read, so it must
    # answer "is the toolchain usable?" — not be a constant.
    emit({"ok": not required_missing, "context": ctx is not None,
          "toolchain": rows, "missing": missing,
          "missing_required": required_missing})
