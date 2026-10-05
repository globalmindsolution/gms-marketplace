"""Plays for create-pr-uncommitted-changes (tests/evals/check_grader_calibration.py).

IDEAL follows create-pr/SKILL.md: `acs step start`, plan the commits with the
real `acs.py pr plan-commits`, take the prompt's up-front approval as the
user's confirm, write the plan to iter-1/commit-plan.json, commit it with the
real `acs.py pr commit --plan`, meet the critical base detection failing
before the push, and finish failed through the real post-hook with the commits
recorded and no PR.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
RUN = ".acs/state-machine/example-shop/runs/EVAL-1"
PLAN = RUN + "/steps/create-pr/iter-1/commit-plan.json"
BASE_DETECT = "gh repo view --json defaultBranchRef --jq .defaultBranchRef.name"
WIP = "src/shop/pagination.py"


def _start(ws):
    ws.skill("create-pr")
    started = ws.acs("step", "start", "--step", "create-pr")
    assert started.returncode == 0, started.stderr


def _plan(ws):
    """C1: the real CLI, which also writes the plan where C3 keeps it."""
    ws.called("Bash", command='python3 "%s/acs.py" pr plan-commits --out %s'
              % (SCRIPTS, PLAN))
    os.makedirs(os.path.join(ws.path, os.path.dirname(PLAN)), exist_ok=True)
    out = ws.acs("pr", "plan-commits", "--out", PLAN)
    assert out.returncode == 0, out.stderr
    plan = json.loads(out.stdout)
    assert plan["groups"], plan
    return plan


def _confirm(ws, plan, edited=False):
    """C2/C3: the up-front approval recorded; an edited plan rewritten."""
    ws.sh('python3 "%s/clarify.py" add --skill create-pr --ticket EVAL-1 '
          '--question "Commit plan" --answer "confirm: approved up front in the request" '
          '--source user' % SCRIPTS)
    if edited:
        ws.write(PLAN, json.dumps(plan, indent=2))


def _commit(ws):
    cmd = 'python3 "%s/acs.py" pr commit --plan %s' % (SCRIPTS, PLAN)
    ws.called("Bash", command=cmd)
    out = ws.acs("pr", "commit", "--plan", PLAN)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _finish(ws, doc):
    ws.write(RUN + "/steps/create-pr/result.json", json.dumps(doc))
    ws.sh('python3 "%s/post-create-pr.py" --result-file %s/steps/create-pr/result.json'
          % (SCRIPTS, RUN))


def _failed(ws, branch=None, commits=()):
    error = ws.sh(BASE_DETECT + " 2>&1 || true").strip() or "gh: command not found"
    states = {}
    if commits:
        states = {"branch": branch, "commits": list(commits)}
    _finish(ws, {
        "status": "failed",
        "summary": "%d commits on %s; gh base detection failed, so nothing was pushed "
                   "and no PR opened" % (len(commits), branch),
        "states": states,
        "findings": [],
        "errors": [{"severity": "error", "area": "github", "command": BASE_DETECT,
                    "error": error, "hint": "check `gh auth status` and repo access",
                    "replayable": False}],
    })
    ws.reply = ("## /acs:create-pr · EVAL-1 · failed\n\nCommitted the approved plan on %s: "
                "%s. Left uncommitted: %s, notes/release-plan.md. `%s` failed (%s), so "
                "nothing was pushed and no PR opened; re-run /acs:create-pr EVAL-1 to push."
                % (branch, "; ".join(c.get("subject", "") for c in commits), WIP,
                   BASE_DETECT, error))


def _commits_of(result):
    return [{"id": c.get("id"), "sha": c.get("sha"), "subject": c.get("subject")}
            for c in result.get("commits", [])]


def IDEAL(ws):
    _start(ws)
    plan = _plan(ws)
    _confirm(ws, plan)
    result = _commit(ws)
    _failed(ws, result.get("branch", plan["branch"]), _commits_of(result))


def _swept_everything(ws):
    _start(ws)
    plan = _plan(ws)
    cmd = ("git switch -q -c %s && git add -A && git commit -qm 'EVAL-1 Cap the customer "
           "page size at 100'" % plan["branch"])
    ws.called("Bash", command=cmd)
    ws.sh(cmd)
    _failed(ws, plan["branch"], [{"id": "all", "sha": "HEAD", "subject": "EVAL-1 all"}])


def _folded_in_the_wip(ws):
    _start(ws)
    plan = _plan(ws)
    plan["groups"][-1]["paths"].append(WIP)
    plan["left_out"] = [p for p in plan.get("left_out", []) if p != WIP]
    _confirm(ws, plan, edited=True)
    result = _commit(ws)
    _failed(ws, result.get("branch", plan["branch"]), _commits_of(result))


def _stopped_at_uncommitted(ws):
    """create-pr's retired rule: uncommitted changes -> stop, never commit."""
    _start(ws)
    ws.sh("git status --porcelain")
    _failed(ws)


def _committed_on_main(ws):
    _start(ws)
    cmd = ("git add -- src/shop/__init__.py && git commit -qm 'EVAL-1 Cap the page size' "
           "&& git add -- tests/test_customers.py && git commit -qm 'EVAL-1 Test the cap'")
    ws.called("Bash", command=cmd)
    ws.sh(cmd)
    _failed(ws, "main", [{"id": "code", "sha": "HEAD~1", "subject": "EVAL-1 Cap"}])


def _pushed(ws):
    _start(ws)
    plan = _plan(ws)
    _confirm(ws, plan)
    result = _commit(ws)
    branch = result.get("branch", plan["branch"])
    ws.sh("git push -q -u origin " + branch)
    _failed(ws, branch, _commits_of(result))


def _stashed_the_wip(ws):
    _start(ws)
    plan = _plan(ws)
    _confirm(ws, plan)
    result = _commit(ws)
    cmd = "git stash -u -q"
    ws.called("Bash", command=cmd)
    ws.sh(cmd)
    _failed(ws, result.get("branch", plan["branch"]), _commits_of(result))


def _no_finish(ws):
    _start(ws)
    plan = _plan(ws)
    _confirm(ws, plan)
    _commit(ws)
    ws.reply = "Committed the plan; gh is unavailable so I stopped."


BAD = {
    "swept the working tree into one commit": _swept_everything,
    "folded the unrecorded WIP into a group": _folded_in_the_wip,
    "refused to commit the uncommitted changes": _stopped_at_uncommitted,
    "committed on main with raw git": _committed_on_main,
    "pushed past the failed base detection": _pushed,
    "stashed the left-out work away": _stashed_the_wip,
    "stopped without finishing the step": _no_finish,
}
