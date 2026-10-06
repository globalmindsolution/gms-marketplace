"""Calibration plays for breakdown-ticket-split-oversized-story.

IDEAL does what /acs:breakdown-ticket does on a story, through the plugin's
own writers: `acs step start --step breakdown-ticket --ticket EVAL-1`, the
conversion to an epic as an `acs.py ticket save` patch, new-ticket.py
--parent EVAL-1 for each confirmed child (the story's features inherited),
the confirmed acceptance criteria written into each child through `acs.py
ticket save`, then result.json and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/breakdown-ticket"
PLAN = "docs/development/order-management/EVAL-1/plan.md"
CHILDREN = [
    ("Checkout and order storage", "story", "3",
     ["POST /checkout charges the card through the payments gateway and creates the order",
      "A declined card returns HTTP 402 with error code card_declined and creates no order",
      "Orders and refunds are stored in two new tables created by a migration"]),
    ("Refunds", "story", "2",
     ["POST /orders/{id}/refund refunds the charge through the payments gateway and marks the order refunded",
      "A refund older than 30 days is rejected with HTTP 409 and error code refund_window_closed"]),
    ("Merchant CSV export", "task", "2",
     ["GET /merchant/orders/export returns every order as CSV for accounting",
      "The export lists one row per order with its id, date, total and status"]),
]


def _start(ws):
    ws.skill("breakdown-ticket")
    started = ws.acs("step", "start", "--step", "breakdown-ticket", "--ticket", "EVAL-1",
                     "--args", "EVAL-1 " + PLAN)
    assert started.returncode == 0, started.stderr


def _convert(ws):
    saved = ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-",
                   stdin=json.dumps({"type": "epic", "needs_design": True,
                                     "title": "[EPIC] Storefront order management"}))
    assert saved.returncode == 0, saved.stderr


def _mint(ws, children, parent="--parent EVAL-1 "):
    ids = []
    for title, ttype, points, criteria in children:
        out = ws.sh('python3 "%s/new-ticket.py" --title "%s" --type %s %s'
                    '--priority medium --needs-design false --story-points %s'
                    % (SCRIPTS, title, ttype, parent, points))
        tid = json.loads(out)["ticket_id"]
        ids.append(tid)
        saved = ws.acs("ticket", "save", "--ticket", tid, "--from", "-",
                       stdin=json.dumps({"acceptance_criteria": criteria}))
        assert saved.returncode == 0, saved.stderr
    return ids


def _finish(ws, ids, converted_from="story"):
    result = {"status": "completed", "summary": "split EVAL-1 into %d children" % len(ids),
              "states": {"ticket_id": "EVAL-1", "type": "epic", "converted_from": converted_from,
                         "children": ids, "minted": ids, "design_status": None},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-breakdown-ticket.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    _convert(ws)
    _finish(ws, _mint(ws, CHILDREN))


def _fresh_roots(ws):
    """Left EVAL-1 a story and minted three unrelated root tickets."""
    _start(ws)
    _mint(ws, CHILDREN, parent="")


def _converted_only(ws):
    """Converted EVAL-1 and stopped before minting anything."""
    _start(ws)
    _convert(ws)
    _finish(ws, [])


def _missed_a_seam(ws):
    """Minted two of the three confirmed children."""
    _start(ws)
    _convert(ws)
    _finish(ws, _mint(ws, CHILDREN[:2]))


BAD = {
    "minted fresh roots instead of converting": _fresh_roots,
    "converted and minted nothing": _converted_only,
    "missed a confirmed child": _missed_a_seam,
}
