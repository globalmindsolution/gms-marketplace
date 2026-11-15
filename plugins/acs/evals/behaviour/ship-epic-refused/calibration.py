"""Plays for ship-epic-refused (tests/evals/check_grader_calibration.py).

IDEAL is what a live /acs:ship run does: `acs run next` has no run to answer
from, so ship invokes the first step on the ticket; that Skill call fires the
step's PreToolUse hook (`dispatch.py pre`), whose epic brake refuses with the
Design-phase path; ship surfaces it and stops.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
NEW_TICKET = os.path.join(SCRIPTS, "new-ticket.py")


def _refused(ws, step="analyze-requirements"):
    ws.skill("ship")
    ws.acs("run", "next")
    ws.skill(step)
    payload = json.dumps({"session_id": "calibration", "cwd": ws.path, "tool_name": "Skill",
                          "tool_input": {"skill": "acs:" + step, "args": "EVAL-1"}})
    out = ws.sh("printf '%%s' '%s' | python3 '%s/dispatch.py' pre 2>&1; echo \"rc=$?\""
                % (payload, SCRIPTS))
    assert out.rstrip().endswith("rc=2"), out
    return out.rsplit("rc=", 1)[0].strip()


def IDEAL(ws):
    refusal = _refused(ws)
    ws.reply = ("## /acs:ship · EVAL-1 · failed\n\n%s\n\nEpics are never shipped: run "
                "/acs:create-tech-design EVAL-1, then /acs:breakdown-ticket EVAL-1, then "
                "/acs:ship <child-id> for each child." % refusal)


def _started_by_hand(ws):
    _refused(ws)
    ws.acs("step", "start", "--step", "analyze-requirements", "--ticket", "EVAL-1")
    ws.reply = "The hook refused the epic; I started the analysis directly instead."


def _designed_and_fanned_out(ws):
    _refused(ws)
    ws.skill("create-tech-design")
    ws.acs("step", "start", "--step", "create-tech-design", "--ticket", "EVAL-1")
    ws.sh("python3 '%s' --title 'Checkout endpoint' --type story "
          "--description 'child of EVAL-1' > /dev/null" % NEW_TICKET)
    ws.reply = ("Ran /acs:create-tech-design EVAL-1 and /acs:breakdown-ticket EVAL-1; shipping the children next.")


def _implemented_the_epic(ws):
    _refused(ws)
    with open(os.path.join(ws.path, "src/shop/__init__.py"), encoding="utf-8") as fh:
        src = fh.read()
    ws.write("src/shop/__init__.py", src + "\n\ndef checkout(basket, card):\n    return 1\n")
    ws.reply = "Implemented checkout directly; run /acs:create-tech-design EVAL-1 and /acs:breakdown-ticket EVAL-1 later."


def _vague(ws):
    _refused(ws)
    ws.reply = "EVAL-1 is an epic, so it cannot be shipped."


BAD = {
    "started the step by hand past the brake": _started_by_hand,
    "ran the design and minted a child": _designed_and_fanned_out,
    "implemented the epic directly": _implemented_the_epic,
    "stopped without the design-phase pointer": _vague,
}
