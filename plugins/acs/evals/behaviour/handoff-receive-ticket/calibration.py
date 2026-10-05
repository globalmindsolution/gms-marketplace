"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:handoff does in receive mode: Step 3 runs the real
writer, `acs.py handoff receive EVAL-1`, which applies Lan's work as
uncommitted changes, restores the ticket and run into this workspace and
deletes the remote ref, then shows the note and `continue_with`.

Not a BAD play here, because no free grader can see it: leaving the remote
ref behind. The receive deletes `.eval-origin.git/refs/acs/handoff/EVAL-1`,
a file the scaffold made, and no grader can assert a scaffold-made file is
gone. The baseline criteria carry it instead.
"""

import json


def _receive(ws):
    done = ws.acs("handoff", "receive", "EVAL-1")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def IDEAL(ws):
    ws.skill("handoff")
    got = _receive(ws)
    assert got["continue_with"] == "/acs:code EVAL-1" and got["ref_deleted"], got
    ws.reply = ("Received EVAL-1 from %s (%s).\n\nNote:\n%s\n\nChanged: %s\n\nNext: %s"
                % (got["sender"]["name"], got["sent_at"], got["note"],
                   ", ".join(c["path"] for c in got["work_changes"]), got["continue_with"]))


def _committed_it(ws):
    IDEAL(ws)
    ws.sh("git add -A && git commit -qm 'EVAL-1 from Lan'")


def _work_only(ws):
    ws.skill("handoff")
    ws.sh("git fetch -q origin refs/acs/handoff/EVAL-1 && "
          "git checkout FETCH_HEAD -- work && cp -r work/. . && rm -rf work && git reset -q")
    ws.reply = ("Picked up Lan's work. Her decision: clamp to 100, never a 400. "
                "Next: /acs:code EVAL-1")


def _no_note(ws):
    IDEAL(ws)
    ws.reply = "Received EVAL-1. Next: /acs:code EVAL-1"


def _guessed_command(ws):
    IDEAL(ws)
    ws.reply = ws.reply.replace("/acs:code EVAL-1", "/acs:review-code EVAL-1")


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("handoff"),
    "received, then committed the work": _committed_it,
    "unpacked the work by hand, without the run": _work_only,
    "never showed the note": _no_note,
    "printed a continue command of its own": _guessed_command,
}
