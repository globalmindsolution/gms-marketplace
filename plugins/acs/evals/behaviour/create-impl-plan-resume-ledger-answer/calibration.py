"""Calibration plays for create-impl-plan-resume-ledger-answer.

IDEAL does what a resumed /acs:create-impl-plan does, through the plugin's
own writers: `acs step start` (reconcile, handoff summary), `clarify.py
list` (C-5 answers the planner's question), the draft with the codec in its
own module, the Publish copy (uncommitted), `acs.py filemap set`, result.json and
the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-impl-plan"
PUBLISHED = "docs/tickets/EVAL-1/plan.md"
FILES = ["src/shop/cursor.py", "src/shop/__init__.py", "tests/test_cursor.py",
         "tests/test_customers.py", "README.md"]
PLAN = '# Plan — EVAL-1: Cursor pagination for GET /customers\n\nPlanned from docs/tickets/EVAL-1/analysis.md and C-5.\n\n## Approach\n\nPer C-5 the cursor codec lives in a new module, `src/shop/cursor.py`\n(`encode(last_id)`, `decode(cursor)` raising `InvalidCursor`);\n`list_customers` in `src/shop/__init__.py` imports it, accepts `cursor` and\nreturns `next_cursor`. `offset` keeps working; `limit` defaults to 20, max 100.\n\n## Tests\n\n| AC | Test |\n|---|---|\n| AC-1 | tests/test_customers.py: a cursor returns the following page |\n| AC-2 | tests/test_customers.py: `next_cursor` null on the last page |\n| AC-3 | tests/test_cursor.py: a malformed cursor raises `InvalidCursor` -> 400 `invalid_cursor` |\n\nRun `python3 -m pytest -q --cov=src --cov-fail-under=90`; coverage target 90%.\n\n## Contract\ndelivery_path: small\nowes:\n  api_contract: true\n  test_cases: true\n  e2e: false\n  reason: "GET /customers gains a query parameter, a response field and an error code"\n\n### Executor tasks & file map\n- task 1: src/shop/cursor.py, src/shop/__init__.py, tests/test_cursor.py, tests/test_customers.py, README.md\n'


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-impl-plan")
    started = ws.acs("step", "start", "--step", "create-impl-plan", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    return json.loads(started.stdout)


def _publish(ws, text):
    ws.write(STEP + "/plan.md", text)
    ws.sh('mkdir -p docs/tickets/EVAL-1 && cp "%s/plan.md" "%s"' % (STEP, PUBLISHED))


def _declare(ws, files):
    declared = ws.acs("filemap", "set", "--skill", "code", "--iteration", "1", "--task", "1",
                      *[arg for path in files for arg in ("--file", path)])
    assert declared.returncode == 0, declared.stderr
    return json.loads(declared.stdout)["tasks"]


def _finish(ws, status="completed", file_map=None, published=True, summary="calibration"):
    states = {"plan_approved": False, "file_map": file_map or {}}
    if published:
        states["plan_path"] = PUBLISHED
    result = {"status": status, "summary": summary, "states": states,
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-impl-plan.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def IDEAL(ws):
    context = _start(ws)
    assert context["reconcile"] is True
    ws.sh('python3 "%s/clarify.py" list --ticket EVAL-1 > /dev/null' % SCRIPTS)
    _publish(ws, PLAN)
    _finish(ws, file_map=_declare(ws, FILES))


def _planned_from_scratch(ws):
    """Ignored C-5: put the codec in __init__.py and asked again."""
    _start(ws)
    ws.sh('python3 "%s/clarify.py" add --skill create-impl-plan --ticket EVAL-1 '
          '--question "Where does the cursor codec live?" --answer "src/shop/__init__.py" '
          '--source assumption --rationale "simplest" > /dev/null' % SCRIPTS)
    plain = PLAN.replace("src/shop/cursor.py, ", "").replace("`src/shop/cursor.py`", "`src/shop/__init__.py`")
    _publish(ws, plain)
    _finish(ws, file_map=_declare(ws, [f for f in FILES if f != "src/shop/cursor.py"]))


def _started_only(ws):
    _start(ws)


BAD = {
    "planned from scratch, ignoring the ledger": _planned_from_scratch,
    "reconciled, then wrote nothing": _started_only,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed what it published on a new ticket branch"] = _committed_on_a_ticket_branch
