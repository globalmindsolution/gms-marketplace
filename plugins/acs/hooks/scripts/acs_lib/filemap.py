"""acs_lib.filemap — the executor file-map write guard (MAR-529).

Split out of acs_lib.lifecycle by MAR-572, which is code motion only: the
guard grew alongside the lifecycle hooks that feed it, and together they put
that module over E1's 800-line budget. The dependency runs one way — this
module reads the active-agent records lifecycle writes, and lifecycle reads
nothing back — so the seam is the section boundary, not a new abstraction.
"""

import os
import posixpath
from datetime import datetime, timezone

import claude_code_adapter as cc  # noqa: E402

from ._common import GateError, _note, _warn, now_iso, read_json, write_json
from .artifacts import ticket_docs_root, tickets_path
from .lifecycle import (BLOCK_LIMIT, active_agents, active_agents_dir,
    resolve_partition)


# ---------------------------------------------------------------------------
# The executor file map (MAR-529)
# ---------------------------------------------------------------------------
#
# "Mutate ONLY the files in your task's file map" was a bullet in the executor
# charter. Plugin agents cannot carry frontmatter hooks, so the enforcement
# point is the plugin's own PreToolUse hook, keyed on the active agent that
# SubagentStart recorded.
#
# SCOPE, STATED PLAINLY: the guard checks a write against the UNION of the
# iteration's declared task file maps, not against the one task the running
# executor was given. Per-task binding is not achievable with what Claude Code
# provides -- neither SubagentStart nor PreToolUse carries a task index, and
# parallel executors of the same agent_type run at once, so there is nothing to
# bind an agent to its task by. What the union still enforces is the property
# that actually goes wrong: an executor wandering outside the PLAN's scope.
# Disjointness BETWEEN tasks stays the coordinator's job, which is what its
# parallel-vs-sequential decision already exists to decide.

#: The declared file map for one iteration, under phases/<skill>/.
FILEMAP_FILENAME_FMT = "iter-%s-filemap.json"

#: Tool -> the tool_input key naming the path it would write.
WRITE_TOOL_PATH_KEYS = {
    "Write": "file_path",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
}


def filemap_path(tdir, skill, iteration):
    return os.path.join(tdir, "phases", skill, FILEMAP_FILENAME_FMT % iteration)


def load_filemap(tdir, skill, iteration):
    doc = read_json(filemap_path(tdir, skill, iteration))
    tasks = doc.get("tasks") if isinstance(doc, dict) else None
    return tasks if isinstance(tasks, dict) else None


def save_filemap_task(tdir, skill, iteration, task, files):
    """Declare one executor task's file map. Returns the whole iteration's map.

    Per task, and additive, because the coordinator declares them one at a time
    as it decomposes the plan -- declaring task 2 must not erase task 1."""
    path = filemap_path(tdir, skill, iteration)
    doc = read_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("tasks"), dict):
        doc = {"skill": skill, "iteration": str(iteration), "tasks": {}}
    # An entry that normalises away ("/", ".", "./") can never match anything,
    # so storing it would silently grant nothing while looking like a
    # declaration. A coordinator typo should not read as a successful declare.
    entries = sorted({normalize_repo_path(f) for f in files if f})
    empties = [f for f in files if f and not normalize_repo_path(f)]
    if empties:
        raise GateError("file map entry %r names no path inside the repo" % empties[0])
    doc["tasks"][str(task)] = [e for e in entries if e]
    doc["declared_at"] = now_iso()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json(path, doc)
    return doc["tasks"]


def normalize_repo_path(path):
    """A repo-relative POSIX path, however it was written.

    The plan names repo-relative paths; a hook payload carries absolute ones.
    Both have to compare equal, so both land here."""
    text = str(path or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    text = text.lstrip("/")
    if not text:
        return ""
    # normpath collapses INTERIOR `..` segments. Without it `docs/../../../etc/
    # passwd` normalises to itself, matches the declared entry `docs/`, and the
    # anti-traversal check below only ever sees a LEADING escape -- so a
    # declared directory became a tunnel out of the repo.
    text = posixpath.normpath(text)
    return "" if text in (".", "/") else text


def path_in_filemap(target, tasks, checkout_root_path=None):
    """Is `target` (a write path from a hook payload) inside the declared map?

    A declared entry matches the file itself or anything under it when it names
    a directory, so a plan that says `docs/api/` covers the files in it -- the
    plans write both forms and the guard should not care which."""
    candidate = normalize_repo_path(target)
    if checkout_root_path and os.path.isabs(str(target)):
        try:
            candidate = normalize_repo_path(
                os.path.relpath(os.path.realpath(str(target)),
                                os.path.realpath(checkout_root_path)))
        except (OSError, ValueError):
            pass
    if candidate.startswith("../"):
        return False
    for entry in {f for files in (tasks or {}).values() for f in files}:
        if candidate == entry or candidate.startswith(entry.rstrip("/") + "/"):
            return True
    return False


#: How long a SubagentStart record may still mean "running". Nothing clears
#: the record when a subagent dies without a clean SubagentStop, so without a
#: bound one interrupted executor would deny every later write in the partition
#: for good -- fail-CLOSED forever, which is not what the guard promises.
EXECUTOR_RECORD_TTL_SECONDS = 6 * 60 * 60


def _record_is_current(entry, session_id=None, now=None):
    """Is this SubagentStart record still describing a running executor?

    Two independent reasons it may not be, both of which the record itself can
    answer: it belongs to a DIFFERENT session (that session's subagent cannot
    be writing in this one), or it is simply too old. `stop_attempts` above the
    block cap is a third: SubagentStop already gave up on that agent."""
    if session_id and entry.get("session_id") and entry["session_id"] != session_id:
        return False
    if int(entry.get("stop_attempts") or 0) > BLOCK_LIMIT:
        return False
    started = entry.get("started_at")
    if not started:
        return True
    try:
        age = (now or datetime.now(timezone.utc)) - datetime.fromisoformat(
            str(started).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    return age.total_seconds() <= EXECUTOR_RECORD_TTL_SECONDS


def active_executor(tdir, session_id=None):
    """The most recent recorded agent whose role is `executor`, or None.

    "Is an acs executor running" is the whole condition: the guard must not
    touch a planner (read-only by charter), a verifier, or the coordinator's own
    writes, all of which legitimately go outside any task's file map.

    Records that cannot still be describing a running executor are skipped --
    see _record_is_current. Nothing clears the record when a subagent dies
    mid-flight, and a guard that denies every write in a partition until
    someone hand-edits it is worse than the scope creep it prevents."""
    for entry in active_agents(tdir):
        if entry.get("role") == "executor" and _record_is_current(entry, session_id):
            return entry
    return None


def file_map_guard(payload):
    """PreToolUse on the write tools: deny a write outside the declared map.

    Fails OPEN at every step where the answer is not clearly "outside the map":
    not an acs partition, no executor running, no map declared for this
    iteration (a TRIVIAL lane runs no planner at all), or a tool whose payload
    does not name a path. The rule exists to stop scope creep, not to stop work
    the plan never had an opinion about.
    """
    # ---- half one: does this guard apply at all? FAILS OPEN. ----------------
    # A bug in deciding scope must not deny every write on the machine, so this
    # half answers "no" on anything it cannot work out. Note it is only the
    # SCOPE question that is forgiving; once we are past it, an error means the
    # write could not be checked, and dispatch.run_file_map_guard denies.
    try:
        key = WRITE_TOOL_PATH_KEYS.get(payload.get("tool_name"))
        if not key:
            return 0
        _ticket_id, tdir, ctx = resolve_partition(cc.payload_cwd(payload))
        if not tdir:
            return 0
        executor = active_executor(tdir, cc.hook_session_id(payload))
        if not executor:
            return 0
    except Exception as exc:  # noqa: BLE001 - scope questions fail open
        _note("file-map guard not applied: %r" % exc)
        return 0

    # ---- half two: is THIS write inside the declared map? FAILS CLOSED. -----
    # Reading the target lives here, not above: a write tool whose tool_input
    # cannot be read WHILE AN EXECUTOR IS RUNNING is an unverifiable write, and
    # the caller denies rather than waving it through.
    tool_input = payload.get("tool_input")
    if tool_input is not None and not isinstance(tool_input, dict):
        # Not "no path" but "a payload shape this guard cannot read". While an
        # executor is running that is an unverifiable write, not an absent one.
        _warn("%s carried a %s tool_input, which the file map cannot be checked "
              "against. STOP and return `needs_input`."
              % (payload.get("tool_name"), type(tool_input).__name__))
        return 2
    target = (tool_input or {}).get(key)
    if not target or not isinstance(target, str):
        return 0  # no path named: this call writes nothing for the map to cover

    # The guard's OWN control inputs are denied outright, never exempted. The
    # exemption used to cover the whole workspace, and both inputs live in it:
    # the active-agents record is what arms the guard, and the file map is what
    # it checks against -- so one Write to either switched the guard off from
    # inside the very agent it constrains. Workspace-wide also meant every
    # OTHER ticket's code-state.json, plan-approval.json and counters.json were
    # writable by an executor scoped to this one. The ticket docs tree joins
    # them: the plan an executor is checked against lives there.
    reason = _guard_control_input(target, tdir, ctx)
    if reason:
        _warn(
            "%s is %s.\n"
            "An executor cannot widen or disarm its own scope. If the map is "
            "wrong, STOP and return `needs_input` naming the file, so the "
            "coordinator can adjust it." % (target, reason))
        return 2

    # What IS exempt: this executor's own phase artifacts, and only those.
    phase_dir = os.path.join(tdir, "phases", executor.get("skill") or "")
    if _under(target, phase_dir):
        return 0

    iteration = _current_iteration(tdir, executor.get("skill"))
    tasks = load_filemap(tdir, executor.get("skill"), iteration)
    if not tasks:
        return 0  # nothing declared: the plan has no opinion, so neither has this
    if path_in_filemap(target, tasks, ctx.get("checkout_root")):
        return 0
    declared = sorted({f for files in tasks.values() for f in files})
    _warn(
        "%s is outside this task's file map.\n"
        "Declared for /acs:%s iteration %s:\n  %s\n"
        "Do not improvise scope: STOP and return `needs_input` naming the file, "
        "so the coordinator can adjust the file map."
        % (target, executor.get("skill"), iteration, "\n  ".join(declared)))
    return 2


def _guard_control_input(target, tdir, ctx):
    """Why this write is aimed at a control input the guard denies outright
    -- a reason for the denial message -- or None.

    Three things. The active-agents record (which says an executor is running)
    and any iteration's file map (which says what it may touch): either one
    lets an executor answer the guard's own question, so neither is writable
    while the guard is armed. And the ticket docs tree,
    <settings.artifacts.tickets_path>/<ID>/ (ticket.md, design.md, plan.md,
    test-cases.md ...), which the coordinator and the ticket skills own: an
    executor rewriting the plan it is being checked against is the same move
    as rewriting the map. Opting out of the tree (tickets_path null) lifts
    that third case, since the folder then means nothing to acs."""
    own = "the file-map guard's own control input"
    if _under(target, active_agents_dir(tdir)):
        return own
    normalized = normalize_repo_path(target)
    prefix, suffix = FILEMAP_FILENAME_FMT.split("%s")
    base = os.path.basename(normalized)
    if base.startswith(prefix) and base.endswith(suffix):
        return own
    settings = (ctx or {}).get("settings")
    docs_root = ticket_docs_root(settings, (ctx or {}).get("checkout_root"))
    if docs_root:
        rel = normalize_repo_path(tickets_path(settings))
        if _under(target, docs_root) or normalized == rel or normalized.startswith(rel + "/"):
            return ("the ticket docs tree (%s/), a control input only the coordinator "
                    "and the ticket skills write" % rel)
    return None


def _is_guard_control_input(target, tdir, ctx):
    return _guard_control_input(target, tdir, ctx) is not None


def _under(target, directory):
    """Is `target` inside `directory`? Absolute-path comparison, symlinks
    resolved, and never true for a relative path (which is repo-relative and so
    is never inside the workspace)."""
    if not directory or not os.path.isabs(str(target)):
        return False
    try:
        root = os.path.realpath(directory)
        return os.path.realpath(str(target)).startswith(root.rstrip("/") + "/")
    except (OSError, ValueError):
        return False


def _current_iteration(tdir, skill):
    """The iteration whose file map applies: the highest one declared.

    The coordinator declares a fresh map before each iteration's executors, so
    the newest declaration is the one in force."""
    directory = os.path.join(tdir, "phases", skill or "")
    best = "1"
    prefix, suffix = FILEMAP_FILENAME_FMT.split("%s")
    try:
        names = os.listdir(directory)
    except OSError:
        return best
    for name in names:
        if name.startswith(prefix) and name.endswith(suffix):
            token = name[len(prefix):-len(suffix)]
            if token.isdigit() and int(token) >= int(best):
                best = token
    return best
