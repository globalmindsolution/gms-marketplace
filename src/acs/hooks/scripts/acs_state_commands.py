"""acs_state_commands — the acs.py handlers for the TWO STATE MACHINES.

Split out of `acs_commands` when it crossed the 800-line budget. The line is
by SUBJECT, not by size: everything here writes or reads `run.json` or a
step's `state.json` (§4.3/§4.4) — `acs run *`, `acs step *`, and the result
document a step finishes from. Nothing else in `acs_commands` touches either
file, and nothing here touches the forge, the tracker or the ticket tree.

`acs_commands` re-exports every handler, and `acs.py` re-exports those in
turn, so `acs.cmd_step_start` and friends keep resolving by name.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_lib import workflow  # noqa: E402

from acs_cli import context_or_die, die, emit, read_json_arg  # noqa: E402


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


#: The PR fields the exempt-pr validator reads.
_PR_VIEW_FIELDS = "number,state,headRefName,baseRefName,labels,isDraft,url"


def _exempt_pr_start(args, ctx, gate):
    """`/acs:merge-pr --pr N`: the sanctioned exempt merge of a PR that is not
    a run's. It resolves NO run and writes NO partition, lock, pointer or
    state -- an exempt PR is not a step of anything, and creating a run for it
    would put a position in a ledger nothing else will ever fill.

    Exits 2 with clean stderr, never a traceback, on any failure.
    """
    if args.step != "merge-pr":
        die("step start", "--pr is only valid with --step merge-pr (got --step %s)"
            % args.step)
    kind, pr_ref = lib.classify_merge_pr_arg(args.pr, ctx["settings"].get("ticket_prefix"))
    if kind != "exempt-pr" or not pr_ref:
        die("step start", "--pr %r does not parse to a PR reference "
                          "(use --pr N, #N, or a PR URL)" % args.pr)
    try:
        pr = lib.gh_pr_view(pr_ref, _PR_VIEW_FIELDS)
    except lib.GateError as exc:
        die("step start", str(exc))
    ok, message = lib.validate_exempt_pr(pr, ctx["settings"])
    if not ok:
        die("step start", message)
    notice = lib.gate_notice(gate)
    if notice:
        sys.stderr.write(notice + "\n")
    emit({
        "ok": True,
        "step": args.step,
        "mode": "exempt-pr",
        "repo_id": ctx["repo_id"],
        "workspace": ctx["workspace"],
        "checkout_id": ctx["checkout_id"],
        "checkout_root": ctx["checkout_root"],
        "plugin_root": ctx["plugin_root"],
        "settings": ctx["settings"],
        "settings_sources": ctx["settings_sources"],
        "gate_enforcement": gate,
        "exempt_reason": message,
        "pr": {
            "number": pr.get("number"),
            "url": pr.get("url"),
            "branch": pr.get("headRefName"),
            "base": pr.get("baseRefName"),
            "labels": lib._pr_labels(pr),
        },
    })


def _resume_id_for_allocate(args, ctx):
    """The ticket id an `--allocate` run is RESUMING, or None to mint a new one.

    Resume reuses the existing partition: `/acs:ship` re-invokes an interrupted
    `create-ticket` with the ticket id as its argument, and allocating again
    there would mint a second ticket for the same work.

    Only `--ticket`, or -- for `create-ticket` alone -- an `--args` value that
    IS an id, counts. The session pointer and the branch name do not: both name
    whatever this checkout last touched, which is not the same question as "is
    this run a resume".

    The `--args` half is narrowed to `create-ticket` because it is the only
    step `/acs:ship` re-invokes with the id as its argument. A product-level
    leg routes its own resume through `--ticket`, so args-derived reuse buys it
    nothing -- and would let a delivery ticket be adopted by a flow that never
    owned it, writing one flow's state into another's partition.
    """
    explicit = (args.ticket or "").strip() if getattr(args, "ticket", None) else ""
    if explicit:
        return explicit
    if args.step != "create-ticket":
        return None
    text = (getattr(args, "args", None) or "").strip()
    prefix = (ctx.get("settings") or {}).get("ticket_prefix")
    if text and prefix and lib.ticket_id_from_text(text, prefix) == text:
        return text
    return None


def _allocate_delivery_ticket(args, ctx):
    """Mint (or resume) the delivery ticket a product-level skill works under.

    These skills are never steps of `ship` (§2.4): they produce a document set
    and need a ticket to carry the work, so they allocate one at Start. That is
    the one thing `acs step start` does beyond the two state machines.
    """
    workspace, repo_id = ctx["workspace"], ctx["repo_id"]
    if args.doc_set and args.step != "create-docs":
        die("step start", "--doc-set is only valid with --step create-docs")
    if args.step not in lib.DELIVERY_TICKET_SKILLS and args.step != "create-ticket":
        die("step start", "--allocate is only valid for /acs:create-ticket and the "
                          "product-level skills")
    if args.step == "create-docs" and not args.doc_set:
        die("step start", "--step create-docs --allocate needs --doc-set <%s>: each "
                          "run delivers exactly one doc set" % "|".join(sorted(lib.DOC_SETS)))

    existing_id = _resume_id_for_allocate(args, ctx)
    if existing_id:
        existing_dir, archived = lib.find_ticket_partition(workspace, repo_id, existing_id)
        if not archived and os.path.isdir(existing_dir):
            existing = lib.load_ticket(existing_dir)
            if existing:
                if args.seed_next is not None:
                    die("step start",
                        "--seed-next repairs the id counter for a newly minted "
                        "ticket, but %s already has a live partition to resume, so "
                        "nothing would be minted and the seed would be ignored. "
                        "Drop --seed-next to resume it, or name an id that does "
                        "not exist yet." % existing_id)
                return existing_id, existing_dir, existing, True

    prefix = ctx["settings"]["ticket_prefix"]
    repo_root = ctx.get("main_repo_root") or ctx["checkout_root"]
    try:
        ticket_id = lib.allocate_ticket_id(workspace, repo_id, prefix,
                                           repo_root=repo_root, seed_next=args.seed_next)
    except lib.ReconciliationRequired as exc:
        die("step start", exc.render("acs.py step start --step %s --allocate "
                                     "--seed-next <n>" % args.step))
    except lib.GuardTimeout as exc:
        # No id was minted and no partition exists: nothing is durable, so this
        # is a clean refusal rather than a crash.
        die("step start", "%s\nNo ticket id was minted and no state was written; "
                          "re-run once the other writer finishes." % exc)
    tdir = lib.ticket_dir(workspace, repo_id, ticket_id)
    os.makedirs(tdir, exist_ok=True)
    title = args.title or (lib.DOC_SET_TITLES[args.doc_set] if args.doc_set
                           else lib.DELIVERY_TICKET_TITLES.get(args.step,
                                                               "(ticket under analysis)"))
    ttype = "task" if args.step in lib.DELIVERY_TICKET_SKILLS else args.ttype
    ticket = lib.new_ticket_doc(ticket_id, title, ttype, status="in_progress",
                                doc_set=args.doc_set)
    lib.save_ticket(tdir, ticket)
    try:
        lib.update_index(workspace, repo_id, ticket, archived=False)
    except lib.GuardTimeout as exc:
        die("step start", "%s\nThe id %s IS minted and its partition written, but "
                          "tickets-index.json has no entry for it yet; the entry is "
                          "rebuilt from ticket.json by the next write to the index, "
                          "and re-running resumes this same id." % (exc, ticket_id))
    return ticket_id, tdir, ticket, False


def _ensure_run_for_ticket(ctx, ticket_id):
    """The run whose subject is this ticket, created when absent, and pointed
    at by this checkout. Idempotent: a resumed allocation finds its own."""
    repo = lib.repo_dir(ctx["workspace"], ctx["repo_id"])
    rdir = lib.run_dir(repo, ticket_id)
    if lib.load_run(rdir) is None:
        wf, wf_path = lib.workflow_for(ctx, with_path=True)
        lib.create_run(repo, {"kind": "ticket", "ticket_id": ticket_id}, wf, wf_path,
                       run_id=ticket_id)
    lib.point_checkout_at(ctx, ticket_id, None)
    return rdir


def cmd_step_start(args):
    """step -> in_progress, after the invariants hold. Writer for the
    PreToolUse(Skill) transition."""
    # The gate verdict FIRST, and the refusal with it. Under
    # `hook_gates.when_absent: refuse` a run with no evidence that the gates
    # fired is blocked BEFORE any partition, lock, pointer or ledger write, so
    # a refused run leaves nothing to unwind and no invocation carrying a
    # verdict nobody acted on.
    ctx = context_or_die("step start")
    evidence, verdict = lib.gate_evidence(ctx, args.step)
    if verdict.get("response") == "refuse" and not verdict.get("gated"):
        notice = lib.gate_notice(verdict)
        if notice:
            sys.stderr.write(notice + "\n")
        sys.exit(2)
    if getattr(args, "pr", None):
        return _exempt_pr_start(args, ctx, verdict)
    allocated = None
    if getattr(args, "allocate", False):
        ticket_id, _tdir, _ticket, reused = _allocate_delivery_ticket(args, ctx)
        allocated = {"ticket_id": ticket_id, "reused": reused}
        args.run = args.run or ticket_id
        # A minted ticket needs the RUN that carries the work, and the run's
        # id IS the ticket id (§4.2). Without this the step has a subject and
        # nowhere to record itself, which is what "no run 'SHOP-1'" meant.
        _ensure_run_for_ticket(ctx, ticket_id)
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
        lib.append_invocation(rdir, args.step, doc["run_id"], gate=verdict)
        if evidence is not None:
            lib.consume_gate_evidence(ctx, evidence)
        lib.point_checkout_at(ctx, doc["run_id"], args.step)
    except lib.GateError as exc:
        die("step start", str(exc))
    notice = lib.gate_notice(verdict)
    if notice:
        sys.stderr.write(notice + "\n")
    out = _start_context(ctx, rdir, doc, args.step, wf,
                         in_workflow=in_workflow, gate=verdict, reconcile=reconcile,
                         handoff_summary=handoff_summary,
                         prior_status=previous.get("status"))
    if allocated:
        out["allocated"] = allocated
    emit(out)


def _start_context(ctx, rdir, doc, step, wf, in_workflow, gate,
                   reconcile, handoff_summary, prior_status):
    """The context document a coordinator parses at Start.

    It replaces skill-start.py's, and it is the same document for every skill
    (§3.11): one resolution, printed once, rather than a per-skill assembly
    each gate had its own copy of. `ticket` and `design` are present only when
    the run's SUBJECT is a ticket -- a run started from a prompt or a document
    has neither, and inventing empty ones would read as "no design required"
    rather than "not that kind of run".
    """
    entry = lib.step_entry(doc, step)
    subject = doc.get("subject") or {}
    ticket_id = subject.get("ticket_id")
    out = {
        "ok": True,
        "run_id": doc["run_id"],
        "step": step,
        "status": entry.get("status") or "in_progress",
        "in_workflow": in_workflow,
        "iteration": lib.iteration_of(doc, step, wf) if in_workflow else 1,
        "subject": subject,
        "ticket_id": ticket_id,
        "partition": rdir,
        "workflow": doc.get("workflow"),
        "cursor": doc.get("cursor"),
        "repo_id": ctx["repo_id"],
        "workspace": ctx["workspace"],
        "checkout_id": ctx["checkout_id"],
        "checkout_root": ctx["checkout_root"],
        "plugin_root": ctx["plugin_root"],
        "settings": ctx["settings"],
        "settings_sources": ctx["settings_sources"],
        "models": (ctx["settings"].get("models") or {}),
        "reconcile": reconcile,
        "handoff_summary": handoff_summary,
        "prior_status": prior_status,
        "gate_enforcement": gate,
    }
    if ticket_id:
        tdir, _archived = lib.find_ticket_partition(
            ctx["workspace"], ctx["repo_id"], ticket_id)
        ticket = lib.load_ticket(tdir)
        if isinstance(ticket, dict):
            out["ticket"] = ticket
            required, design_dir, source = lib.design_requirement(ctx, tdir, ticket)
            out["design"] = {"required": required, "dir": design_dir, "source": source}
    return out


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

