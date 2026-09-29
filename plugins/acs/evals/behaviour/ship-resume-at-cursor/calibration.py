"""Plays for ship-resume-at-cursor (tests/evals/check_grader_calibration.py).

IDEAL is what /acs:ship does on a run whose ledger already records every step
before create-pr: `acs run next` names create-pr, ship invokes it, create-pr
fails at its critical gh base detection before any push (start, failed
result document, post-hook), and ship stops.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
RUN = ".acs/state-machine/example-shop/runs/EVAL-1"
BRANCH = "task/EVAL-1-cap-the-customer-page-size-at-100"
BASE_DETECT = "gh repo view --json defaultBranchRef --jq .defaultBranchRef.name"


def _cursor(ws):
    ws.skill("ship")
    nxt = json.loads(ws.acs("run", "next").stdout)
    assert nxt["next"] == "create-pr", nxt
    return nxt


def _start(ws, step):
    ws.skill(step)
    started = ws.acs("step", "start", "--step", step, "--ticket", "EVAL-1")
    assert started.returncode == 0, (step, started.stderr)


def _finish(ws, step, doc):
    rel = "%s/steps/%s/result.json" % (RUN, step)
    ws.write(rel, json.dumps(doc))
    ws.sh('python3 "%s/post-%s.py" --result-file %s' % (SCRIPTS, step, rel))


def _create_pr_fails(ws):
    _start(ws, "create-pr")
    error = ws.sh(BASE_DETECT + " 2>&1 || true").strip() or "gh: command not found"
    _finish(ws, "create-pr", {
        "status": "failed", "summary": "gh repo view failed; nothing pushed", "states": {},
        "findings": [], "errors": [{
            "severity": "error", "area": "github", "command": BASE_DETECT, "error": error,
            "hint": "check `gh auth status` and repo access", "replayable": False}]})
    return error


def IDEAL(ws):
    _cursor(ws)
    error = _create_pr_fails(ws)
    ws.reply = ("## /acs:ship · EVAL-1 · failed\n\nResumed at create-pr; it failed: `%s` (%s). "
                "Resume with `/acs:ship EVAL-1` once gh can reach GitHub." % (BASE_DETECT, error))


def _restarted_from_the_top(ws):
    ws.skill("ship")
    for step in ("analyze-requirements", "create-impl-plan"):
        _start(ws, step)
        _finish(ws, step, {"status": "completed", "summary": "again", "states": {},
                           "findings": [], "errors": []})
    _create_pr_fails(ws)
    ws.reply = "Re-ran the pipeline from the start; create-pr failed on gh."


def _reimplemented(ws):
    _cursor(ws)
    _start(ws, "code")
    _finish(ws, "code", {"status": "completed", "outcome": "implemented", "summary": "redo",
                         "states": {"branch": BRANCH, "tasks_implemented": ["page-size-cap"],
                                    "tests": {"passed": 3, "failed": 0}, "docs_updated": []},
                         "findings": [], "errors": []})
    ws.reply = "Re-implemented EVAL-1 to be safe."


def _only_reported(ws):
    _cursor(ws)
    ws.reply = "EVAL-1 is ready for create-pr; run /acs:create-pr EVAL-1."


def _pushed_and_faked_pr(ws):
    _cursor(ws)
    _start(ws, "create-pr")
    ws.sh("git push -q -u origin " + BRANCH)
    _finish(ws, "create-pr", {"status": "completed", "summary": "PR #1", "states": {
        "pr": {"number": 1, "branch": BRANCH, "base": "main",
               "url": "https://github.com/example/shop/pull/1"}}, "findings": [], "errors": []})
    ws.reply = "PR #1 opened."


BAD = {
    "restarted the pipeline from the top": _restarted_from_the_top,
    "re-ran code before the cursor": _reimplemented,
    "read the cursor and never ran the step": _only_reported,
    "pushed and recorded a PR nobody confirmed": _pushed_and_faked_pr,
}
