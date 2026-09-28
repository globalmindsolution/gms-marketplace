"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:handoff does: it writes the soft-context flush at
steps/<in-flight step>/handoff-context.md, then lets the real writer,
`handoff.py`, finalize the invocation and the step and release the lock.

Not a BAD play here, because no free grader can see it: running `acs step
start` before the handoff. Measured 2026-09-28, a start on a step already
`in_progress` for this checkout resumes the open invocation (prior_status
in_progress) rather than opening a second, so the ledger reads the same either
way. The baseline criteria carry it instead.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
STEP_DIR = ".acs/state-machine/example-shop/runs/EVAL-1/steps/code"
FLUSH = """# Handoff context — EVAL-1 / code (iteration 1, implementation in flight)

## Done (verified)
- Failing test committed: tests/test_page_cap.py

## Next actions
1. Make tests/test_page_cap.py pass in src/shop/__init__.py.

## User clarifications & decisions
- A limit above 100 is silently clamped to 100, never rejected with a 400.
"""
SUMMARY = ("done: failing cap test committed; in flight: none; next: make "
           "tests/test_page_cap.py pass; decisions: clamp to 100, no 400 -- detail in "
           "steps/code/handoff-context.md")


def _handoff(ws):
    out = ws.sh("python3 '%s/handoff.py' --run EVAL-1 --summary '%s'" % (SCRIPTS, SUMMARY))
    return json.loads(out)


def IDEAL(ws):
    ws.skill("handoff")
    ws.write(STEP_DIR + "/handoff-context.md", FLUSH)
    done = _handoff(ws)
    assert done["continue_with"] == "/acs:code EVAL-1" and done["lock_released"], done
    ws.reply = ("Continue in a fresh session with: %s\n\nFlushed %s/handoff-context.md. "
                "Lock released." % (done["continue_with"], STEP_DIR))


def _flush_only(ws):
    ws.skill("handoff")
    ws.write(STEP_DIR + "/handoff-context.md", FLUSH)
    ws.reply = "Continue with /acs:code EVAL-1. Lock released."


def _no_flush(ws):
    ws.skill("handoff")
    done = _handoff(ws)
    ws.reply = "Continue with %s. Lock released." % done["continue_with"]


def _step_finish(ws):
    ws.skill("handoff")
    ws.write(STEP_DIR + "/handoff-context.md", FLUSH)
    ws.acs("step", "finish", "--step", "code", "--run", "EVAL-1", "--status", "interrupted",
           "--stop-reason", "context_pressure", "--summary", SUMMARY)
    ws.reply = "Continue with /acs:code EVAL-1. Lock released."


def _wrong_command(ws):
    IDEAL(ws)
    ws.reply = "Handed off. Pick it up with /acs:ship EVAL-1 in a new session."


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("handoff"),
    "flushed the context but never ran handoff.py": _flush_only,
    "ran handoff.py without flushing the decision": _no_flush,
    "finalized with step finish instead of handoff.py": _step_finish,
    "printed a continue command of its own": _wrong_command,
}
