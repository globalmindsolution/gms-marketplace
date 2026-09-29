"""Plays for code-prompt-subject (see tests/evals/check_grader_calibration.py).

IDEAL is /acs:code's no-plan branch on a prompt subject, through the real
writers: the Skill call's PreToolUse gate (`dispatch.py pre`) resolves the
prompt to a run of its own and `acs.py step start --step code` reads it back; the implicit plan is recorded at that run's steps/code/plan.md
(a coordinator Write -- there is no CLI writer for it); the small leg's one
implementer works test-first on a branch named for the run; result.json; and
`post-code.py`.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
DISPATCH = os.path.join(PLUGIN, "hooks", "scripts", "dispatch.py")
PROMPT = ("Cap the customer page size: list_customers must never use a limit above 100; "
          "a larger limit is clamped to 100.")

PLAN = '''# Plan — cap the customer page size (implicit, from the prompt)

`list_customers` in `src/shop/__init__.py` accepts any `limit`; clamp it to
`MAX_PAGE_SIZE = 100`.

## Test strategy

New `tests/test_page_size_cap.py`, failing first: a limit of 500 comes back
as 100; a limit of 20 is unchanged.

## Contract
delivery_path: small
owes:
  api_contract: false
  test_cases: false
  e2e: false
  reason: "one clamp in one library function"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_page_size_cap.py
'''

CAPPED = '''PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    return {"items": [], "offset": offset, "limit": min(limit, MAX_PAGE_SIZE)}
'''

TEST = '''from shop import list_customers


def test_a_larger_limit_is_clamped_to_100():
    assert list_customers(limit=500)["limit"] == 100
'''


def _gate(ws):
    """The Skill call and its PreToolUse hook, as Claude Code fires it: the gate
    resolves the prompt to a run of its own. `acs.py step start --args` alone
    does not create a prompt run; the hook does."""
    ws.skill("code")
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Skill",
                          "tool_input": {"skill": "acs:code", "args": PROMPT},
                          "session_id": "calibration", "cwd": ws.path})
    ws.write(".calibration-payload.json", payload)
    ws.sh("python3 '%s' pre < .calibration-payload.json && rm .calibration-payload.json"
          % DISPATCH)


def _code(ws, plan=True, source=CAPPED, branch=True, ticket=False):
    _gate(ws)
    if ticket:
        ws.skill("create-ticket")
        ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
               "--title", "Cap the customer page size", "--args", PROMPT)
    start = ws.acs("step", "start", "--step", "code", "--args", PROMPT)
    assert start.returncode == 0, start.stderr
    ctx = json.loads(start.stdout)
    code = os.path.relpath(os.path.join(ctx["partition"], "steps", "code"), ws.path)
    if plan:
        ws.write(code + "/plan.md", PLAN)
    ws.skill("code-small")
    if source is None:
        return
    if branch:
        ws.sh("git checkout -q -b task/%s" % ctx["run_id"])
    ws.write("src/shop/__init__.py", source)
    ws.write("tests/test_page_size_cap.py", TEST)
    ws.sh("git add src/shop/__init__.py tests/test_page_size_cap.py"
          " && git commit -qm 'Cap the customer page size at 100'")
    ws.write(code + "/iter-1/implementer.json", json.dumps({
        "files_changed": ["src/shop/__init__.py", "tests/test_page_size_cap.py"],
        "tests": {"commands": ["python3 -m pytest -q tests/test_page_size_cap.py"],
                  "passed": 1, "failed": 0},
        "coverage": {"percent": None, "target": "measured in review"},
        "commits": ["Cap the customer page size at 100"], "problems": [], "seams": []}))
    ws.write(code + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 1,
        "summary": "limit clamped to 100; 1 targeted test green",
        "states": {"branch": "task/%s" % ctx["run_id"], "tasks_implemented": ["1"],
                   "tests": {"passed": 1, "failed": 0}, "docs_updated": []},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --run '%s' --result-file '%s/result.json'"
          % (POST_CODE, ctx["run_id"], code))


def IDEAL(ws):
    _code(ws)


BAD = {
    "fired and implemented nothing": lambda ws: _code(ws, plan=False, source=None),
    "implemented without recording the implicit plan": lambda ws: _code(ws, plan=False),
    "committed the change on main": lambda ws: _code(ws, branch=False),
    "minted a ticket for the prompt": lambda ws: _code(ws, ticket=True),
}
