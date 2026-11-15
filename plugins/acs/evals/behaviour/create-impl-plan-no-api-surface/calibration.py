"""Calibration plays for create-impl-plan-no-api-surface.

IDEAL does what /acs:create-impl-plan's coordinator does, through the
plugin's own writers: `acs step start`, the planner's draft in the step
directory, the Publish copy left uncommitted on main (ADR-0127), `acs.py filemap set`, then result.json and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-impl-plan"
PUBLISHED = "docs/development/customer-listing/EVAL-1/plan.md"
FILES = ["src/shop/__init__.py", "tests/test_slow_listing_log.py"]
PLAN = '# Plan — EVAL-1: Log slow customer listings\n\nPlanned from docs/development/customer-listing/EVAL-1/analysis.md.\n\n## Approach\n\nWrap the body of `list_customers` in `src/shop/__init__.py` with\n`time.perf_counter()`; above `SLOW_LISTING_MS = 200` log one WARNING on\n`logging.getLogger("shop")` naming offset, limit and elapsed ms. The return\nvalue and signature do not change.\n\n## Tests\n\n| AC | Test (tests/test_slow_listing_log.py) |\n|---|---|\n| AC-1 | a patched 250 ms call logs exactly one WARNING on `shop` |\n| AC-2 | that warning names offset, limit and 250 |\n| AC-3 | a patched 200 ms call logs nothing |\n\nRun `python3 -m pytest -q --cov=src --cov-fail-under=90`; coverage target 90%.\n\n## Documentation\n\ndocs/product/prd.md and docs/product/roadmap.md make no claim this changes.\n\n## Contract\ndelivery_path: trivial\nowes:\n  test_cases: true\n  e2e: false\n  reason: "Operator log line only: GET /customers keeps its parameters, response and errors"\n\n### Executor tasks & file map\n- task 1: src/shop/__init__.py, tests/test_slow_listing_log.py\n'


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
    ws.sh('mkdir -p docs/development/customer-listing/EVAL-1 && cp "%s/plan.md" "%s"' % (STEP, PUBLISHED))


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
    _start(ws)
    _publish(ws, PLAN)
    _finish(ws, file_map=_declare(ws, FILES))


def _owes_a_contract(ws):
    """Owed the retired API contract step for an operator log line."""
    _start(ws)
    _publish(ws, PLAN.replace("owes:\n", "owes:\n  api_contract: true\n"))
    _finish(ws, file_map=_declare(ws, FILES))


def _silent_owes(ws):
    """A Contract block with no owes table: silence, which is not a no."""
    _start(ws)
    head, tail = PLAN.split("owes:", 1)
    _publish(ws, head + "### Executor tasks & file map" + tail.split("### Executor tasks & file map", 1)[1])
    _finish(ws, file_map=_declare(ws, FILES))


def _started_only(ws):
    _start(ws)


BAD = {
    "owed the retired API contract step for a log line": _owes_a_contract,
    "left owes out of the Contract block": _silent_owes,
    "fired the skill, started the step, wrote nothing": _started_only,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed what it published on a new ticket branch"] = _committed_on_a_ticket_branch
