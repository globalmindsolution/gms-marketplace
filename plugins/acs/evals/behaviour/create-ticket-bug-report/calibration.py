"""Calibration plays for create-ticket-bug-report.

IDEAL does what /acs:create-ticket does on a bug report, through the plugin's
own writers: `acs step start --allocate` (the mandatory first action), the bug
author and the reviewer spawned (Step 1b), Step 3's rewrite of ticket.json
with the bug fields through `acs.py ticket save`, then result.json and the
post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

P = ".acs/state-machine/example-shop"
TICKET = P + "/EVAL-1/ticket.json"
STEP = P + "/runs/EVAL-1/steps/create-ticket"
REQUEST = "The customer listing ignores the page size we ask for."

BUG = {
    "title": "Customer listing ignores a page size above 20",
    "type": "bug", "priority": "medium", "children": [],
    "severity": "high",
    "reproduction": "1. Start from a database with 60 customers.\n"
                    "2. Call list_customers(offset=0, limit=50).\n"
                    "3. Look at the response's limit and the number of items.",
    "expected": "The response honours limit=50: \"limit\": 50 and up to 50 customers.",
    "actual": "The response says \"limit\": 20 and holds at most 20 customers.",
    "environment": "shop 2.4.0, Python 3.12, default settings",
    "description": "## Summary\n\nThe customer listing ignores a requested page size above 20.\n\n"
                   "## Notes\n\nacs-ticket: EVAL-1\n",
    "acceptance_criteria": [
        "A regression test reproduces the bug: list_customers(limit=50) over 60 customers fails before the fix and passes after it",
        "list_customers(offset=0, limit=50) returns \"limit\": 50 and 50 customers when 60 exist",
        "A limit outside 1-100 is rejected with a ValueError naming the allowed range"],
}


def _start(ws):
    ws.skill("create-ticket")
    started = ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
                     "--title", "(ticket under analysis)", "--args", REQUEST)
    assert started.returncode == 0, started.stderr


def _drafted(ws, author="bug-author"):
    ws.called("Agent", subagent_type="acs:create-ticket-" + author,
              prompt='<task skill="create-ticket" phase="%s" ticket-id="EVAL-1" iteration="1">' % author)
    ws.called("Agent", subagent_type="acs:create-ticket-reviewer",
              prompt='<task skill="create-ticket" phase="reviewer" ticket-id="EVAL-1" iteration="1">')


def _save(ws, fields):
    with open(os.path.join(ws.path, TICKET), encoding="utf-8") as fh:
        ticket = json.load(fh)
    ticket.update(fields)
    saved = ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-", stdin=json.dumps(ticket))
    assert saved.returncode == 0, saved.stderr


def _finish(ws, ttype="bug"):
    result = {"status": "completed", "summary": "bug filed; reviewer passed on iteration 1",
              "states": {"ticket_id": "EVAL-1", "type": ttype,
                         "children": [],
                         "prd_trace": {"feature": "F1 Customer listing", "divergence": None}},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-ticket.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    _drafted(ws)
    _save(ws, BUG)
    _finish(ws)


def _typed_a_task(ws):
    """Filed the report as a task, its bug details left in prose."""
    _start(ws)
    _drafted(ws, "task-author")
    task = {k: v for k, v in BUG.items()
            if k not in ("severity", "reproduction", "expected", "actual", "environment")}
    _save(ws, dict(task, type="task"))
    _finish(ws, ttype="task")


def _no_regression_criterion(ws):
    """A bug with its fields but no regression test among its criteria."""
    _start(ws)
    _drafted(ws)
    _save(ws, dict(BUG, acceptance_criteria=BUG["acceptance_criteria"][1:]))
    _finish(ws)


def _drafted_inline(ws):
    """Wrote the bug itself, spawning neither the bug author nor the reviewer."""
    _start(ws)
    _save(ws, BUG)
    _finish(ws)


BAD = {
    "filed as a task": _typed_a_task,
    "no regression criterion": _no_regression_criterion,
    "drafted inline without the author": _drafted_inline,
}
