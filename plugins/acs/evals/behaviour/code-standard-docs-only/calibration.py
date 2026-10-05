"""Plays for code-standard-docs-only (see
tests/evals/check_grader_calibration.py).

IDEAL is what the code-standard leg does on this docs-only plan, through its
real writers: `acs.py step start --step code` (which passes the approval brake
the scaffold's `acs.py plan check` satisfied), one implementer per plan task
-- slices 1 and 2, each writing only its own paths (nothing committed --
ADR-0127), writing no test and reporting at `iter-1/implementer-<k>.json` --
the leg's result.json, and `post-code.py`.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
CODE = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/code"

PAGE = '''# GET /customers

Lists customers, one page at a time.

| Parameter | Default | Meaning |
|---|---|---|
| `offset` | `0` | how many customers to skip |
| `limit` | `20` | how many customers per page |

Response: `{"items": [...], "offset": <offset>, "limit": <limit>}`.
'''


def _written(ws):
    """`states.files`: every repo path the run left uncommitted for /acs:create-pr
    (ADR-0127) -- the scaffold's own uncommitted ticket docs aside."""
    out = ws.sh("git status --porcelain --untracked-files=all")
    return sorted(line[3:] for line in out.splitlines()
                  if not line[3:].startswith((".acs/", "docs/development/", "docs/architecture/lld/")))


def _report(ws, name, files):
    ws.write(CODE + "/iter-1/" + name, json.dumps({
        "files_changed": files,
        "tests": {"commands": ["python3 -m pytest -q"], "passed": 1, "failed": 0},
        "coverage": {"percent": None, "target": "measured in review"},
        "problems": [], "seams": []}))


def _code(ws, tasks=(1, 2), sliced=True, test=False, touch_source=False):
    ws.skill("code")
    ws.skill("code-standard")
    start = ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1")
    assert start.returncode == 0, start.stderr
    if not tasks:
        return
    if 1 in tasks:
        ws.write("docs/api/customers.md", PAGE)
    if 2 in tasks:
        ws.sh("printf -- '\\nSee [docs/api/customers.md](docs/api/customers.md) for the full reference.\\n' >> README.md")
        ws.sh("sed -i 's/^## \\[2.4.0\\]/## [Unreleased]\\n\\n- API reference for GET \\/customers.\\n\\n&/' CHANGELOG.md")
    if test:
        ws.write("tests/test_customers_doc.py", "def test_documented():\n    assert True\n")
    if touch_source:
        ws.sh("sed -i 's/return {\"items\": \\[\\], \"offset\": offset, \"limit\": limit}/"
              "return {\"items\": [], \"offset\": max(offset, 0), \"limit\": limit}/' src/shop/__init__.py")
    if sliced:
        if 1 in tasks:
            _report(ws, "implementer-1.json", ["docs/api/customers.md"])
        if 2 in tasks:
            _report(ws, "implementer-2.json", ["README.md", "CHANGELOG.md"])
    else:
        _report(ws, "implementer.json", ["docs/api/customers.md", "README.md", "CHANGELOG.md"])
    ws.write(CODE + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 1,
        "summary": "API page, README link and CHANGELOG entry; docs only; existing tests green",
        "states": {"files": _written(ws), "tasks_implemented": [str(t) for t in tasks],
                   "tests": {"passed": 1, "failed": 0},
                   "docs_updated": ["docs/api/customers.md", "README.md", "CHANGELOG.md"]},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --result-file '%s/result.json'" % (POST_CODE, CODE))


def IDEAL(ws):
    _code(ws)


BAD = {
    "fired the leg and did nothing": lambda ws: _code(ws, tasks=()),
    "ran only the API page partition": lambda ws: _code(ws, tasks=(1,)),
    "ran both partitions as one un-sliced implementer": lambda ws: _code(ws, sliced=False),
    "wrote a test on a docs-only ticket": lambda ws: _code(ws, test=True),
    "changed the code it was documenting": lambda ws: _code(ws, touch_source=True),
}
