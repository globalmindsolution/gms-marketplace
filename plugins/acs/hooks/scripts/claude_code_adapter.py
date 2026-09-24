#!/usr/bin/env python3
"""claude_code_adapter.py -- the one module that encodes what acs assumes
about Claude Code's *undocumented* interfaces.

What is left of them is the hook envelope: the JSON a hook receives on stdin.
Its `session_id` and `cwd` (or `workspace.current_dir`) fields, plus the
subagent-lifecycle trio `agent_id`, `agent_type` and `last_assistant_message`
(SubagentStart/SubagentStop), are named here once, so a rename upstream is one
edit. The transcript record shape, attribution fields, subagent transcript
layout and statusLine payload keys this module also used to encode went with
the usage measurement and status line that read them (ADR-0103, ADR-0104).

Stdlib-only (Python 3.9+, no pip). No acs_lib import: acs_lib depends on this
module, never the reverse.

Every accessor is total -- a malformed or absent value yields None (or the
documented empty), never an exception. Callers do not validate Claude Code's
output.
"""

import os

# ---------------------------------------------------------------------------
# 1. Hook envelope
# ---------------------------------------------------------------------------

HOOK_SESSION_ID = "session_id"
HOOK_CWD = "cwd"
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
#: of what a caller asking for None means.
_NO_DEFAULT = object()


def payload_cwd(payload, default=_NO_DEFAULT):
    """The working directory a payload resolves to.

    One probe order for every payload shape: `workspace.current_dir`, then
    top-level `cwd`, then `default` -- which defaults to the process cwd, what
    most callers want. Pass `default=None` to get None instead, for a caller
    that must never construct a value."""
    payload = _dict(payload)
    value = _str_or_none(_dict(payload.get(HOOK_WORKSPACE)).get(HOOK_WORKSPACE_DIR))
    if value:
        return value
    value = _str_or_none(payload.get(HOOK_CWD))
    if value:
        return value
    return os.getcwd() if default is _NO_DEFAULT else default
