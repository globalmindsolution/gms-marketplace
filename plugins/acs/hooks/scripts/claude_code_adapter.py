#!/usr/bin/env python3
"""claude_code_adapter.py -- the one module that encodes what acs assumes
about Claude Code's *undocumented* interfaces.

Token and attribution measurement rests on four interfaces that Claude Code
does not publish as a contract. Before this module they were spelled out in
several scripts, so a rename upstream broke measurement in several places and
each one degraded (or silently dropped records) its own way. Every assumption
now lives here, once:

1. **Hook envelope fields** -- the JSON a hook receives on stdin:
   `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `tool_input`,
   plus the subagent-lifecycle trio `agent_id`, `agent_type` and
   `last_assistant_message` (SubagentStart/SubagentStop).
2. **Transcript JSONL record shape** -- `timestamp`, `message.usage.*` (the
   four token classes), `message.model`.
3. **Attribution fields** -- `attributionSkill` on main-session records,
   `attributionAgent` on a subagent's own records, the observed `acs:` prefix
   and the `-planner`/`-executor`/`-verifier` suffixes.
4. **Subagent transcript directory layout** --
   `<dirname(transcript_path)>/<session_id>/subagents/**.jsonl`, with
   `session_id` derived from the transcript's own basename.

One cross-cutting concern lives here for the same reason:

- **One degradation switch.** `unavailable(reason)` is the only way a caller
  marks a measurement unavailable. It logs the reason and returns it, so
  "why is this unavailable?" has a single answer path instead of one
  convention per module. It never raises.

Stdlib-only (Python 3.9+, no pip). No acs_lib import: acs_lib depends on this
module, never the reverse.

Every accessor is total -- a malformed or absent value yields None (or the
documented empty), never an exception. Callers measure; they do not validate
Claude Code's output.
"""

import datetime
import json
import os
import sys

# ---------------------------------------------------------------------------
# 1. Hook envelope
# ---------------------------------------------------------------------------

HOOK_SESSION_ID = "session_id"
HOOK_TRANSCRIPT_PATH = "transcript_path"
HOOK_CWD = "cwd"
HOOK_EVENT_NAME = "hook_event_name"
HOOK_TOOL_INPUT = "tool_input"
HOOK_WORKSPACE = "workspace"
HOOK_WORKSPACE_DIR = "current_dir"

#: SubagentStart / SubagentStop only. Undocumented like the rest of this
#: section: the events are documented, these payload keys are not. They are
#: named here rather than at their call sites so a rename upstream is one edit
#: -- and so the blast radius of that rename is visible in one place.
HOOK_AGENT_ID = "agent_id"
HOOK_AGENT_TYPE = "agent_type"
HOOK_LAST_ASSISTANT_MESSAGE = "last_assistant_message"


def _dict(value):
    return value if isinstance(value, dict) else {}


def _str_or_none(value):
    return value if isinstance(value, str) and value else None


def hook_session_id(payload):
    """The envelope's session id, or None."""
    return _str_or_none(_dict(payload).get(HOOK_SESSION_ID))


def hook_transcript_path(payload):
    """The envelope's transcript path, or None. Never constructed from cwd."""
    return _str_or_none(_dict(payload).get(HOOK_TRANSCRIPT_PATH))


def hook_event_name(payload):
    """The envelope's hook event name, or None."""
    return _str_or_none(_dict(payload).get(HOOK_EVENT_NAME))


def hook_tool_input(payload):
    """The envelope's tool_input object, or {} when absent/malformed."""
    return _dict(_dict(payload).get(HOOK_TOOL_INPUT))


def hook_agent_id(payload):
    """The SubagentStart/SubagentStop agent id, or None.

    Absence is a real case, not a malformed payload: a Claude Code that does
    not send the field, and a subagent whose start event never reached us.
    Callers must have an answer for None rather than assuming it."""
    return _str_or_none(_dict(payload).get(HOOK_AGENT_ID))


def hook_agent_type(payload):
    """The SubagentStart/SubagentStop agent type (e.g. `acs:code-executor`)."""
    return _str_or_none(_dict(payload).get(HOOK_AGENT_TYPE))


def hook_last_assistant_message(payload):
    """The subagent's final message text on SubagentStop, or None.

    acs reads its `<result>`/`<handoff>` element out of this. If the key is
    ever renamed upstream every acs subagent looks like it returned nothing,
    so this accessor is the single place that assumption is written down."""
    return _str_or_none(_dict(payload).get(HOOK_LAST_ASSISTANT_MESSAGE))


#: Distinguishes "no default given" from an explicit default of None. Without
#: it, `payload_cwd(p, default=None)` returned the process cwd -- the opposite
#: of what a caller asking for None means, and how record_session_marker came
#: to invent a cwd for an envelope that carried none.
_NO_DEFAULT = object()


def payload_cwd(payload, default=_NO_DEFAULT):
    """The working directory a payload resolves to.

    One probe order for every payload shape: `workspace.current_dir`, then
    top-level `cwd`, then `default` -- which
    defaults to the process cwd, what most callers want. Pass `default=None`
    to get None instead: a caller that must never construct a value (the
    session marker records envelope fields verbatim) needs the probe order
    without the fallback."""
    payload = _dict(payload)
    value = _str_or_none(_dict(payload.get(HOOK_WORKSPACE)).get(HOOK_WORKSPACE_DIR))
    if value:
        return value
    value = _str_or_none(payload.get(HOOK_CWD))
    if value:
        return value
    return os.getcwd() if default is _NO_DEFAULT else default


# ---------------------------------------------------------------------------
# 2. Transcript JSONL record shape
# ---------------------------------------------------------------------------

#: The four token classes Claude Code reports, in the order acs buckets them.
USAGE_FIELDS = ("input_tokens", "output_tokens",
                "cache_creation_input_tokens", "cache_read_input_tokens")
#: acs's own bucket names, positionally paired with USAGE_FIELDS.
BUCKET_KEYS = ("input", "output", "cache_creation", "cache_read")

RECORD_TIMESTAMP = "timestamp"
RECORD_MESSAGE = "message"
MESSAGE_USAGE = "usage"
MESSAGE_MODEL = "model"


def record_timestamp(record):
    """The record's raw timestamp string, or None. Parsing is the caller's."""
    return _str_or_none(_dict(record).get(RECORD_TIMESTAMP))


def record_usage(record):
    """The record's `message.usage` object, or None when it carries none.

    Privacy boundary: this is the only door into `message`, and it opens on
    `usage` alone -- never content, prompt text, or tool results."""
    usage = _dict(record).get(RECORD_MESSAGE)
    usage = _dict(usage).get(MESSAGE_USAGE)
    return usage if isinstance(usage, dict) else None


def record_model(record):
    """The record's `message.model`, or None."""
    return _str_or_none(_dict(_dict(record).get(RECORD_MESSAGE)).get(MESSAGE_MODEL))


# ---------------------------------------------------------------------------
# 3. Attribution fields
# ---------------------------------------------------------------------------

RECORD_ATTRIBUTION_SKILL = "attributionSkill"
RECORD_ATTRIBUTION_AGENT = "attributionAgent"

#: Observed prefix on every attributionSkill value acs emits ("acs:code").
SKILL_PREFIX = "acs:"
#: Observed agent-name suffixes, mapped to acs's reflection-role vocabulary
#: (executor and verifier only since ADR-0092; `planner` survives in recorded
#: role_usage rows from older runs, never as a spawnable agent).
ROLE_SUFFIXES = (("-executor", "executor"),
                 ("-verifier", "verifier"))


def record_attribution_skill(record):
    """A main-session record's `attributionSkill`, or None."""
    return _str_or_none(_dict(record).get(RECORD_ATTRIBUTION_SKILL))


def record_attribution_agent(record):
    """A subagent record's own `attributionAgent`, or None."""
    return _str_or_none(_dict(record).get(RECORD_ATTRIBUTION_AGENT))


def strip_skill_prefix(name):
    """"acs:code" -> "code"; anything else is returned unchanged (None-safe)."""
    if not isinstance(name, str) or not name:
        return None
    return name[len(SKILL_PREFIX):] if name.startswith(SKILL_PREFIX) else name


def agent_role(attribution_agent, default="other"):
    """Map an observed agent name to a reflection role.

    Suffix-matches ROLE_SUFFIXES; a present-but-unmatched value yields
    `default` (still attributed, never dropped), an absent one None."""
    name = _str_or_none(attribution_agent)
    if name is None:
        return None
    for suffix, role in ROLE_SUFFIXES:
        if name.endswith(suffix):
            return role
    return default


# ---------------------------------------------------------------------------
# 4. Subagent transcript directory layout
# ---------------------------------------------------------------------------

TRANSCRIPT_SUFFIX = ".jsonl"
SUBAGENTS_DIRNAME = "subagents"


def session_id_from_transcript(transcript_path):
    """The session id a transcript path encodes ("<...>/<session_id>.jsonl").

    Derived from the recorded path's own basename -- never a cwd-constructed
    slug. None when the path is absent/malformed."""
    path = _str_or_none(transcript_path)
    if path is None:
        return None
    return os.path.splitext(os.path.basename(path))[0] or None


def subagents_dir(transcript_path):
    """The directory holding this session's subagent transcripts, or None.

    `<dirname(transcript_path)>/<session_id>/subagents`. Existence is the
    caller's business; this only says where to look."""
    session_id = session_id_from_transcript(transcript_path)
    if session_id is None:
        return None
    return os.path.join(os.path.dirname(transcript_path), session_id, SUBAGENTS_DIRNAME)


def is_transcript_file(name):
    """True for a transcript JSONL name.

    The privacy boundary depends on this being suffix-exact: a
    "*.meta.json" sidecar must never match, so it is never enumerated and
    never opened."""
    return isinstance(name, str) and name.endswith(TRANSCRIPT_SUFFIX)


# ---------------------------------------------------------------------------
# The one degradation switch
# ---------------------------------------------------------------------------

#: The value every degraded measurement carries, everywhere.
UNAVAILABLE = "unavailable"

#: Optional JSONL destination for degradation reasons. Unset (the default),
#: reasons go to stderr only under ACS_DEBUG -- a hook must stay quiet.
DEGRADATION_LOG_ENV = "ACS_DEGRADATION_LOG"
DEBUG_ENV = "ACS_DEBUG"

MAX_DEGRADATION_LOG_BYTES = 256 * 1024


def unavailable(reason, detail=None, source=None):
    """Mark a measurement unavailable, logging why. Returns `reason`.

    The single switch: no caller invents its own degradation path, so every
    "unavailable" in a metrics artifact traces to one call site here. Never
    raises -- a failure to log is not a reason to lose the measurement's own
    degraded result."""
    try:
        _log_degradation({"ts": _now_iso(), "reason": reason,
                          "detail": detail, "source": source})
    except Exception:
        pass
    return reason


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0, tzinfo=None).isoformat() + "Z"


def _log_degradation(entry):
    path = os.environ.get(DEGRADATION_LOG_ENV)
    if path:
        if os.path.exists(path) and os.path.getsize(path) > MAX_DEGRADATION_LOG_BYTES:
            os.replace(path, path + ".1")
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return
    if os.environ.get(DEBUG_ENV):
        sys.stderr.write("acs: measurement unavailable (%s)\n" % entry.get("reason"))
