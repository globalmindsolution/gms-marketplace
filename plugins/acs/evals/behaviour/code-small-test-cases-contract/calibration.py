"""Plays for code-small-test-cases-contract (see tests/evals/check_grader_calibration.py).

IDEAL is what the code-small leg does on this plan, through its real writers:
`acs.py step start --step code`, one implementer that writes a test per TC-n
row of test-cases.md (its TC id in the docstring) and then the guard, commits
on the ticket branch and reports at steps/code/iter-1/implementer.json, the
leg's result.json, and `post-code.py`.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
CODE = ".acs/state-machine/example-shop/runs/EVAL-1/steps/code"
BRANCH = "task/EVAL-1-reject-a-non-positive-page-limit"

GUARDED = '''PAGE_SIZE = 20


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    # a limit below 1 is a caller bug, never a page
    if limit < 1:
        raise ValueError("limit must be >= 1")
    return {"items": [], "offset": offset, "limit": limit}
'''

TEST = '''"""list_customers refuses a non-positive limit (EVAL-1)."""
import pytest

from shop import list_customers


def test_a_zero_limit_is_refused():
    """TC-1"""
    with pytest.raises(ValueError):
        list_customers(limit=0)


def test_a_negative_limit_is_refused():
    """TC-2"""
    with pytest.raises(ValueError):
        list_customers(limit=-5)


def test_a_limit_of_one_is_a_page():
    """TC-3"""
    assert list_customers(limit=1) == {"items": [], "offset": 0, "limit": 1}
'''

# tests written from the acceptance criteria, ignoring the case document
UNTRACED = TEST.replace('"""TC-1"""', '"""AC-1"""').replace(
    '"""TC-2"""', '"""AC-1"""').replace('"""TC-3"""', '"""AC-2"""')


def _code(ws, source=GUARDED, test=TEST, test_path="tests/test_list_customers.py"):
    ws.skill("code")
    ws.skill("code-small")
    start = ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1")
    assert start.returncode == 0, start.stderr
    if source is None:
        return
    ws.write("src/shop/__init__.py", source)
    ws.write(test_path, test)
    ws.sh("git add src/shop/__init__.py %s && git commit -qm 'EVAL-1 Reject a non-positive page limit'"
          % test_path)
    ws.write(CODE + "/iter-1/implementer.json", json.dumps({
        "files_changed": ["src/shop/__init__.py", test_path],
        "tests": {"commands": ["python3 -m pytest -q " + test_path], "passed": 3, "failed": 0},
        "coverage": {"percent": None, "target": "measured in review"},
        "commits": ["EVAL-1 Reject a non-positive page limit"], "problems": [], "seams": []}))
    ws.write(CODE + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 1,
        "summary": "limit below 1 refused; TC-1..TC-3 green",
        "states": {"branch": BRANCH, "tasks_implemented": ["1"],
                   "tests": {"passed": 3, "failed": 0}, "docs_updated": []},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --result-file '%s/result.json'" % (POST_CODE, CODE))


def IDEAL(ws):
    _code(ws)


BAD = {
    "fired the leg and did nothing": lambda ws: _code(ws, source=None),
    "wrote its tests from the ACs, not the case document": lambda ws: _code(ws, test=UNTRACED),
    "dropped TC-3": lambda ws: _code(ws, test=TEST.split("\n\n\ndef test_a_limit_of_one")[0] + "\n"),
    "wrote the tests and never the guard": lambda ws: _code(
        ws, source=GUARDED.replace('    if limit < 1:\n        raise ValueError("limit must be >= 1")\n', "")),
    "named the test module after the ticket": lambda ws: _code(
        ws, test_path="tests/test_eval_1.py"),
}
