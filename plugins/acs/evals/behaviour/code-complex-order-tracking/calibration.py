"""Plays for code-complex-order-tracking (see
tests/evals/check_grader_calibration.py).

IDEAL is what the code-complex leg does on this plan, through its real
writers: `acs.py step start --step code` (which passes the approval brake the
scaffold's `acs.py plan check` satisfied); slices 1 and 2, each writing only
its own paths (nothing committed -- ADR-0127) and writing
`iter-1/implementer-<k>.json`; the integration slice, whose map the leg
declares as task 3 with `acs.py filemap set` and which writes
`iter-1/implementer-integration.json`; the leg's result.json; and `post-
code.py`.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
CODE = ".acs/state-machine/example-shop/runs/EVAL-1/steps/code"

ORDERS = '''STATUSES = ("placed", "paid", "shipped", "delivered")


class Order(object):
    def __init__(self):
        self.status = STATUSES[0]


def advance(order, status):
    """Move an order exactly one step forward."""
    here = STATUSES.index(order.status)
    if status not in STATUSES or STATUSES.index(status) != here + 1:
        raise ValueError("cannot move %s to %s" % (order.status, status))
    order.status = status
'''

UNGUARDED = ORDERS.replace(
    '    here = STATUSES.index(order.status)\n'
    '    if status not in STATUSES or STATUSES.index(status) != here + 1:\n'
    '        raise ValueError("cannot move %s to %s" % (order.status, status))\n', "")

TRACKING = '''LABELS = {"placed": "Order received", "paid": "Payment confirmed",
          "shipped": "On its way", "delivered": "Delivered"}


def tracking_label(status):
    """What a shopper reads for an order status."""
    return LABELS[status]
'''

SEAMED = TRACKING.replace(
    'def tracking_label',
    'from shop.orders import STATUSES\n\nassert set(LABELS) == set(STATUSES)\n\n\ndef tracking_label')


def _written(ws):
    """`states.files`: every repo path the run left uncommitted for /acs:create-pr
    (ADR-0127) -- the scaffold's own uncommitted ticket docs aside."""
    out = ws.sh("git status --porcelain --untracked-files=all")
    return sorted(line[3:] for line in out.splitlines()
                  if not line[3:].startswith((".acs/", "docs/development/", "docs/architecture/lld/")))


def _report(ws, name, files, **extra):
    doc = {"files_changed": files,
           "tests": {"commands": ["python3 -m pytest -q " + " ".join(
               f for f in files if f.startswith("tests/"))], "passed": 2, "failed": 0},
           "coverage": {"percent": None, "target": "measured in review"},
           "problems": [],
           "seams": ["src/shop/tracking.py: labels every orders.STATUSES entry"]}
    doc.update(extra)
    ws.write(CODE + "/iter-1/" + name, json.dumps(doc))


def _code(ws, leg, orders=ORDERS, tracking=True, integrate=True):
    ws.skill("code")
    if leg:
        ws.skill(leg)
    start = ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1")
    assert start.returncode == 0, start.stderr
    if orders is None:
        return
    # the wave: both partition slices, spawned in one message
    ws.write("src/shop/orders.py", orders)
    ws.write("tests/test_orders.py", "from shop.orders import Order, advance\n")
    _report(ws, "implementer-1.json", ["src/shop/orders.py", "tests/test_orders.py"])
    if tracking:
        ws.write("src/shop/tracking.py", TRACKING)
        ws.write("tests/test_tracking.py", "from shop.tracking import tracking_label\n")
        _report(ws, "implementer-2.json", ["src/shop/tracking.py", "tests/test_tracking.py"])
    if tracking and integrate:
        # then the integration slice, alone, over the seam
        declared = ws.acs("filemap", "set", "--iteration", "1", "--task", "3",
                          "--file", "src/shop/tracking.py",
                          "--file", "tests/test_order_tracking.py")
        assert declared.returncode == 0, declared.stderr
        ws.write("src/shop/tracking.py", SEAMED)
        ws.write("tests/test_order_tracking.py", "from shop.orders import STATUSES\n")
        _report(ws, "implementer-integration.json",
                ["src/shop/tracking.py", "tests/test_order_tracking.py"],
                seams_changed=[{"file": "src/shop/tracking.py",
                                "what": "labels derived against orders.STATUSES",
                                "why": "a status without a label breaks the shopper view",
                                "slices": ["1", "2"]}])
    ws.write(CODE + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 1,
        "summary": "order lifecycle and tracking labels; 2 slices + integration",
        "states": {"files": _written(ws), "tasks_implemented": ["1", "2"],
                   "tests": {"passed": 6, "failed": 0}, "docs_updated": []},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --result-file '%s/result.json'" % (POST_CODE, CODE))


def IDEAL(ws):
    _code(ws, "code-complex")


BAD = {
    "stayed in /acs:code and implemented it without the leg":
        lambda ws: _code(ws, None),
    "dispatched the wrong leg": lambda ws: _code(ws, "code-standard"),
    "fired the leg and did nothing": lambda ws: _code(ws, "code-complex", orders=None),
    "behaved like standard and skipped the integration implementer":
        lambda ws: _code(ws, "code-complex", integrate=False),
    "implemented only the orders partition":
        lambda ws: _code(ws, "code-complex", tracking=False),
    "let orders move backwards": lambda ws: _code(ws, "code-complex", orders=UNGUARDED),
}
