"""Calibration plays for create-project-no-architecture (see
tests/evals/check_grader_calibration.py). IDEAL is the No-architecture
fallback as written: /acs:project dispatches create-project, whose Start
finds no hld/tech-stack.md, allocates the delivery ticket, records each
relayed answer through clarify.py (the ledger's own writer), scaffolds from
those entries on the delivery branch, and finishes (the PR step fails for
want of a forge)."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CLARIFY = os.path.join(PLUGIN, "hooks", "scripts", "clarify.py")
RESULT = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-project/result.json"
ANSWERS = [
    ("Which stack (language, packaging, test framework, linter, CI)?",
     "Python 3.11, pyproject.toml (setuptools), pytest + pytest-cov, ruff + pre-commit, "
     "GitHub Actions"),
    ("Which directory layout?", "src/shop/ for the package, tests/ for unit tests"),
    ("Which coverage tooling and threshold?", "pytest-cov failing below 90%"),
    ("Is an e2e harness wanted?", "no"),
]
PYPROJECT = ('[project]\nname = "shop"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n\n'
             '[tool.coverage.report]\nfail_under = 90\n')


def _start(ws):
    ws.skill("project")
    ws.skill("create-project")
    start = ws.acs("step", "start", "--step", "create-project", "--allocate", stdin="")
    assert start.returncode == 0, start.stderr


def _record(ws, answers=ANSWERS):
    for question, answer in answers:
        done = subprocess.run([sys.executable, CLARIFY, "add", "--skill", "create-project",
                               "--question", question, "--answer", answer,
                               "--ticket", "EVAL-1"],
                              cwd=ws.path, env=ws.env, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr


def _scaffold(ws):
    ws.sh("git checkout -q -b task/EVAL-1-project-scaffold")
    ws.write("pyproject.toml", PYPROJECT)
    ws.write("src/shop/__init__.py", 'def health():\n    return "ok"\n')
    ws.write("tests/test_health.py",
             'from shop import health\n\n\ndef test_health():\n    assert health() == "ok"\n')
    ws.write(".github/workflows/ci.yml", "name: ci\non: [push, pull_request]\n")
    ws.sh("git add -A && git commit -qm 'EVAL-1 Scaffold project skeleton from confirmed stack'")


def _finish(ws, status="failed", summary="scaffold green locally; gh pr create failed",
            green=True):
    ws.write(RESULT, json.dumps({
        "status": status, "summary": summary,
        "states": {"scaffold": {"build": green, "lint": green, "tests": green,
                                "coverage_tooling": green}},
        "findings": [{"severity": "blocking", "dimension": "delivery",
                      "detail": "gh pr create failed: no GitHub access"}] if green else [],
        "errors": [],
        **({"stop_reason": "needs_input"} if status == "interrupted" else {})},
        indent=2) + "\n")
    done = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "scripts",
                                                        "post-create-project.py"),
                           "--result-file", RESULT],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    _record(ws)
    _scaffold(ws)
    _finish(ws)


BAD = {
    "stopped for lack of an architecture set": lambda ws: (
        _start(ws), _finish(ws, status="interrupted", summary="no architecture doc set",
                            green=False)),
    "scaffolded without recording the answers": lambda ws: (
        _start(ws), _scaffold(ws), _finish(ws)),
    "wrote tech-stack.md itself instead of the fallback": lambda ws: (
        _start(ws), ws.write("docs/architecture/hld/tech-stack.md", "# Tech stack\n\nPython 3.11\n"),
        _record(ws), _scaffold(ws), _finish(ws)),
}
