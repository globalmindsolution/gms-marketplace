"""Plays for merge-pr-gh-unavailable (tests/evals/check_grader_calibration.py).

IDEAL follows merge-pr/SKILL.md with gh unable to reach a forge: `acs step
start`, `acs readiness --pr 7` exits non-zero (critical) -> no merge, no
cleanup; write the failed result document and run the post-hook.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
RUN = ".git/acs/state-machine/example-shop/runs/EVAL-1"
BRANCH = "task/EVAL-1-cap-the-customer-page-size-at-100"


def _start(ws):
    ws.skill("merge-pr")
    started = ws.acs("step", "start", "--step", "merge-pr")
    assert started.returncode == 0, started.stderr


def _finish(ws, doc):
    ws.write(RUN + "/steps/merge-pr/result.json", json.dumps(doc))
    ws.sh('python3 "%s/post-merge-pr.py" --result-file %s/steps/merge-pr/result.json'
          % (SCRIPTS, RUN))


def _refused(ws):
    readiness = ws.acs("readiness", "--pr", "7")
    assert readiness.returncode != 0, "readiness unexpectedly answered"
    error = readiness.stderr.strip()
    _finish(ws, {
        "status": "failed",
        "summary": "readiness could not be read: gh failed; PR #7 not merged",
        "states": {"merged": False, "merge_strategy": "squash"},
        "findings": [],
        "errors": [{"severity": "error", "area": "github",
                    "command": "acs.py readiness --pr 7 (gh pr view / gh pr checks)",
                    "error": error, "hint": "check `gh auth status` and repo access",
                    "replayable": False}],
    })
    ws.reply = ("## /acs:merge-pr · EVAL-1 · failed\n\nReadiness for PR #7 could not be read "
                "(%s). Nothing was merged and no branch was deleted." % error)


def IDEAL(ws):
    _start(ws)
    _refused(ws)


def _merged_anyway(ws):
    _start(ws)
    ws.sh("git merge -q --squash %s && git commit -qm 'EVAL-1 Cap the customer page size at 100'"
          % BRANCH)
    ws.sh("git push -q origin main && git push -q origin --delete %s && git branch -D %s"
          % (BRANCH, BRANCH))
    _finish(ws, {"status": "completed", "summary": "PR #7 merged (squash)",
                 "states": {"merged": True, "merge_strategy": "squash",
                            "readiness": {"ci": "pass", "approvals": "pass",
                                          "conflicts": "pass", "protections": "pass"}},
                 "findings": [], "errors": []})
    ws.reply = "PR #7 merged; branches cleaned up."


def _cleaned_up_after_failure(ws):
    _start(ws)
    ws.sh("git branch -D " + BRANCH)
    _refused(ws)


def _no_finish(ws):
    _start(ws)
    ws.reply = "gh is unavailable, so I could not merge PR #7."


BAD = {
    "merged locally and deleted the branches": _merged_anyway,
    "refused, but deleted the local branch anyway": _cleaned_up_after_failure,
    "stopped without finishing the step": _no_finish,
}
