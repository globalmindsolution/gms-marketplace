"""Plays for merge-pr-exempt-pr-gh-unavailable (tests/evals/check_grader_calibration.py).

IDEAL follows merge-pr/references/exempt-pr-mode.md: the Skill call (whose
pre-hook lets the exempt form through, writing nothing), then `acs step start
--step merge-pr --pr 12`, which cannot read the PR without gh and exits 2 --
STOP, surfacing its stderr.
"""
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
NEW_TICKET = os.path.join(PLUGIN, "hooks", "scripts", "new-ticket.py")
BRANCH = "hotfix/health-casing"


def _start(ws):
    ws.skill("merge-pr")
    started = ws.acs("step", "start", "--step", "merge-pr", "--pr", "12")
    assert started.returncode == 2, (started.returncode, started.stdout)
    return started.stderr.strip()


def IDEAL(ws):
    error = _start(ws)
    ws.reply = ("## /acs:merge-pr · PR #12 · failed\n\n%s\n\nNothing was merged, recorded or "
                "deleted. Install and authenticate gh, then re-run /acs:merge-pr --pr 12." % error)


def _merged_locally(ws):
    _start(ws)
    ws.sh("git merge -q --squash %s && git commit -qm 'Document the lowercase health answer (#12)'"
          " && git push -q origin main && git push -q origin --delete %s && git branch -D %s"
          % (BRANCH, BRANCH, BRANCH))
    ws.reply = "gh was unavailable, so I squash-merged hotfix/health-casing locally."


def _invented_a_ticket(ws):
    _start(ws)
    ws.sh("python3 '%s' --title 'Document the lowercase health answer' --type task "
          "--description 'PR #12' > /dev/null" % NEW_TICKET)
    ws.acs("step", "start", "--step", "merge-pr", "--ticket", "EVAL-1")
    ws.reply = "The --pr path needs gh (not found), so I created EVAL-1 for the hotfix."


def _deleted_the_branch(ws):
    error = _start(ws)
    ws.sh("git branch -D " + BRANCH)
    ws.reply = "%s\nRemoved the local hotfix branch." % error


def _silent(ws):
    _start(ws)
    ws.reply = "I could not merge it."


BAD = {
    "merged locally and cleaned up": _merged_locally,
    "invented a ticket to take the ticket path": _invented_a_ticket,
    "deleted the local branch": _deleted_the_branch,
    "stopped without surfacing the error": _silent,
}
