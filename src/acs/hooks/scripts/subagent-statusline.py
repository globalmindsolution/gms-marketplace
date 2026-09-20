#!/usr/bin/env python3
"""subagent-statusline.py — optional Claude Code agent-panel rows for acs subagents.

Claude Code invokes this once per refresh tick with ONE JSON object on stdin:

    {"columns": <usable row width>, "tasks": [{"id", "name", "type", "status",
     "description", "label", "startTime", "tokenCount", "cwd", ...}, ...]}

For every task we recognize as an acs subagent (`<skill>-<role>`, where the
roles are the ones `acs_lib.skills` knows), we emit one JSON line:

    {"id": "<task id>", "content": "<row body>"}

restyling the row as, e.g.:

    ▶ review · review-code-lens · MAR-590 · 45k tok · 1m32s

Tasks we do not recognize get NO line — they keep Claude Code's default
rendering. We never crash and never write garbage: on any problem we emit
nothing and the panel falls back to defaults.

Wire-up (offered by /acs:setup Step 7b; statusLine rules apply — user-owned,
absolute path, never forced):

    {"subagentStatusLine": {"type": "command",
                            "command": "python3 /abs/path/hooks/scripts/subagent-statusline.py"}}
"""

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import claude_code_adapter as cc  # noqa: E402,F401
from acs_lib import skills as skills_registry  # noqa: E402

# Skill and role vocabulary come from the TREE, not from a list kept here.
# The hard-coded nine skills went stale twice over -- `create-spec` outlived
# its skill by two releases, and `code-verifier` outlived its agent -- while
# every real agent file is `agents/<skill>-<role>.md` and says so by its name.
ROLE_RE = re.compile(r"\b([a-z0-9]+(?:-[a-z0-9]+)*?)-(%s)\b"
                     % "|".join(skills_registry.AGENT_ROLES))
PHASE = {"planner": "plan", "executor": "execute", "verifier": "verify",
         "lens": "review", "adjudicator": "adjudicate"}
STATUS_GLYPH = {"running": "▶", "in_progress": "▶", "pending": "○",
                "completed": "✓", "done": "✓", "failed": "✗", "error": "✗"}


def detect_role(task):
    """(skill, role), or (None, None). The skill must be a real skill
    directory: `<anything>-executor` in a description is not an acs subagent."""
    try:
        known = skills_registry.skill_agents()
    except Exception:  # noqa: BLE001 -- a status line never crashes
        known = {}
    if not known:
        return None, None
    for key in ("type", "name", "label", "description"):
        value = task.get(key)
        if not isinstance(value, str):
            continue
        for match in ROLE_RE.finditer(value):
            if match.group(2) in known.get(match.group(1), ()):
                return match.group(1), match.group(2)
    return None, None


def run_for(task):
    """Best effort: the per-checkout pointer of the task's cwd names the run.

    A run id reads like its subject (§4.2) -- `MAR-590`,
    `fix-the-login-timeout-3f2a` -- so it is as useful here as a ticket id
    was, and it is defined for the runs that have no ticket at all."""
    cwd = task.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return None
    try:
        import acs_lib as lib
        ctx = lib.build_context(cwd)
        return lib.current_run_id(ctx)
    except Exception:  # noqa: BLE001 -- a status line never crashes
        return None


def elapsed(start):
    if not isinstance(start, (int, float)) or start <= 0:
        return None
    if start > 1e12:  # epoch milliseconds
        start = start / 1000.0
    seconds = int(time.time() - start)
    if seconds < 0:
        return None
    if seconds < 60:
        return "%ds" % seconds
    return "%dm%02ds" % (seconds // 60, seconds % 60)


def tokens(count):
    if not isinstance(count, (int, float)) or count <= 0:
        return None
    if count >= 1000:
        return "%.0fk tok" % (count / 1000.0)
    return "%d tok" % count


def row(task, columns):
    skill, role = detect_role(task)
    if not skill:
        return None
    glyph = STATUS_GLYPH.get(str(task.get("status") or "").lower(), "▶")
    bits = ["%s %s" % (glyph, PHASE.get(role, role)), "%s-%s" % (skill, role)]
    run_id = run_for(task)
    if run_id:
        bits.insert(2, run_id)
    tok = tokens(task.get("tokenCount"))
    if tok:
        bits.append(tok)
    span = elapsed(task.get("startTime"))
    if span:
        bits.append(span)
    content = " · ".join(bits)
    if isinstance(columns, int) and columns > 4 and len(content) > columns:
        content = content[: columns - 1] + "…"
    return {"id": task.get("id"), "content": content}


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return
    columns = payload.get("columns")
    for task in payload.get("tasks") or []:
        if not isinstance(task, dict) or task.get("id") in (None, ""):
            continue
        try:
            line = row(task, columns)
        except Exception:
            line = None  # never break the panel for one row
        if line:
            sys.stdout.write(json.dumps(line) + "\n")


if __name__ == "__main__":
    main()
