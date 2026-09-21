"""acs_lib.posthook — what happens when a step ENDS.

Carved out of `gates.py`, which had grown past the 800-line budget the E1
split set. The seam is the one the file's own section comment already drew:
everything here runs after a coordinator has finished, from the post-hook's
argv down to the archive a merged ticket leaves behind, and none of it is
reachable from the PreToolUse path.

`gates` re-exports every public name, so `lib.run_post` and
`lib.run_post_exempt_pr` resolve exactly as before.
"""

import json
import os
import shutil
import sys

from ._common import (DELIVERY_TICKET_SKILLS, GateError, WorkflowError, now_iso,
                      read_json, write_json)
from .repo import (GuardTimeout, archive_dir, current_branch,
                   find_ticket_partition, index_path, repo_dir, sessions_dir)
from .artifacts import load_ticket, save_ticket
from .tickets import update_index
from .metrics import update_metrics
from .lock import release_lock
from .step import STEP_STATUSES, STOP_REASONS
from .derive import DERIVED_KEYS, derive_states, disagreements
from . import derive, run as run_machine, sessions, step as step_machine, workflow

# `gates` owns the context, the epic lookup and the workflow resolver, and it
# imports this module's siblings rather than this module, so this is not a
# cycle.
from .gates import _workflow_for, build_context, parent_epic_dir

# ---------------------------------------------------------------------------
# Post-hook persistence
# ---------------------------------------------------------------------------

def _warn_unraisably(text):
    """Emit an advisory that must not cost the caller its `release_lock`.

    `run_post` passes a point of no return at `save_state`: the invocation is
    durably finalized from there, and the only calls to `release_lock` are
    inside the `try:` below it and in that `try:`'s GuardTimeout arm. An
    advisory written between the two that raises escapes `run_post`, skips
    `release_lock`, and wedges the run's brake until the 24h staleness timeout
    or an audited force_release -- so an unwritable stderr must not be able to
    strand the very step these advisories are reporting on.

    os.write, not sys.stderr.write, for the reason gates.run_pre_payload's
    evidence-write handler records from a real encounter: a buffered write leaves the message pending and the
    interpreter's flush at shutdown then fails where nothing can catch it
    (CPython exits 120). Writing the fd raises HERE, inside the handler, and
    leaves nothing behind. This makes only these advisories safe -- any other
    buffered stderr write in the process still exits 120 on an unwritable
    stderr, which is why the tests covering this assert the lock was RELEASED
    rather than asserting an exit code.
    """
    try:
        os.write(2, text.encode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        pass


def _read_result_from_argv():
    """post-<skill>.py CLI: --result-file <path> | JSON on stdin, plus convenience flags."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-file", help="path to a JSON result document")
    parser.add_argument("--run", help="run id (overrides the checkout pointer)")
    # A ticket-subject run's id IS the ticket id (§4.2), so the old spelling
    # keeps working rather than failing on an operator's muscle memory.
    parser.add_argument("--ticket", dest="run", help=argparse.SUPPRESS)
    # The STEP's terminal statuses, not the RUN's: this flag finalizes one
    # invocation. `abandoned` is a run-level human decision (`acs run
    # abandon`) and was never a status a post-hook could write.
    parser.add_argument("--status",
                        choices=[s for s in run_machine.STEP_STATUSES
                                 if s != "in_progress"])
    parser.add_argument("--stop-reason", choices=list(run_machine.STOP_REASONS))
    args = parser.parse_args()
    result = {}
    if args.result_file:
        data = read_json(args.result_file)
        if not isinstance(data, dict):
            sys.stderr.write("acs: result file %s is missing or not a JSON object\n" % args.result_file)
            sys.exit(1)
        result = data
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            try:
                result = json.loads(raw)
            except json.JSONDecodeError as exc:
                sys.stderr.write("acs: invalid JSON result on stdin: %s\n" % exc)
                sys.exit(1)
    if args.status:
        result["status"] = args.status
    if args.stop_reason:
        result["stop_reason"] = args.stop_reason
    if not result:
        # Defaulting an absent result to "completed" would finalize the run and
        # open the next gate on nothing at all. The status must be stated.
        if args.result_file:
            # Naming the path matters: told only "no result document", an
            # operator who did pass one would reissue the same command.
            sys.stderr.write(
                "acs: result file %s is empty — it must carry at least a status\n"
                % args.result_file)
        else:
            sys.stderr.write(
                "acs: no result document — pass --result-file <path>, JSON on stdin, "
                "or --status explicitly\n")
        sys.exit(1)
    if not result.get("status"):
        sys.stderr.write(
            "acs: result document has no 'status' — one of %s is required\n"
            % ", ".join(s for s in run_machine.STEP_STATUSES if s != "in_progress"))
        sys.exit(1)
    return result, args.run


def _epic_auto_done(ctx, ticket):
    """When the merged ticket is the last open child of an epic, mark the epic done."""
    parent_id, pdir = parent_epic_dir(ctx, ticket)
    if not parent_id or not pdir:
        return None
    index = read_json(index_path(ctx["workspace"], ctx["repo_id"])) or {"tickets": {}}
    parent_ticket = load_ticket(pdir)
    children = (parent_ticket or {}).get("children") or (index["tickets"].get(parent_id, {}).get("children")) or []
    if not children:
        return None
    for child in children:
        if child == ticket["id"]:
            continue
        entry = index["tickets"].get(child)
        if not entry or entry.get("status") != "done":
            return None
    if parent_ticket:
        parent_ticket["status"] = "done"
        save_ticket(pdir, parent_ticket)
        update_index(ctx["workspace"], ctx["repo_id"], parent_ticket)
        return parent_id
    return None


def _archive_partition(ctx, tdir, ticket_id):
    dest_root = archive_dir(ctx["workspace"], ctx["repo_id"])
    os.makedirs(dest_root, exist_ok=True)
    dest = os.path.join(dest_root, ticket_id)
    if os.path.isdir(dest):
        dest = os.path.join(dest_root, "%s-%s" % (ticket_id, now_iso().replace(":", "")))
    shutil.move(tdir, dest)
    return dest


def _clear_pointers_for_ticket(ctx, run_id):
    """Clear every checkout pointer that names this run.

    One DIRECTORY per checkout now (`sessions/<ckid>/pointer.json`), keyed on
    `run_id` -- five prefixed files keyed on `ticket_id` was the old shape
    (ADR-0097). It clears the pointer rather than removing the directory,
    because `session.json`, `cost.jsonl` and `runtime.json` are the checkout's
    and outlive any one run.
    """
    sdir = sessions_dir(ctx["workspace"], ctx["repo_id"])
    if not os.path.isdir(sdir):
        return
    repo = repo_dir(ctx["workspace"], ctx["repo_id"])
    for ckid in os.listdir(sdir):
        if not os.path.isdir(os.path.join(sdir, ckid)):
            continue
        pointer = sessions.load_pointer(repo, ckid)
        if isinstance(pointer, dict) and pointer.get("run_id") == run_id:
            try:
                sessions.save_pointer(repo, ckid, run_id=None)
            except OSError:
                pass


#: How the operator repairs the repo-level half of a post hook that hit a guard
#: timeout, keyed by "is this merge-pr". EVERY other hook has a next post hook
#: that rebuilds the index entry from ticket.json -- merge-pr is the terminal
#: one, so nothing runs after it and the gap it leaves is durable until someone
#: closes it. Telling a merge-pr operator "it self-heals" was worse than saying
#: nothing: it named a mechanism that does not exist for the one hook where the
#: consequences (partition never archived, pointer never cleared, parent epic
#: never completed) are permanent.
_POST_GUARD_REPAIR = {
    False: ("The index entry is rebuilt from ticket.json by the next post hook, "
            "so it self-heals."),
    True: ("merge-pr is the TERMINAL post hook: nothing runs after it, so this "
           "does NOT self-heal -- the index still reads in_review, the partition "
           "is not archived, the session pointer is not cleared, and a parent "
           "epic is not auto-completed. ticket.json already reads done, so the "
           "merge itself IS recorded and no work is lost; what is missing is "
           "repo-level bookkeeping. Surface this gap rather than repairing it "
           "blind."),
}


def run_post(skill):
    """Entry point for post-<skill>.py: persist one step's outcome.

    The order matters and is the same as before the re-key, because the
    reasoning behind it has not changed:

      1. DERIVE first (MAR-523). The gate-bearing states keys are computed
         from the artifacts, never read from the skill's own document, so
         what gets persisted is the derived view and the disagreements ride
         on the invocation record, which is append-only and audited.
      2. finalize the INVOCATION (the step machine), then transition the
         STEP (the run machine). One writer owns each.
      3. the ticket, the metrics and the lock last, because they are
         repo-level and a guard timeout there must leave the run's own record
         durable rather than stranded.
    """
    result, explicit_run = _read_result_from_argv()
    cwd = os.getcwd()
    try:
        ctx = build_context(cwd)
    except GateError as exc:
        sys.stderr.write("acs post-%s: %s\n" % (skill, exc))
        sys.exit(1)

    repo = repo_dir(ctx["workspace"], ctx["repo_id"])
    run_id = explicit_run or sessions.current_run_id(repo, ctx["checkout_id"])
    if not run_id:
        sys.stderr.write("acs post-%s: could not resolve the run (pass --run).\n" % skill)
        sys.exit(1)
    rdir = run_machine.run_dir(repo, run_id)
    doc = run_machine.load_run(rdir)
    if doc is None:
        sys.stderr.write("acs post-%s: no run %s at %s.\n" % (skill, run_id, rdir))
        sys.exit(1)
    try:
        wf = _workflow_for(ctx)
    except WorkflowError as exc:
        sys.stderr.write("acs post-%s: %s\n" % (skill, exc))
        sys.exit(1)

    errors = step_machine.validate_result(result, skill)
    if errors:
        sys.stderr.write("acs post-%s: the result document is not admissible: %s\n"
                         % (skill, "; ".join(errors)))
        sys.exit(1)
    status = result["status"]

    try:
        derived, notes = derive_states(
            rdir, skill, result, settings=ctx["settings"], run_id=run_id,
            since=(step_machine.last_invocation(
                step_machine.load_state(rdir, skill, run_id)) or {}).get("started_at"),
            branch=(result.get("states") or {}).get("branch") or current_branch(cwd))
    except Exception as exc:  # noqa: BLE001
        # A derivation that cannot run degrades to "not derived", never to a
        # stranded step: it happens BEFORE the finalize below, so anything it
        # raised would otherwise leave the invocation in_progress with the
        # lock held, and the next gate would refuse with "crashed or still
        # running elsewhere" while the coordinator's result was lost.
        derived, notes = {}, {"__error__": "derivation failed (%r); no key was "
                                           "computed from artifacts" % exc}
    conflicts = disagreements(result.get("states") or {}, derived)
    if derived:
        result.setdefault("states", {}).update(derived)

    # Persist the document itself, not only its effects. I3 requires a
    # completed step to have a result.json, and the reason it does is that the
    # invocation record says WHAT happened while the result says what the
    # skill claimed -- a step whose claim is gone cannot be audited against
    # its outcome later.
    write_json(step_machine.result_path(rdir, skill), result)
    state, entry = step_machine.finalize_invocation(rdir, skill, run_id, result)
    entry["derived_states"] = {"values": derived, "provenance": notes,
                               "overrode": [{"key": key, "supplied": was, "derived": now}
                                            for key, was, now in conflicts]}
    step_machine.save_state(rdir, skill, state)
    for key, was, now in conflicts:
        # Unraisable: this loop is already past save_state, so see _warn_unraisably.
        _warn_unraisably(
            "acs post-%s: states.%s was %r in the result document; the artifacts say "
            "%r (%s). The derived value is what was written.\n"
            % (skill, key, was, now, notes.get(key, "derived")))

    # The RUN transition, only for a step the workflow names. A skill invoked
    # on its own -- `standardize-project`, the product skills -- has step state
    # but no position in a run, and I5 refuses a `steps` entry that the
    # workflow does not name. The two machines are separate, which is what
    # lets the invocation above be recorded either way.
    if workflow.has_step(wf, skill):
        doc = run_machine.finish_step(
            rdir, skill, wf, status=status, outcome=result.get("outcome"),
            summary=result.get("summary") or result.get("stop_reason"),
            stop_reason=result.get("stop_reason"),
            extra={"leg": result["leg"]} if result.get("leg") else None)

    ticket_id = (doc.get("subject") or {}).get("ticket_id")
    tdir = None
    if ticket_id:
        tdir, _archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    epic_done = None
    archived_to = None
    # A mis-shaped `states.pr` degrades to "no number recorded" rather than
    # stranding the step. `states` is a bare object in result.schema.json, so
    # validate_result admits any JSON value here, and save_state above has
    # ALREADY persisted the invocation -- raising would escape the GuardTimeout
    # arm below, skip release_lock, and leave the next gate refusing a run that
    # in fact finished. Refusing is the pre-hook's job, and the brake in `gates`
    # still refuses this value there, so nothing is swallowed by warning here.
    recorded_pr = (result.get("states") or {}).get("pr")
    if recorded_pr is not None and not isinstance(recorded_pr, dict):
        # Unraisable, or this warning becomes the leak it exists to prevent.
        _warn_unraisably(
            "acs post-%s: states.pr is not an object (it is a %s), so no PR number "
            "was recorded in metrics.json. The step is finalized either way; correct "
            "the reference and the next gate will accept it.\n"
            % (skill, type(recorded_pr).__name__))
    try:
        ticket = load_ticket(tdir) if tdir and os.path.isdir(tdir) else None
        if ticket:
            if status == "completed":
                if skill == "create-pr" and ticket.get("status") != "done":
                    ticket["status"] = "in_review"
                    save_ticket(tdir, ticket)
                # A delivery-ticket skill opens its OWN PR, so a recorded
                # `states.pr` from one moves the ticket to review just as
                # create-pr does.
                if (skill in DELIVERY_TICKET_SKILLS
                        and recorded_pr
                        and ticket.get("status") != "done"):
                    ticket["status"] = "in_review"
                    save_ticket(tdir, ticket)
                if skill == "merge-pr":
                    ticket["status"] = "done"
                    save_ticket(tdir, ticket)
            update_index(ctx["workspace"], ctx["repo_id"], ticket)

        pr_number = recorded_pr.get("number") if isinstance(recorded_pr, dict) else None
        update_metrics(
            ctx["workspace"], ctx["repo_id"], run_entry=entry,
            pr_created=(status == "completed" and bool(recorded_pr)
                        and skill in (["create-pr"] + list(DELIVERY_TICKET_SKILLS))),
            pr_merged=(skill == "merge-pr" and status == "completed"),
            pr_number=pr_number,
        )
        release_lock(rdir, cwd)

        if doc.get("status") in run_machine.TERMINAL_RUN_STATUSES:
            sessions.save_pointer(repo, ctx["checkout_id"], run_id=None,
                                  checkout_path=ctx.get("checkout_root"))
        if skill == "merge-pr" and status == "completed" and ticket:
            epic_done = _epic_auto_done(ctx, ticket)
            # The index row says `archived: true`, so the archive has to exist.
            # These two calls were dropped in the run re-key while the claim
            # stayed: the partition was left live, `runs/<id>/` kept resolving
            # forever, every session pointer kept naming a merged ticket, and
            # `/acs:release --draft` -- which enumerates `archive/*` first --
            # silently fell back to git-log for every merged ticket.
            _clear_pointers_for_ticket(ctx, ticket_id)
            if tdir and os.path.isdir(tdir):
                archived_to = _archive_partition(ctx, tdir, ticket_id)
            update_index(ctx["workspace"], ctx["repo_id"], ticket, archived=True)
    except GuardTimeout as exc:
        release_lock(rdir, cwd)
        # The repo-level writers refuse rather than write unguarded, and they
        # sit AFTER the run-level writes, so this is a PARTIAL step. Say
        # exactly which half is durable -- the operator is repairing a
        # repo-level gap, not re-running the step. What "repair" means differs
        # by hook, which is what _POST_GUARD_REPAIR carries.
        sys.stderr.write(
            "acs post-%s: %s\n"
            "%s's invocation, result and run.json ARE written and the lock is "
            "released; the repo-level writes (tickets-index.json, metrics.json%s) "
            "are not. %s This run's tokens and cost are lost from metrics.json. "
            "Do NOT re-run this hook to repair it -- the step is already "
            "finalized, so a second call appends a second invocation.\n"
            % (skill, exc, run_id,
               ", and the partition archive" if skill == "merge-pr" else "",
               _POST_GUARD_REPAIR[skill == "merge-pr"]))
        sys.exit(1)

    out = {"ok": True, "skill": skill, "run_id": run_id, "status": status,
           "outcome": result.get("outcome"), "cursor": doc.get("cursor"),
           "run_status": doc.get("status")}
    if archived_to:
        out["archived_to"] = archived_to
    if epic_done:
        out["epic_done"] = epic_done
    print(json.dumps(out, indent=2))
