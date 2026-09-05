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
import posixpath
import re
import sys
import xml.etree.ElementTree as ET

import claude_code_adapter as cc  # noqa: E402

from datetime import datetime, timezone

from ._common import GateError, HOOKED_SKILLS, now_iso, read_json, write_json, write_text
from .repo import find_ticket_partition, pointer_path, resolve_ticket_id, sessions_dir
from .state import last_run, last_run_status, load_pipeline, load_state, load_ticket
from . import verdict

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


def _release_agent(tdir, payload):
    """Drop this subagent's record and its refusal counter, whichever keys it
    was tracked under.

    Called only where the subagent stopped CLEANLY. On a give-up the record is
    deliberately left in place: it carries the refusal count that reached the
    cap, and deleting it would reset that count so the next attempt started
    from zero and the cap never held. A given-up record stops arming MAR-529's
    guard by a different route -- _record_is_current treats stop_attempts above
    the cap as no longer running."""
    clear_agent(tdir, stop_counter_key(payload))
    agent_id = cc.hook_agent_id(payload)
    if agent_id:
        clear_agent(tdir, agent_id)


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
# Each returns an exit code. 0 always means "carry on". THREE of them can
# return 2, for different reasons and with different failure polarity:
# subagent_stop and stop block to FORCE an action (and fail open, via
# dispatch.run_lifecycle), while file_map_guard DENIES one (and fails closed
# once it is in scope, via dispatch.run_file_map_guard). Every one of them
# treats "this is not an acs ticket" and "there is nothing to do" as the same
# answer, because in most sessions they are.


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
                  % (cc.hook_agent_type(payload), attempts))
            return 0  # record kept: it carries the refusal count that got us here
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
                  % (cc.hook_agent_type(payload), attempts, "; ".join(errors)))
            return 0  # record kept: it carries the refusal count that got us here
        _warn("%s's message does not validate against acs-messages.xsd:\n  %s\n"
              "Return a corrected message." % (cc.hook_agent_type(payload), "\n  ".join(errors)))
        return 2

    try:
        written = write_phase_snapshot(tdir, skill, role, message)
        if written:
            _note("wrote %s" % written)
    except BaseException:
        # A snapshot write that raises must not leave the agent recorded, or
        # MAR-529's guard stays armed against a subagent that has stopped. The
        # release cannot go in a `finally` here: the verdict check below may
        # legitimately send this subagent back, and that path must KEEP the
        # record so its refusal count survives.
        _release_agent(tdir, payload)
        raise

    verdict_errors = check_verifier_verdict(tdir, skill, role, message)
    if verdict_errors:
        if attempts > BLOCK_LIMIT:
            _warn("%s's verdict is still unusable after %d attempts (%s); letting the "
                  "subagent stop -- the coordinator must record the failure"
                  % (cc.hook_agent_type(payload), attempts, "; ".join(verdict_errors)))
            return 0  # record kept: it carries the refusal count that got us here
        _warn("%s must write a valid verdict.json alongside its report:\n  %s\n"
              "Write it and answer again." % (cc.hook_agent_type(payload),
                                              "\n  ".join(verdict_errors)))
        return 2

    _release_agent(tdir, payload)
    return 0


#: Skills whose verifier owes a verdict.json. ONLY /acs:code: MAR-527's
#: contract is written in agents/code-verifier.md, and the other fourteen
#: agents/*-verifier.md files were never given it. Gating on the ROLE alone
#: held every one of them to a contract they had never been told about, so a
#: docs-sync or create-pr run burnt BLOCK_LIMIT extra verifier turns and ended
#: with a "verdict is still unusable" warning.
VERDICT_SKILLS = ("code",)


def check_verifier_verdict(tdir, skill, role, message,
                           ticket_id=None, expect_iteration=None):
    """Errors in the verdict a VERIFIER must have written, or [] for anyone else.

    The verdict is the one thing only the verifier knows, and the coordinator
    used to transcribe it. Validating it here is what makes it a finding rather
    than a claim -- in particular `passed` must agree with the findings
    (acs_lib.verdict), so a verdict that says it passed while carrying a
    blocking finding is rejected instead of believed.
    """
    if role != "verifier" or skill not in VERDICT_SKILLS:
        return []
    try:
        root = ET.fromstring(message)
    except ET.ParseError:
        return []
    if root.tag != "result":
        return []  # a handoff/needs_input answer reports no verdict
    if root.get("status") != "completed":
        return []  # verification did not finish; there is nothing to have judged
    iteration = root.get("iteration") or "1"
    lens = root.get("lens")
    for constraint in root.iter("constraint"):
        if constraint.get("name") == "verify_lens":
            lens = (constraint.text or "").strip() or None
    doc_skill = root.get("skill") or skill
    path = verdict.verdict_path(tdir, doc_skill, iteration, lens)
    doc = read_json(path)
    if doc is None:
        return ["no verdict at %s" % path]
    # The document's own identity is checked against the message's, not just
    # its shape: a verdict found at the right PATH can still be about another
    # ticket, skill or iteration, and only the path was ever checked before.
    return verdict.validate_verdict(
        doc, lens=lens, skill=doc_skill,
        ticket_id=ticket_id or root.get("ticket-id"),
        iteration=expect_iteration or iteration)


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
    # writable by an executor scoped to this one.
    if _is_guard_control_input(target, tdir, ctx):
        _warn(
            "%s is the file-map guard's own control input.\n"
            "An executor cannot widen or disarm its own scope. If the map is "
            "wrong, STOP and return `needs_input` naming the file, so the "
            "coordinator can adjust it." % target)
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


def _is_guard_control_input(target, tdir, ctx):
    """Is this write aimed at something the guard itself reads to decide?

    Two things: the active-agents record (which says an executor is running)
    and any iteration's file map (which says what it may touch). Either one
    lets an executor answer the guard's own question, so neither is writable
    while the guard is armed."""
    if _under(target, active_agents_dir(tdir)):
        return True
    normalized = normalize_repo_path(target)
    prefix, suffix = FILEMAP_FILENAME_FMT.split("%s")
    base = os.path.basename(normalized)
    if base.startswith(prefix) and base.endswith(suffix):
        return True
    return False


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
