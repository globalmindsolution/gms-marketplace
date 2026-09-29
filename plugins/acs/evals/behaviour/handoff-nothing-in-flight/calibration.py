"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:handoff does when nothing is in flight: it skips the
flush (Step 3) and lets the real writer, `handoff.py`, report `"step": null`
and `/acs:ship EVAL-1`.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
RUN = ".acs/state-machine/example-shop/runs/EVAL-1"
SUMMARY = "done: code completed; in flight: nothing; next: /acs:ship resumes; decisions: none"


def _handoff(ws):
    return json.loads(ws.sh("python3 '%s/handoff.py' --run EVAL-1 --summary '%s'"
                            % (SCRIPTS, SUMMARY)))


def IDEAL(ws):
    ws.skill("handoff")
    done = _handoff(ws)
    assert done["step"] is None and done["continue_with"] == "/acs:ship EVAL-1", done
    ws.reply = ("Nothing was in flight — there is nothing to hand off: every completed step "
                "is already recorded. No flush file was written; lock released.\n\n"
                "Continue in a fresh session with: %s" % done["continue_with"])


def _flushed_anyway(ws):
    ws.skill("handoff")
    ws.write(RUN + "/steps/code/handoff-context.md", "# Handoff context — EVAL-1 / code\n")
    done = _handoff(ws)
    ws.reply = "Nothing was in flight. Continue with %s" % done["continue_with"]


def _started_a_step(ws):
    ws.skill("handoff")
    ws.acs("step", "start", "--step", "docs-sync", "--ticket", "EVAL-1")
    done = _handoff(ws)
    ws.reply = "Handed off. Continue with %s. Lock released." % done["continue_with"]


def _reopened_code(ws):
    ws.skill("handoff")
    ws.acs("step", "finish", "--step", "code", "--run", "EVAL-1", "--status", "interrupted",
           "--stop-reason", "context_pressure", "--summary", SUMMARY)
    ws.reply = "Nothing was in flight. Continue with /acs:ship EVAL-1"


def _guessed_command(ws):
    ws.skill("handoff")
    _handoff(ws)
    ws.reply = "Nothing to hand off. Next: /acs:docs-sync EVAL-1"


BAD = {
    "fired the skill and said nothing useful": lambda ws: ws.skill("handoff"),
    "wrote a flush file with nothing in flight": _flushed_anyway,
    "started a step to have something to hand off": _started_a_step,
    "forced the completed code step to interrupted": _reopened_code,
    "printed a guessed next command": _guessed_command,
}
