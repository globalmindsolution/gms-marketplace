"""acs_lib.lifecycle — the subagent and stop lifecycle events (MAR-528).

Before this module acs bound exactly two hook events: PreToolUse (matcher
`Skill`) and SessionEnd. Everything else the pipeline needs at a lifecycle
boundary was an instruction in a SKILL.md for the coordinator to remember:
snapshot the subagent's XML, validate it, finish the run before stopping, flush
context before a compaction. An instruction a model must remember is not an
enforcement point — it is a request.

Claude Code exposes the four events those instructions were standing in for, and
plugin hooks fire inside subagents, so each one becomes deterministic here:

  SubagentStart  records which acs agent is active, so a later guard can ask
                 "is an executor running, and what was it allowed to touch?"
                 (MAR-529 consumes this; nothing here reads it back.)
  SubagentStop   validates the returned XML and writes the phase snapshot the
                 coordinator wrote by hand. The message carries `skill`,
                 `phase`, `ticket-id` and `iteration`, so the snapshot's path is
                 fully determined by the message -- there is nothing to guess.
  Stop           refuses to end a turn that left a run `in_progress` with no
                 result document, and names the finish step.
  PreCompact     writes handoff-context.md from state, so what survives a
                 compaction is the ledger rather than whatever happened to
                 remain in the window.

**Every one of these fails OPEN.** A lifecycle hook that raises would break a
session over bookkeeping; only Stop and SubagentStop block at all, and only on
the specific condition they exist for. Both cap how often they block
(BLOCK_LIMIT), because a hook that can refuse forever is a hung session, and
SessionEnd already finalizes an abandoned run as `interrupted`.
"""

import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import claude_code_adapter as cc  # noqa: E402

from ._common import GateError, HOOKED_SKILLS, now_iso, read_json, write_json, write_text
from .repo import find_ticket_partition, pointer_path, resolve_ticket_id, sessions_dir
from .state import last_run, last_run_status, load_pipeline, load_state, load_ticket

#: agent_type suffix -> the phase name its artifact is filed under.
ROLE_PHASES = {"planner": "plan", "executor": "execute", "verifier": "verify"}

#: How many times one hook may refuse the same thing before giving up and
#: letting it through with a warning. A hook that can block forever is a hung
#: session; SessionEnd finalizes an abandoned run as `interrupted` regardless,
#: so the worst case of giving up is a run the safety net already handles.
#:
#: Read it as "refuse at most this many times, then let it through": BOTH
#: blocking hooks compare with `>` against a 1-based attempt count, so both
#: refuse exactly twice and let the third through. They disagreed once --
#: subagent_stop used `>=` and so refused only once -- which made the number in
#: INTERNALS.md and the CHANGELOG wrong for one of the two hooks.
BLOCK_LIMIT = 2

#: Where SubagentStart's records live: ONE FILE PER AGENT, under this directory
#: in the partition, named from the payload's `agent_id`.
#:
#: A single shared JSON object was the obvious shape and the wrong one. Every
#: writer would have had to read-modify-write it, and the case this record
#: exists for -- a parallel executor fan-out (skills/code/SKILL.md) -- is
#: exactly when two SubagentStart hooks run at once: both read the same
#: pre-image and the second `os.replace` silently drops the first agent. Losing
#: an entry loses that agent's `stop_attempts` too, which is the cap standing
#: between a malformed message and an unbounded refuse-retry loop. Per-agent
#: files remove the interleaving entirely -- each file has exactly one writer.
ACTIVE_AGENTS_DIRNAME = "active-agents"

#: What PreCompact writes, in the partition, for whoever picks the ticket up.
HANDOFF_CONTEXT_FILENAME = "handoff-context.md"

#: The root elements a subagent may return (acs-messages.xsd). `task` is the
#: coordinator's direction, never a subagent's answer, so it is not here.
RESULT_ROOTS = ("result", "handoff")

#: A returned message, in either form the schema allows: a paired element, or
#: an empty one written self-closing (`<result .../>` -- every child of `result`
#: is minOccurs="0", so a subagent legitimately returns one with no body).
_MESSAGE_RE = re.compile(r"<(result|handoff)\b(?:[^>]*/>|.*?</\1>)", re.DOTALL)


def parse_agent_type(agent_type):
    """('code', 'executor') from 'acs:code-executor'; (None, None) for anything else.

    Split from the RIGHT: skill names contain hyphens (`create-pr`,
    `docs-sync`, `standardize-project`), so splitting from the left would make
    `acs:create-pr-executor` a skill named "create" -- a bug that only shows up
    on the hyphenated half of the skill list.
    """
    if not isinstance(agent_type, str) or not agent_type.startswith("acs:"):
        return None, None
    skill, _, role = agent_type[len("acs:"):].rpartition("-")
    if role not in ROLE_PHASES or skill not in HOOKED_SKILLS:
        return None, None
    return skill, role


def active_agents_dir(tdir):
    return os.path.join(tdir, ACTIVE_AGENTS_DIRNAME)


def agent_record_path(tdir, agent_id):
    """The file holding one agent's record.

    `agent_id` is an opaque upstream string, so it is never used as a path
    component as-is: it is reduced to a safe stem and disambiguated with a
    digest, which keeps the name readable while making `../` and friends
    unrepresentable."""
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", agent_id or "")[:48] or "agent"
    digest = hashlib.sha1((agent_id or "").encode("utf-8")).hexdigest()[:10]
    return os.path.join(active_agents_dir(tdir), "%s-%s.json" % (stem, digest))


def active_agents(tdir):
    """Every recorded agent in this partition, newest first. [] when none."""
    entries = []
    try:
        names = sorted(os.listdir(active_agents_dir(tdir)))
    except OSError:
        return entries
    for name in names:
        if not name.endswith(".json"):
            continue
        entry = read_json(os.path.join(active_agents_dir(tdir), name))
        # `agent_type` separates a real SubagentStart record from the stub
        # count_agent_stop_attempt writes when it has to invent its own key:
        # the stub is a refusal counter, never a running agent.
        if isinstance(entry, dict) and entry.get("agent_id") and entry.get("agent_type"):
            entries.append(entry)
    entries.sort(key=lambda e: e.get("started_at") or "", reverse=True)
    return entries


def record_agent_start(tdir, agent_id, agent_type, session_id=None, checkout_id=None):
    """Add one agent to the partition's active-agents record. Returns the entry.

    Keyed by `agent_id` because that is what SubagentStop hands back, and
    because two executors of the same type run in parallel on a fan-out."""
    skill, role = parse_agent_type(agent_type)
    entry = {
        "agent_id": agent_id,
        "agent_type": agent_type,
        "skill": skill,
        "role": role,
        "phase": ROLE_PHASES.get(role),
        "session_id": session_id,
        "checkout_id": checkout_id,
        "started_at": now_iso(),
        "stop_attempts": 0,
    }
    write_json(agent_record_path(tdir, agent_id), entry)
    return entry


def read_agent(tdir, agent_id):
    entry = read_json(agent_record_path(tdir, agent_id))
    return entry if isinstance(entry, dict) else None


def count_agent_stop_attempt(tdir, agent_id):
    """Bump and return this agent's stop_attempts, so SubagentStop can refuse a
    malformed message once without refusing it forever.

    Creates the record when SubagentStart never wrote one (an older Claude Code,
    a restart mid-subagent, a partition that did not resolve at start time). The
    cap is the ONLY thing standing between a malformed message and an
    unbounded refuse-retry loop, so it must not depend on a sibling event
    having fired.
    """
    path = agent_record_path(tdir, agent_id)
    entry = read_json(path)
    if not isinstance(entry, dict):
        entry = {"agent_id": agent_id, "stop_attempts": 0, "started_at": None}
    entry["stop_attempts"] = int(entry.get("stop_attempts") or 0) + 1
    write_json(path, entry)
    return entry["stop_attempts"]


def open_clarifications(tdir):
    """The partition's unanswered clarifications. [] when there are none."""
    doc = read_json(os.path.join(tdir, "clarifications.json"))
    return [c for c in ((doc or {}).get("clarifications") or [])
            if isinstance(c, dict) and c.get("status") != "answered"]


def stop_counter_key(payload):
    """The key SubagentStop counts refusals under. Never None.

    `agent_id` when the payload carries one. When it does not -- a Claude Code
    without the field, or a restart between start and stop -- falling back to a
    CONSTANT would be the same bug as hardcoding the count: every refusal would
    look like the first one and the cap would never be reached, which is an
    unbounded refuse-retry loop rather than the bounded one the cap promises.
    The fallback is therefore still per-subagent: the session and agent type
    together, which is as narrow as the payload allows."""
    agent_id = cc.hook_agent_id(payload)
    if agent_id:
        return agent_id
    return "session:%s/%s" % (cc.hook_session_id(payload) or "-",
                              cc.hook_agent_type(payload) or "-")


def clear_agent(tdir, agent_id):
    """Drop an agent from the active record. Silent when it was never there."""
    try:
        os.unlink(agent_record_path(tdir, agent_id))
        return True
    except OSError:
        return False


def extract_message(text):
    """The LAST <result>/<handoff> element in a subagent's final message.

    A subagent's message is XML, but a model reliably wraps it in prose or a
    fence, and may quote an earlier message before its own. The last complete
    element is the one it is returning."""
    if not isinstance(text, str):
        return None
    matches = list(_MESSAGE_RE.finditer(text))
    return matches[-1].group(0) if matches else None


def phase_artifact_path(tdir, skill, iteration, phase):
    return os.path.join(tdir, "phases", skill, "iter-%s-%s.xml" % (iteration, phase))


def in_flight_skill(tdir, ctx, ticket_id=None):
    """The skill whose run is `in_progress` in this partition, or None.

    Pointer first (the checkout says what it is working on), then a scan of the
    hooked skills. handoff.py, the Stop hook and PreCompact all need exactly
    this resolution; a second copy is how two of them start disagreeing."""
    candidates = []
    pointer = read_json(pointer_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]))
    if isinstance(pointer, dict) and pointer.get("skill"):
        candidates.append(pointer["skill"])
    candidates += [s for s in HOOKED_SKILLS if s not in candidates]
    for skill in candidates:
        if last_run_status(tdir, skill) == "in_progress":
            return skill
    return None


def resolve_partition(cwd, ctx=None):
    """(ticket_id, tdir, ctx) for this checkout, or (None, None, ctx/None).

    Total by design: a lifecycle hook fires in every session, most of which are
    not working an acs ticket, and "not ours" must be indistinguishable from
    "nothing to do"."""
    from .gates import build_context  # gates imports this module's siblings, not it
    if ctx is None:
        try:
            ctx = build_context(cwd)
        except GateError:
            return None, None, None
    ticket_id, _src = resolve_ticket_id(cwd, ctx["settings"], ctx["workspace"], ctx["repo_id"])
    if not ticket_id:
        return None, None, ctx
    tdir, archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    if archived or not os.path.isdir(tdir):
        return None, None, ctx
    return ticket_id, tdir, ctx


def stop_block_path(ctx):
    return os.path.join(sessions_dir(ctx["workspace"], ctx["repo_id"]),
                        "%s-stop-blocks.json" % ctx["checkout_id"])


def count_stop_block(ctx, key):
    """Bump and return how many times this checkout has refused to stop for
    `key` (a ticket/skill pair). BLOCK_LIMIT caps it."""
    path = stop_block_path(ctx)
    doc = read_json(path)
    if not isinstance(doc, dict):
        doc = {}
    doc[key] = int(doc.get(key) or 0) + 1
    write_json(path, doc)
    return doc[key]


def clear_stop_blocks(ctx):
    """Reset the counter once nothing is in flight, so a long session that
    legitimately blocked twice can still block on the NEXT abandoned run."""
    path = stop_block_path(ctx)
    if isinstance(read_json(path), dict):
        write_json(path, {})


def result_document(tdir, skill):
    """The phase result document post-<skill>.py consumes, or None."""
    doc = read_json(os.path.join(tdir, "phases", skill, "result.json"))
    return doc if isinstance(doc, dict) else None


def render_handoff_context(tdir, ticket_id, skill):
    """The markdown PreCompact leaves behind: what state says, not what the
    window happens to still hold.

    Deliberately short and entirely derived. A compaction is the moment the
    conversation stops being the record, so this points at the artifacts rather
    than trying to summarize them -- a summary written from a half-compacted
    window is exactly the unreliable thing it is replacing."""
    ticket = load_ticket(tdir) or {}
    pipeline = load_pipeline(tdir, ticket_id) or {}
    lines = [
        "# Handoff context — %s" % ticket_id,
        "",
        "_Written by the acs PreCompact hook at %s from the ticket ledger, not "
        "from the conversation. Re-read the files it names before continuing._" % now_iso(),
        "",
        "## Ticket",
        "",
        "- **%s** — %s" % (ticket_id, ticket.get("title") or "(no title recorded)"),
        "- type `%s` · status `%s` · lane `%s` · size `%s` · stakes `%s`"
        % (ticket.get("type"), ticket.get("status"), ticket.get("lane"),
           ticket.get("size"), ticket.get("stakes")),
        "- partition: `%s`" % tdir,
    ]
    if ticket.get("parent"):
        lines.append("- parent epic: `%s`" % ticket["parent"])

    lines += ["", "## Pipeline", ""]
    steps = pipeline.get("steps") if isinstance(pipeline.get("steps"), dict) else {}
    if steps:
        for name in sorted(steps):
            step = steps[name] if isinstance(steps[name], dict) else {}
            lines.append("- `%s` — %s" % (name, step.get("status") or "unknown"))
    else:
        lines.append("- no pipeline steps recorded yet")

    lines += ["", "## In flight", ""]
    if skill:
        state = load_state(tdir, skill, ticket_id)
        entry = last_run(state) or {}
        lines.append("- `/acs:%s` run started %s is **%s**"
                     % (skill, entry.get("started_at"), entry.get("status")))
        lines.append("- phase artifacts: `%s`" % os.path.join(tdir, "phases", skill))
        result = result_document(tdir, skill)
        lines.append("- result document: %s"
                     % ("written (status `%s`)" % result.get("status") if result
                        else "**not written yet** — the run cannot be finalized without it"))
        findings = [f for f in (state.get("findings") or []) if isinstance(f, dict)]
        if findings:
            lines += ["", "### Findings carried into this run", ""]
            for finding in findings:
                lines.append("- `%s`/`%s` — %s" % (finding.get("severity"),
                                                   finding.get("dimension"),
                                                   finding.get("detail")))
        lines += ["", "### Next", "",
                  "- finish it: write the result document, then "
                  "`acs.py finish --ticket %s --skill %s --status <completed|failed|...>`"
                  % (ticket_id, skill),
                  "- or hand it off: `handoff.py --summary \"...\"`"]
    else:
        lines.append("- no run is in progress; the next step is whichever pipeline "
                     "step above is not yet `completed`")

    open_items = open_clarifications(tdir)
    if open_items:
        lines += ["", "## Open clarifications", ""]
        for item in open_items:
            lines.append("- `%s` (%s) — %s" % (item.get("id"), item.get("status"),
                                                item.get("question")))
    return "\n".join(lines) + "\n"


def write_handoff_context(tdir, ticket_id, skill):
    # Render BEFORE writing, and write atomically. Both halves guard the same
    # thing from different directions: rendering first means a renderer that
    # raises cannot destroy the previous handoff-context.md, and write_text
    # means a crash or a hook timeout MID-WRITE cannot either. PreCompact is
    # exactly the moment there is nothing left to rebuild this file from.
    body = render_handoff_context(tdir, ticket_id, skill)
    path = os.path.join(tdir, HANDOFF_CONTEXT_FILENAME)
    write_text(path, body)
    return path



# ---------------------------------------------------------------------------
# Hook entry points — dispatch.py calls exactly these
# ---------------------------------------------------------------------------
#
# Each returns an exit code. 0 always means "carry on"; only subagent_stop and
# stop can return 2, and only for the one condition they exist for. Every one
# of them treats "this is not an acs ticket" and "there is nothing to do" as
# the same answer, because in most sessions they are.


def subagent_start(payload):
    """SubagentStart: record which acs agent is running, in the partition.

    Informational — Claude Code documents no blocking for this event, and there
    is nothing here worth blocking a subagent over. The record exists so a
    PreToolUse guard can ask what the running executor was allowed to touch
    (MAR-529) instead of trusting prose."""
    agent_id = payload.get("agent_id")
    skill, _role = parse_agent_type(payload.get("agent_type"))
    if not agent_id or not skill:
        return 0  # another plugin's agent, or a Claude Code without these fields
    _ticket_id, tdir, ctx = resolve_partition(payload.get("cwd") or os.getcwd())
    if not tdir:
        return 0
    record_agent_start(tdir, agent_id, payload.get("agent_type"),
                       session_id=payload.get("session_id"),
                       checkout_id=ctx["checkout_id"] if ctx else None)
    return 0


def subagent_stop(payload, validator=None):
    """SubagentStop: validate the returned XML and write the phase snapshot.

    The snapshot was the coordinator's job, which made it the coordinator's job
    to get right on every iteration of every skill. The message carries `skill`,
    `phase`, `ticket-id` and `iteration` (acs-messages.xsd), so the path is
    fully determined by the message and nothing has to be remembered.

    Blocks (exit 2) on a message that does not validate, so the subagent gets
    the errors and can answer again — but only BLOCK_LIMIT times: a hook that
    refuses forever is a hung session, and the skill contract already says a
    still-invalid message fails the run rather than looping.
    """
    agent_id = cc.hook_agent_id(payload)
    skill, role = parse_agent_type(cc.hook_agent_type(payload))
    if not skill:
        return 0
    _ticket_id, tdir, _ctx = resolve_partition(cc.payload_cwd(payload))
    if not tdir:
        return 0

    message = extract_message(cc.hook_last_assistant_message(payload))
    attempts = count_agent_stop_attempt(tdir, stop_counter_key(payload))
    if message is None:
        if attempts > BLOCK_LIMIT:
            _warn("no <result>/<handoff> element in %s's final message after %d attempts; "
                  "the coordinator must record the failure in its own result document"
                  % (payload.get("agent_type"), attempts))
            return 0
        _warn("%s returned no <result> or <handoff> element. Return one, validated "
              "against acs-messages.xsd, as your final message." % payload.get("agent_type"))
        return 2

    if validator is None:
        from validate_xml import validate_structurally as validator  # noqa: N813
    errors = validator(message)  # a LIST of error strings; empty means valid
    if errors:
        if attempts > BLOCK_LIMIT:
            _warn("%s's message is still invalid after %d attempts (%s); letting the "
                  "subagent stop — the coordinator must record the failure"
                  % (payload.get("agent_type"), attempts, "; ".join(errors)))
            return 0
        _warn("%s's message does not validate against acs-messages.xsd:\n  %s\n"
              "Return a corrected message." % (payload.get("agent_type"), "\n  ".join(errors)))
        return 2

    written = write_phase_snapshot(tdir, skill, role, message)
    if written:
        _note("wrote %s" % written)
    clear_agent(tdir, stop_counter_key(payload))
    if agent_id:
        clear_agent(tdir, agent_id)
    return 0


def write_phase_snapshot(tdir, skill, role, message):
    """Persist a validated subagent message as its phase snapshot. Returns the
    path, or None when the message's own attributes do not say where it goes."""
    try:
        root = ET.fromstring(message)
    except ET.ParseError:
        return None
    if root.tag == "handoff":
        return None  # a handoff is not a phase artifact; the run's ledger carries it
    phase = root.get("phase") or ROLE_PHASES.get(role)
    # The schema defaults an absent `iteration` to 1, so a message that omits it
    # is CLAIMING to be iteration 1 -- which on a later iteration would land on
    # the earlier one's snapshot. The message is what is wrong there, not the
    # path, so this says so rather than guessing at a counter it cannot see.
    declared_iteration = root.get("iteration")
    iteration = declared_iteration or "1"
    declared_skill = root.get("skill") or skill
    if not phase:
        return None
    path = phase_artifact_path(tdir, declared_skill, iteration, phase)
    if declared_iteration is None and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            if fh.read().strip() != message.strip():
                _warn("%s omitted `iteration`, which the schema reads as 1, and %s "
                      "already holds a different message. Echo the task's iteration "
                      "in the result." % (role or "the subagent", path))
    write_text(path, message if message.endswith("\n") else message + "\n")
    return path


def stop(payload):
    """Stop: refuse to end a turn that abandoned an in_progress run.

    A run left `in_progress` with no result document is the failure mode the
    whole ledger is built to avoid: the next skill's gate reads "not completed"
    and blocks, and nobody finds out until the next invocation. SessionEnd
    finalizes it as `interrupted`, which is a safety net, not an outcome.

    Refuses at most BLOCK_LIMIT times per checkout and run — after that it says
    so and lets the turn end, because a session that cannot stop is worse than
    a run the safety net will mark interrupted.
    """
    cwd = payload.get("cwd") or os.getcwd()
    ticket_id, tdir, ctx = resolve_partition(cwd)
    if not tdir:
        return 0
    skill = in_flight_skill(tdir, ctx, ticket_id)
    if not skill:
        clear_stop_blocks(ctx)
        return 0
    key = "%s/%s" % (ticket_id, skill)
    result = result_document(tdir, skill)
    if result and result.get("status") in ("completed", "failed", "interrupted", "handed_off"):
        # The document exists; only the post hook is outstanding, and its own
        # absence is what the next gate reports. Not this hook's call to make.
        return 0

    waiting = open_clarifications(tdir)
    if waiting:
        # A run stopped on an OPEN QUESTION is not an abandoned run. The skill
        # contract requires the coordinator to ask before executing on an
        # ambiguous spec (skills/code/SKILL.md), and a turn has to end for the
        # user to answer. Refusing here would push the model to invent a
        # terminal status at exactly the boundary the contract says not to
        # guess at -- and because the counter is keyed per ticket/skill and is
        # only cleared when nothing is in flight, two legitimate pauses would
        # also burn the whole budget, letting a genuinely abandoned run later
        # in the same run stop unchallenged.
        _note("/acs:%s for %s is in_progress with %d open clarification(s); "
              "ending the turn so they can be answered."
              % (skill, ticket_id, len(waiting)))
        return 0

    blocks = count_stop_block(ctx, key)
    if blocks > BLOCK_LIMIT:
        _warn("/acs:%s for %s is still in_progress after %d reminders; ending the turn. "
              "SessionEnd will finalize it as `interrupted`." % (skill, ticket_id, BLOCK_LIMIT))
        return 0
    _warn(
        "/acs:%s for %s is still `in_progress` and has no result document.\n"
        "Write %s and finish the run before stopping:\n"
        "  python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py\" finish "
        "--ticket %s --skill %s --status <completed|failed|interrupted>\n"
        "If the work genuinely cannot continue, hand it off instead:\n"
        "  python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py\" --summary \"...\""
        % (skill, ticket_id, os.path.join(tdir, "phases", skill, "result.json"),
           ticket_id, skill))
    return 2


def pre_compact(payload):
    """PreCompact: write handoff-context.md from state before the window shrinks.

    Compaction is the moment the conversation stops being the record. What
    survives should therefore be the ledger — the ticket, the pipeline, the
    in-flight run, the open clarifications, and the exact command that finishes
    it — not a summary of a window that is already half gone.
    """
    cwd = payload.get("cwd") or os.getcwd()
    ticket_id, tdir, ctx = resolve_partition(cwd)
    if not tdir:
        return 0
    skill = in_flight_skill(tdir, ctx, ticket_id)
    path = write_handoff_context(tdir, ticket_id, skill)
    _note("wrote %s before compaction" % path)
    return 0


def _warn(message):
    sys.stderr.write("acs: %s\n" % message)


def _note(message):
    """Progress chatter, only under $ACS_DEBUG — a hook that prints on every
    subagent turn is noise in the transcript."""
    if os.environ.get("ACS_DEBUG"):
        sys.stderr.write("acs: %s\n" % message)
