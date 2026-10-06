"""Calibration plays for create-ticket-epic-no-children.

IDEAL does what /acs:create-ticket's coordinator does, inline, through the
plugin's own writers: `acs step start --allocate` (the mandatory first
action), Step 3's rewrite of ticket.json through `acs.py ticket save`, then
result.json and the post-hook."""

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


def _finish(ws, ttype="epic", needs_design=True, children=()):
    result = {"status": "completed", "summary": "epic created; children deferred to --fan-out",
              "states": {"ticket_id": "EVAL-1", "type": ttype, "needs_design": needs_design,
                         "children": list(children),
                         "prd_trace": {"feature": "F3 Order tracking (P1, roadmap Q1)",
                                       "divergence": None}},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-ticket.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


EPIC = {"title": "[EPIC] Order tracking", "type": "epic", "needs_design": True, "children": [],
        "priority": "high",
        "description": "## Summary\n\nShoppers track an order from payment to delivery.\n\n## Notes\n\nacs-ticket: EVAL-1\n",
        "acceptance_criteria": ["A shopper sees the current status of each of their orders",
                                "A shopper is emailed on every order status change"]}


def IDEAL(ws):
    _start(ws)
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
              '--needs-design false > /dev/null' % (SCRIPTS, title))
    _finish(ws, children=["EVAL-2", "EVAL-3"])


def _typed_story(ws):
    """Treated the epic as one story and left needs_design false."""
    _start(ws)
    _save(ws, **dict(EPIC, title="Order tracking", type="story", needs_design=False))
    _finish(ws, ttype="story", needs_design=False)


BAD = {
    "fired the skill, allocated, wrote nothing": _started_only,
    "minted children in the creation run": _minted_children,
    "typed it a story without a design": _typed_story,
}
