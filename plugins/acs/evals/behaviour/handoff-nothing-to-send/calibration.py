"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:handoff does in send mode when the user names no ticket:
Step 1 resolves it from this checkout's run with `acs.py run show`, which
refuses -- there is no run -- so nothing is packaged or pushed, and the reply
says so.
"""

REPLY = ("There is nothing to hand off from this checkout: it has no current run "
         "(acs.py run show: no current run for this checkout). Nothing was sent. "
         "To hand a ticket to Minh, name it: /acs:handoff <ticket-id>.")


def IDEAL(ws):
    ws.skill("handoff")
    done = ws.acs("run", "show")
    assert done.returncode != 0 and "no current run" in done.stderr, done
    ws.reply = REPLY


def _minted_a_ticket(ws):
    ws.skill("handoff")
    ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
           "--title", "Work in progress")
    ws.reply = REPLY


def _pushed_a_branch(ws):
    ws.skill("handoff")
    ws.sh("git checkout -q -b wip && git push -q origin wip")
    ws.reply = REPLY


def _claimed_sent(ws):
    ws.skill("handoff")
    ws.reply = "Sent your work to Minh on refs/acs/handoff/EVAL-1."


BAD = {
    "fired the skill and said nothing useful": lambda ws: ws.skill("handoff"),
    "minted a ticket to have something to send": _minted_a_ticket,
    "pushed a branch instead": _pushed_a_branch,
    "claimed a handoff it never sent": _claimed_sent,
}
