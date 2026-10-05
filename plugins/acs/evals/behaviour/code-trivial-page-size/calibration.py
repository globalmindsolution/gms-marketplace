"""Plays for code-trivial-page-size (see
tests/evals/check_grader_calibration.py).

IDEAL is what the code-trivial leg does on this plan, through its real
writers: `acs.py step start --step code`, ONE un-sliced implementer's TDD
edits left uncommitted (ADR-0127), its report at
steps/code/iter-1/implementer.json, the leg's result.json, and `post-code.py`.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
CODE = ".acs/state-machine/example-shop/runs/EVAL-1/steps/code"

SOURCE = '''PAGE_SIZE = 25


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    return {"items": [], "offset": offset, "limit": limit}
'''

# the default overridden at the call instead of the constant corrected
OVERRIDDEN = SOURCE.replace("PAGE_SIZE = 25", "PAGE_SIZE = 20").replace(
    "limit=PAGE_SIZE", "limit=25")

TEST = '''from shop import list_customers


def test_the_default_page_holds_25_customers():
    assert list_customers()["limit"] == 25
'''


def _written(ws):
    """`states.files`: every repo path the run left uncommitted for /acs:create-pr
    (ADR-0127) -- the scaffold's own uncommitted ticket docs aside."""
    out = ws.sh("git status --porcelain --untracked-files=all")
    return sorted(line[3:] for line in out.splitlines()
                  if not line[3:].startswith((".acs/", "docs/tickets/")))


def _report(ws, name):
    ws.write(CODE + "/iter-1/" + name, json.dumps({
        "files_changed": ["src/shop/__init__.py", "tests/test_page_size.py", "README.md"],
        "tests": {"commands": ["python3 -m pytest -q tests/test_page_size.py"],
                  "passed": 1, "failed": 0},
        "coverage": {"percent": None, "target": "measured in review"},
        "docs_updated": ["README.md"], "problems": [], "seams": []}))


def _code(ws, leg, source, reports=("implementer.json",)):
    ws.skill("code")
    if leg:
        ws.skill(leg)
    start = ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1")
    assert start.returncode == 0, start.stderr
    if source is None:
        return
    ws.write("src/shop/__init__.py", source)
    ws.write("tests/test_page_size.py", TEST)
    ws.sh("sed -i 's/20 per page/25 per page/' README.md")
    for name in reports:
        _report(ws, name)
    ws.write(CODE + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 1,
        "summary": "PAGE_SIZE 25; README updated; 1 targeted test green",
        "states": {"files": _written(ws), "tasks_implemented": ["1"],
                   "tests": {"passed": 1, "failed": 0}, "docs_updated": ["README.md"]},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --result-file '%s/result.json'" % (POST_CODE, CODE))


def IDEAL(ws):
    _code(ws, "code-trivial", SOURCE)


BAD = {
    "stayed in /acs:code and implemented it without the leg":
        lambda ws: _code(ws, None, SOURCE),
    "dispatched the wrong leg": lambda ws: _code(ws, "code-small", SOURCE),
    "fired the leg and did nothing": lambda ws: _code(ws, "code-trivial", None),
    "overrode the default instead of correcting the constant":
        lambda ws: _code(ws, "code-trivial", OVERRIDDEN),
    "sliced the work across parallel implementers":
        lambda ws: _code(ws, "code-trivial", SOURCE,
                         reports=("implementer-1.json", "implementer-2.json")),
}
