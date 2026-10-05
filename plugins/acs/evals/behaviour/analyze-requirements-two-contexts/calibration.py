"""Calibration plays for analyze-requirements-two-contexts.

IDEAL does what /acs:analyze-requirements' coordinator does on a change that
spans two bounded contexts (ADR-0133), through the plugin's own writers where
they exist: `acs step start`, `clarify.py add` for each answer the prompt
relayed, the draft FOLDER in the step directory -- a README with its contexts
table and one file per context, order cancellation and payment refunds -- the
Publish copy of every file into the run's Development folder left uncommitted
on main (ADR-0127), then result.json with `files` and the post-hook. The
analyst's and impact reviewer's phase files are workspace detail no grader
reads, so only the draft is played.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
DRAFT = STEP + "/iter-1/analysis"
PUBLISHED = "docs/development/checkout-with-card-payments/EVAL-1/analysis"

README = """---
ticket: EVAL-1
ready_for_planning: true
api_surface: false
needs_design_recommendation: false
---

# Analysis — EVAL-1: Refund the card when a paid order is cancelled

## Scope and summary

Cancelling an unshipped paid order should refund its card charge in full,
automatically; today support refunds by hand. Shipped orders still cannot be
cancelled. No HTTP endpoint changes.

## Contexts

| Context | File | Purpose |
|---|---|---|
| Order cancellation | [order-cancellation.md](order-cancellation.md) | when an order may be cancelled, and what cancelling records |
| Payment refunds | [payment-refunds.md](payment-refunds.md) | how a card charge is refunded through the gateway |

## Refined acceptance criteria

- AC-1 testable — lands in both contexts.
- AC-2 testable — order cancellation.
- AC-3 testable — both contexts: the refund fails, the cancellation stands.

## Cross-cutting risks and decisions

- Cancellation now calls the payments gateway synchronously: a slow gateway
  slows cancelling (see [payment-refunds.md](payment-refunds.md)).

## Questions and assumptions

- C-1 refund amount — answered: always the full charge.
- C-2 refund timing — answered: synchronously, on cancel, same gateway.
- C-3 declined refund — answered: order stays cancelled, failure recorded.
- C-4 HTTP surface — answered: unchanged.

Assumptions: none.

## Verdict

Ready for planning; api_surface false; no design needed.
"""

CANCELLATION = """---
context: order-cancellation
---

# Order cancellation

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/orders.py | orders | `cancel_order` requests the refund and records a failed one | src/shop/orders.py:8 |
| tests/test_orders.py | tests | new cases for cancel-with-refund | new |

## Rules and edge cases

- Only an unshipped order can be cancelled (src/shop/orders.py:10).

## Risks

- A declined refund must not undo the cancellation.

## Open questions

_None._

## API notes

_None._ The refund itself is [payment-refunds.md](payment-refunds.md).
"""

REFUNDS = """---
context: payment-refunds
---

# Payment refunds

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/payments.py | payments | new `refund(charge_id)` beside `charge` | src/shop/payments.py:1 |
| tests/test_payments.py | tests | new cases for refund and decline | new |

## Rules and edge cases

- A refund is always for the full charge.

## Risks

- Payments are load-bearing: a refund moves money (src/shop/payments.py).

## Open questions

_None._

## API notes

_None._
"""

ANALYSIS = {"README.md": README, "order-cancellation.md": CANCELLATION,
            "payment-refunds.md": REFUNDS}

ANSWERS = [
    ("How much is refunded?", "Always the full charge"),
    ("When and how is the refund requested?", "Synchronously on cancel, same gateway"),
    ("What if the gateway declines the refund?", "Order stays cancelled; failure recorded"),
    ("Does any HTTP endpoint change?", "No"),
]


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("analyze-requirements")
    started = ws.acs("step", "start", "--step", "analyze-requirements", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    shown = ws.acs("artifacts", "show")
    assert shown.returncode == 0, shown.stderr
    target = json.loads(shown.stdout)["paths"]["analysis.md"]
    assert target.replace(os.sep, "/").endswith(PUBLISHED + "/README.md"), target
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill analyze-requirements --ticket EVAL-1 '
              '--question "%s" --answer "%s" > /dev/null' % (SCRIPTS, question, answer))


def _publish(ws, files, target=PUBLISHED):
    """The draft folder, then the Publish copy of every file (ADR-0133)."""
    for name, text in files.items():
        ws.write(DRAFT + "/" + name, text)
    ws.sh('mkdir -p "%s" && cp "%s"/*.md "%s"/' % (target, DRAFT, target))


def _finish(ws):
    result = {"status": "completed", "summary": "calibration",
              "states": {"ready_for_planning": True, "api_surface": False,
                         "questions_open": 0, "files": _written(ws)},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    _publish(ws, ANALYSIS)
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _one_long_file(ws):
    """The pre-ADR-0133 shape: one analysis.md beside where the folder goes."""
    _start(ws)
    text = README + CANCELLATION.split("---\n", 2)[2] + REFUNDS.split("---\n", 2)[2]
    ws.write(STEP + "/analysis.md", text)
    ws.sh('mkdir -p "%s" && cp "%s/analysis.md" "%s.md"'
          % (os.path.dirname(PUBLISHED), STEP, PUBLISHED))
    _finish(ws)


def _one_context_for_both(ws):
    """Lumped both contexts into one file: the split by bounded context lost."""
    _start(ws)
    merged = CANCELLATION + REFUNDS.split("---\n", 2)[2]
    readme = README.replace(
        "| Payment refunds | [payment-refunds.md](payment-refunds.md) | how a card charge "
        "is refunded through the gateway |\n", "")
    _publish(ws, {"README.md": readme, "order-cancellation.md": merged})
    _finish(ws)


def _index_instead_of_readme(ws):
    """Named the entry file index.md, which a forge does not render."""
    _start(ws)
    files = dict(ANALYSIS)
    files["index.md"] = files.pop("README.md")
    _publish(ws, files)
    _finish(ws)


def _context_left_out_of_the_table(ws):
    """Wrote both context files but linked only one from the README."""
    _start(ws)
    _publish(ws, dict(ANALYSIS, **{"README.md": README.replace(
        "[payment-refunds.md](payment-refunds.md)", "payment refunds")}))
    _finish(ws)


def _committed(ws):
    IDEAL(ws)
    ws.sh("git add docs && git commit -qm 'EVAL-1 analysis'")


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "published one long analysis.md": _one_long_file,
    "one context file holding both contexts": _one_context_for_both,
    "an index.md in place of the README": _index_instead_of_readme,
    "a context file left out of the README's table": _context_left_out_of_the_table,
    "committed the analysis": _committed,
}
