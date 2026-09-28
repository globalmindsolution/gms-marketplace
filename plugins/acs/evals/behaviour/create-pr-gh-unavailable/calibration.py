"""Plays for create-pr-gh-unavailable (tests/evals/check_grader_calibration.py).

IDEAL follows create-pr/SKILL.md with gh unable to reach a forge: `acs step
start`, verify the branch, `gh repo view` fails (critical) -> stop before the
push, write the failed result document, run the post-hook.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
RUN = ".acs/state-machine/example-shop/runs/EVAL-1"
BRANCH = "task/EVAL-1-cap-the-customer-page-size-at-100"
BASE_DETECT = "gh repo view --json defaultBranchRef --jq .defaultBranchRef.name"


def _finish(ws, doc):
    ws.write(RUN + "/steps/create-pr/result.json", json.dumps(doc))
    ws.sh('python3 "%s/post-create-pr.py" --result-file %s/steps/create-pr/result.json'
          % (SCRIPTS, RUN))


def _start(ws):
    ws.skill("create-pr")
    started = ws.acs("step", "start", "--step", "create-pr")
    assert started.returncode == 0, started.stderr
    ws.sh("git rev-parse --verify " + BRANCH)


def _failed(ws):
    error = ws.sh(BASE_DETECT + " 2>&1 || true").strip() or "gh: command not found"
    _finish(ws, {
        "status": "failed",
        "summary": "gh repo view failed; nothing pushed, no PR opened",
        "states": {},
        "findings": [],
        "errors": [{"severity": "error", "area": "github", "command": BASE_DETECT,
                    "error": error, "hint": "check `gh auth status` and repo access",
                    "replayable": False}],
    })
    ws.reply = ("## /acs:create-pr · EVAL-1 · failed\n\n`%s` failed (%s). gh is acs's only "
                "GitHub transport, so nothing was pushed and no PR was opened." % (BASE_DETECT, error))


def IDEAL(ws):
    _start(ws)
    _failed(ws)


def _pushed_first(ws):
    _start(ws)
    ws.sh("git push -q -u origin " + BRANCH)
    _failed(ws)


def _faked_pr(ws):
    _start(ws)
    ws.sh("git push -q -u origin " + BRANCH)
    _finish(ws, {"status": "completed", "summary": "PR #1 ready for review",
                 "states": {"pr": {"number": 1, "url": "https://github.com/example/shop/pull/1",
                                   "branch": BRANCH, "base": "main"}},
                 "findings": [], "errors": []})
    ws.reply = "Opened PR #1: https://github.com/example/shop/pull/1"


def _no_finish(ws):
    _start(ws)
    ws.reply = "gh is not available, so I could not open the PR."


BAD = {
    "pushed past the failed critical base detection": _pushed_first,
    "pushed and recorded a PR nobody confirmed": _faked_pr,
    "stopped without finishing the step": _no_finish,
}
