"""Calibration plays for create-data-design-physical-disabled (see
tests/evals/check_grader_calibration.py).

The repo, the ticket and the documents are create-data-design-orders', so the
plays reuse that case's calibration (loaded by path, without bytecode). The
one difference is the setting: `physical-schema` is not in
design.lld_types, so IDEAL writes the logical ERD alone, records
`types: ["logical-erd"]`, and names only what it wrote in states.files.
"""

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_HERE, "..", "create-data-design-orders", "calibration.py")
_spec = importlib.util.spec_from_file_location("calibration_create_data_design_orders_shared", _PATH)
orders = importlib.util.module_from_spec(_spec)
_saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
try:
    _spec.loader.exec_module(orders)
finally:
    sys.dont_write_bytecode = _saved

L, ERD, SCHEMA, FEATURE_README = orders.L, orders.ERD, orders.SCHEMA, orders.FEATURE_README
WRITTEN = [L + "/README.md", FEATURE_README, ERD]

REPLY = ("## /acs:create-data-design · EVAL-1 · completed\n\n- **Results**: logical ERD for "
         "orders (CUSTOMER, PRODUCT, ORDER, ORDER_LINE) under docs/architecture/lld/orders/data/, "
         "proposed v1. No physical schema: `physical-schema` is not enabled in "
         "design.lld_types. Documents only, left uncommitted for the publish.\n"
         "- **Next**: /acs:create-flows EVAL-1")


def _logical_only(ws):
    orders._start(ws)
    orders._write_docs(ws, physical=None)
    ws.sh('python3 "%s/acs.py" design check %s' % (orders.SCRIPTS, ERD))
    ws.sh('python3 "%s/mermaid_lint.py" %s' % (orders.SCRIPTS, ERD))
    ws.sh('python3 "%s/structure_lint.py" --sections "Scope; Entities; Relationships; Diagram" '
          '--ordered %s' % (orders.SCRIPTS, ERD))
    orders._review(ws)


def IDEAL(ws):
    _logical_only(ws)
    orders._finish(ws, files=WRITTEN, types=("logical-erd",))
    ws.reply = REPLY


def _wrote_the_disabled_type(ws):
    """Ignored the setting: wrote the physical schema as if it were enabled."""
    orders.IDEAL(ws)


def _claimed_the_disabled_type(ws):
    """Wrote only the ERD but recorded physical-schema among the types written."""
    _logical_only(ws)
    orders._finish(ws, files=WRITTEN, types=("logical-erd", "physical-schema"))


def _wrote_nothing(ws):
    """Read 'physical-schema disabled' as 'no data types enabled' and stopped."""
    ws.skill("create-data-design")
    started = ws.acs("step", "start", "--step", "create-data-design", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    orders._finish(ws, files=[], types=())


def _schema_inside_the_erd(ws):
    """Kept the disabled type's content by folding the tables, indexes and
    migration outline into the logical ERD."""
    orders._start(ws)
    orders._write_docs(ws, logical=orders.LOGICAL + "\n" + orders.PHYSICAL.split("\n", 2)[2],
                       physical=None)
    orders._review(ws)
    orders._finish(ws, files=WRITTEN, types=("logical-erd",))


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("create-data-design"),
    "wrote the physical schema although disabled": _wrote_the_disabled_type,
    "recorded the disabled type as written": _claimed_the_disabled_type,
    "treated it as no data types enabled": _wrote_nothing,
    "folded the physical schema into the ERD": _schema_inside_the_erd,
    "never ran the post-hook": lambda ws: (orders._start(ws), orders._write_docs(ws, physical=None)),
}
