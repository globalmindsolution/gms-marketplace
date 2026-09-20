"""acs_lib.gates — context resolution, the pre-hook gates and post-hook
persistence (extracted from acs_lib.py by MAR-522).

Gates check inputs and safety brakes only; the pipeline order lives in
workflows/ship.yaml (acs_lib.workflow) and is advised, never enforced, here
(acs_lib.advisory).
"""


import fnmatch
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
import claude_code_adapter as cc  # noqa: E402

from ._common import (DELIVERY_TICKET_SKILLS, GateError, HOOKED_SKILLS, PRODUCT_SKILLS,
                      RUN_STATUSES, now_iso, plugin_root, read_json, write_json)
from .settings import load_settings, validate_settings
from .repo import GuardTimeout, archive_dir, checkout_id, current_branch, checkout_root, find_ticket_partition, index_path, main_repo_root, pointer_path, record_session_marker, repo_partition_id, resolve_ticket_id, sessions_dir, state_path
from .hostgates import record_gate_evidence
from .lock import check_lock, read_lock, release_lock
from .tickets import load_ticket, save_ticket, update_index
from .metrics import update_metrics
from .setup_helpers import classify_merge_pr_arg, tracker_cli_warning
from .derive import derive_states, disagreements
from . import workflow
from ._common import WorkflowError
from .repo import repo_dir
from . import run as run_machine
from . import sessions
from . import skills as skills_registry
from . import step as step_machine
from . import stepgate
from .gate_inputs import e2e_case_count  # noqa: F401
from .advisory import workflow_advisory



def run_post_exempt_pr(cwd):
    """Metrics-only post-hook for /acs:merge-pr --pr: bump the repo pr_merged
    metric via the existing update_metrics pr_merged path and touch nothing else —
    no ticket state, index write, pipeline, archive, lock, or pointer. Returns the
    confirmation dict; raises GateError if the context cannot be built."""
    ctx = build_context(cwd)
    update_metrics(ctx["workspace"], ctx["repo_id"], pr_merged=True)
    return {"ok": True, "mode": "exempt-pr", "pr_merged": True}


# ---------------------------------------------------------------------------
# Context resolution shared by hooks & helper scripts
# ---------------------------------------------------------------------------

def build_context(cwd, require_workspace=True):
    """Resolve everything deterministic about where we are. Raises GateError."""
    if not checkout_root(cwd):
        raise GateError("acs requires a git repository; %s is not inside one." % cwd)
    settings, sources = load_settings(cwd)
    if require_workspace and not sources:
        raise GateError("no .acs/settings.json found (user or project scope). Run /acs:setup first.")
    workspace = validate_settings(settings, cwd, require_workspace=require_workspace)
    repo_id = repo_partition_id(cwd)
    if not repo_id:
        raise GateError("could not derive a repo identity (git remote or directory name).")
    return {
        "cwd": cwd,
        "settings": settings,
        "settings_sources": sources,
        "workspace": workspace,
        "repo_id": repo_id,
        "checkout_id": checkout_id(cwd),
        "checkout_root": checkout_root(cwd),
        "main_repo_root": main_repo_root(cwd),
        "plugin_root": plugin_root(),
    }


def parent_epic_dir(ctx, ticket):
    parent = (ticket or {}).get("parent")
    if not parent:
        return None, None
    pdir, _archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], parent)
    return parent, (pdir if os.path.isdir(pdir) else None)


def design_requirement(ctx, tdir, ticket):
    """Returns (required, design_dir, source) — the partition whose design.md applies:
    the ticket's own when it needs design, else the parent epic's when that needs design."""
    if ticket.get("needs_design"):
        return True, tdir, "own"
    parent, pdir = parent_epic_dir(ctx, ticket)
    if parent and pdir:
        parent_ticket = load_ticket(pdir)
        if parent_ticket and parent_ticket.get("needs_design"):
            return True, pdir, "parent"
    return False, None, None


# ---------------------------------------------------------------------------
# The pre-hook gate
#
# A gate answers exactly two questions: does the artifact this skill READS
# exist, and would running now do damage that re-running cannot undo? It never
# answers a third -- is this skill next? Order is /acs:ship's business, via
# `acs run next`; a skill invoked by hand is never asked whether it is next,
# which is what makes every skill independently invocable (§3.11). Out of
# order costs one advisory line on stderr, exit 0.
#
# The seventeen per-skill gate functions and the four-family GATE_INPUTS
# partition that classified them are gone. The INPUT half is generic now: it
# reads skills/<name>/acs.yaml's reads.required, which is the same declaration
# `acs workflow validate` checks a step list's order against. One declaration,
# two enforcers, and they cannot disagree.
#
# What stayed per-skill is only what is genuinely a SAFETY BRAKE.
# ---------------------------------------------------------------------------

#: Safety brakes, by skill. Each returns None or raises GateError. These are
#: the checks that are not "does an input exist" -- the ones where running
#: anyway would do damage a re-run could not undo.
def _brake_code(ctx, rdir, doc, wf):
    """On the deep paths the plan must be APPROVED, and the approval must be
    for the plan that is on disk now. An implementer working from a plan the
    human approved a revision ago is the failure this prevents."""
    from . import plan_contract
    plan = run_machine.artifact_path(rdir, "plan", None, wf)
    if not plan or not os.path.isfile(plan):
        return None
    path = plan_contract.delivery_path(plan_contract.read(plan))
    if path not in ("standard", "complex"):
        return None
    approval = os.path.join(run_machine.step_dir(rdir, "create-impl-plan"),
                            "plan-approval.json")
    record = read_json(approval)
    if not isinstance(record, dict) or not record.get("approved"):
        raise GateError(
            "the %s delivery path requires an approved plan, and %s records none. "
            "Run /acs:create-impl-plan and approve its plan first." % (path, approval))
    digest = _sha256_file(plan)
    if record.get("plan_sha256") != digest:
        raise GateError(
            "the approval at %s is for a different revision of the plan (approved "
            "%s, on disk %s). An edited plan is an unapproved plan: re-approve it."
            % (approval, (record.get("plan_sha256") or "?")[:12], digest[:12]))
    return None


def _brake_create_pr(ctx, rdir, doc, wf):
    """A review that did not pass never becomes a PR. verifier_passed is
    DERIVED from review-code's verdict by the post-hook (MAR-523/527), so this
    reads the ledger rather than trusting any skill's self-report."""
    entry = run_machine.step_entry(doc, "review-code")
    if not entry:
        return None
    state = step_machine.load_state(rdir, "review-code", doc["run_id"])
    if state.get("states", {}).get("verifier_passed") is not True:
        raise GateError(
            "/acs:review-code ran for this run and did not pass (verifier_passed is not "
            "true). Fix the findings in its verdict and re-review before opening a PR.")
    return None


def _merge_pr_arg_text(payload):
    """The raw argument string, read the same way subject_from_payload reads
    it. /acs:merge-pr's exempt non-ticket forms (--pr N, #N, a PR URL) are
    parsed from this before any run is resolved: an exempt PR merge is not a
    step of a run and must not create one."""
    tool_input = payload.get("tool_input") or {}
    for key in ("args", "arguments", "argument"):
        if isinstance(tool_input.get(key), str):
            return tool_input[key]
    return ""


def _sha256_file(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


BRAKES = {
    "code": _brake_code,
    "create-pr": _brake_create_pr,
}


def _require_architecture_doc_set(ctx):
    root = ctx["checkout_root"]
    base = os.path.join(root, ctx["settings"].get("architecture_path", "docs/architecture"))
    if not os.path.isdir(base):
        raise GateError("no architecture doc set at %s — run /acs:create-architecture first." % base)
    return None


#: Skills that need the architecture doc set before they can do anything.
ARCHITECTURE_GATED = ("project", "create-project", "standardize-project", "create-docs")


def gate_step(ctx, skill, payload, standalone=True):
    """The whole pre-hook gate for one skill. Returns the run id it gated, or
    None for a skill that is not a step (setup, metrics, handoff...).

    Order of business, and each line is load-bearing:
      1. a skill that is not a step has nothing here to check
      2. the run: this checkout's current one, or a new one over the subject
      3. the invariants, BEFORE any write (§4.3) -- a drifted ledger is
         refused here rather than discovered three steps later
      4. the inputs, from the skill's own declaration
      5. the safety brakes
      6. the no-op: nothing owed means the step is completed here and the
         coordinator is never spawned
    """
    manifests = skills_registry.load_manifests()
    if skill in ARCHITECTURE_GATED:
        _require_architecture_doc_set(ctx)

    # Only the skills the RESOLVED WORKFLOW runs go through a run. A skill
    # that declares reads/writes but is not a step of this workflow is a
    # skill someone invoked on its own -- and the design and product skills
    # (create-prd, create-architecture, create-ticket) are never steps of
    # `ship` at all. `create-ticket` in particular MAKES a subject; requiring
    # it to name one first would be circular.
    try:
        resolved = workflow.resolve_workflow(ctx.get("checkout_root"))
        wf = workflow.validate_workflow_file(resolved["path"])
    except WorkflowError as exc:
        raise GateError("the workflow does not validate: %s" % exc)
    if not workflow.has_step(wf, skill):
        return None

    rdir, doc, wf = resolve_run_for(ctx, skill, payload)
    if rdir is None:
        return None
    stepgate.check_invariants(rdir, wf, manifests)

    fell_back = stepgate.check_inputs(rdir, skill, manifests, wf, standalone=standalone)
    for artifact in fell_back:
        sys.stderr.write(
            "acs: no %s for this run; /acs:%s will work from the run's subject instead.\n"
            % (artifact, skill))

    brake = BRAKES.get(skill)
    if brake:
        brake(ctx, rdir, doc, wf)

    settled = stepgate.settle_no_op(rdir, skill, doc["run_id"], wf, manifests)
    if settled:
        outcome, reason = settled
        raise NothingOwed(skill, outcome, reason)
    return doc["run_id"]


class NothingOwed(Exception):
    """Not an error: the pre-hook settled this step because the plan said
    nothing was owed, so the coordinator must not run. Carried as an exception
    because it has to unwind the gate, but reported as a success."""

    def __init__(self, skill, outcome, reason):
        self.skill, self.outcome, self.reason = skill, outcome, reason
        super().__init__("%s: %s (%s)" % (skill, outcome, reason))


def resolve_run_for(ctx, skill, payload):
    """(rdir, doc, wf) for the run this invocation belongs to.

    The checkout's current run when it has one, else a new run over whatever
    subject the invocation named -- a ticket id, a prompt or a document. Every
    skill accepts all three (§3.11), so this is the same resolution for all of
    them.
    """
    repo = repo_dir(ctx["workspace"], ctx["repo_id"])
    try:
        resolved = workflow.resolve_workflow(ctx.get("checkout_root"))
        wf = workflow.validate_workflow_file(resolved["path"])
    except WorkflowError as exc:
        raise GateError("the workflow does not validate: %s" % exc)

    run_id = sessions.current_run_id(repo, ctx["checkout_id"])
    if run_id:
        rdir = run_machine.run_dir(repo, run_id)
        doc = run_machine.load_run(rdir)
        if doc is not None and doc.get("status") not in run_machine.TERMINAL_RUN_STATUSES:
            return rdir, doc, wf

    subject = subject_from_payload(ctx, payload)
    if subject is None:
        raise GateError(
            "no current run for this checkout and no subject in the invocation. "
            "Give /acs:%s a ticket id, a prompt or a path to a document." % skill)

    if subject["kind"] == "ticket":
        row = run_machine.latest_open_run(repo, "ticket", subject["ticket_id"])
        if row:
            rdir = run_machine.run_dir(repo, row["run_id"])
            sessions.save_pointer(repo, ctx["checkout_id"], run_id=row["run_id"],
                                  checkout_path=ctx.get("checkout_root"))
            return rdir, run_machine.require_run(rdir), wf

    run_id, rdir, doc = run_machine.create_run(repo, subject, wf, resolved["path"])
    sessions.save_pointer(repo, ctx["checkout_id"], run_id=run_id,
                          checkout_path=ctx.get("checkout_root"))
    return rdir, doc, wf


def subject_from_payload(ctx, payload):
    """A ticket id, a prompt or a document, from the skill's own arguments.

    The three are told apart by shape rather than by a flag: a bare token that
    looks like <PREFIX>-<n> is a ticket, an existing path is a document, and
    anything else is a prompt. A developer typing
    `/acs:code "fix the login timeout"` should not have to learn a flag.
    """
    tool_input = payload.get("tool_input") or {}
    text = ""
    for key in ("args", "arguments", "argument"):
        if isinstance(tool_input.get(key), str):
            text = tool_input[key].strip()
            break
    if not text:
        return None
    prefix = (ctx.get("settings") or {}).get("ticket_prefix") or "[A-Z]+"
    token = text.split()[0]
    if re.match(r"^%s-\d+$" % prefix, token):
        return {"kind": "ticket", "ticket_id": token}
    candidate = os.path.join(ctx.get("checkout_root") or ctx["cwd"], token)
    if os.path.isfile(candidate):
        return {"kind": "document", "path": token, "sha256": _sha256_file(candidate)}
    return {"kind": "prompt", "text": text}


def run_pre(skill):
    """Entry point for pre-<skill>.py: read the hook payload from stdin, gate, exit 0/2."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    sys.exit(run_pre_payload(skill, payload))


def run_pre_payload(skill, payload, record_marker=True):
    """Gate one skill from an already-parsed hook payload; return the exit code.

    Separate from run_pre so the dispatcher can gate in-process rather than
    spawning a forwarder: a subprocess that hangs or dies takes its exit code
    with it, and anything other than 2 lets the skill run.

    `record_marker=False` is for a caller that is NOT a hook event -- `acs.py
    gate`, which answers "would this gate pass?" without a PreToolUse envelope.
    Such a payload carries no session_id or transcript_path, and
    record_session_marker faithfully persists those as null (deliberately: it
    never guesses), which would overwrite the real marker and cost the next run
    its usage attribution.

    Once a ticket-scoped gate passes, the out-of-order advisory (one stderr
    line, exit still 0) is printed when the skill's ship.yaml needs are not
    satisfied for that ticket (acs_lib.advisory)."""
    cwd = cc.payload_cwd(payload)
    try:
        ctx = build_context(cwd)
        try:
            if record_marker:
                record_session_marker(ctx, payload)
        except Exception:  # a marker-write bug must never block a gated skill
            pass
        try:
            if record_marker:
                record_gate_evidence(ctx, skill)
        except Exception as exc:  # fail-open too (MAR-514), but not silently
            # This write is the only evidence skill-start has that the gate
            # fired, so a failure here is why a genuinely gated run will report
            # its enforcement as unconfirmed. The warning gets its OWN handler:
            # an unwritable stderr must not escape into the fail-closed arm
            # below and block the very run this arm exists to let through.
            #
            # os.write, not sys.stderr.write, because the handler is not the
            # last chance to fail: a buffered write leaves the message pending,
            # and the interpreter's flush at shutdown then fails where nothing
            # can catch it (CPython exits 120 -- seen on 3.12, not 3.11).
            # Writing the fd directly raises here, inside the handler, and
            # leaves nothing behind. Note this only makes THIS warning safe --
            # any other buffered stderr write in the same process still exits
            # 120 on an unwritable stderr, which is why the test that covers
            # this asserts the gate did not BLOCK rather than asserting 0.
            try:
                os.write(2, (
                    "acs: warning: could not record the gate's evidence (%r) — "
                    "this run proceeds gated, but will report its hook "
                    "enforcement as unconfirmed\n" % (exc,)
                ).encode("utf-8", "replace"))
            except Exception:
                pass
        warn = tracker_cli_warning(ctx["settings"])
        if warn:
            sys.stderr.write("acs: warning: %s\n" % warn)
        try:
            run_id = gate_step(ctx, skill, payload)
        except NothingOwed as owed:
            # Not a refusal to report as one: the step is COMPLETE. Exit 2
            # stops the Skill from running, which is the point -- no
            # coordinator, no tokens -- and the message says what was
            # recorded rather than what was wrong.
            sys.stderr.write(
                "acs: /acs:%s has nothing to do on this run — recorded %s (%s). "
                "The step is complete.\n" % (owed.skill, owed.outcome, owed.reason))
            return 2
        if run_id:
            advisory = workflow_advisory(ctx, skill, run_id)
            if advisory:
                sys.stderr.write(advisory + "\n")
            _mark_step_started(ctx, skill, run_id)
    except GateError as exc:
        sys.stderr.write("acs pre-%s: blocked — %s\n" % (skill, exc))
        return 2
    except TimeoutError as exc:  # a gate that never returns must not let the skill run
        sys.stderr.write("acs pre-%s: blocked — gate timed out: %s\n" % (skill, exc))
        return 2
    except Exception as exc:  # fail closed: a gating system must not fail open
        sys.stderr.write("acs pre-%s: blocked — unexpected error in gate: %r\n" % (skill, exc))
        return 2
    except (SystemExit, KeyboardInterrupt) as exc:
        # Neither is an Exception. A gate calling sys.exit(), or a SIGINT
        # arriving mid-gate, would otherwise leave this frame with an exit code
        # that is not 2 -- which Claude Code reads as "not blocked".
        sys.stderr.write("acs pre-%s: blocked — gate exited early: %r\n" % (skill, exc))
        return 2
    return 0


# ---------------------------------------------------------------------------
# Post-hook persistence
# ---------------------------------------------------------------------------

def _read_result_from_argv():
    """post-<skill>.py CLI: --result-file <path> | JSON on stdin, plus convenience flags."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-file", help="path to a JSON result document")
    parser.add_argument("--run", help="run id (overrides the checkout pointer)")
    parser.add_argument("--status", choices=[s for s in RUN_STATUSES if s != "in_progress"])
    parser.add_argument("--stop-reason")
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
            % ", ".join(s for s in RUN_STATUSES if s != "in_progress"))
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


def _clear_pointers_for_ticket(ctx, ticket_id):
    sdir = sessions_dir(ctx["workspace"], ctx["repo_id"])
    if not os.path.isdir(sdir):
        return
    for name in os.listdir(sdir):
        if not name.endswith(".json"):
            continue
        pointer = read_json(os.path.join(sdir, name))
        if isinstance(pointer, dict) and pointer.get("ticket_id") == ticket_id:
            try:
                os.unlink(os.path.join(sdir, name))
            except OSError:
                pass


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
        resolved = workflow.resolve_workflow(ctx.get("checkout_root"))
        wf = workflow.validate_workflow_file(resolved["path"])
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

    state = step_machine.finalize_invocation(rdir, skill, run_id, result)
    entry = step_machine.last_invocation(state) or {}
    entry["derived_states"] = {"values": derived, "provenance": notes,
                               "overrode": [{"key": key, "supplied": was, "derived": now}
                                            for key, was, now in conflicts]}
    step_machine.save_state(rdir, skill, state)
    for key, was, now in conflicts:
        sys.stderr.write(
            "acs post-%s: states.%s was %r in the result document; the artifacts say "
            "%r (%s). The derived value is what was written.\n"
            % (skill, key, was, now, notes.get(key, "derived")))

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
    try:
        ticket = load_ticket(tdir) if tdir and os.path.isdir(tdir) else None
        if ticket:
            if status == "completed":
                if skill == "create-pr" and ticket.get("status") != "done":
                    ticket["status"] = "in_review"
                    save_ticket(tdir, ticket)
                if skill == "merge-pr":
                    ticket["status"] = "done"
                    save_ticket(tdir, ticket)
            update_index(ctx["workspace"], ctx["repo_id"], ticket)

        pr_number = ((result.get("states") or {}).get("pr") or {}).get("number")
        update_metrics(
            ctx["workspace"], ctx["repo_id"], run_entry=entry,
            pr_created=(status == "completed" and bool((result.get("states") or {}).get("pr"))
                        and skill == "create-pr"),
            pr_merged=(skill == "merge-pr" and status == "completed"),
            pr_number=pr_number,
        )
        release_lock(rdir, cwd)

        if doc.get("status") in run_machine.TERMINAL_RUN_STATUSES:
            sessions.save_pointer(repo, ctx["checkout_id"], run_id=None,
                                  checkout_path=ctx.get("checkout_root"))
        if skill == "merge-pr" and status == "completed" and ticket:
            epic_done = _epic_auto_done(ctx, ticket)
            update_index(ctx["workspace"], ctx["repo_id"], ticket, archived=True)
    except GuardTimeout as exc:
        release_lock(rdir, cwd)
        sys.stderr.write(
            "acs post-%s: %s\n"
            "This step's invocation, result and run.json ARE written and the lock is "
            "released; the repo-level writes (tickets-index.json, metrics.json) are "
            "not. This run's tokens and cost are lost from metrics.json. Do NOT "
            "re-run this hook to repair it -- the step is already finalized, so a "
            "second call appends a second invocation.\n" % (skill, exc))
        sys.exit(1)

    out = {"ok": True, "skill": skill, "run_id": run_id, "status": status,
           "outcome": result.get("outcome"), "cursor": doc.get("cursor"),
           "run_status": doc.get("status")}
    if archived_to:
        out["archived_to"] = archived_to
    if epic_done:
        out["epic_done"] = epic_done
    print(json.dumps(out, indent=2))


def _mark_step_started(ctx, skill, run_id):
    """step -> in_progress, and the pointer follows it. The pre-hook is the
    one writer of this transition (§4.3)."""
    repo = repo_dir(ctx["workspace"], ctx["repo_id"])
    rdir = run_machine.run_dir(repo, run_id)
    try:
        resolved = workflow.resolve_workflow(ctx.get("checkout_root"))
        wf = workflow.validate_workflow_file(resolved["path"])
        run_machine.start_step(rdir, skill, wf)
        step_machine.append_invocation(rdir, skill, run_id)
        sessions.save_pointer(repo, ctx["checkout_id"], run_id=run_id, step=skill,
                              checkout_path=ctx.get("checkout_root"))
    except (GateError, WorkflowError) as exc:
        raise GateError(str(exc))


# ---------------------------------------------------------------------------
# SessionEnd safety net
# ---------------------------------------------------------------------------

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


def session_end(payload):
    """Finalize any run this checkout left in_progress as `interrupted` and release
    its lock — abnormal endings must still write state (docs/requirements/functional/hooks.md)."""
    cwd = cc.payload_cwd(payload)
    try:
        ctx = build_context(cwd)
    except GateError:
        return  # uninitialized repo: nothing to clean up
    pointer = read_json(pointer_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]))
    if not isinstance(pointer, dict) or not pointer.get("ticket_id"):
        return
    ticket_id = pointer["ticket_id"]
    tdir, archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    if archived or not os.path.isdir(tdir):
        return
    lock = read_lock(tdir)
    if not (isinstance(lock, dict) and lock.get("checkout_id") == ctx["checkout_id"]):
        return  # not our session's ticket anymore
    # The release is the POINT of this safety net, so it happens whatever the
    # repo-level writes do. update_metrics is guarded and now refuses rather
    # than writing unguarded; before this the raise skipped the release and
    # dispatch.py swallowed it, so the net exited 0 having left the ticket
    # locked by a process that no longer exists -- and a cross-host lock
    # stranded that way does not read as stale for 24 hours.
    try:
        for skill in HOOKED_SKILLS:
            state = read_json(state_path(tdir, skill))
            if not isinstance(state, dict):
                continue
            runs = state.get("runs") or []
            if runs and isinstance(runs[-1], dict) and runs[-1].get("status") == "in_progress":
                _state, entry = finalize_run(tdir, skill, ticket_id, {
                    "status": "interrupted",
                    "stop_reason": "session ended while the skill was in progress",
                })
                update_pipeline(tdir, ticket_id, skill, "interrupted",
                                summary="session ended mid-skill",
                                flow="product" if skill in PRODUCT_SKILLS else "ticket")
                # keep repo-level metrics consistent with the ticket ledger:
                # an interrupted run still spent time/tokens
                update_metrics(ctx["workspace"], ctx["repo_id"], run_entry=entry)
    except GuardTimeout as exc:
        sys.stderr.write(
            "acs session-end: %s\n%s's run is finalized as interrupted and the "
            "lock is released; metrics.json was not updated, so this run's tokens "
            "and cost are lost from it.\n" % (exc, ticket_id))
    finally:
        release_lock(tdir, cwd)
