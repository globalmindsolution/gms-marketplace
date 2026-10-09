"""Calibration plays for create-ticket-epic-no-children.

IDEAL does what /acs:create-ticket's coordinator does, through the plugin's
own writers: `acs step start --allocate` (the mandatory first action), the
epic author and the reviewer spawned (Step 1b), Step 3's rewrite of
ticket.json through `acs.py ticket save`, then result.json and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

P = ".acs/state-machine/example-shop"
TICKET = P + "/EVAL-1/ticket.json"
STEP = P + "/runs/EVAL-1/steps/create-ticket"
REQUEST = "Order tracking for shoppers (PRD feature F3)"


def _start(ws):
    ws.skill("create-ticket")
    started = ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
                     "--title", "(ticket under analysis)", "--args", REQUEST)
    assert started.returncode == 0, started.stderr


def _save(ws, **fields):
    with open(os.path.join(ws.path, TICKET), encoding="utf-8") as fh:
        ticket = json.load(fh)
    ticket.update(fields)
    saved = ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-", stdin=json.dumps(ticket))
    assert saved.returncode == 0, saved.stderr


def _finish(ws, ttype="epic", children=()):
    result = {"status": "completed", "summary": "epic created; children deferred to /acs:breakdown-ticket",
              "states": {"ticket_id": "EVAL-1", "type": ttype,
                         "children": list(children),
                         "prd_trace": {"feature": "F3 Order tracking (P1, roadmap Q1)",
                                       "divergence": None}},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-ticket.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


EPIC = {"title": "[EPIC] Order tracking", "type": "epic", "children": [],
        "priority": "high", "features": ["order-tracking"],
        "description": "## Summary\n\nShoppers track an order from payment to delivery.\n\n## Notes\n\nacs-ticket: EVAL-1\n",
        "acceptance_criteria": ["A shopper sees the current status of each of their orders",
                                "A shopper is emailed on every order status change"]}


def _drafted(ws, author="epic-author"):
    ws.called("Agent", subagent_type="acs:create-ticket-" + author,
              prompt='<task skill="create-ticket" phase="%s" ticket-id="EVAL-1" iteration="1">' % author)
    ws.called("Agent", subagent_type="acs:create-ticket-reviewer",
              prompt='<task skill="create-ticket" phase="reviewer" ticket-id="EVAL-1" iteration="1">')


def IDEAL(ws):
    _start(ws)
    _drafted(ws)
    _save(ws, **EPIC)
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _minted_children(ws):
    """Decomposed the epic in its own creation run."""
    _start(ws)
    _save(ws, **EPIC)
    for title in ("Carrier status intake", "Order status page"):
        ws.sh('python3 "%s/new-ticket.py" --title "%s" --type story --parent EVAL-1 '
              '> /dev/null' % (SCRIPTS, title))
    _finish(ws, children=["EVAL-2", "EVAL-3"])


def _typed_story(ws):
    """Treated the epic as one story."""
    _start(ws)
    _drafted(ws, "story-author")
    _save(ws, **dict(EPIC, title="Order tracking", type="story"))
    _finish(ws, ttype="story")


def _unlinked(ws):
    """An epic linking no PRD feature: the post-hook refuses the run (ADR-0144)."""
    _start(ws)
    _drafted(ws)
    _save(ws, **dict(EPIC, features=[]))
    _finish(ws)


BAD = {
    "linked no PRD feature": _unlinked,
    "fired the skill, allocated, wrote nothing": _started_only,
    "minted children in the creation run": _minted_children,
    "typed it a story": _typed_story,
}
