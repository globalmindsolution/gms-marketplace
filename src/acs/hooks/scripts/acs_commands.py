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
from acs_lib import workflow  # noqa: E402

from acs_cli import (context_or_die, die, emit, load_ticket_or_die,
    partition_or_die, read_json_arg, run_or_die)  # noqa: E402


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
    if args.skill not in lib.HOOKED_SKILLS:
        die("gate", "unknown skill %r (expected one of %s)"
            % (args.skill, ", ".join(sorted(lib.HOOKED_SKILLS))))
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
# delivery path
# ---------------------------------------------------------------------------

def _resolve_run(command, run_id=None):
    """(rdir, doc, ctx, wf) for the run this command acts on.

    Every `acs run` / `acs step` verb defaults to THIS CHECKOUT'S CURRENT RUN
    and takes --run only to name another, because nobody should have to type a
    run id (§4.9). The pointer already records it.
    """
    ctx = context_or_die(command)
    repo = lib.repo_dir(ctx["workspace"], ctx["repo_id"])
    if run_id is None:
        run_id = lib.current_run_id(ctx)
    if not run_id:
        die(command, "no current run for this checkout, and no --run given. "
                     "Start one by invoking a skill with a ticket id, a prompt or a "
                     "document, or name an existing run with --run.")
    rdir = lib.run_dir(repo, run_id)
    doc = lib.load_run(rdir)
    if doc is None:
        die(command, "no run %r (expected %s)" % (run_id, rdir))
    try:
        resolved = lib.resolve_workflow(ctx.get("checkout_root"))
        wf = lib.validate_workflow_file(resolved["path"])
    except lib.WorkflowError as exc:
        die(command, str(exc))
    return rdir, doc, ctx, wf


def cmd_run_show(args):
    """The run ledger: its subject, status, cursor, steps and loops."""
    _rdir, doc, _ctx, _wf = _resolve_run("run show", args.run)
    emit({"ok": True, "run": doc})


def cmd_run_next(args):
    """The cursor: the first step in workflow order that is not completed.

    This replaces `workflow next`'s ready-set. With no `needs:` graph there is
    nothing to traverse and nothing to record as skipped -- one step is next,
    or the run is done."""
    _rdir, doc, _ctx, wf = _resolve_run("run next", args.run)
    cursor = lib.cursor(doc, wf)
    emit({"ok": True, "run_id": doc["run_id"], "next": cursor,
          "status": doc.get("status"),
          "done": cursor is None})


def cmd_run_check(args):
    """Invariants I1-I5 (§4.3). Exit 2 when the ledger has drifted, so a
    caller can refuse to write to it rather than discovering the drift three
    steps later."""
    rdir, doc, _ctx, wf = _resolve_run("run check", args.run)
    errors, warnings = lib.check_run(rdir, wf)
    emit({"ok": not errors, "run_id": doc["run_id"],
          "errors": errors, "warnings": warnings})
    if errors:
        die("run check", "; ".join(errors))


def cmd_run_abandon(args):
    """run -> abandoned. The one transition no hook makes: a human decides a
    run is not worth finishing."""
    rdir, doc, _ctx, _wf = _resolve_run("run abandon", args.run)
    if not args.reason:
        die("run abandon", "--reason is required: an abandoned run that does not say why "
                           "is a run somebody re-reads in a month and cannot act on.")
    doc = lib.abandon_run(rdir, args.reason)
    emit({"ok": True, "run_id": doc["run_id"], "status": doc["status"],
          "reason": args.reason})


def cmd_run_new(args):
    """Record a new run over a subject: a ticket id, a prompt or a document.
    The id is DERIVED from the subject (§4.2), never allocated."""
    ctx = context_or_die("run new")
    repo = lib.repo_dir(ctx["workspace"], ctx["repo_id"])
    subject = _subject_from_args(args)
    try:
        resolved = lib.resolve_workflow(ctx.get("checkout_root"))
        wf = lib.validate_workflow_file(resolved["path"])
        run_id, rdir, doc = lib.create_run(repo, subject, wf, resolved["path"])
    except (lib.WorkflowError, lib.GateError) as exc:
        die("run new", str(exc))
    lib.point_checkout_at(ctx, run_id)
    emit({"ok": True, "run_id": run_id, "path": rdir, "subject": subject,
          "cursor": doc.get("cursor")})


def _subject_from_args(args):
    if args.ticket:
        return {"kind": "ticket", "ticket_id": args.ticket}
    if args.document:
        import hashlib
        try:
            with open(args.document, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
        except OSError as exc:
            die("run new", "cannot read %s: %s" % (args.document, exc))
        return {"kind": "document", "path": args.document, "sha256": digest}
    if args.prompt:
        return {"kind": "prompt", "text": args.prompt}
    die("run new", "give a subject: --ticket, --prompt or --document.")


# ---------------------------------------------------------------------------
# the step machine
# ---------------------------------------------------------------------------

def _ctx_of(rdir):
    """The context a run directory sits in. Cheap to rebuild and safer than
    threading ctx through: the pointer write must name THIS checkout."""
    return context_or_die("step start")


def cmd_step_start(args):
    """step -> in_progress, after the invariants hold. Writer for the
    PreToolUse(Skill) transition."""
    rdir, doc, _ctx, wf = _resolve_run("step start", args.run)
    in_workflow = _require_step(wf, args.step, "step start")
    try:
        # The lock, before the transition. This is the WRITER for `in_progress`
        # (§4.3), and a transition written without the lock is exactly the
        # two-sessions-one-ledger interleaving the lock exists to prevent. The
        # gate takes it too; acquiring it twice from one checkout is a no-op.
        ok, message = lib.check_lock(rdir, _ctx["checkout_id"])
        if not ok:
            die("step start", message)
        lib.acquire_lock(rdir, _ctx.get("checkout_root") or os.getcwd())
        lib.check_invariants(rdir, wf)
        # What the PREVIOUS invocation left behind, read before this one opens
        # (§4.4 resumption). A step recorded `interrupted` or `failed` is simply
        # re-run, and the coordinator reconciles recorded state against reality
        # rather than trusting it -- so it has to be told there is something to
        # reconcile, and handed whatever the last session flushed.
        previous = lib.last_invocation(lib.load_step_state(rdir, args.step, doc["run_id"])) or {}
        reconcile = previous.get("status") in ("interrupted", "failed")
        handoff_summary = previous.get("handoff_summary") if reconcile else None
        if in_workflow:
            doc = lib.start_step(rdir, args.step, wf)
        # Both machines, one verb. The run records the TRANSITION and the step
        # opens the INVOCATION; a caller that got only the first would leave a
        # step in_progress with no record of the session doing it, and the
        # guard would have no invocation to append its denials to.
        # Gate evidence (MAR-583), which §7 keeps: weigh whether
        # PreToolUse(Skill) actually fired for this step, record the verdict on
        # the invocation, and SAY SO when it cannot be confirmed. The evidence
        # is written fail-open, so a failed write looks exactly like a runtime
        # that never fired the hook -- which is why the run reports itself
        # degraded rather than pretending either way.
        ctx = _ctx_of(rdir)
        evidence, verdict = lib.gate_evidence(ctx, args.step)
        lib.append_invocation(rdir, args.step, doc["run_id"], gate=verdict)
        if evidence is not None:
            lib.consume_gate_evidence(ctx, evidence)
        lib.point_checkout_at(ctx, doc["run_id"], args.step)
    except lib.GateError as exc:
        die("step start", str(exc))
    notice = lib.gate_notice(verdict)
    if notice:
        sys.stderr.write(notice + "\n")
    entry = lib.step_entry(doc, args.step)
    emit({"ok": True, "run_id": doc["run_id"], "step": args.step,
          "status": entry.get("status") or "in_progress",
          "in_workflow": in_workflow, "gate_enforcement": verdict,
          "iteration": lib.iteration_of(doc, args.step, wf) if in_workflow else 1,
          "reconcile": reconcile, "handoff_summary": handoff_summary,
          "prior_status": previous.get("status")})


def cmd_step_finish(args):
    """step -> completed / failed / interrupted, then the cursor, the loop and
    the run's own status. One writer owns every consequence of a step ending,
    which is what keeps them consistent."""
    rdir, doc, _ctx, wf = _resolve_run("step finish", args.run)
    in_workflow = _require_step(wf, args.step, "step finish")
    outcome, summary, status, stop_reason = args.outcome, args.summary, args.status, args.stop_reason
    if args.no_op:
        status = "completed"
    elif not args.status:
        result = lib.load_result(rdir, args.step)
        if result is None:
            die("step finish", "no result.json for %s — a step's transition is read from "
                               "its result document, not asserted on the command line "
                               "(pass --status to override for a step that cannot write one)."
                               % args.step)
        errors = lib.validate_result(result, args.step)
        if errors:
            die("step finish", "result.json is not admissible: %s" % "; ".join(errors))
        status = result.get("status")
        outcome = outcome or result.get("outcome")
        summary = summary or result.get("summary")
        stop_reason = stop_reason or result.get("stop_reason")
    try:
        if in_workflow:
            doc = lib.finish_step(rdir, args.step, wf, status=status, outcome=outcome,
                                  summary=summary, stop_reason=stop_reason)
    except lib.GateError as exc:
        die("step finish", str(exc))
    emit({"ok": True, "run_id": doc["run_id"], "step": args.step,
          "status": lib.step_entry(doc, args.step).get("status") or status,
          "in_workflow": in_workflow,
          "outcome": outcome, "cursor": doc.get("cursor"),
          "run_status": doc.get("status"),
          "loops": doc.get("loops") or {}})


def cmd_step_show(args):
    """One step's own state: its invocations, states, findings and errors."""
    rdir, doc, _ctx, _wf = _resolve_run("step show", args.run)
    emit({"ok": True, "run_id": doc["run_id"], "step": args.step,
          "entry": lib.step_entry(doc, args.step),
          "state": lib.load_step_state(rdir, args.step, doc["run_id"])})


def _require_step(wf, step, command):
    """`--step` validates against the RESOLVED WORKFLOW and, failing that, the
    SKILL DIRECTORIES. That is two open sources of truth in place of the
    argparse enum that was the closed skill list in its fourth place.

    Returns True when the workflow names it. A skill the workflow does not name
    is not an error: `/acs:standardize-project` and the product skills are real
    skills with real state, invoked on their own (§3.11). They keep their step
    state -- the two machines are separate, which is what makes this possible
    -- and record no run transition, because they have no position in a run and
    I5 would refuse one.
    """
    if lib.has_step(wf, step):
        return True
    if not lib.is_skill(step):
        die(command, "%r is neither a step of this workflow (%s) nor a skill "
                     "directory" % (step, ", ".join(lib.steps_of(wf))))
    return False


def cmd_result_validate(args):
    """Check a step's result document BEFORE the post-hook consumes it: the
    central envelope, then the skill's OWN outcome vocabulary. Replaces
    `phase validate` -- "phase" meant three unrelated things, and this one is
    the result document."""
    result = read_json_arg("result validate", args.result_file)
    errors = lib.validate_result(result, args.skill)
    # A REPORT, not a refusal: the whole point is to check a document before
    # the post-hook consumes it, so an inadmissible one is the answer rather
    # than an error. Exit 2 is reserved for a file that could not be read,
    # which is a usage mistake rather than a finding about the document.
    emit({"ok": not errors, "skill": args.skill, "status": result.get("status"),
          "outcome": result.get("outcome"),
          "vocabulary": lib.outcome_vocabulary(args.skill), "errors": errors})


# ---------------------------------------------------------------------------
# file lists
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

    Refuses to write a delivery path: it is judged once from the plan and
    recorded through `acs.py path set`, which is the call that refuses to move
    a ticket already on one (ADR-0095)."""
    ticket_id, tdir, ctx = partition_or_die("ticket save", args.ticket)
    current = load_ticket_or_die("ticket save", tdir, ticket_id)
    incoming = read_json_arg("ticket save", args.source)

    if not current.get("id"):
        die("ticket save", "the stored ticket.json for %s has no id" % ticket_id)
    if "id" in incoming and incoming["id"] != current["id"]:
        die("ticket save", "document id %r does not match the partition's %r"
            % (incoming.get("id"), current.get("id")))
    guarded = [k for k in ("delivery_path", "delivery_path_reason")
               if k in incoming and incoming[k] != current.get(k)]
    if guarded:
        die("ticket save", "%s is not a ticket field — the delivery path lives on "
            "pipeline-state.json and moves only through `acs.py path set`"
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
    run_id, rdir, ctx = run_or_die("lock status", args.run)
    view = _lock_view(rdir, run_id, ctx)
    view["lock_path"] = lib.lock_path(rdir)
    view["audit_path"] = lib.lock_audit_path(rdir)
    emit(view)


def cmd_lock_force_unlock(args):
    """Break a lock this checkout does not hold, recording who and why.

    The audited escape hatch for the case release_lock refuses by design: the
    holding session is gone but its lock is not (and, cross-host, will not read
    as stale for 24 hours). --reason is required and lands in the ticket's
    append-only lock-events.jsonl before the lock file is removed."""
    run_id, rdir, ctx = run_or_die("lock force-unlock", args.run)
    before = _lock_view(rdir, run_id, ctx)
    if not before["held"]:
        emit({"ok": True, "run_id": run_id, "forced": False,
              "detail": "no lock file at %s" % lib.lock_path(rdir)})
        return
    if before["held_by_me"] and not args.force:
        die("lock force-unlock",
            "this checkout holds the lock — the post hook releases it; pass --force "
            "to break your own lock anyway")
    try:
        result = lib.force_release_lock(rdir, os.getcwd(), args.reason, actor=args.actor)
    except (ValueError, lib.GateError) as exc:
        die("lock force-unlock", str(exc))
    emit({"ok": True, "run_id": run_id, "forced": result["forced"],
          "detail": result["detail"], "audit_path": result["audit_path"],
          "broken_lock": result["lock"], "was_stale": before["stale"],
          "staleness_basis": before["basis"]})
def cmd_filemap_set(args):
    """Declare one executor task's file map, so the PreToolUse guard can enforce
    the executor charter's "mutate ONLY the files in your task's file map".

    Per task and additive: the coordinator declares them one at a time as it
    decomposes the plan, and declaring task 2 must not erase task 1."""
    run_id, rdir, _ctx = run_or_die("filemap set", args.run)
    files = list(args.file)
    if args.files_from:
        files += [line.strip() for line in
                  read_lines_arg("filemap set", args.files_from) if line.strip()]
    if not files:
        die("filemap set", "declare at least one file (--file, or --files-from FILE)")
    tasks = lib.save_filemap_task(rdir, args.skill, args.iteration, args.task, files)
    emit({"ok": True, "run_id": run_id, "skill": args.skill,
          "iteration": str(args.iteration), "task": str(args.task),
          "files": tasks[str(args.task)],
          "path": lib.filemap_path(rdir, args.skill, args.iteration),
          "tasks": tasks})


def cmd_filemap_show(args):
    """The declared map for an iteration, plus the union the guard enforces."""
    run_id, rdir, _ctx = run_or_die("filemap show", args.run)
    tasks = lib.load_filemap(rdir, args.skill, args.iteration) or {}
    emit({"ok": True, "run_id": run_id, "skill": args.skill,
          "iteration": str(args.iteration), "declared": bool(tasks), "tasks": tasks,
          "union": sorted({f for files in tasks.values() for f in files}),
          "path": lib.filemap_path(rdir, args.skill, args.iteration)})
def cmd_guard_events(args):
    """The file-map guard denials the latest run recorded.

    The audit trail /acs:metrics and external tooling read without knowing the
    state-file layout: one object, `events` in the order they were denied."""
    run_id, rdir, _ctx = run_or_die("guard events", args.run)
    path = lib.state_path(rdir, args.skill)
    if not os.path.exists(path):
        die("guard events", "no %s state file at %s" % (args.skill, path))
    entry = lib.last_invocation(lib.load_state(rdir, args.skill, run_id)) or {}
    events = entry.get("guard_events") or []
    emit({"ok": True, "run_id": run_id, "skill": args.skill,
          "count": len(events), "events": events, "path": path})


def cmd_verdict_show(args):
    """The verifier's verdict for one iteration — validated, not just printed.

    `passed` in the output is DERIVED from the findings, so a document that
    claims otherwise shows up as an error here rather than as a pass."""
    run_id, rdir, _ctx = run_or_die("verdict show", args.run)
    doc = lib.load_verdict(rdir, args.skill, args.iteration, args.lens)
    path = lib.verdict_path(rdir, args.skill, args.iteration, args.lens)
    if doc is None:
        die("verdict show", "no verdict at %s" % path)
    errors = lib.validate_verdict(doc, lens=args.lens, skill=args.skill,
                                  run_id=run_id, iteration=args.iteration)
    if errors:
        # `passed` is DERIVED from the findings, and an absent findings list
        # derives True -- so emitting it beside ok:false told the coordinator
        # (whose instructions say to copy `passed`, and never mention `ok`)
        # that an unusable document was a pass. A document we cannot validate
        # has no verdict to report.
        die("verdict show", "the verdict at %s is not usable: %s"
            % (path, "; ".join(errors)))
    emit({"ok": True, "run_id": run_id, "path": path,
          "passed": lib.derived_passed(doc), "claimed_passed": doc.get("passed"),
          "blocking": len(lib.blocking_findings(doc)), "errors": [],
          "verdict": doc})


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


# ---------------------------------------------------------------------------
# workflow — the declarative ship pipeline (workflows/ship.yaml)
# ---------------------------------------------------------------------------

def _checkout_root_or_die(command):
    """`show` and `validate` are about FILES: they need the checkout (where
    the override would live), not a configured workspace, so `validate
    --file` works on a repo that has not run /acs:setup yet."""
    root = lib.checkout_root(os.getcwd())
    if not root:
        die(command, "acs requires a git repository; %s is not inside one." % os.getcwd())
    return root


def cmd_workflow_show(args):
    """The resolved workflow: the consumer's .acs/workflows/ship.yaml when
    present, else the plugin default. Parsed, not validated -- `validate`
    is the check; `show` answers "which file, and what does it say"."""
    root = _checkout_root_or_die("workflow show")
    try:
        resolved = lib.resolve_workflow(root)
    except lib.WorkflowError as exc:
        die("workflow show", str(exc))
    emit({"ok": True, "source": resolved["source"], "path": resolved["path"],
          "workflow": resolved["workflow"]})


def cmd_workflow_validate(args):
    """Schema plus semantic checks over the resolved workflow (or --file).
    Exit 0 with the step list; exit 2 with `<path>:<line>: <reason>` on
    stderr, echoed as `{ok: false, line, reason}` on stdout."""
    if args.file:
        source, path = "file", args.file
    else:
        root = _checkout_root_or_die("workflow validate")
        try:
            resolved = lib.resolve_workflow(root)
        except lib.WorkflowError as exc:
            die("workflow validate", str(exc))
        source, path = resolved["source"], resolved["path"]
    try:
        doc = lib.validate_workflow_file(path)
    except lib.WorkflowError as exc:
        emit({"ok": False, "source": source, "path": path, "line": exc.line,
              "reason": exc.reason})
        die("workflow validate", str(exc))
    emit({"ok": True, "source": source, "path": path,
          "name": lib.workflow_name(path), "version": doc.get("version"),
          "steps": lib.steps_of(doc), "loops": lib.loops_of(doc),
          "warnings": lib.order_warnings(doc)})


def cmd_artifacts_show(args):
    """Where one ticket's documents live (docs folder, partition or legacy
    location), whether the tree is active, and the derived status. Read-only,
    so an archived ticket is answered too."""
    ctx = context_or_die("artifacts show")
    try:
        ticket_id, tdir, _archived = lib.resolve_active_partition(
            os.getcwd(), ctx, explicit=args.ticket, allow_archived=True)
        out = lib.artifacts.describe(ctx, ticket_id, tdir)
    except lib.GateError as exc:
        die("artifacts show", str(exc))
    emit(dict(out, ok=True))
