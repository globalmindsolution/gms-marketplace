"""Calibration plays for create-test-docs-cursor-pagination.

IDEAL does what /acs:create-test-docs' coordinator does, through the plugin's
own writers where they exist: `acs step start`, the test-designer's draft in
the step directory, the Publish copy into docs/development/customer-listing/EVAL-1/ left uncommitted
on main (ADR-0127: no branch, no commit), then result.json with outcome
cases_written and the post-hook.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-test-docs"
PUBLISHED = "docs/development/customer-listing/EVAL-1/test-cases.md"

CASES = r"""---
ticket: EVAL-1
cases: 4
e2e_cases: 0
---

# Test cases — EVAL-1: Cursor pagination for GET /customers

## Scope

The three acceptance criteria and the one contract item (GET /customers) in
docs/architecture/lld/customer-listing/EVAL-1/api-contract.md, at unit level in tests/ with pytest, as
docs/development/customer-listing/EVAL-1/plan.md plans. The plan owes no e2e.

## Cases

| ID | AC | Type | Preconditions | Steps | Expected | Suite |
| --- | --- | --- | --- | --- | --- | --- |
| TC-1 | AC-1 | unit | 45 customers | take `next_cursor` of page 1, request with it | page 2 starts after the last id of page 1 | `tests/test_customers.py` |
| TC-2 | AC-2 | unit | 45 customers | walk every page with `limit=20` | `next_cursor` set on pages 1-2, `null` on page 3 | `tests/test_customers.py` |
| TC-3 | AC-3 | unit | none | request with `cursor=%%%` | 400 with error code `invalid_cursor` | `tests/test_customers.py` |
| TC-4 | AC-1 | unit | 45 customers | request with both `offset=5` and a cursor | the cursor wins; `offset` is ignored | `tests/test_customers.py` |

## Traceability

| AC | Cases |
| --- | --- |
| AC-1 | TC-1, TC-4 |
| AC-2 | TC-2 |
| AC-3 | TC-3 |

## Gaps and assumptions

_None._
"""


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-test-docs")
    started = ws.acs("step", "start", "--step", "create-test-docs", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws, cases, untraced=()):
    result = {"status": "completed", "outcome": "cases_written", "summary": "calibration",
              "states": {"cases": cases, "e2e_cases": 0, "untraced_acs": list(untraced)},
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-test-docs.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def _publish(ws, text):
    ws.write(STEP + "/test-cases.md", text)
    ws.sh('mkdir -p "%s" && cp "%s/test-cases.md" "%s"' % (os.path.dirname(PUBLISHED), STEP, PUBLISHED))


def IDEAL(ws):
    _start(ws)
    _publish(ws, CASES)
    _finish(ws, 4)


def _started_only(ws):
    _start(ws)


def _dropped_a_criterion(ws):
    """Published a table that never traces AC-3 and has no invalid_cursor case."""
    _start(ws)
    rows = [line for line in CASES.splitlines() if not line.startswith("| TC-3 ")]
    _publish(ws, "\n".join(rows).replace("cases: 4", "cases: 3") + "\n")
    _finish(ws, 3)


def _wrote_the_tests(ws):
    """Published the document, then wrote the test code itself."""
    _start(ws)
    _publish(ws, CASES)
    ws.write("tests/test_customers.py", "def test_cursor():\n    assert True\n")
    _finish(ws, 4)


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "left AC-3 untraced": _dropped_a_criterion,
    "wrote the tests itself": _wrote_the_tests,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed what it published on a new ticket branch"] = _committed_on_a_ticket_branch
