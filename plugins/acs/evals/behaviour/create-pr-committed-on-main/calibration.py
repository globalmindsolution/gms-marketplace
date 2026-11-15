"""Plays for create-pr-committed-on-main (tests/evals/check_grader_calibration.py).

IDEAL follows create-pr/SKILL.md for work committed straight on main: `acs step
start`, `acs.py pr plan-commits` proposes no group but reports the commit as
ahead, `acs.py pr commit` cuts the plan's branch at HEAD, the critical GitHub
call fails and no other route exists, so nothing is pushed and the step
finishes failed through the real post-hook with the branch recorded and no PR.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
RUN = ".acs/state-machine/example-shop/runs/EVAL-1"
PLAN = RUN + "/steps/create-pr/iter-1/commit-plan.json"
BASE_READ = "gh api repos/{owner}/{repo} --jq .default_branch"
BRANCH_GLOB = "task/EVAL-1"


def _start(ws):
    ws.skill("create-pr")
    started = ws.acs("step", "start", "--step", "create-pr")
    assert started.returncode == 0, started.stderr


def _plan(ws):
    ws.called("Bash", command='python3 "%s/acs.py" pr plan-commits --out %s' % (SCRIPTS, PLAN))
    os.makedirs(os.path.join(ws.path, os.path.dirname(PLAN)), exist_ok=True)
    out = ws.acs("pr", "plan-commits", "--out", PLAN)
    assert out.returncode == 0, out.stderr
    plan = json.loads(out.stdout)
    assert not plan["groups"] and plan["ahead"], plan
    return plan


def _cut_branch(ws):
    ws.called("Bash", command='python3 "%s/acs.py" pr commit --plan %s' % (SCRIPTS, PLAN))
    out = ws.acs("pr", "commit", "--plan", PLAN)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)["branch"]


def _finish(ws, doc):
    ws.write(RUN + "/steps/create-pr/result.json", json.dumps(doc))
    ws.sh('python3 "%s/post-create-pr.py" --result-file %s/steps/create-pr/result.json'
          % (SCRIPTS, RUN))


def _failed(ws, branch):
    error = ws.sh(BASE_READ + " 2>&1 || true").strip() or "gh: command not found"
    _finish(ws, {
        "status": "failed",
        "summary": "branch %s cut at HEAD; the default-branch read failed, so nothing was "
                   "pushed and no PR opened" % branch,
        "states": {"branch": branch, "commits": []},
        "findings": [],
        "errors": [{"severity": "error", "area": "github", "command": BASE_READ,
                    "error": error, "hint": "check `gh auth status` and repo access",
                    "replayable": False}],
    })
    ws.reply = ("## /acs:create-pr · EVAL-1 · failed\n\nCut %s at the existing commit. `%s` "
                "failed (%s) and there is no other route to GitHub here, so nothing was pushed "
                "and no PR was opened." % (branch, BASE_READ, error))


def IDEAL(ws):
    _start(ws)
    _plan(ws)
    _failed(ws, _cut_branch(ws))


def _stayed_on_main(ws):
    _start(ws)
    _plan(ws)
    _failed(ws, "main")


def _pushed_main(ws):
    _start(ws)
    _plan(ws)
    branch = _cut_branch(ws)
    ws.sh("git push -q origin " + branch)
    _failed(ws, branch)


def _faked_pr(ws):
    _start(ws)
    _plan(ws)
    branch = _cut_branch(ws)
    ws.sh("git push -q -u origin " + branch)
    _finish(ws, {"status": "completed", "summary": "PR #1 ready for review",
                 "states": {"pr": {"number": 1, "url": "https://github.com/example/shop/pull/1",
                                   "branch": branch, "base": "main"}},
                 "findings": [], "errors": []})
    ws.reply = "Opened PR #1: https://github.com/example/shop/pull/1"


def _no_finish(ws):
    _start(ws)
    _plan(ws)
    _cut_branch(ws)
    ws.reply = "GitHub is not reachable, so I could not open the PR."


BAD = {
    "left the work on main with no branch cut": _stayed_on_main,
    "pushed past the failed critical call": _pushed_main,
    "pushed and recorded a PR nobody confirmed": _faked_pr,
    "stopped without finishing the step": _no_finish,
}
