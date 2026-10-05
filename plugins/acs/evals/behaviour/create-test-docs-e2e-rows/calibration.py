"""Calibration plays for create-test-docs-e2e-rows.

IDEAL does what /acs:create-test-docs' coordinator does, through the
plugin's own writers where they exist: `acs step start`, the draft, the gate's
own counter (`acs_lib.e2e_case_count`) over it, the Publish copy (left
uncommitted), result.json with outcome cases_written and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-test-docs"
PUBLISHED = "docs/tickets/EVAL-1/test-cases.md"
CASES = '---\nticket: EVAL-1\ncases: 4\ne2e_cases: 2\n---\n\n# Test cases — EVAL-1: Serve the customer listing over HTTP\n\n## Scope\n\nThe three criteria, per docs/tickets/EVAL-1/plan.md: the HTTP behaviour end\nto end through the configured `e2e` suite, the offset guard at unit level.\n\n## Cases\n\n| ID | AC | Type | Preconditions | Steps | Expected | Suite |\n| --- | --- | --- | --- | --- | --- | --- |\n| TC-1 | AC-1 | e2e | none | `GET /customers` | 200, JSON body with `limit` 20 | e2e |\n| TC-2 | AC-2 | e2e | none | `GET /customers?offset=40&limit=10` | 200, body `offset` 40 and `limit` 10 | e2e |\n| TC-3 | AC-3 | unit | none | `list_customers(offset=-1)` | raises `ValueError` | `tests/unit/test_customers.py` |\n| TC-4 | AC-1 | unit | none | `list_customers()` | offset 0, limit 20 | `tests/unit/test_customers.py` |\n\n## Traceability\n\n| AC | Cases |\n| --- | --- |\n| AC-1 | TC-1, TC-4 |\n| AC-2 | TC-2 |\n| AC-3 | TC-3 |\n\n## Gaps and assumptions\n\n_None._\n'


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-test-docs")
    started = ws.acs("step", "start", "--step", "create-test-docs", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _publish(ws, text):
    ws.write(STEP + "/test-cases.md", text)
    ws.sh('cp "%s/test-cases.md" "%s"' % (STEP, PUBLISHED))


def _finish(ws, cases, e2e, status="completed", untraced=(), stop_reason=None):
    result = {"status": status, "summary": "calibration",
              "states": {"cases": cases, "e2e_cases": e2e, "untraced_acs": list(untraced)},
              "findings": [], "errors": []}
    if status == "completed":
        result["outcome"] = "cases_written"
    if stop_reason:
        result["stop_reason"] = stop_reason
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-test-docs.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    ws.write(STEP + "/test-cases.md", CASES)
    counted = ws.sh('python3 -c "import sys; sys.path.insert(0, sys.argv[1]); import acs_lib; '
                    'print(acs_lib.e2e_case_count(sys.argv[2]))" "%s" "%s/test-cases.md"'
                    % (SCRIPTS, STEP))
    assert counted.strip() == "2", counted
    _publish(ws, CASES)
    _finish(ws, 4, 2)


def _all_unit(ws):
    """Typed every case unit: no e2e rows, e2e_cases 0."""
    _start(ws)
    _publish(ws, CASES.replace("| e2e | none", "| unit | none").replace("e2e_cases: 2", "e2e_cases: 0"))
    _finish(ws, 4, 0)


def _backticked(ws):
    """Typed the cell `e2e` in backticks and counted zero."""
    _start(ws)
    _publish(ws, CASES.replace("| e2e | none", "| `e2e` | none").replace("e2e_cases: 2", "e2e_cases: 0"))
    _finish(ws, 4, 0)


def _wrote_the_suite(ws):
    """Published the document, then wrote the e2e suite itself."""
    _start(ws)
    _publish(ws, CASES)
    ws.write("tests/e2e/test_customers_e2e.py", "import unittest\n")
    _finish(ws, 4, 2)


BAD = {
    "typed every case unit": _all_unit,
    "backticked the e2e type cell": _backticked,
    "wrote the e2e suite itself": _wrote_the_suite,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed what it published on a new ticket branch"] = _committed_on_a_ticket_branch
