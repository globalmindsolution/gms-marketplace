"""Calibration plays for standardize-project-no-architecture (see
tests/evals/check_grader_calibration.py). IDEAL is the leg's real path with
no architecture set: `acs step start --allocate`, the delivery branch, the
missing CI and coverage config added as new files and committed by name,
and a result whose `states.recommended_follow_ups` carries
/acs:create-architecture, run through the leg's post-hook."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RESULT = ".acs/state-machine/example-shop/runs/EVAL-1/steps/standardize-project/result.json"
ARCH = {"title": "Bootstrap the architecture doc set",
        "rationale": "no architecture set: project-structure checks skipped",
        "target_path": "/acs:create-architecture"}
CI = ("name: ci\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
      "    steps:\n      - uses: actions/checkout@v4\n      - run: pip install pytest pytest-cov\n"
      "      - run: python3 -m pytest --cov=src --cov-fail-under=90 tests\n")


def _start(ws):
    ws.skill("standardize-project")
    start = ws.acs("step", "start", "--step", "standardize-project", "--allocate", "--args", "",
                   stdin="")
    assert start.returncode == 0, start.stderr
    ws.sh("git checkout -q -b task/EVAL-1-brownfield-project-standardization")


def _finish(ws, follow_ups, status="failed"):
    ws.write(RESULT, json.dumps({
        "status": status, "summary": "additive scaffold verified; gh pr create failed",
        "states": {"audit": {"principles": "present", "standards": "present",
                             "project_structure": "absent",
                             "readiness_tooling": {"ci": False, "pre_commit": True,
                                                   "coverage": False, "e2e": "n/a"}},
                   "scaffold": {"files_added": [".github/workflows/ci.yml", ".coveragerc"]},
                   "recommended_follow_ups": follow_ups},
        "findings": [{"severity": "blocking", "dimension": "delivery",
                      "detail": "gh pr create failed"}], "errors": []}, indent=2) + "\n")
    done = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "scripts",
                                                        "post-standardize-project.py"),
                           "--result-file", RESULT],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr


def _scaffold(ws):
    ws.write(".github/workflows/ci.yml", CI)
    ws.write(".coveragerc", "[run]\nsource = src\n\n[report]\nfail_under = 90\n")
    ws.sh("git add -- .github/workflows/ci.yml .coveragerc && "
          "git commit -qm 'EVAL-1 Additively scaffold missing tooling'")


def IDEAL(ws):
    _start(ws)
    _scaffold(ws)
    _finish(ws, [ARCH])


BAD = {
    "stopped at Start for lack of an architecture set": lambda ws: (
        ws.skill("standardize-project"),
        setattr(ws, "reply", "No architecture set found; run /acs:create-architecture first.")),
    "wrote the architecture docs itself": lambda ws: (
        _start(ws), _scaffold(ws),
        ws.write("docs/architecture/hld/tech-stack.md", "# Tech stack\n\nPython 3.11\n"),
        _finish(ws, [])),
    "scaffolded and forgot the architecture follow-up": lambda ws: (
        _start(ws), _scaffold(ws), _finish(ws, [])),
    "recommended it but scaffolded nothing": lambda ws: (_start(ws), _finish(ws, [ARCH])),
}
