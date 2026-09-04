#!/usr/bin/env python3
"""claude_code_adapter.py -- the one module that encodes what acs assumes
about Claude Code's *undocumented* interfaces.

Cost, token, and attribution measurement rests on five interfaces that Claude
Code does not publish as a contract. Before this module they were spelled out
in five different scripts, so a rename upstream broke measurement in five
places and each one degraded (or silently dropped records) its own way. Every
assumption now lives here, once:

1. **Hook envelope fields** -- the JSON a hook receives on stdin:
   `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `tool_input`.
2. **Transcript JSONL record shape** -- `timestamp`, `message.usage.*` (the
   four token classes), `message.model`.
3. **Attribution fields** -- `attributionSkill` on main-session records,
   `attributionAgent` on a subagent's own records, the observed `acs:` prefix
   and the `-planner`/`-executor`/`-verifier` suffixes.
4. **Subagent transcript directory layout** --
   `<dirname(transcript_path)>/<session_id>/subagents/**.jsonl`, with
   `session_id` derived from the transcript's own basename.
5. **statusLine / subagentStatusLine payload keys** -- `model.display_name`,
   `workspace.current_dir`, and the cost/duration probe order.

Two cross-cutting concerns live here for the same reason:

- **One degradation switch.** `unavailable(reason)` is the only way a caller
  marks a measurement unavailable. It logs the reason and returns it, so
  "why is this unavailable?" has a single answer path instead of one
  convention per module. It never raises.
- **`claude_version()`** records which Claude Code build produced a sample,
  so a future shape change can be dated against the version that introduced
  it. Cached (bounded TTL, optional on-disk cache) because measurement hooks
  run per tick.

Stdlib-only (Python 3.9+, no pip). No acs_lib import: acs_lib depends on this
module, never the reverse.

Every accessor is total -- a malformed or absent value yields None (or the
documented empty), never an exception. Callers measure; they do not validate
Claude Code's output.
"""

import datetime
import json
import os
import subprocess
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


#: Distinguishes "no default given" from an explicit default of None. Without
#: it, `payload_cwd(p, default=None)` returned the process cwd -- the opposite
#: of what a caller asking for None means, and how record_session_marker came
#: to invent a cwd for an envelope that carried none.
_NO_DEFAULT = object()


def payload_cwd(payload, default=_NO_DEFAULT):
    """The working directory a payload resolves to.

    One probe order shared by hook envelopes and statusLine payloads:
    `workspace.current_dir`, then top-level `cwd`, then `default` -- which
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
#: Observed agent-name suffixes, mapped to acs's reflection-role vocabulary.
ROLE_SUFFIXES = (("-planner", "planner"),
                 ("-executor", "executor"),
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
# 5. statusLine / subagentStatusLine payload keys
# ---------------------------------------------------------------------------

STATUS_MODEL = "model"
STATUS_MODEL_DISPLAY_NAME = "display_name"

#: Cost probe order: (container key or None, key). A None container means the
#: payload's own top level. Tried in order, then a bounded recursive scan.
COST_PROBE_ORDER = (("cost", "total_cost_usd"),
                    ("cost", "total_cost"),
                    (None, "total_cost_usd"))
#: API-duration probe order -- a structural mirror of COST_PROBE_ORDER.
DURATION_PROBE_ORDER = (("cost", "total_api_duration_ms"),
                        ("cost", "total_api_duration"),
                        (None, "total_api_duration_ms"))


def status_model_display_name(payload, default="Claude"):
    """The payload's `model.display_name`, or `default`."""
    name = _str_or_none(_dict(_dict(payload).get(STATUS_MODEL)).get(STATUS_MODEL_DISPLAY_NAME))
    return name if name else default


def probe_source(container, key):
    """The `src` label recorded for a probe hit ("cost.total_cost_usd")."""
    return key if container is None else "%s.%s" % (container, key)


# ---------------------------------------------------------------------------
# The one degradation switch
# ---------------------------------------------------------------------------

#: The value every degraded measurement carries, everywhere.
UNAVAILABLE = "unavailable"

#: Optional JSONL destination for degradation reasons. Unset (the default),
#: reasons go to stderr only under ACS_DEBUG -- a status line must stay quiet.
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


# ---------------------------------------------------------------------------
# Which Claude Code produced a sample
# ---------------------------------------------------------------------------

CLAUDE_VERSION_TTL_SECONDS = 24 * 60 * 60
_VERSION_MEMO = {}


def claude_version(cache_path=None, ttl_seconds=CLAUDE_VERSION_TTL_SECONDS):
    """`claude --version`, or None when it cannot be determined.

    Recorded alongside cost samples so a shape change can be dated against
    the build that introduced it. Measurement hooks run per tick, so the
    probe is cached: in-process always, and on disk when `cache_path` is
    given (refreshed once per `ttl_seconds`). Never raises, never blocks
    longer than the subprocess timeout."""
    if cache_path:
        cached = _read_version_cache(cache_path, ttl_seconds)
        if cached is not None:
            return cached.get("version")
    elif "version" in _VERSION_MEMO:
        return _VERSION_MEMO["version"]

    version = _probe_claude_version()
    _VERSION_MEMO["version"] = version
    if cache_path:
        _write_version_cache(cache_path, version)
    return version


def _probe_claude_version():
    try:
        proc = subprocess.run(["claude", "--version"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        return proc.stdout.decode("utf-8", errors="replace").strip() or None
    except Exception:
        return None


def _read_version_cache(path, ttl_seconds):
    try:
        age = _now_epoch() - os.path.getmtime(path)
        if age > ttl_seconds:
            return None
        with open(path, "r", encoding="utf-8") as fh:
            cached = json.load(fh)
        return cached if isinstance(cached, dict) else None
    except Exception:
        return None


def _write_version_cache(path, version):
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"version": version, "probed_at": _now_iso()}, fh, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        pass


def _now_epoch():
    import time
    return time.time()
