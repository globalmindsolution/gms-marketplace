"""Calibration plays for create-impl-plan-cursor-pagination.

IDEAL does what /acs:create-impl-plan's coordinator does, through the
plugin's own writers where they exist: `acs step start`, the planner's draft
in the step directory, `acs.py filemap set` for the one executor task, the
Publish copy into docs/development/customer-listing/EVAL-1/ left uncommitted on main (ADR-0127: no
branch, no commit), then result.json and the post-hook. The planner's and
plan reviewer's own phase files are workspace detail no grader reads.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-impl-plan"
PUBLISHED = "docs/development/customer-listing/EVAL-1/plan.md"
FILES = ["src/shop/__init__.py", "tests/test_customers.py", "README.md"]

PLAN = """# Plan — EVAL-1: Cursor pagination for GET /customers

Planned from docs/development/customer-listing/EVAL-1/analysis.md (ready for planning), the ticket's three acceptance criteria and the approved API contract,
docs/architecture/lld/customer-listing/api/customers.md (via EVAL-1/api-contract.md): its shapes and error codes are binding.

## Approach

`list_customers` in `src/shop/__init__.py` gains a keyword-only `cursor`
argument. The cursor is the URL-safe base64 of the last customer id on the
page; decoding failure raises `InvalidCursor`, which the handler maps to
HTTP 400 with error code `invalid_cursor`. Every response carries
`next_cursor` (null on the last page). `offset` keeps working, deprecated;
when both are given, `cursor` wins. `limit` defaults to 20, capped at 100.

Rejected: a signed cursor (HMAC). Nothing in the repo holds a secret today,
and tampering is already caught as a malformed or unknown id.

Not done here: removing `offset`, or paging any other endpoint.

## Tests

| AC | Test (tests/test_customers.py) |
|---|---|
| AC-1 | a cursor returns the page after the customer it encodes |
| AC-2 | `next_cursor` is set mid-list and null on the last page |
| AC-3 | a malformed cursor raises `InvalidCursor` -> 400 `invalid_cursor` |

Run `python3 -m pytest -q --cov=src --cov-fail-under=90`; the coverage target
is 90%.

## Documentation

README.md's API section documents `cursor` and `next_cursor`.
docs/product/prd.md and docs/product/roadmap.md make no claim this changes.

## Risks

GET /customers is a public API: `offset` clients must keep working.

## Contract
delivery_path: small
owes:
  test_cases: true
  e2e: false
  reason: "GET /customers gains a query parameter, a response field and an error code; no browser flow"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_customers.py, README.md
"""


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-impl-plan")
    started = ws.acs("step", "start", "--step", "create-impl-plan", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws, file_map):
    result = {"status": "completed", "summary": "calibration",
              "states": {"plan_path": PUBLISHED, "plan_approved": False, "file_map": file_map},
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-impl-plan.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def _publish(ws, text):
    ws.write(STEP + "/plan.md", text)
    ws.sh('mkdir -p "%s" && cp "%s/plan.md" "%s"' % (os.path.dirname(PUBLISHED), STEP, PUBLISHED))


def IDEAL(ws):
    _start(ws)
    _publish(ws, PLAN)
    declared = ws.acs("filemap", "set", "--skill", "code", "--iteration", "1", "--task", "1",
                      *[arg for path in FILES for arg in ("--file", path)])
    assert declared.returncode == 0, declared.stderr
    _finish(ws, json.loads(declared.stdout)["tasks"])


def _started_only(ws):
    _start(ws)


def _template_plan_no_contract(ws):
    """Published a free-form plan with no Contract block, never declared the
    file map, and never finished the step."""
    _start(ws)
    _publish(ws, PLAN.split("## Contract")[0])


def _owes_the_retired_contract_step(ws):
    """Did everything, but owed the API contract as a step -- a key ADR-0134
    retired: the contract is a Design input the plan reads."""
    _start(ws)
    _publish(ws, PLAN.replace("owes:\n", "owes:\n  api_contract: true\n"))
    declared = ws.acs("filemap", "set", "--skill", "code", "--iteration", "1", "--task", "1",
                      *[arg for path in FILES for arg in ("--file", path)])
    _finish(ws, json.loads(declared.stdout)["tasks"])


def _ignored_the_contract(ws):
    """Planned from the analysis alone, never naming the approved contract."""
    _start(ws)
    _publish(ws, PLAN.replace(
        ", the ticket's three acceptance criteria and the approved API contract,\n"
        "docs/architecture/lld/customer-listing/api/customers.md (via EVAL-1/api-contract.md): "
        "its shapes and error codes are binding.", " and the ticket's three acceptance criteria."))
    declared = ws.acs("filemap", "set", "--skill", "code", "--iteration", "1", "--task", "1",
                      *[arg for path in FILES for arg in ("--file", path)])
    _finish(ws, json.loads(declared.stdout)["tasks"])


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "a plan without the Contract block, map undeclared": _template_plan_no_contract,
    "owed the retired api_contract step": _owes_the_retired_contract_step,
    "planned without reading the approved contract": _ignored_the_contract,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed what it published on a new ticket branch"] = _committed_on_a_ticket_branch
