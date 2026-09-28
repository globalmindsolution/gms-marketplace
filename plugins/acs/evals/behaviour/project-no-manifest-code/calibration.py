"""Calibration plays for project-no-manifest-code (see
tests/evals/check_grader_calibration.py). IDEAL is the documented path: the
evidence table finds no row, so /acs:project reports bootstrap and
dispatches create-project; the leg's Start allocates its delivery ticket,
its greenfield gate finds app/, tests/ and requirements.txt, and it goes
straight to Finish with the refusal. The umbrella reports and stops."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RUN = ".acs/state-machine/example-shop/runs/EVAL-1/steps/"

REFUSAL = {
    "status": "failed",
    "summary": "greenfield-only: repository already contains substantive sources",
    "states": {"scaffold": {"build": False, "lint": False, "tests": False,
                            "coverage_tooling": False}},
    "findings": [{"severity": "blocking", "dimension": "greenfield",
                  "detail": "app/__init__.py, requirements.txt, tests/test_health.py"}],
    "errors": []}


def _post_hook(ws, leg, result):
    path = RUN + leg + "/result.json"
    ws.write(path, json.dumps(result, indent=2) + "\n")
    done = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "scripts",
                                                        "post-%s.py" % leg),
                           "--result-file", path],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr


def _start(ws, leg, first=True):
    if first:
        ws.skill("project")
    ws.skill(leg)
    start = ws.acs("step", "start", "--step", leg, "--allocate", "--args", "", stdin="")
    assert start.returncode == 0, start.stderr


def IDEAL(ws):
    _start(ws, "create-project")
    _post_hook(ws, "create-project", REFUSAL)
    ws.reply = ("## /acs:project · failed\n\n- **Mode**: bootstrap → create-project\n"
                "- **Evidence**: none found; checked pyproject.toml, setup.py, ...\n"
                "- **Leg**: EVAL-1 — failed — greenfield-only: app/, tests/, requirements.txt\n")


def _then_standardized(ws):
    IDEAL(ws)
    _start(ws, "standardize-project", first=False)
    ws.write(".github/workflows/ci.yml", "name: ci\non: [push]\n")


def _scaffolded_anyway(ws):
    _start(ws, "create-project")
    ws.write("pyproject.toml", '[project]\nname = "shop"\nversion = "0.1.0"\n')
    ws.write("app/__init__.py", 'def health():\n    return "ok"\n')
    _post_hook(ws, "create-project", {
        "status": "completed", "summary": "scaffolded",
        "states": {"scaffold": {"build": True, "lint": True, "tests": True,
                                "coverage_tooling": True}},
        "findings": [], "errors": []})


BAD = {
    "re-dispatched standardize-project after the refusal": _then_standardized,
    "scaffolded over the existing code": _scaffolded_anyway,
    "reported the mode and dispatched nothing": lambda ws: (
        ws.skill("project"), setattr(ws, "reply", "Mode: bootstrap -> create-project")),
}
