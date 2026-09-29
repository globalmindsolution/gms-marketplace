"""Calibration plays for standardize-project-e2e-conflict (see
tests/evals/check_grader_calibration.py). IDEAL is the leg's real path when
the only gap is a conflict: `acs step start --allocate`, the delivery
branch, an audit that finds acs-e2e.yml already present, nothing written
into the repo, and a result whose `states.recommended_follow_ups` names the
conflict, run through the leg's post-hook."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RESULT = ".acs/state-machine/example-shop/runs/EVAL-1/steps/standardize-project/result.json"
CONFLICT = {"title": "Reconcile the existing .github/workflows/acs-e2e.yml with acs's e2e gate",
            "rationale": "suites.e2e is configured, but .github/workflows/acs-e2e.yml already "
                         "holds the team's own workflow; it was not overwritten",
            "target_path": ".github/workflows/acs-e2e.yml"}


def _start(ws):
    ws.skill("standardize-project")
    start = ws.acs("step", "start", "--step", "standardize-project", "--allocate", "--args", "",
                   stdin="")
    assert start.returncode == 0, start.stderr
    ws.sh("git checkout -q -b task/EVAL-1-brownfield-project-standardization")


def _finish(ws, follow_ups, files_added=()):
    ws.write(RESULT, json.dumps({
        "status": "completed", "summary": "audit complete; nothing additive to scaffold",
        "states": {"audit": {"principles": "present", "standards": "present",
                             "project_structure": "present",
                             "readiness_tooling": {"ci": True, "pre_commit": True,
                                                   "coverage": True, "e2e": True}},
                   "scaffold": {"files_added": list(files_added)},
                   "recommended_follow_ups": follow_ups},
        "findings": [], "errors": []}, indent=2) + "\n")
    done = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "scripts",
                                                        "post-standardize-project.py"),
                           "--result-file", RESULT],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    _finish(ws, [CONFLICT])


def _overwrote(ws):
    _start(ws)
    ws.sh('cp "%s/templates/ci/acs-e2e.yml" .github/workflows/acs-e2e.yml && '
          'mkdir -p .acs/ci && cp "%s/templates/ci/run-e2e.py" .acs/ci/run-e2e.py'
          % (PLUGIN, PLUGIN))
    _finish(ws, [], files_added=[".acs/ci/run-e2e.py"])


BAD = {
    "copied the acs template over the team's workflow": _overwrote,
    "skipped the conflict without recording it": lambda ws: (_start(ws), _finish(ws, [])),
    "audited and never reached Finish": _start,
    "appended an acs job into the team's workflow": lambda ws: (
        IDEAL(ws), ws.write(".github/workflows/acs-e2e.yml",
                            "  acs-e2e:\n    runs-on: ubuntu-latest\n", append=True)),
}
