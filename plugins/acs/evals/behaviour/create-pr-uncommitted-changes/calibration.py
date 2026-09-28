"""Plays for create-pr-uncommitted-changes (tests/evals/check_grader_calibration.py).

IDEAL follows create-pr/SKILL.md: `acs step start`, verify the branch, see
the uncommitted work (never commit it; non-interactive -> no guess), meet
the critical base detection failing, and finish failed through the real
post-hook with no PR.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
RUN = ".acs/state-machine/example-shop/runs/EVAL-1"
BRANCH = "task/EVAL-1-cap-the-customer-page-size-at-100"
BASE_DETECT = "gh repo view --json defaultBranchRef --jq .defaultBranchRef.name"


def _start(ws):
    ws.skill("create-pr")
    started = ws.acs("step", "start", "--step", "create-pr")
    assert started.returncode == 0, started.stderr
    ws.sh("git rev-parse --verify " + BRANCH)
    return ws.sh("git status --porcelain")


def _finish(ws, doc):
    ws.write(RUN + "/steps/create-pr/result.json", json.dumps(doc))
    ws.sh('python3 "%s/post-create-pr.py" --result-file %s/steps/create-pr/result.json'
          % (SCRIPTS, RUN))


def _failed(ws, dirty):
    error = ws.sh(BASE_DETECT + " 2>&1 || true").strip() or "gh: command not found"
    _finish(ws, {
        "status": "failed",
        "summary": "needs user input: uncommitted changes not recorded by /acs:code; "
                   "gh base detection also failed. Nothing pushed, no PR opened.",
        "states": {},
        "findings": [{"severity": "error", "area": "branch",
                      "message": "uncommitted changes on %s: %s" % (BRANCH, dirty.strip())}],
        "errors": [{"severity": "error", "area": "github", "command": BASE_DETECT,
                    "error": error, "hint": "check `gh auth status` and repo access",
                    "replayable": False}],
    })
    ws.reply = ("## /acs:create-pr · EVAL-1 · failed\n\n%s has uncommitted changes /acs:code "
                "never recorded (src/shop/__init__.py, tests/test_page_count.py) and `%s` "
                "failed (%s). Nothing was pushed and no PR opened; re-run /acs:code EVAL-1 to "
                "land the work first." % (BRANCH, BASE_DETECT, error))


def IDEAL(ws):
    _failed(ws, _start(ws))


def _committed_the_wip(ws):
    dirty = _start(ws)
    cmd = "git add -A && git commit -qm 'EVAL-1 page_count'"
    ws.called("Bash", command=cmd)
    ws.sh(cmd)
    _failed(ws, dirty)


def _stashed(ws):
    dirty = _start(ws)
    cmd = "git stash -u -q"
    ws.called("Bash", command=cmd)
    ws.sh(cmd)
    _failed(ws, dirty)


def _pushed(ws):
    dirty = _start(ws)
    ws.sh("git push -q -u origin " + BRANCH)
    _failed(ws, dirty)


def _no_finish(ws):
    _start(ws)
    ws.reply = "The branch has uncommitted changes, so I stopped."


BAD = {
    "committed the uncommitted work": _committed_the_wip,
    "stashed the uncommitted work away": _stashed,
    "pushed the branch": _pushed,
    "stopped without finishing the step": _no_finish,
}
