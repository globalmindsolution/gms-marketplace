"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:handoff does with a review in flight: it writes the
soft-context flush at steps/review-code/handoff-context.md (the step run.json
names in_progress), then lets the real writer, `handoff.py`, finalize the
invocation and the step and release the lock.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
RUN = ".acs/state-machine/example-shop/runs/EVAL-1"
FLUSH = """# Handoff context — EVAL-1 / review-code (review in flight)

## Done (verified)
- tests/test_page_cap.py read: the cap test is fine.

## Next actions
1. Review the change in src/shop/__init__.py (the min(limit, 100) clamp).

## User clarifications & decisions
- A negative limit is out of scope for EVAL-1 and gets its own ticket later:
  not a blocking finding in this review.
"""
SUMMARY = ("done: cap test reviewed; in flight: review of src/shop/__init__.py; next: "
           "finish that review; decisions: negative limit out of scope (own ticket) -- "
           "detail in steps/review-code/handoff-context.md")


def _handoff(ws):
    return json.loads(ws.sh("python3 '%s/handoff.py' --run EVAL-1 --summary '%s'"
                            % (SCRIPTS, SUMMARY)))


def IDEAL(ws):
    ws.skill("handoff")
    ws.write(RUN + "/steps/review-code/handoff-context.md", FLUSH)
    done = _handoff(ws)
    assert done["continue_with"] == "/acs:review-code EVAL-1" and done["lock_released"], done
    ws.reply = ("Continue in a fresh session with: %s\n\nFlushed %s/steps/review-code/"
                "handoff-context.md. Lock released." % (done["continue_with"], RUN))


def _flushed_under_code(ws):
    ws.skill("handoff")
    ws.write(RUN + "/steps/code/handoff-context.md", FLUSH)
    done = _handoff(ws)
    ws.reply = "Continue with %s. Lock released." % done["continue_with"]


def _handed_off_code(ws):
    ws.skill("handoff")
    ws.write(RUN + "/steps/review-code/handoff-context.md", FLUSH)
    ws.acs("step", "finish", "--step", "code", "--run", "EVAL-1", "--status", "interrupted",
           "--stop-reason", "context_pressure", "--summary", SUMMARY)
    done = _handoff(ws)
    ws.reply = "Continue with /acs:code EVAL-1. Lock released."


def _step_finish(ws):
    ws.skill("handoff")
    ws.write(RUN + "/steps/review-code/handoff-context.md", FLUSH)
    ws.acs("step", "finish", "--step", "review-code", "--run", "EVAL-1", "--status",
           "interrupted", "--stop-reason", "context_pressure", "--summary", SUMMARY)
    ws.reply = "Continue with /acs:review-code EVAL-1. Lock released."


def _lost_decision(ws):
    ws.skill("handoff")
    ws.write(RUN + "/steps/review-code/handoff-context.md",
             "# Handoff context — EVAL-1 / review-code\n\n## Next actions\n1. Finish the review.\n")
    done = _handoff(ws)
    ws.reply = "Continue with %s. Lock released." % done["continue_with"]


def _wrong_command(ws):
    IDEAL(ws)
    ws.reply = "Handed off. Pick it up with /acs:ship EVAL-1 in a new session. Lock released."


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("handoff"),
    "flushed under steps/code/": _flushed_under_code,
    "handed off the completed code step": _handed_off_code,
    "finalized with step finish instead of handoff.py": _step_finish,
    "flushed without the decision": _lost_decision,
    "printed a continue command of its own": _wrong_command,
}
