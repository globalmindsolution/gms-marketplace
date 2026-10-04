"""Calibration plays for create-flows-components-enabled (see
tests/evals/check_grader_calibration.py).

The repo, the ticket, the flow and the state machine are
create-flows-order-cancellation's, so the plays reuse that case's
calibration (loaded by path, without bytecode). The difference is the
setting: component-detail and class are enabled, so IDEAL also runs the
`write-components` slice, which writes components/orders.md -- Responsibility,
Internals (a flowchart), Types (a classDiagram), Collaborators -- versioned
like the rest, and records it in states.files and its types in states.types.
"""

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_HERE, "..", "create-flows-order-cancellation", "calibration.py")
_spec = importlib.util.spec_from_file_location("calibration_create_flows_order_cancellation_shared",
                                               _PATH)
flows = importlib.util.module_from_spec(_spec)
_saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
try:
    _spec.loader.exec_module(flows)
finally:
    sys.dont_write_bytecode = _saved

COMPONENT = flows.L + "/orders/components/orders.md"
TYPES = ("sequence", "activity", "state", "component-detail", "class")

INTERNALS = """```mermaid
flowchart TD
  handler["cancel handler"] --> guard{"TRANSITIONS allows cancelled"}
  guard -->|no| refuse["IllegalTransition, 409"]
  guard -->|"yes, paid"| refund["payments.refund"]
  guard -->|"yes, placed"| move["_move to cancelled"]
  refund --> move
```"""

CLASSES = """```mermaid
classDiagram
  class Order {
    +int customer_id
    +list lines
    +str status
    +str payment_id
  }
  class IllegalTransition
  class OrdersModule {
    +place_order(customer_id, lines) Order
    +pay_order(order, token) Order
    +cancel_order(order) Order
  }
  OrdersModule ..> Order : moves
  OrdersModule ..> IllegalTransition : raises
```"""

COMPONENT_DOC = """# Component -- orders

## Responsibility

src/shop/orders.py owns an order and its lifecycle (hld/c4-container.md, shop).

## Internals

%s

## Types

%s

## Collaborators

- payments (src/shop/payments.py): `charge`, `refund`.
""" % (INTERNALS, CLASSES)


def _components(ws, doc=COMPONENT_DOC):
    ws.write(COMPONENT, doc)
    init = ws.acs("design", "init", "--status", "proposed", "--ticket", "EVAL-1",
                  "--feature", "orders", COMPONENT)
    assert init.returncode == 0, init.stderr


def IDEAL(ws):
    flows._start(ws)
    flows._write(ws)
    _components(ws)
    ws.sh('python3 "%s/acs.py" design check %s %s %s'
          % (flows.SCRIPTS, flows.FLOW, flows.STATE, COMPONENT))
    ws.sh('python3 "%s/mermaid_lint.py" %s %s %s'
          % (flows.SCRIPTS, flows.FLOW, flows.STATE, COMPONENT))
    ws.sh('python3 "%s/structure_lint.py" --sections "Responsibility; Internals; Types; '
          'Collaborators" --ordered %s' % (flows.SCRIPTS, COMPONENT))
    flows._review(ws)
    flows._finish(ws, files=flows.FILES + [COMPONENT], types=TYPES)
    ws.reply = ("## /acs:create-flows · EVAL-1 · completed\n\n- **Results**: cancel-order flow, "
                "the order state machine, and components/orders.md (internals and classes: "
                "component-detail and class are enabled) under docs/architecture/lld/orders/, "
                "proposed v1; left as local uncommitted changes for you to review and commit.")


def _skipped_components(ws):
    """Read the default catalog, not the repo's setting: no components doc."""
    flows.IDEAL(ws)


def _no_class_diagram(ws):
    """class is enabled, yet the component doc has no Types classDiagram."""
    flows._start(ws)
    flows._write(ws)
    _components(ws, doc=COMPONENT_DOC.replace("## Types\n\n" + CLASSES + "\n\n", ""))
    flows._review(ws)
    flows._finish(ws, files=flows.FILES + [COMPONENT], types=TYPES)


def _component_unrecorded(ws):
    """Wrote the component doc but left it out of states.files."""
    flows._start(ws)
    flows._write(ws)
    _components(ws)
    flows._review(ws)
    flows._finish(ws, types=TYPES)


def _component_as_code(ws):
    """'Detailed' the component by writing it."""
    IDEAL(ws)
    ws.write("src/shop/cancel.py", "def cancel_order(order):\n    return order\n")


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("create-flows"),
    "skipped the components although enabled": _skipped_components,
    "component doc without the class diagram": _no_class_diagram,
    "component doc left out of states.files": _component_unrecorded,
    "wrote code for the component": _component_as_code,
}
