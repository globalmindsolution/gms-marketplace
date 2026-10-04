"""Plays for code-standard-customer-search (see
tests/evals/check_grader_calibration.py).

IDEAL is what the code-standard leg does on this plan, through its real
writers: `acs.py step start --step code` (which passes the approval brake the
scaffold's `acs.py plan check` satisfied), one implementer per plan task --
slices 1 and 2, each writing only its own paths (nothing committed --
ADR-0127) and writing `iter-1/implementer-<k>.json` -- the leg's result.json,
and `post-code.py`.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
CODE = ".acs/state-machine/example-shop/runs/EVAL-1/steps/code"

SEARCH = '''def search_customers(customers, query):
    """Customers whose name contains query, case-insensitively, in input order."""
    needle = (query or "").strip().lower()
    if not needle:
        raise ValueError("query must not be blank")
    return [c for c in customers if needle in c["name"].lower()]
'''

TEST = '''import pytest

from shop.search import search_customers

CUSTOMERS = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Natalie"}]


def test_a_fragment_matches_case_insensitively_in_order():
    assert search_customers(CUSTOMERS, "ali") == [{"name": "Alice"}, {"name": "Natalie"}]


@pytest.mark.parametrize("query", ["", "  "])
def test_a_blank_query_is_refused(query):
    with pytest.raises(ValueError):
        search_customers(CUSTOMERS, query)
'''


def _written(ws):
    """`states.files`: every repo path the run left uncommitted for /acs:create-pr
    (ADR-0127) -- the scaffold's own uncommitted ticket docs aside."""
    out = ws.sh("git status --porcelain --untracked-files=all")
    return sorted(line[3:] for line in out.splitlines()
                  if not line[3:].startswith((".acs/", "docs/tickets/")))


def _report(ws, name, files):
    ws.write(CODE + "/iter-1/" + name, json.dumps({
        "files_changed": files,
        "tests": {"commands": ["python3 -m pytest -q tests/test_search.py"],
                  "passed": 3, "failed": 0},
        "coverage": {"percent": None, "target": "measured in review"},
        "problems": [], "seams": []}))


def _task1(ws):
    ws.write("src/shop/search.py", SEARCH)
    ws.write("tests/test_search.py", TEST)


def _task2(ws):
    ws.sh("printf -- '- `GET /customers/search?q=` finds customers by name.\\n' >> README.md")
    ws.sh("sed -i 's/^## \\[2.4.0\\]/## [Unreleased]\\n\\n- Customer search by name.\\n\\n&/' CHANGELOG.md")


def _finish(ws):
    ws.write(CODE + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 1,
        "summary": "search_customers and its docs; 2 slices; 3 targeted tests green",
        "states": {"files": _written(ws), "tasks_implemented": ["1", "2"],
                   "tests": {"passed": 3, "failed": 0},
                   "docs_updated": ["README.md", "CHANGELOG.md"]},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --result-file '%s/result.json'" % (POST_CODE, CODE))


def _code(ws, leg, tasks=(1, 2), sliced=True):
    ws.skill("code")
    if leg:
        ws.skill(leg)
    start = ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1")
    assert start.returncode == 0, start.stderr
    if not tasks:
        return
    if 1 in tasks:
        _task1(ws)
    if 2 in tasks:
        _task2(ws)
    if sliced:
        if 1 in tasks:
            _report(ws, "implementer-1.json", ["src/shop/search.py", "tests/test_search.py"])
        if 2 in tasks:
            _report(ws, "implementer-2.json", ["README.md", "CHANGELOG.md"])
    else:
        _report(ws, "implementer.json", ["src/shop/search.py", "tests/test_search.py",
                                         "README.md", "CHANGELOG.md"])
    _finish(ws)


def IDEAL(ws):
    _code(ws, "code-standard")


BAD = {
    "stayed in /acs:code and implemented it without the leg":
        lambda ws: _code(ws, None),
    "dispatched the wrong leg": lambda ws: _code(ws, "code-small"),
    "fired the leg and did nothing": lambda ws: _code(ws, "code-standard", tasks=()),
    "implemented task 1 and dropped the documentation partition":
        lambda ws: _code(ws, "code-standard", tasks=(1,)),
    "ran both partitions as one un-sliced implementer":
        lambda ws: _code(ws, "code-standard", sliced=False),
}
