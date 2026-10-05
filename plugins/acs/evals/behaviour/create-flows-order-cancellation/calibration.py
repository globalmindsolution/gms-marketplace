"""Calibration plays for create-flows-order-cancellation (see
tests/evals/check_grader_calibration.py).

IDEAL does what /acs:create-flows' coordinator and its subagents do, through
the plugin's own writers where they exist: `acs step start`, the
`clarify.py add` answers the prompt relayed, one un-sliced survey whose State
machine inventory pins the transitions the flow implies (no feature `flows/`
documents yet, so no gap analysis), the two write slices -- `write-cancel-order`
(the flow, with the README files) and `write-states` (the order's state
machine) -- each file versioned through `acs.py design init --status
proposed`, no seam reported so no integration pass, the three reviewer slices
joined with `acs.py notes merge`, the $0 checks, then result.json with every
written path in states.files and the real post-hook. component-detail and
class are off by default, so nothing is written under components/.
"""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-flows"
L = "docs/architecture/lld"
FLOW = L + "/orders/flows/cancel-order.md"
STATE = L + "/orders/flows/state-order.md"
FEATURE_README = L + "/orders/README.md"

SEQUENCE = """```mermaid
sequenceDiagram
  actor Shopper
  participant Orders as shop orders
  participant Gateway as Payments gateway
  Shopper->>Orders: POST /orders/{id}/cancel
  alt order is placed
    Orders->>Orders: cancel_order marks it cancelled
    Orders-->>Shopper: 200 cancelled
  else order is paid
    Orders->>Gateway: refund(payment_id)
    Gateway-->>Orders: refunded
    Orders->>Orders: cancel_order marks it cancelled
    Orders-->>Shopper: 200 cancelled
  else order is shipped or delivered
    Orders-->>Shopper: 409 order_not_cancellable
  end
```"""

FLOW_DOC = """# Flow -- cancel order

## Purpose

A shopper cancels an order until it ships (EVAL-1, all three criteria); a
paid order is refunded through the payments gateway first.

## Trigger

`POST /orders/{id}/cancel` from the shopper (planned).

## Participants

- Shopper
- shop orders (src/shop/orders.py)
- Payments gateway (hld/c4-container.md; src/shop/payments.py `refund`)

## Sequence

%s

## Activity

```mermaid
flowchart TD
  start["POST /orders/{id}/cancel"] --> status{"order status"}
  status -->|placed| cancel["mark cancelled"]
  status -->|paid| refund["refund through the gateway"]
  refund -->|refunded| cancel
  refund -->|declined| failed["502 refund_failed, order stays paid"]
  status -->|"shipped or delivered"| refuse["409 order_not_cancellable"]
  cancel --> ok["200 cancelled"]
```

## Errors and edge cases

- Shipped or delivered: 409 `order_not_cancellable`, nothing changes.
- The gateway declines the refund: 502 `refund_failed`, the order stays paid.
- Cancelling a cancelled order: 409 `order_not_cancellable`.
""" % SEQUENCE

STATE_DIAGRAM = """```mermaid
stateDiagram-v2
  [*] --> placed : POST /orders
  placed --> paid : POST /orders/{id}/pay
  paid --> shipped : parcel left
  shipped --> delivered : parcel arrived
  placed --> cancelled : POST /orders/{id}/cancel
  paid --> cancelled : POST /orders/{id}/cancel after refund
  delivered --> [*]
  cancelled --> [*]
  classDef planned stroke-dasharray: 5 5
  class cancelled planned
```"""

STATE_DOC = """# State machine -- order

## Entity

ORDER (hld/data-model.md); its `status` is moved by src/shop/orders.py:5
`TRANSITIONS`.

## States

placed, paid, shipped, delivered (built); cancelled (planned).

## Transitions

%s

| From | To | Trigger |
|---|---|---|
| placed | cancelled (planned) | POST /orders/{id}/cancel |
| paid | cancelled (planned) | POST /orders/{id}/cancel, after the refund |

## Invariants

- A shipped or delivered order is never cancelled.
- A paid order is cancelled only after its refund succeeded.
""" % STATE_DIAGRAM

README = """# orders

PRD feature F4 (Orders). HLD containers: shop, Payments gateway.

| Ticket | Change |
|---|---|
| EVAL-1 | cancel-order flow; order state machine |
"""

ANSWERS = [
    ("How many flows?", "One, cancel-order, covering placed, paid and shipped orders"),
    ("What happens when the gateway declines the refund?", "502 refund_failed; the order stays paid"),
]
FILES = [L + "/README.md", FEATURE_README, FLOW, STATE]


def _start(ws):
    ws.skill("create-flows")
    started = ws.acs("step", "start", "--step", "create-flows", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    ws.sh("mkdir -p %s && git status --porcelain > %s/baseline-status.txt" % (STEP, STEP))
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill create-flows --ticket EVAL-1 '
              '--question "%s" --answer "%s"' % (SCRIPTS, question, answer))
    ws.write(STEP + "/iter-1/authoring.md",
             "## Flow inventory\n\ncancel-order (planned), group cancel-order.\n\n"
             "## State machine inventory\n\nORDER (src/shop/orders.py:5): placed -> cancelled, "
             "paid -> cancelled on POST /orders/{id}/cancel.\n\n## Vocabulary\n\nshop, "
             "Payments gateway (hld/c4-container.md).\n\n## Reviewer checklist\n\n"
             "- every status change in the sequence is a transition\n")


def _write(ws, flow=FLOW_DOC, state=STATE_DOC, version=True):
    ws.write(FLOW, flow)
    ws.write(FEATURE_README, README)
    ws.write(L + "/README.md", "| orders | F4 Orders | [orders/](orders/) |\n", append=True)
    ws.write(STEP + "/iter-1/designer-write-cancel-order.json",
             json.dumps({"files_changed": [FLOW, FEATURE_README, L + "/README.md"], "seams": []}))
    ws.write(STATE, state)
    ws.write(STEP + "/iter-1/designer-write-states.json",
             json.dumps({"files_changed": [STATE], "seams": []}))
    if version:
        init = ws.acs("design", "init", "--status", "proposed", "--ticket", "EVAL-1",
                      "--feature", "orders", FLOW, STATE)
        assert init.returncode == 0, init.stderr


def _review(ws):
    slices = ("agreement", "references", "form")
    for slice_id in slices:
        ws.write("%s/iter-1/reviewer-%s.md" % (STEP, slice_id),
                 "## Findings\n\nnone (slice %s)\n" % slice_id)
    merged = ws.acs("notes", "merge", "--out", STEP + "/iter-1/reviewer.md",
                    *["%s/iter-1/reviewer-%s.md" % (STEP, s) for s in slices])
    assert merged.returncode == 0, merged.stderr


def _finish(ws, files=None, types=("sequence", "activity", "state")):
    result = {"status": "completed",
              "summary": "1 flow and 1 state machine for orders; review passed on iteration 1",
              "states": {"feature": ["orders"], "files": FILES if files is None else files,
                         "types": list(types),
                         "gaps": {"undocumented": 0, "unimplemented": 0, "drifted": 0},
                         "flows": 1, "state_machines": 1},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result, indent=2))
    done = subprocess.run([sys.executable, os.path.join(SCRIPTS, "post-create-flows.py"),
                           "--result-file", STEP + "/result.json"],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    _write(ws)
    ws.sh('python3 "%s/acs.py" design check %s %s' % (SCRIPTS, FLOW, STATE))
    ws.sh('python3 "%s/mermaid_lint.py" %s %s' % (SCRIPTS, FLOW, STATE))
    ws.sh('python3 "%s/structure_lint.py" --sections "Purpose; Trigger; Participants; Sequence; '
          'Activity; Errors and edge cases" --ordered %s' % (SCRIPTS, FLOW))
    ws.sh('python3 "%s/structure_lint.py" --sections "Entity; States; Transitions; Invariants" '
          '--ordered %s' % (SCRIPTS, STATE))
    _review(ws)
    _finish(ws)
    ws.reply = ("## /acs:create-flows · EVAL-1 · completed\n\n- **Results**: "
                "docs/architecture/lld/orders/flows/cancel-order.md (sequence and activity) and "
                "flows/state-order.md (placed -> cancelled and paid -> cancelled added, planned), "
                "both proposed v1; no components (not enabled); left as local uncommitted "
                "changes for you to review and commit.\n- **Findings**: info -- no lld/orders/api/ or data/ documents yet.\n"
                "- **Next**: /acs:analyze-requirements EVAL-1")


def _wrote_components(ws):
    """component-detail and class are off -- and a component doc was written."""
    IDEAL(ws)
    ws.write(L + "/orders/components/orders-service.md",
             "# orders service\n\n## Responsibility\n\nOrders.\n")


def _state_machine_missing_the_cancel(ws):
    """Copied the code's lifecycle into the state machine: the flow's cancel
    messages change the order's state, and no transition shows it."""
    built_only = "\n".join(line for line in STATE_DOC.split("\n")
                           if "cancelled" not in line)
    _start(ws)
    _write(ws, state=built_only)
    _review(ws)
    _finish(ws)


def _shipped_orders_cancellable(ws):
    """Drew a transition the criteria forbid."""
    _start(ws)
    _write(ws, state=STATE_DOC.replace("  delivered --> [*]",
                                       "  shipped --> cancelled : POST /orders/{id}/cancel\n"
                                       "  delivered --> [*]"))
    _review(ws)
    _finish(ws)


def _sequence_without_the_refund(ws):
    """The flow skips the gateway: a paid order is cancelled with no refund."""
    _start(ws)
    _write(ws, flow=FLOW_DOC.replace("    Orders->>Gateway: refund(payment_id)\n"
                                     "    Gateway-->>Orders: refunded\n", ""))
    _review(ws)
    _finish(ws)


def _no_front_matter(ws):
    _start(ws)
    _write(ws, version=False)
    _review(ws)
    _finish(ws)


def _wrote_code(ws):
    """Implemented the cancel endpoint instead of designing it."""
    IDEAL(ws)
    ws.write("src/shop/cancel.py", "def cancel_order(order):\n    order['status'] = 'cancelled'\n")


def _recorded_no_files(ws):
    _start(ws)
    _write(ws)
    _review(ws)
    _finish(ws, files=[])


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("create-flows"),
    "wrote components although not enabled": _wrote_components,
    "state machine misses the transitions the sequence implies": _state_machine_missing_the_cancel,
    "state machine lets a shipped order be cancelled": _shipped_orders_cancellable,
    "sequence cancels a paid order without the refund": _sequence_without_the_refund,
    "no version front matter": _no_front_matter,
    "wrote code": _wrote_code,
    "states.files left empty": _recorded_no_files,
    "never ran the post-hook": lambda ws: (_start(ws), _write(ws)),
}
