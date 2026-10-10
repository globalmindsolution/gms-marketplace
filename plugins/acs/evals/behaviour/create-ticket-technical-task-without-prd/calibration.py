"""Calibration plays for create-ticket-technical-task-without-prd (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--allocate`, the task author and the reviewer, Step 3's `acs.py ticket save`
with no features (no PRD, and a technical task needs none, ADR-0144), then
result.json and the post-hook, which completes it."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-ticket"
TASK = {"title": "Run the test suite on Python 3.13 and drop 3.11", "type": "task",
        "priority": "medium", "children": [],
        "description": "## Summary\n\nMove the test runner to Python 3.13.\n\n## Notes\n\nacs-ticket: EVAL-1\n",
        "acceptance_criteria": ["CI runs the unit suite on Python 3.13",
                                "The CI matrix no longer lists Python 3.11"]}


def _start(ws, author="task-author"):
    ws.skill("create-ticket")
    started = ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
                     "--title", "(ticket under analysis)", "--args", "Move the test runner to 3.13")
    assert started.returncode == 0, started.stderr
    ws.called("Agent", subagent_type="acs:create-ticket-" + author,
              prompt='<task skill="create-ticket" phase="%s" ticket-id="EVAL-1" iteration="1">'
              % author)
    ws.called("Agent", subagent_type="acs:create-ticket-reviewer",
              prompt='<task skill="create-ticket" phase="reviewer" ticket-id="EVAL-1" iteration="1">')


def _save(ws, fields):
    saved = ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-",
                   stdin=json.dumps(fields))
    assert saved.returncode == 0, saved.stderr


def _finish(ws, status, ttype="task"):
    ws.write(STEP + "/result.json", json.dumps({
        "status": status, "summary": "task created; reviewer passed on iteration 1",
        "states": {"ticket_id": "EVAL-1", "type": ttype, "children": [],
                   "prd_trace": {"feature": None, "divergence": None}},
        "findings": [], "errors": []}))
    # `|| true`: a link the PRD cannot back is refused here, leaving the step open.
    ws.sh('python3 "%s/post-create-ticket.py" --result-file "%s/result.json" || true'
          % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    _save(ws, TASK)
    _finish(ws, "completed")
    ws.reply = "Created EVAL-1 (task): run the test suite on Python 3.13 and drop 3.11."


def _refused_for_a_prd(ws):
    _start(ws)
    _finish(ws, "failed")
    ws.reply = "There is no PRD; write one with /acs:create-prd first."


def _invented_a_feature(ws):
    _start(ws)
    _save(ws, dict(TASK, features=["ci"]))
    _finish(ws, "completed")


def _typed_a_story(ws):
    _start(ws, "story-author")
    _save(ws, dict(TASK, type="story"))
    _finish(ws, "completed", "story")


BAD = {
    "refused for want of a PRD": _refused_for_a_prd,
    "invented a feature link": _invented_a_feature,
    "typed it a story": _typed_a_story,
}
