"""Plays for code-trivial-out-of-map-typo (see
tests/evals/check_grader_calibration.py).

IDEAL is what the code-trivial leg does on this plan, through its real
writers: `acs.py step start --step code`, ONE un-sliced implementer that runs
the red test, fixes the mapped module and leaves it uncommitted, its report at
steps/code/iter-1/implementer.json, the leg's result.json, and `post-code.py`.
src/shop/emails.py is outside the map and never written.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_CODE = os.path.join(PLUGIN, "hooks", "scripts", "post-code.py")
CODE = ".acs/state-machine/example-shop/runs/EVAL-1/steps/code"


def _written(ws):
    """`states.files`: every repo path the run left uncommitted for /acs:create-pr
    (ADR-0127) -- the scaffold's own uncommitted ticket docs aside."""
    out = ws.sh("git status --porcelain --untracked-files=all")
    return sorted(line[3:] for line in out.splitlines()
                  if not line[3:].startswith((".acs/", "docs/development/", "docs/architecture/lld/")))


def _code(ws, leg="code-trivial", fix=True, emails=False, test=None,
          reports=("implementer.json",)):
    ws.skill("code")
    if leg:
        ws.skill(leg)
    start = ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1")
    assert start.returncode == 0, start.stderr
    if not (fix or emails or test):
        return
    files = []
    if fix:
        ws.sh("sed -i 's/\"Helo, %s!\"/\"Hello, %s!\"/' src/shop/__init__.py")
        files.append("src/shop/__init__.py")
    if emails:
        ws.sh("sed -i 's/Helo from shop/Hello from shop/' src/shop/emails.py")
        files.append("src/shop/emails.py")
    if test:
        ws.write("tests/test_greeting.py", test)
        files.append("tests/test_greeting.py")
    for name in reports:
        ws.write(CODE + "/iter-1/" + name, json.dumps({
            "files_changed": files,
            "tests": {"commands": ["python3 -m pytest -q tests/test_greeting.py"],
                      "passed": 1, "failed": 0},
            "coverage": {"percent": None, "target": "measured in review"},
            "problems": [], "seams": []}))
    ws.write(CODE + "/result.json", json.dumps({
        "status": "completed", "outcome": "implemented", "iteration": 1,
        "summary": "greeting spelled Hello; tests/test_greeting.py green",
        "states": {"files": _written(ws), "tasks_implemented": ["1"],
                   "tests": {"passed": 1, "failed": 0}, "docs_updated": []},
        "findings": [], "errors": []}))
    ws.sh("python3 '%s' --result-file '%s/result.json'" % (POST_CODE, CODE))


def IDEAL(ws):
    _code(ws)


BAD = {
    "fired the leg and did nothing": lambda ws: _code(ws, fix=False),
    "dispatched the wrong leg": lambda ws: _code(ws, leg="code-small"),
    "fixed the out-of-map email subject too": lambda ws: _code(ws, emails=True),
    "made the red test expect the typo": lambda ws: _code(
        ws, fix=False, test='from shop import greeting\n\n\ndef test_the_greeting():\n'
                            '    assert greeting("Ann") == "Helo, Ann!"\n'),
    "sliced a one-line fix across implementers": lambda ws: _code(
        ws, reports=("implementer-1.json", "implementer-2.json")),
}
