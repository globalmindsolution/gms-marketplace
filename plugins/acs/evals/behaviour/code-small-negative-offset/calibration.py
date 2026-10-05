"""Plays for code-small-negative-offset (see
tests/evals/check_grader_calibration.py).

IDEAL is what the code-small leg does on this plan, through its real writers:
`acs.py step start --step code`, the implementer's TDD edits left uncommitted
(ADR-0127), its report at steps/code/iter-1/implementer.json, the leg's
result.json, and `post-code.py`.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
CODE = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/code"

GUARDED = '''PAGE_SIZE = 20


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    # a negative offset is a caller bug, never a page
    if offset < 0:
        raise ValueError("offset must be >= 0")
    return {"items": [], "offset": offset, "limit": limit}
'''

CLAMPED = GUARDED.replace(
    '    if offset < 0:\n        raise ValueError("offset must be >= 0")\n',
    '    offset = max(offset, 0)\n')

TEST = '''import pytest

from shop import list_customers


def test_a_negative_offset_is_refused():
    with pytest.raises(ValueError):
        list_customers(offset=-1)


def test_offset_zero_is_the_first_page():
    assert list_customers(offset=0) == {"items": [], "offset": 0, "limit": 20}
'''


def _written(ws):
    """`states.files`: every repo path the run left uncommitted for /acs:create-pr
    (ADR-0127) -- the scaffold's own uncommitted ticket docs aside."""
    out = ws.sh("git status --porcelain --untracked-files=all")
    return sorted(line[3:] for line in out.splitlines()
                  if not line[3:].startswith((".acs/", "docs/development/", "docs/architecture/lld/")))


def _code(ws, leg, source, test=TEST, finish=True):
    ws.skill("code")
    if leg:
        ws.skill(leg)
    start = ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1")
    assert start.returncode == 0, start.stderr
    if source is None:
        return
    ws.write("src/shop/__init__.py", source)
    ws.write("tests/test_list_customers.py", test)
    ws.write(CODE + "/iter-1/implementer.json", json.dumps({
        "files_changed": ["src/shop/__init__.py", "tests/test_list_customers.py"],
        "tests": {"commands": ["python3 -m pytest -q tests/test_list_customers.py"],
                  "passed": 2, "failed": 0},
        "coverage": {"percent": None, "target": "measured in review"},
        "problems": [], "seams": []}))
    if not finish:
        return
    ws.write(CODE + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 1,
        "summary": "negative offset refused; 2 targeted tests green",
        "states": {"files": _written(ws), "tasks_implemented": ["1"],
                   "tests": {"passed": 2, "failed": 0}, "docs_updated": []},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --result-file '%s/result.json'" % (POST_CODE, CODE))


def IDEAL(ws):
    _code(ws, "code-small", GUARDED)


BAD = {
    "stayed in /acs:code and implemented it without the leg":
        lambda ws: _code(ws, None, GUARDED),
    "dispatched the wrong leg": lambda ws: _code(ws, "code-standard", GUARDED),
    "fired the leg and did nothing": lambda ws: _code(ws, "code-small", None),
    "clamped the offset instead of refusing it":
        lambda ws: _code(ws, "code-small", CLAMPED),
    "implemented but never finished the step":
        lambda ws: _code(ws, "code-small", GUARDED, finish=False),
}
