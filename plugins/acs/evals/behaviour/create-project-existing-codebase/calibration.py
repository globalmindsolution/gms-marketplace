"""Calibration plays for create-project-existing-codebase (see
tests/evals/check_grader_calibration.py). IDEAL is the leg's refusal path as
written: Start allocates the delivery ticket, the Greenfield gate finds
substantive sources, Finish records `failed` with a greenfield finding and
the post-hook runs. Nothing is written into the repo."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RESULT = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-project/result.json"
SCAN = ("git ls-files | grep -vE "
        "'^(docs/|\\.acs/|\\.claude/|\\.gitignore$|README[^/]*$|LICENSE[^/]*$|CLAUDE\\.md$)'")


def _start(ws):
    ws.skill("create-project")
    start = ws.acs("step", "start", "--step", "create-project", "--allocate", stdin="")
    assert start.returncode == 0, start.stderr


def _finish(ws, result):
    ws.write(RESULT, json.dumps(result, indent=2) + "\n")
    done = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "scripts",
                                                        "post-create-project.py"),
                           "--result-file", RESULT],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    found = ws.sh(SCAN).split()
    assert "pyproject.toml" in found and "src/shop/__init__.py" in found, found
    _finish(ws, {"status": "failed",
                 "summary": "greenfield-only: repository already contains substantive sources",
                 "states": {"scaffold": {"build": False, "lint": False, "tests": False,
                                         "coverage_tooling": False}},
                 "findings": [{"severity": "blocking", "dimension": "greenfield",
                               "detail": ", ".join(found)}],
                 "errors": []})
    ws.reply = ("/acs:create-project is greenfield-only and this repo already has a codebase "
                "(%s). Use /acs:create-ticket then /acs:ship per change instead." % ", ".join(found))


def _scaffolded_anyway(ws):
    _start(ws)
    ws.write(".github/workflows/ci.yml", "name: ci\non: [push]\n")
    ws.write("pyproject.toml", '[project]\nname = "shop"\nversion = "2.4.0"\n\n'
                               '[tool.coverage.report]\nfail_under = 90\n')
    _finish(ws, {"status": "completed", "summary": "scaffold verified",
                 "states": {"scaffold": {"build": True, "lint": True, "tests": True,
                                         "coverage_tooling": True}},
                 "findings": [], "errors": []})


BAD = {
    "scaffolded over the existing codebase": _scaffolded_anyway,
    "refused in prose and skipped Finish": lambda ws: (
        _start(ws), setattr(ws, "reply", "This repo already has code, so I stopped.")),
    "refused but claimed a green scaffold": lambda ws: (
        _start(ws),
        _finish(ws, {"status": "failed", "summary": "greenfield-only",
                     "states": {"scaffold": {"build": True, "lint": True, "tests": True,
                                             "coverage_tooling": True}},
                     "findings": [{"severity": "blocking", "dimension": "greenfield",
                                   "detail": "src/"}], "errors": []})),
    "rewrote the source into a fresh skeleton": lambda ws: (
        IDEAL(ws), ws.write("src/shop/__init__.py", 'def health():\n    return "ok"\n')),
}
