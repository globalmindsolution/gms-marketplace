"""Calibration plays for standardize-project-nothing-missing (see
tests/evals/check_grader_calibration.py). IDEAL is the leg's zero-gap path:
`acs step start --allocate`, an audit that finds every set and every
readiness tool present, nothing scaffolded, and a result with an empty
`states.recommended_follow_ups`, run through the leg's post-hook."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RESULT = ".acs/state-machine/example-shop/runs/EVAL-1/steps/standardize-project/result.json"
PRESENT = {"principles": "present", "standards": "present", "project_structure": "present",
           "readiness_tooling": {"ci": True, "pre_commit": True, "coverage": True, "e2e": "n/a"}}


def _start(ws):
    ws.skill("standardize-project")
    start = ws.acs("step", "start", "--step", "standardize-project", "--allocate", "--args", "",
                   stdin="")
    assert start.returncode == 0, start.stderr


def _finish(ws, audit=PRESENT, follow_ups=(), files_added=()):
    ws.write(RESULT, json.dumps({
        "status": "completed", "summary": "audit complete: zero gaps, nothing to scaffold",
        "states": {"audit": audit, "scaffold": {"files_added": list(files_added)},
                   "recommended_follow_ups": list(follow_ups)},
        "findings": [], "errors": []}, indent=2) + "\n")
    done = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "scripts",
                                                        "post-standardize-project.py"),
                           "--result-file", RESULT],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    _finish(ws)
    ws.reply = "Nothing to add: every audited set and readiness tool is already present."


def _added_redundant_ci(ws):
    _start(ws)
    ws.sh("git checkout -q -b task/EVAL-1-brownfield-project-standardization")
    ws.write(".github/workflows/acs-tests.yml", "name: acs tests\non: [pull_request]\n")
    ws.sh("git add -- .github/workflows/acs-tests.yml && git commit -qm 'EVAL-1 Add CI'")
    _finish(ws, files_added=[".github/workflows/acs-tests.yml"])


def _missed_the_sets(ws):
    _start(ws)
    _finish(ws, audit=dict(PRESENT, principles="absent", standards="absent"), follow_ups=[
        {"title": "Bootstrap the principles/ doc set", "rationale": "none found",
         "target_path": "/acs:create-principles"}])


BAD = {
    "added a redundant CI workflow": _added_redundant_ci,
    "recommended a doc set that already exists": _missed_the_sets,
    "said nothing was missing and never ran Finish": lambda ws: (
        _start(ws), setattr(ws, "reply", "Nothing to add.")),
    "rewrote the existing CI workflow": lambda ws: (
        IDEAL(ws), ws.write(".github/workflows/ci.yml", "name: ci\non: [push]\n")),
}
