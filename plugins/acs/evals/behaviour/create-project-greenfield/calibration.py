"""Calibration plays for create-project-greenfield (see
tests/evals/check_grader_calibration.py). IDEAL does what /acs:project ->
create-project does on this greenfield repo, through the plugin's own
writers: allocate the delivery ticket, scaffold on the delivery branch, write
result.json and run the leg's post-hook. `gh pr create` has no forge in an
eval run, so the ideal result is `failed` with a delivery finding."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-project"

PYPROJECT = """[project]
name = "shop"
version = "0.1.0"
requires-python = ">=3.11"

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff", "pre-commit"]

[tool.pytest.ini_options]
pythonpath = ["src"]
addopts = "--cov=shop --cov-report=term-missing"

[tool.coverage.report]
fail_under = 90

[tool.ruff]
line-length = 100
"""

CI = """name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -e .[dev]
      - run: ruff check . && ruff format --check .
      - run: pytest
"""


def _post_hook(ws, result):
    ws.write(STEP + "/result.json", json.dumps(result, indent=2) + "\n")
    done = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "scripts",
                                                        "post-create-project.py"),
                           "--result-file", STEP + "/result.json"],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr


def _start(ws, leg="create-project"):
    ws.skill("project")
    ws.skill(leg)
    start = ws.acs("step", "start", "--step", leg, "--allocate", stdin="")
    assert start.returncode == 0, start.stderr


def IDEAL(ws):
    _start(ws)
    ws.sh("git checkout -q -b task/EVAL-1-project-scaffold")
    ws.write("pyproject.toml", PYPROJECT)
    ws.write("src/shop/__init__.py", 'def health():\n    return "ok"\n')
    ws.write("src/shop/app.py", "from http.server import BaseHTTPRequestHandler\n")
    ws.write("tests/test_health.py",
             'from shop import health\n\n\ndef test_health():\n    assert health() == "ok"\n')
    ws.write(".github/workflows/ci.yml", CI)
    ws.write(".pre-commit-config.yaml", "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
                                        "    rev: v0.6.9\n    hooks:\n      - id: ruff\n")
    ws.sh("git add -A && git commit -qm 'EVAL-1 Scaffold project skeleton per architecture doc set'")
    _post_hook(ws, {"status": "failed",
                    "summary": "scaffold green locally; gh pr create failed (no forge access)",
                    "states": {"scaffold": {"build": True, "lint": True, "tests": True,
                                            "coverage_tooling": True}},
                    "findings": [{"severity": "blocking", "dimension": "delivery",
                                  "detail": "gh pr create failed: no GitHub access"}],
                    "errors": []})


def _refused_as_brownfield(ws):
    _start(ws)
    _post_hook(ws, {"status": "failed",
                    "summary": "greenfield-only: repository already contains substantive sources",
                    "states": {"scaffold": {"build": False, "lint": False, "tests": False,
                                            "coverage_tooling": False}},
                    "findings": [{"severity": "blocking", "dimension": "greenfield",
                                  "detail": "docs/"}], "errors": []})


def _no_coverage_floor(ws):
    _start(ws)
    ws.write("pyproject.toml", PYPROJECT.replace("fail_under = 90", "show_missing = true"))
    ws.write("tests/test_health.py", "def test_health():\n    assert True\n")
    ws.write(".github/workflows/ci.yml", CI)
    _post_hook(ws, {"status": "completed", "summary": "scaffolded",
                    "states": {"scaffold": {"build": True, "lint": True, "tests": True,
                                            "coverage_tooling": True}},
                    "findings": [], "errors": []})


def _hand_scaffold_without_the_leg(ws):
    ws.skill("project")
    ws.write("pyproject.toml", PYPROJECT)
    ws.write("tests/test_health.py", "def test_health():\n    assert True\n")
    ws.write(".github/workflows/ci.yml", CI)


BAD = {
    "refused the greenfield repo and scaffolded nothing": _refused_as_brownfield,
    "coverage tooling that never fails the run": _no_coverage_floor,
    "scaffolded by hand without dispatching the leg": _hand_scaffold_without_the_leg,
    "dispatched standardize-project on a greenfield repo": lambda ws: _start(ws, "standardize-project"),
}
