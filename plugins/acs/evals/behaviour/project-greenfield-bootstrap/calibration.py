"""Calibration plays for project-greenfield-bootstrap (see
tests/evals/check_grader_calibration.py). IDEAL is /acs:project's real path
on a greenfield repo: report bootstrap mode, dispatch create-project, whose
own Start allocates the "Project scaffold" delivery ticket, scaffold on the
delivery branch, write the result and run the leg's post-hook. `gh pr
create` has no forge in an eval run, so the ideal result is `failed` with a
delivery finding."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RUN = ".acs/state-machine/example-shop/runs/EVAL-1/steps/"

PYPROJECT = """[project]
name = "shop"
version = "0.1.0"
requires-python = ">=3.11"

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff", "pre-commit"]

[tool.pytest.ini_options]
pythonpath = ["src"]
addopts = "--cov=shop --cov-fail-under=90"
"""

REPLY = ("## /acs:project · failed\n\n"
         "- **Mode**: bootstrap → create-project\n"
         "- **Evidence**: none found; checked pyproject.toml, setup.py, package.json, go.mod, "
         "Cargo.toml, pom.xml, build.gradle, build.gradle.kts, .pre-commit-config.yaml, .coveragerc\n"
         "- **Leg**: EVAL-1 — failed — gh pr create failed (no GitHub access)\n"
         "- **Findings**: gh pr create failed\n"
         "- **Next**: /acs:create-project\n")


def _post_hook(ws, leg, result):
    path = RUN + leg + "/result.json"
    ws.write(path, json.dumps(result, indent=2) + "\n")
    done = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "scripts",
                                                        "post-%s.py" % leg),
                           "--result-file", path],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr


def _leg(ws, leg):
    ws.skill("project")
    ws.skill(leg)
    start = ws.acs("step", "start", "--step", leg, "--allocate", "--args", "", stdin="")
    assert start.returncode == 0, start.stderr


def _scaffold(ws):
    ws.sh("git checkout -q -b task/EVAL-1-project-scaffold")
    ws.write("pyproject.toml", PYPROJECT)
    ws.write("src/shop/__init__.py", 'def health():\n    return "ok"\n')
    ws.write("tests/test_health.py",
             'from shop import health\n\n\ndef test_health():\n    assert health() == "ok"\n')
    ws.write(".github/workflows/ci.yml", "name: ci\non: [push, pull_request]\n")
    ws.write(".pre-commit-config.yaml", "repos: []\n")
    ws.sh("git add -A && git commit -qm 'EVAL-1 Scaffold project skeleton per architecture doc set'")


def IDEAL(ws):
    _leg(ws, "create-project")
    _scaffold(ws)
    _post_hook(ws, "create-project", {
        "status": "failed", "summary": "scaffold green locally; gh pr create failed",
        "states": {"scaffold": {"build": True, "lint": True, "tests": True,
                                "coverage_tooling": True}},
        "findings": [{"severity": "blocking", "dimension": "delivery",
                      "detail": "gh pr create failed: no GitHub access"}], "errors": []})
    ws.reply = REPLY


def _wrong_leg(ws):
    _leg(ws, "standardize-project")
    ws.write(".github/workflows/ci.yml", "name: ci\non: [push]\n")
    _post_hook(ws, "standardize-project", {
        "status": "failed", "summary": "additive scaffold done; gh pr create failed",
        "states": {"scaffold": {"files_added": [".github/workflows/ci.yml"]},
                   "recommended_follow_ups": []},
        "findings": [], "errors": []})
    ws.reply = "## /acs:project · failed\n\n- **Mode**: standardize → standardize-project\n"


def _by_hand(ws):
    ws.skill("project")
    ws.write("pyproject.toml", PYPROJECT)
    ws.write("tests/test_health.py", "def test_health():\n    assert True\n")
    ws.reply = REPLY


BAD = {
    "dispatched standardize-project on a greenfield repo": _wrong_leg,
    "stated the mode and dispatched nothing": lambda ws: (
        ws.skill("project"), setattr(ws, "reply", REPLY)),
    "scaffolded by hand without dispatching the leg": _by_hand,
    "never said which mode it picked": lambda ws: (IDEAL(ws), setattr(ws, "reply", "Done.")),
}
