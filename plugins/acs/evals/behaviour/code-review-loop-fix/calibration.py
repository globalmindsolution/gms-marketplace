"""Plays for code-review-loop-fix (see tests/evals/check_grader_calibration.py).

IDEAL is iteration 2 of the review loop, through the real writers: /acs:code
dispatches the plan's `small` leg, `acs.py step start --step code` opens
iteration 2, the implementer writes the failing test for F-1-1's
`resolved_when` first, fixes `page_bounds`, leaves both files uncommitted
(ADR-0127: no branch, no commit) and reports them at
steps/code/iter-2/implementer.json, and the leg's result.json answers F-1-1 by
id -- naming the files it changed -- before `post-code.py` finishes the step.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
CODE = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/code"

TEST = '''from shop import list_customers_page, page_bounds


def test_a_page_holds_per_page_customers():
    customers = list(range(50))
    assert len(list_customers_page(customers, page=2, per_page=10)) == 10


def test_page_one_is_the_first_page():
    assert page_bounds(1, 10) == (0, 10)
    assert list_customers_page(list(range(50)), page=1, per_page=10) == list(range(10))


def test_page_two_is_the_next_page():
    assert list_customers_page(list(range(50)), page=2, per_page=10) == list(range(10, 20))
'''


def _fix(ws):
    ws.sh("sed -i 's/start = page \\* per_page/start = (page - 1) * per_page/' src/shop/__init__.py")
    ws.write("tests/test_pagination.py", TEST)


def _code(ws, fix=True, commit=False, answer="fixed", branch=None, finish=True):
    ws.skill("code")
    ws.skill("code-small")
    start = ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1")
    assert start.returncode == 0, start.stderr
    assert json.loads(start.stdout)["iteration"] == 2
    if not finish:
        return
    # since_sha: the verdict's reviewed_sha, the working-tree snapshot it judged.
    with open(os.path.join(ws.path, ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/"
                           "review-code/verdict.json"), encoding="utf-8") as fh:
        since = json.load(fh)["reviewed_sha"]
    if branch:
        ws.sh("git checkout -q -b %s" % branch)
    if fix:
        _fix(ws)
    if fix and commit:
        ws.sh("git add src/shop/__init__.py tests/test_pagination.py"
              " && git commit -qm 'EVAL-1 Page 1 is the first page'")
    ws.write(CODE + "/iter-2/implementer.json", json.dumps({
        "files_changed": ["src/shop/__init__.py", "tests/test_pagination.py"],
        "tests": {"commands": ["python3 -m pytest -q tests/test_pagination.py"],
                  "passed": 3, "failed": 0},
        "coverage": {"percent": None, "target": "measured in review"},
        "problems": [], "seams": []}))
    resolutions = []
    if answer == "fixed":
        resolutions = [{"id": "F-1-1", "status": "fixed",
                        "files": ["src/shop/__init__.py", "tests/test_pagination.py"],
                        "tests": ["tests/test_pagination.py::test_page_one_is_the_first_page"]}]
    elif answer == "disputed":
        resolutions = [{"id": "F-1-1", "status": "disputed",
                        "reason": "page numbers could be read as 0-based"}]
    ws.write(CODE + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 2,
        "since_sha": since, "resolutions": resolutions,
        "summary": "F-1-1 %s" % (answer or "not answered"),
        "states": {"tasks_implemented": ["1"],
                   "files": ["src/shop/__init__.py", "tests/test_pagination.py"],
                   "tests": {"passed": 3, "failed": 0}, "docs_updated": []},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --result-file '%s/result.json'" % (POST_CODE, CODE))


def IDEAL(ws):
    _code(ws)


BAD = {
    "fired and never implemented the fix": lambda ws: _code(ws, finish=False),
    "disputed the finding instead of fixing it":
        lambda ws: _code(ws, fix=False, answer="disputed"),
    "committed the fix": lambda ws: _code(ws, commit=True),
    "fixed it on a new branch": lambda ws: _code(ws, branch="task/EVAL-1-fix-review"),
    "fixed it without answering the finding by id": lambda ws: _code(ws, answer=None),
}
