"""acs_lib.gates — context resolution, the pre-hook gates and post-hook
persistence (extracted from acs_lib.py by MAR-522).

Gates check inputs and safety brakes only; the pipeline order lives in
workflows/ship.yaml (acs_lib.workflow) and is advised, never enforced, here
(acs_lib.advisory).
"""


import collections
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
                      now_iso, plugin_root, read_json, write_json)
from .settings import load_settings, validate_settings
from .repo import GuardTimeout, archive_dir, checkout_id, current_branch, checkout_root, find_ticket_partition, index_path, main_repo_root, pointer_path, record_session_marker, repo_partition_id, resolve_ticket_id, sessions_dir
from .hostgates import record_gate_evidence
from .lock import acquire_lock, check_lock, read_lock, release_lock
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
from .gate_inputs import _refuse_epic, e2e_case_count  # noqa: F401
from .advisory import workflow_advisory



def _workflow_for(ctx, with_path=False):
    """The resolved workflow for this checkout, and optionally where it came
    from. One spelling, because five copies of `resolve_workflow` +
    `validate_workflow_file` is five places for an override to be honoured in
    four."""
    resolved = workflow.resolve_workflow(ctx.get("checkout_root"))
    wf = workflow.validate_workflow_file(resolved["path"])
    return (wf, resolved["path"]) if with_path else wf


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
# What stayed per-skill is only what is genuinely a SAFETY BRAKE, and it sits
# in three tables consulted BEFORE the workflow is resolved: ARCHITECTURE_GATED
# and PRD_GATED for a repo DOCUMENT precondition, SUBJECT_GATES for one about
# the subject TICKET. All three gate skills that are legitimately not steps of
# `ship` (§2.4), which is why none of them may sit behind the `has_step`
# return -- a safety brake must not be switchable off by a workflow edit.
# ---------------------------------------------------------------------------

# The brakes themselves live in `acs_lib.brakes` (one layer down: they read
# the run and the repo, and resolve nothing). Re-exported here because every
# caller reaches them through `gates`.
from .brakes import (ARCHITECTURE_GATED, BRAKES, PRD_GATED,  # noqa: E402,F401
                     _brake_code, _brake_create_pr, _brake_no_epics,
                     _EPIC_VERBS, _merge_pr_arg_text, _require_prd,
                     _require_architecture_doc_set, _sha256_file)


def _run_dirs_for_ticket(repo, ticket_id):
    """Every run partition this ticket has, newest first.

    A second run on one subject is `<ticket>-r2` (`run.derive_run_id`), so the
    ticket-keyed join names at most the first of them and a lock or a PR
    recorded by any later one is invisible to it. The join stays as the last
    entry, so a run directory the index does not list is still asked."""
    rdirs, seen = [], set()
    for row in reversed(run_machine.find_runs_for_subject(repo, "ticket", ticket_id)):
        run_id = row.get("run_id")
        if run_id and run_id not in seen:
            seen.add(run_id)
            rdirs.append(run_machine.run_dir(repo, run_id))
    fallback, _archived = run_machine.partition_for_ticket(repo, ticket_id)
    if fallback not in rdirs:
        rdirs.append(fallback)
    return rdirs


def _resolve_ticket_for_gate(ctx, payload, skill):
    """(ticket_id, tdir, ticket) for a gate whose subject is a TICKET, not a run."""
    args_text = ""
    tool_input = payload.get("tool_input") or {}
    for key in ("args", "arguments", "argument"):
        if isinstance(tool_input.get(key), str):
            args_text = tool_input[key]
            break
    ticket_id, _source = resolve_ticket_id(ctx["cwd"], ctx["settings"], ctx["workspace"],
                                           ctx["repo_id"], args_text=args_text)
    if not ticket_id:
        raise GateError(
            "could not resolve a ticket id for /%s (no argument, no session pointer, "
            "no ticket in the branch name). Pass it explicitly, e.g. /acs:%s %s-123."
            % (skill, skill, ctx["settings"].get("ticket_prefix", "SHOP")))
    tdir, archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    if archived:
        raise GateError("ticket %s is done and archived (%s); nothing left to run."
                        % (ticket_id, tdir))
    if not os.path.isdir(tdir):
        raise GateError("no workspace partition for %s (expected %s) — run "
                        "/acs:create-ticket first." % (ticket_id, tdir))
    ticket = load_ticket(tdir)
    if not ticket:
        raise GateError("ticket file missing or corrupt at %s/ticket.json — treat as "
                        "not created; run /acs:create-ticket." % tdir)
    # v0.5.0 locks the RUN, not the ticket partition (§4.2), and a subject with
    # two runs has two locks (lock.py:11) -- so every run of this ticket is
    # asked, not only the one whose id happens to BE the ticket id. A ticket
    # that has never been run has nothing to be locked by.
    for rdir in _run_dirs_for_ticket(repo_dir(ctx["workspace"], ctx["repo_id"]),
                                     ticket_id):
        if not os.path.isdir(rdir):
            continue
        ok, message = check_lock(rdir, ctx["checkout_id"])
        if not ok:
            raise GateError(message)
    return ticket_id, tdir, ticket


def gate_create_design(ctx, payload):
    """Brake: a design is only written for a design-significant ticket."""
    ticket_id, _tdir, ticket = _resolve_ticket_for_gate(ctx, payload, "create-design")
    if not ticket.get("needs_design"):
        raise GateError(
            "ticket %s is not flagged needs_design — /create-design only runs for "
            "design-significant tickets; go straight to /acs:code %s."
            % (ticket_id, ticket_id))
    return ticket_id


def _pr_recorded_for(repo, ticket_id):
    """True when a completed step of one of this ticket's runs recorded a PR."""
    for rdir in _run_dirs_for_ticket(repo, ticket_id):
        for skill in ["create-pr"] + list(DELIVERY_TICKET_SKILLS):
            if not os.path.isfile(step_machine.state_path(rdir, skill)):
                continue
            state = step_machine.load_state(rdir, skill)
            pr = (state.get("states") or {}).get("pr") or {}
            # `states` is typed as a bare object (schemas/result.schema.json),
            # so a recorded `pr` can be any JSON value and this brake is where
            # one that is not an object surfaces.
            if not isinstance(pr, dict):
                raise GateError(
                    "states.pr in %s is not an object (it is a %s) — a recorded PR "
                    "reference is an object with a url and/or a number. Correct that "
                    "file, or re-run /acs:create-pr to record the reference again, "
                    "and retry." % (step_machine.state_path(rdir, skill),
                                    type(pr).__name__))
            if not (pr.get("url") or pr.get("number")):
                continue
            if step_machine.last_status(rdir, skill) == "completed":
                return True
    return False


def gate_merge_pr(ctx, payload):
    """Brake: a merge needs a PR reference a completed run actually recorded.

    The exempt non-ticket forms (--pr N, #N, a PR URL, a bare integer with no
    ticket in scope) short-circuit first: such a merge is nobody's ticket, so
    there is no ticket gate to run on it."""
    args_text = _merge_pr_arg_text(payload)
    _resolved, source = resolve_ticket_id(ctx["cwd"], ctx["settings"], ctx["workspace"],
                                          ctx["repo_id"], args_text=args_text)
    kind, _pr_ref = classify_merge_pr_arg(
        args_text, ctx["settings"].get("ticket_prefix"),
        ticket_resolves=source in ("pointer", "branch"))
    if kind == "exempt-pr":
        return None
    ticket_id, _tdir, _ticket = _resolve_ticket_for_gate(ctx, payload, "merge-pr")
    if _pr_recorded_for(repo_dir(ctx["workspace"], ctx["repo_id"]), ticket_id):
        return ticket_id
    raise GateError(
        "no PR reference recorded for %s — /acs:create-pr (or the product-level "
        "skill) must complete first." % ticket_id)


#: skill -> gate, for a skill whose precondition is about the SUBJECT TICKET.
#: The third table beside ARCHITECTURE_GATED and PRD_GATED, and there for the
#: same reason they are: neither skill is a step of `ship` (§2.4), so neither
#: has a run to read its precondition from. A row here resolves a ticket
#: through path joins and `read_json` alone -- it opens no run, takes no lock
#: and settles nothing, which is what keeps `acs gate` inert.
SUBJECT_GATES = {
    "create-design": gate_create_design,
    "merge-pr": gate_merge_pr,
}


#: What the gate judged: the run id it gated (None for a non-step skill) and
#: the run document it judged it against. The DOCUMENT is the addition: a
#: query answers against a run projected in memory, which the advisory cannot
#: load from disk afterwards because it was never written there.
GateOutcome = collections.namedtuple("GateOutcome", "run_id doc")


def gate_step(ctx, skill, payload, standalone=True, mutate=True):
    """The run id `gate_outcome` gated, or None for a skill that is not a step.

    The whole gate lives in `gate_outcome`; this is the long-standing name and
    return value, kept so every CALLER of it is untouched. Anything that
    PATCHES the gate wants `gate_outcome` instead -- that is the name
    `run_pre_payload` looks up, so a fake installed here reaches nothing.
    """
    return gate_outcome(ctx, skill, payload, standalone=standalone,
                        mutate=mutate).run_id


def gate_outcome(ctx, skill, payload, standalone=True, mutate=True):
    """The whole pre-hook gate for one skill, as a GateOutcome.

    Order of business, and each line is load-bearing:
      1. the three non-step tables, then: a skill that is not a step has
         nothing further here to check
      2. the run: this checkout's current one, or a new one over the subject
      3. the invariants, BEFORE any write (§4.3) -- a drifted ledger is
         refused here rather than discovered three steps later
      4. the inputs, from the skill's own declaration
      5. the safety brakes
      6. the no-op: nothing owed means the step is completed here and the
         coordinator is never spawned

    `mutate=False` answers the question WITHOUT the answer's consequences, for
    `acs.py gate` -- which is documented as "run one skill's pre-gate without
    running the skill" and was creating a run, taking the lock, opening the
    step and settling no-ops as a side effect of being asked. It judges the
    run the subject WOULD open (`run.projected_run`) instead of one it creates,
    so the query reaches every check below and still writes nothing.
    """
    manifests = skills_registry.load_manifests()
    if skill in ARCHITECTURE_GATED:
        _require_architecture_doc_set(ctx)
    if skill in PRD_GATED:
        _require_prd(ctx)
    subject_gate = SUBJECT_GATES.get(skill)
    if subject_gate:
        subject_gate(ctx, payload)

    # Only the skills the RESOLVED WORKFLOW runs go through a run. A skill
    # that declares reads/writes but is not a step of this workflow is a
    # skill someone invoked on its own -- and the design and product skills
    # (create-prd, create-architecture, create-ticket) are never steps of
    # `ship` at all. `create-ticket` in particular MAKES a subject; requiring
    # it to name one first would be circular.
    try:
        wf = _workflow_for(ctx)
    except WorkflowError as exc:
        raise GateError("the workflow does not validate: %s" % exc)
    if not workflow.has_step(wf, skill):
        return GateOutcome(None, None)

    rdir, doc, wf = resolve_run_for(ctx, skill, payload, mutate=mutate)
    # The LOCK, before the invariants and before any write. One run, one
    # session: a second checkout that picked this run up would interleave two
    # sessions' writes into one ledger, and the invariants that keep it honest
    # are checked per process. `acquire_lock` is a no-op when this checkout
    # already holds it, so a multi-step session takes it once.
    ok, message = check_lock(rdir, ctx["checkout_id"])
    if not ok:
        raise GateError(message)
    if mutate:
        acquire_lock(rdir, ctx.get("checkout_root") or ctx["workspace"])
    stepgate.check_invariants(rdir, wf, manifests, doc=doc)

    fell_back = stepgate.check_inputs(rdir, skill, manifests, wf,
                                      standalone=standalone, doc=doc)
    for artifact in fell_back:
        sys.stderr.write(
            "acs: no %s for this run; /acs:%s will work from the run's subject instead.\n"
            % (artifact, skill))

    # The epic brake runs for EVERY implementation step, not just the ones
    # that happened to have a gate function before. `code` refusing an epic
    # while `create-impl-plan` planned one is the same mistake caught a step
    # too late, with a plan on disk that should never have been written.
    if skill in _EPIC_VERBS:
        _brake_no_epics(ctx, rdir, dict(doc, __step__=skill), wf)
    brake = BRAKES.get(skill)
    if brake:
        brake(ctx, rdir, doc, wf)

    settled = (stepgate.settle_no_op(rdir, skill, doc["run_id"], wf, manifests)
               if mutate else stepgate.noop_decision(rdir, skill, manifests, wf))
    if settled:
        outcome, reason = settled
        raise NothingOwed(skill, outcome, reason)
    return GateOutcome(doc["run_id"], doc)


class NothingOwed(Exception):
    """Not an error: the pre-hook settled this step because the plan said
    nothing was owed, so the coordinator must not run. Carried as an exception
    because it has to unwind the gate, but reported as a success."""

    def __init__(self, skill, outcome, reason):
        self.skill, self.outcome, self.reason = skill, outcome, reason
        super().__init__("%s: %s (%s)" % (skill, outcome, reason))


def resolve_run_for(ctx, skill, payload, mutate=True):
    """(rdir, doc, wf) for the run this invocation belongs to.

    The checkout's current run when it has one, else a new run over whatever
    subject the invocation named -- a ticket id, a prompt or a document. Every
    skill accepts all three (§3.11), so this is the same resolution for all of
    them. `rdir` is always a run directory: under `mutate=False` it is the one
    the subject WOULD open, which exists only in memory, so a caller reads the
    returned `doc` rather than the path.
    """
    repo = repo_dir(ctx["workspace"], ctx["repo_id"])
    try:
        wf, wf_path = _workflow_for(ctx, with_path=True)
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
            if mutate:
                sessions.save_pointer(repo, ctx["checkout_id"], run_id=row["run_id"],
                                      checkout_path=ctx.get("checkout_root"))
            return rdir, run_machine.require_run(rdir), wf
        # A ticket SUBJECT must be a ticket that exists. A prompt or a document
        # carries its own content, so a run over one is self-describing; a
        # ticket id is a REFERENCE, and minting a run over a reference to
        # nothing produces a run whose subject cannot be read -- discovered
        # several steps later, by whichever step first needs `ticket.json`.
        # Refuse here, where the message can still name the skill that makes
        # one. (A token that is not a ticket id is a prompt, so this never
        # catches `/acs:code "fix the login timeout"`.)
        tdir, _archived = find_ticket_partition(
            ctx["workspace"], ctx["repo_id"], subject["ticket_id"])
        if not os.path.isdir(tdir):
            raise GateError(
                "no ticket %s in this repo's workspace — run /acs:create-ticket "
                "to make one, or give /acs:%s a prompt or a document instead."
                % (subject["ticket_id"], skill))

    if not mutate:
        # Asked, not told: judge the run this subject WOULD open, projected in
        # memory, rather than creating one to answer with. Returning "no run,
        # nothing to check" was not a smaller answer but a different one --
        # the query reported `ok` for an epic the hook refuses outright,
        # because every brake below sits past this return.
        _run_id, rdir, doc = run_machine.projected_run(repo, subject, wf, wf_path)
        return rdir, doc, wf
    run_id, rdir, doc = run_machine.create_run(repo, subject, wf, wf_path)
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


def run_pre_payload(skill, payload, record_marker=True, mutate=True):
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
            # This write is the only evidence the Start path has that the gate
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
            outcome = gate_outcome(ctx, skill, payload, mutate=mutate)
        except NothingOwed as owed:
            # Not a refusal to report as one: the step is COMPLETE. Exit 2
            # stops the Skill from running, which is the point -- no
            # coordinator, no tokens -- and the message says what was
            # recorded rather than what was wrong.
            sys.stderr.write(
                "acs: /acs:%s has nothing to do on this run — recorded %s (%s). "
                "The step is complete.\n" % (owed.skill, owed.outcome, owed.reason))
            return 2
        if outcome.run_id:
            # The judged document, not a re-read: a projected run has none on
            # disk, and the query must print the line the hook would print.
            advisory = workflow_advisory(ctx, skill, outcome.run_id, doc=outcome.doc)
            if advisory:
                sys.stderr.write(advisory + "\n")
            if mutate:
                _mark_step_started(ctx, skill, outcome.run_id)
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


def _mark_step_started(ctx, skill, run_id):
    """step -> in_progress, and the pointer follows it. The pre-hook is the
    one writer of this transition (§4.3)."""
    repo = repo_dir(ctx["workspace"], ctx["repo_id"])
    rdir = run_machine.run_dir(repo, run_id)
    try:
        wf = _workflow_for(ctx)
        run_machine.start_step(rdir, skill, wf)
        step_machine.append_invocation(rdir, skill, run_id)
        sessions.save_pointer(repo, ctx["checkout_id"], run_id=run_id, step=skill,
                              checkout_path=ctx.get("checkout_root"))
    except (GateError, WorkflowError) as exc:
        raise GateError(str(exc))


# ---------------------------------------------------------------------------
# SessionEnd safety net
# ---------------------------------------------------------------------------

def session_end(payload):
    """Finalize whatever step this checkout left `in_progress` as `interrupted`
    and release its lock — an abnormal ending must still write state
    (docs/requirements/functional/hooks.md).

    `interrupted` is the one resumable step state, and `session_end` is the
    stop_reason that says which kind of ending it was (§4.3). A step left
    `in_progress` by a session that no longer exists is the case resume exists
    for, and leaving it that way is what makes the next invocation refuse
    under I1.
    """
    cwd = cc.payload_cwd(payload)
    try:
        ctx = build_context(cwd)
    except GateError:
        return  # uninitialized repo: nothing to clean up
    repo = repo_dir(ctx["workspace"], ctx["repo_id"])
    run_id = sessions.current_run_id(repo, ctx["checkout_id"])
    if not run_id:
        return
    rdir = run_machine.run_dir(repo, run_id)
    doc = run_machine.load_run(rdir)
    if doc is None:
        return
    lock = read_lock(rdir)
    if not (isinstance(lock, dict) and lock.get("checkout_id") == ctx["checkout_id"]):
        return  # not our session's run any more
    # The release is the POINT of this safety net, so it happens whatever the
    # repo-level writes do. Before this, a raise skipped the release and
    # dispatch.py swallowed it, so the net exited 0 having left the run locked
    # by a process that no longer exists -- and a cross-host lock stranded that
    # way does not read as stale for 24 hours.
    try:
        step = run_machine.in_progress_step(doc)
        if step:
            wf = _workflow_for(ctx)
            _state, entry = step_machine.finalize_invocation(rdir, step, run_id, {
                "status": "interrupted",
                "stop_reason": "session_end",
            })
            run_machine.finish_step(rdir, step, wf, status="interrupted",
                                    stop_reason="session_end",
                                    summary="session ended mid-step")
            # keep repo-level metrics consistent with the run ledger: an
            # interrupted invocation still spent time and tokens.
            update_metrics(ctx["workspace"], ctx["repo_id"], run_entry=entry)
    except GuardTimeout as exc:
        sys.stderr.write(
            "acs session-end: %s\n%s's step is finalized as interrupted and the "
            "lock is released; metrics.json was not updated, so this step's tokens "
            "and cost are lost from it.\n" % (exc, run_id))
    finally:
        sessions.save_pointer(repo, ctx["checkout_id"], run_id=run_id, step=None)
        release_lock(rdir, cwd)
