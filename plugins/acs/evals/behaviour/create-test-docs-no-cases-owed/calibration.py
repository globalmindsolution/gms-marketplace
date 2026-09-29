"""Calibration plays for create-test-docs-no-cases-owed.

IDEAL: the Skill call, which the PreToolUse(Skill) hook settles and refuses
-- played through the real hook, `dispatch.py pre` with the Skill payload
(exit 2, run.json gains the no_cases_owed completion) -- and a reply relaying
it."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-test-docs"
PUBLISHED = "docs/tickets/EVAL-1/test-cases.md"


def _start(ws):
    ws.skill("create-test-docs")
    started = ws.acs("step", "start", "--step", "create-test-docs", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _publish(ws, text):
    ws.write(STEP + "/test-cases.md", text)
    ws.sh('cp "%s/test-cases.md" "%s" && git add "%s" && git commit -qm "EVAL-1 Test cases"'
          % (STEP, PUBLISHED, PUBLISHED))


def _finish(ws, cases, e2e, status="completed", untraced=(), stop_reason=None):
    result = {"status": status, "summary": "calibration",
              "states": {"cases": cases, "e2e_cases": e2e, "untraced_acs": list(untraced)},
              "findings": [], "errors": []}
    if status == "completed":
        result["outcome"] = "cases_written"
    if stop_reason:
        result["stop_reason"] = stop_reason
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-test-docs.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def _gate(ws):
    ws.skill("create-test-docs")
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Skill",
                          "tool_input": {"skill": "acs:create-test-docs", "args": "EVAL-1"},
                          "cwd": ws.path})
    ws.sh("printf '%%s' '%s' | python3 \"%s/dispatch.py\" pre 2>/dev/null; test $? -eq 2"
          % (payload, SCRIPTS))


def IDEAL(ws):
    _gate(ws)
    ws.reply = ("/acs:create-test-docs had nothing to do: it recorded no_cases_owed "
                "(docs-only: CONTRIBUTING.md prose; no behaviour to test).")


def _wrote_cases_anyway(ws):
    """Opened the step by hand and wrote a case table nobody owed."""
    _start(ws)
    _publish(ws, "---\nticket: EVAL-1\ncases: 1\ne2e_cases: 0\n---\n")
    _finish(ws, 1, 0)
    ws.reply = "Test cases written."


def _never_invoked(ws):
    ws.reply = "Nothing to do; the plan owes no test cases."


BAD = {
    "wrote test cases that were not owed": _wrote_cases_anyway,
    "answered without invoking the skill": _never_invoked,
}
