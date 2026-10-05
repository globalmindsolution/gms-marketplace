"""Calibration plays for create-ticket-fan-out-designed-epic.

IDEAL does what the --fan-out mode does, through the plugin's own writers:
`acs step start --step create-ticket --run EVAL-1` (no --allocate),
new-ticket.py --parent EVAL-1 for each confirmed child, the confirmed
acceptance criteria written into each child through `acs.py ticket save`,
then result.json and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-ticket"
CHILDREN = [
    ("Carrier status webhooks", "story", "3",
     ["POST /webhooks/carrier/{carrier} with a valid signature stores the status change against its order and returns 204",
      "A callback with a missing or invalid signature is rejected with HTTP 401 and stores nothing"]),
    ("Order status page", "story", "2",
     ["GET /orders/{id}/status returns the order's latest status and its full status history, newest first",
      "An unknown order id returns HTTP 404"]),
    ("Status-change emails", "task", "2",
     ["Every stored status change sends one email to the order's shopper naming the new status"]),
]


def _start(ws, *extra):
    ws.skill("create-ticket")
    started = ws.acs("step", "start", "--step", "create-ticket", "--run", "EVAL-1", *extra)
    assert started.returncode == 0, started.stderr


def _mint(ws, children, with_criteria=True):
    ids = []
    for title, ttype, points, criteria in children:
        out = ws.sh('python3 "%s/new-ticket.py" --title "%s" --type %s --parent EVAL-1 '
                    '--priority medium --needs-design false --story-points %s'
                    % (SCRIPTS, title, ttype, points))
        tid = json.loads(out)["ticket_id"]
        ids.append(tid)
        if with_criteria:
            saved = ws.acs("ticket", "save", "--ticket", tid, "--from", "-",
                           stdin=json.dumps({"acceptance_criteria": criteria}))
            assert saved.returncode == 0, saved.stderr
    return ids


def _finish(ws, ids):
    result = {"status": "completed", "summary": "fanned out %d children" % len(ids),
              "states": {"ticket_id": "EVAL-1", "type": "epic", "needs_design": True,
                         "children": ids,
                         "prd_trace": {"feature": "F3 Order tracking", "divergence": None}},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-ticket.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    _finish(ws, _mint(ws, CHILDREN))


def _no_criteria(ws):
    """Minted the three children but never wrote their criteria."""
    _start(ws)
    _finish(ws, _mint(ws, CHILDREN, with_criteria=False))


def _allocated_first(ws):
    """Treated the invocation as a new request: allocated a fresh id first."""
    ws.skill("create-ticket")
    ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
           "--title", "(ticket under analysis)", "--args", "EVAL-1 --fan-out")
    _mint(ws, CHILDREN)


def _extra_child(ws):
    """Invented a fourth child the user never confirmed."""
    _start(ws)
    extra = CHILDREN + [("Tracking admin dashboard", "story", "3", ["Admins see all shipments"])]
    _finish(ws, _mint(ws, extra))


BAD = {
    "children minted without their criteria": _no_criteria,
    "allocated a new id before minting": _allocated_first,
    "minted an unconfirmed fourth child": _extra_child,
}
