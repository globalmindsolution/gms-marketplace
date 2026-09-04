"""acs_lib.gates — extracted from acs_lib.py by MAR-522."""


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
# The scripts dir, one level up from this package -- sibling helpers
# (claude_code_adapter, usage_reader, cost_sampler) are imported flat.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import claude_code_adapter as cc  # noqa: E402

from ._common import DELIVERY_TICKET_SKILLS, GateError, HOOKED_SKILLS, PRODUCT_SKILLS, RUN_STATUSES, now_iso, plugin_root, read_json
from .settings import load_settings, validate_settings
from .repo import archive_dir, checkout_id, checkout_root, find_ticket_partition, index_path, main_repo_root, pointer_path, record_session_marker, repo_partition_id, resolve_ticket_id, sessions_dir, state_path
from .state import check_lock, finalize_run, last_run_status, load_pipeline, load_state, load_ticket, read_lock, release_lock, save_ticket, skill_completed, update_index, update_pipeline
from .metrics import update_metrics
from .setup_helpers import classify_merge_pr_arg, tracker_cli_warning



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
# Pre-hook gates
# ---------------------------------------------------------------------------

def _require_completed(tdir, skill, ticket_id, hint):
    if not skill_completed(tdir, skill):
        status = last_run_status(tdir, skill)
        if status == "in_progress":
            detail = "/%s is recorded as in_progress for %s (crashed or still running elsewhere); re-run it to reconcile" % (skill, ticket_id)
        elif status:
            detail = "/%s last ended with status '%s' for %s" % (skill, status, ticket_id)
        else:
            detail = "/%s has not run for %s" % (skill, ticket_id)
        raise GateError("%s — %s." % (detail, hint))


def gate_create_prd(ctx, payload):
    return None


def gate_create_requirements(ctx, payload):
    return None


def gate_create_architecture(ctx, payload):
    root = ctx["checkout_root"]
    prd = os.path.join(root, ctx["settings"].get("prd_path", "docs/product"), "prd.md")
    if not os.path.isfile(prd):
        raise GateError("no PRD found at %s — run /acs:create-prd first (it also baselines existing products)." % prd)
    return None


def gate_create_project(ctx, payload):
    _require_architecture_doc_set(ctx)
    return None


def gate_create_ticket(ctx, payload):
    return None


def _resolve_ticket_for_gate(ctx, payload, skill):
    args_text = ""
    tool_input = payload.get("tool_input") or {}
    for key in ("args", "arguments", "argument"):
        if isinstance(tool_input.get(key), str):
            args_text = tool_input[key]
            break
    ticket_id, source = resolve_ticket_id(ctx["cwd"], ctx["settings"], ctx["workspace"], ctx["repo_id"], args_text=args_text)
    if not ticket_id:
        raise GateError(
            "could not resolve a ticket id for /%s (no argument, no session pointer, no ticket in the branch name). "
            "Pass it explicitly, e.g. /acs:%s %s-123." % (skill, skill, ctx["settings"].get("ticket_prefix", "SHOP"))
        )
    tdir, archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    if archived:
        raise GateError("ticket %s is done and archived (%s); nothing left to run." % (ticket_id, tdir))
    if not os.path.isdir(tdir):
        raise GateError("no workspace partition for %s (expected %s) — run /acs:create-ticket first." % (ticket_id, tdir))
    ticket = load_ticket(tdir)
    if not ticket:
        raise GateError("ticket file missing or corrupt at %s/ticket.json — treat as not created; run /acs:create-ticket." % tdir)
    ok, msg = check_lock(tdir, ctx["checkout_id"])
    if not ok:
        raise GateError(msg)
    return ticket_id, tdir, ticket


def gate_create_design(ctx, payload):
    ticket_id, tdir, ticket = _resolve_ticket_for_gate(ctx, payload, "create-design")
    _require_completed(tdir, "create-ticket", ticket_id, "run /acs:create-ticket first")
    if not ticket.get("needs_design"):
        raise GateError(
            "ticket %s is not flagged needs_design — /create-design only runs for design-significant tickets; "
            "go straight to /acs:code %s." % (ticket_id, ticket_id)
        )
    return ticket_id


def gate_docs_sync(ctx, payload):
    # AC-2: docs-sync runs after code (and the post-code test step, when it
    # was active for this ticket), before create-pr. "test" is an UNHOOKED
    # skill (no post-hook, no test-state.json) -- its activation/completion
    # lives only in pipeline-state.json.steps.test, so it is read directly
    # from the ledger rather than via skill_completed/_require_completed.
    ticket_id, tdir, _ticket = _resolve_ticket_for_gate(ctx, payload, "docs-sync")
    _require_completed(tdir, "code", ticket_id, "run /acs:code %s first" % ticket_id)
    pipeline = load_pipeline(tdir, ticket_id)
    test_step = pipeline.get("steps", {}).get("test")
    if test_step is not None and test_step.get("status") != "completed":
        raise GateError(
            "/test is recorded as %r for %s (the post-code test gate was active but has not "
            "completed) — run /acs:test --for-ticket %s and get it green; the run records "
            "the step itself." % (
                test_step.get("status"), ticket_id, ticket_id)
        )
    return ticket_id


def gate_code(ctx, payload):
    # AC-4: unconditional pass-through on LANE once create-ticket has completed --
    # no lane branch, no create-spec/specs/ precondition (create-spec is deleted;
    # the code-planner self-authors the folded spec content when needed). The one
    # branch here keys on the ticket's own type: epics are refused outright.
    ticket_id, _tdir, ticket = _resolve_ticket_for_gate(ctx, payload, "code")
    if ticket.get("type") == "epic":
        raise GateError(
            "ticket %s is an epic — epics are never implemented directly; run "
            "/acs:create-design %s first if the epic has no design yet, then break it down "
            "into child tickets with /acs:create-ticket %s (epic fan-out), then run /acs:code "
            "on a child." % (ticket_id, ticket_id, ticket_id)
        )
    return ticket_id


def gate_create_pr(ctx, payload):
    ticket_id, tdir, _ticket = _resolve_ticket_for_gate(ctx, payload, "create-pr")
    _require_completed(tdir, "code", ticket_id, "run /acs:code %s first" % ticket_id)
    _require_completed(tdir, "docs-sync", ticket_id, "run /acs:docs-sync %s first" % ticket_id)
    state = load_state(tdir, "code", ticket_id)
    if state["states"].get("verifier_passed") is not True:
        raise GateError(
            "/code completed but its verifier did not pass for %s (verifier_passed != true in code-state.json); "
            "re-run /acs:code %s until the review loop reports zero findings." % (ticket_id, ticket_id)
        )
    return ticket_id


def _merge_pr_arg_text(payload):
    """Raw arg string the same way _resolve_ticket_for_gate reads it."""
    tool_input = payload.get("tool_input") or {}
    for key in ("args", "arguments", "argument"):
        if isinstance(tool_input.get(key), str):
            return tool_input[key]
    return ""


def gate_merge_pr(ctx, payload):
    # MAR-9 (C-3): the exempt non-ticket PR forms (--pr N / #N / PR URL / a bare
    # integer that is not a ticket id and no ticket resolves) short-circuit to
    # pass-through BEFORE the ticket gate runs. Every other input falls through to
    # the existing ticket gate verbatim (AC-8). The pre-hook dispatcher treats a
    # plain return (no GateError) as "allow", so returning None here = allow.
    args_text = _merge_pr_arg_text(payload)
    _resolved, _src = resolve_ticket_id(ctx["cwd"], ctx["settings"], ctx["workspace"],
                                        ctx["repo_id"], args_text=args_text)
    ticket_resolves = _src in ("pointer", "branch")
    kind, _pr_ref = classify_merge_pr_arg(
        args_text, ctx["settings"].get("ticket_prefix"), ticket_resolves=ticket_resolves)
    if kind == "exempt-pr":
        return None
    ticket_id, tdir, _ticket = _resolve_ticket_for_gate(ctx, payload, "merge-pr")
    pipeline = load_pipeline(tdir, ticket_id)
    candidates = ["create-pr"] + DELIVERY_TICKET_SKILLS if pipeline.get("flow") != "product" else DELIVERY_TICKET_SKILLS + ["create-pr"]
    for skill in candidates:
        state = read_json(state_path(tdir, skill))
        if isinstance(state, dict):
            pr = (state.get("states") or {}).get("pr") or {}
            if pr.get("url") or pr.get("number"):
                if last_run_status(tdir, skill) == "completed":
                    return ticket_id
    raise GateError(
        "no PR reference recorded for %s — /acs:create-pr (or the product-level skill) must complete first." % ticket_id
    )


def gate_standardize_project(ctx, payload):
    """Pre-hook gate for /acs:standardize-project — requires an architecture doc set
    to audit against (mirrors gate_create_project); principles_path/standards_path
    being unset or absent does NOT hard-block (graceful degradation)."""
    _require_architecture_doc_set(ctx)
    return None


def _require_architecture_doc_set(ctx):
    """Shared precondition for the doc-set producer gates: the architecture
    set (hld/tech-stack.md) must exist before a downstream doc set is built."""
    root = ctx["checkout_root"]
    arch = os.path.join(root, ctx["settings"].get("architecture_path", "docs/architecture"))
    tech_stack = os.path.join(arch, "hld", "tech-stack.md")
    if not os.path.isfile(tech_stack):
        raise GateError(
            "no architecture doc set found at %s (expected hld/tech-stack.md) — run /acs:create-architecture first." % arch
        )


#: Doc-set producers whose ONLY precondition is the architecture doc set. One
#: row each, instead of four functions with the same two-line body (MAR-522).
#: Adding a producer with that precondition is a row here, not a new function.
ARCHITECTURE_DEPENDENT_SKILLS = ("create-quality", "create-operations",
                                 "create-principles", "create-standards")


def _architecture_dependent_gate(skill):
    """Build one architecture-dependent gate, named and documented like a
    hand-written one so `lib.gate_create_quality` still resolves and the
    tracebacks still read as that gate rather than as a shared closure."""
    def gate(ctx, payload):
        _require_architecture_doc_set(ctx)
        return None

    gate.__name__ = gate.__qualname__ = "gate_" + skill.replace("-", "_")
    gate.__doc__ = ("Pre-hook gate for /acs:%s — requires the architecture doc "
                    "set. Generated from ARCHITECTURE_DEPENDENT_SKILLS." % skill)
    return gate


for _skill in ARCHITECTURE_DEPENDENT_SKILLS:
    globals()["gate_" + _skill.replace("-", "_")] = _architecture_dependent_gate(_skill)
del _skill


GATES = {
    "create-prd": gate_create_prd,
    "create-requirements": gate_create_requirements,
    "create-architecture": gate_create_architecture,
    "create-project": gate_create_project,
    "create-quality": gate_create_quality,
    "create-operations": gate_create_operations,
    "create-principles": gate_create_principles,
    "create-standards": gate_create_standards,
    "create-ticket": gate_create_ticket,
    "create-design": gate_create_design,
    "code": gate_code,
    "docs-sync": gate_docs_sync,
    "create-pr": gate_create_pr,
    "merge-pr": gate_merge_pr,
    "standardize-project": gate_standardize_project,
}


def run_pre(skill):
    """Entry point for pre-<skill>.py: read the hook payload from stdin, gate, exit 0/2."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    sys.exit(run_pre_payload(skill, payload))


def run_pre_payload(skill, payload):
    """Gate one skill from an already-parsed hook payload; return the exit code.

    Separate from run_pre so the dispatcher can gate in-process rather than
    spawning a forwarder: a subprocess that hangs or dies takes its exit code
    with it, and anything other than 2 lets the skill run."""
    cwd = payload.get("cwd") or os.getcwd()
    try:
        ctx = build_context(cwd)
        try:
            record_session_marker(ctx, payload)
        except Exception:  # a marker-write bug must never block a gated skill
            pass
        warn = tracker_cli_warning(ctx["settings"])
        if warn:
            sys.stderr.write("acs: warning: %s\n" % warn)
        GATES[skill](ctx, payload)
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
    parser.add_argument("--ticket", help="ticket id (overrides pointer/branch resolution)")
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
    return result, args.ticket


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
    """Entry point for post-<skill>.py."""
    result, explicit_ticket = _read_result_from_argv()
    cwd = os.getcwd()
    try:
        ctx = build_context(cwd)
    except GateError as exc:
        sys.stderr.write("acs post-%s: %s\n" % (skill, exc))
        sys.exit(1)

    ticket_id, _src = resolve_ticket_id(cwd, ctx["settings"], ctx["workspace"], ctx["repo_id"], explicit=explicit_ticket)
    if not ticket_id:
        sys.stderr.write("acs post-%s: could not resolve the ticket id (pass --ticket).\n" % skill)
        sys.exit(1)
    tdir, archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    if archived or not os.path.isdir(tdir):
        sys.stderr.write("acs post-%s: no active partition for %s.\n" % (skill, ticket_id))
        sys.exit(1)

    status = result["status"]  # guaranteed by _read_result_from_argv
    state, entry = finalize_run(tdir, skill, ticket_id, result)
    flow = "product" if skill in PRODUCT_SKILLS else "ticket"
    summary = result.get("handoff_summary") or result.get("stop_reason")
    update_pipeline(tdir, ticket_id, skill, status, summary=summary, flow=flow)

    ticket = load_ticket(tdir)
    epic_done = None
    archived_to = None
    if ticket:
        if status == "completed":
            if skill == "create-pr" and ticket.get("status") != "done":
                ticket["status"] = "in_review"
                save_ticket(tdir, ticket)
            if skill in DELIVERY_TICKET_SKILLS and (result.get("states") or {}).get("pr") and ticket.get("status") != "done":
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
                    and skill in (["create-pr"] + DELIVERY_TICKET_SKILLS)),
        pr_merged=(skill == "merge-pr" and status == "completed"),
        pr_number=pr_number,
    )

    release_lock(tdir, cwd)

    if skill == "merge-pr" and status == "completed" and ticket:
        epic_done = _epic_auto_done(ctx, ticket)
        update_index(ctx["workspace"], ctx["repo_id"], ticket, archived=True)
        _clear_pointers_for_ticket(ctx, ticket_id)
        archived_to = _archive_partition(ctx, tdir, ticket_id)

    out = {"ok": True, "skill": skill, "ticket_id": ticket_id, "status": status}
    if archived_to:
        out["archived_to"] = archived_to
    if epic_done:
        out["epic_marked_done"] = epic_done
    print(json.dumps(out, indent=2))
    sys.exit(0)


# ---------------------------------------------------------------------------
# SessionEnd safety net
# ---------------------------------------------------------------------------

def session_end(payload):
    """Finalize any run this checkout left in_progress as `interrupted` and release
    its lock — abnormal endings must still write state (docs/requirements/functional/hooks.md)."""
    cwd = payload.get("cwd") or os.getcwd()
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
    release_lock(tdir, cwd)
