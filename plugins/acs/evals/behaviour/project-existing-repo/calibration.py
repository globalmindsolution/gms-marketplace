"""Calibration plays for project-existing-repo (see
tests/evals/check_grader_calibration.py). IDEAL is /acs:project's real path
on this repo: report standardize mode, dispatch standardize-project, whose
own Start allocates its delivery ticket, scaffold additively, write the
result and run the leg's post-hook."""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RUN = ".acs/state-machine/example-shop/runs/EVAL-1/steps/"


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


REPLY = ("## /acs:project · failed\n\n"
         "- **Mode**: standardize → standardize-project\n"
         "- **Evidence**: pyproject.toml (python-packaging) found\n"
         "- **Leg**: EVAL-1 — failed — gh pr create failed (no GitHub access)\n")


def IDEAL(ws):
    _leg(ws, "standardize-project")
    ws.sh("git checkout -q -b task/EVAL-1-brownfield-project-standardization")
    ws.write(".github/workflows/ci.yml", "name: ci\non: [push, pull_request]\n")
    ws.write(".pre-commit-config.yaml", "repos: []\n")
    ws.sh("git add -- .github/workflows/ci.yml .pre-commit-config.yaml && "
          "git commit -qm 'EVAL-1 Additively scaffold missing tooling'")
    # recommended_follow_ups sits under `states`, where the leg's SKILL.md puts
    # it: the result envelope admits no top-level key of a skill's own.
    _post_hook(ws, "standardize-project", {
        "status": "failed", "summary": "additive scaffold done; gh pr create failed",
        "states": {"scaffold": {"files_added": [".github/workflows/ci.yml",
                                                ".pre-commit-config.yaml"]},
                   "recommended_follow_ups": [{"title": "Bootstrap the principles/ doc set",
                                               "rationale": "none found",
                                               "target_path": "/acs:create-principles"}]},
        "findings": [{"severity": "blocking", "dimension": "delivery",
                      "detail": "gh pr create failed"}], "errors": []})
    ws.reply = REPLY


def _wrong_leg(ws):
    _leg(ws, "create-project")
    _post_hook(ws, "create-project", {
        "status": "failed",
        "summary": "greenfield-only: repository already contains substantive sources",
        "states": {"scaffold": {"build": False, "lint": False, "tests": False,
                                "coverage_tooling": False}},
        "findings": [{"severity": "blocking", "dimension": "greenfield",
                      "detail": "src/, tests/, pyproject.toml"}], "errors": []})
    ws.reply = "## /acs:project · failed\n\n- **Mode**: bootstrap → create-project\n"


def _rewrote_source(ws):
    IDEAL(ws)
    ws.write("src/shop/__init__.py", 'PAGE_SIZE = 20\n\n\ndef health() -> str:\n    return "ok"\n')


BAD = {
    "dispatched create-project on an existing codebase": _wrong_leg,
    "stated the mode and dispatched nothing": lambda ws: (
        ws.skill("project"), setattr(ws, "reply", REPLY)),
    "rewrote existing source while standardizing": _rewrote_source,
    "never said what decided the mode": lambda ws: (IDEAL(ws), setattr(ws, "reply", "Done.")),
}
