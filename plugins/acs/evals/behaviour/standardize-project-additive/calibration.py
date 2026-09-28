"""Calibration plays for standardize-project-additive (see
tests/evals/check_grader_calibration.py). IDEAL is the leg's real path:
`acs step start --allocate`, the delivery branch, additive files only, a
commit of exactly those files, result.json, and the leg's post-hook."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RESULT = ".acs/state-machine/example-shop/runs/EVAL-1/steps/standardize-project/result.json"
FOLLOW_UPS = [{"title": "Bootstrap the principles/ doc set", "rationale": "no principles set found",
               "target_path": "/acs:create-principles"},
              {"title": "Bootstrap the standards/ doc set", "rationale": "no standards set found",
               "target_path": "/acs:create-standards"}]


def _start(ws):
    ws.skill("standardize-project")
    start = ws.acs("step", "start", "--step", "standardize-project", "--allocate", "--args", "",
                   stdin="")
    assert start.returncode == 0, start.stderr
    ws.sh("git checkout -q -b task/EVAL-1-brownfield-project-standardization")


def _finish(ws, follow_ups=FOLLOW_UPS):
    # Under `states`, where the leg's SKILL.md puts it: the result envelope
    # admits no top-level key of a skill's own.
    ws.write(RESULT, json.dumps({
        "status": "failed", "summary": "additive scaffold verified; gh pr create failed",
        "states": {"audit": {"principles": "absent", "standards": "absent",
                             "project_structure": "present",
                             "readiness_tooling": {"ci": False, "pre_commit": True,
                                                   "coverage": False, "e2e": "n/a"}},
                   "scaffold": {"files_added": [".github/workflows/ci.yml"]},
                   "recommended_follow_ups": follow_ups},
        "findings": [{"severity": "blocking", "dimension": "delivery",
                      "detail": "gh pr create failed"}], "errors": []}, indent=2) + "\n")
    done = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "scripts",
                                                        "post-standardize-project.py"),
                           "--result-file", RESULT],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr


CI = ("name: ci\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
      "    steps:\n      - uses: actions/checkout@v4\n      - run: pip install pytest pytest-cov\n"
      "      - run: python3 -m pytest --cov=src --cov-fail-under=90\n")


def IDEAL(ws):
    _start(ws)
    ws.write(".github/workflows/ci.yml", CI)
    ws.write(".coveragerc", "[run]\nsource = src\n\n[report]\nfail_under = 90\n")
    ws.sh("git add -- .github/workflows/ci.yml .coveragerc && "
          "git commit -qm 'EVAL-1 Additively scaffold missing tooling'")
    _finish(ws)


def _authored_doc_sets(ws):
    _start(ws)
    ws.write(".github/workflows/ci.yml", CI)
    ws.write("docs/principles/principles.md", "# Principles\n")
    _finish(ws, follow_ups=[])


def _rewrote_source(ws):
    IDEAL(ws)
    ws.write("src/shop/__init__.py", 'PAGE_SIZE = 50\n\n\ndef health():\n    return "ok"\n')
    ws.write("tests/test_customers.py", "def test_customers():\n    assert True\n")


BAD = {
    "audited and scaffolded nothing": lambda ws: (_start(ws), _finish(ws)),
    "authored the principles set instead of recommending it": _authored_doc_sets,
    "rewrote existing source and added tests": _rewrote_source,
    "added CI by hand without the leg": lambda ws: ws.write(".github/workflows/ci.yml", CI),
}
