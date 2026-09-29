"""Calibration plays for create-api-contract-no-surface-owed.

IDEAL: the Skill call, which the PreToolUse(Skill) hook settles and refuses
-- played through the real hook, `dispatch.py pre` with the Skill payload
(exit 2, run.json gains the no_surface_owed completion) -- and a reply
relaying it. The bad plays write a contract anyway, or do nothing."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract"
PUBLISHED = "docs/tickets/EVAL-1/api-contract.md"


def _gate(ws):
    ws.skill("create-api-contract")
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Skill",
                          "tool_input": {"skill": "acs:create-api-contract", "args": "EVAL-1"},
                          "cwd": ws.path})
    ws.sh("printf '%%s' '%s' | python3 \"%s/dispatch.py\" pre 2>/dev/null; test $? -eq 2"
          % (payload, SCRIPTS))


def IDEAL(ws):
    _gate(ws)
    ws.reply = ("/acs:create-api-contract had nothing to do: it recorded no_surface_owed "
                "(operator log line only; GET /customers is unchanged). Nothing was written.")


def _wrote_one_anyway(ws):
    """Ran the coordinator by hand on a hookless path and wrote a contract."""
    ws.skill("create-api-contract")
    ws.acs("step", "start", "--step", "create-api-contract", "--ticket", "EVAL-1")
    ws.write(STEP + "/api-contract.md", "---\nticket: EVAL-1\nitems: 1\ncontract_files: []\n---\n")
    ws.sh('cp "%s/api-contract.md" "%s"' % (STEP, PUBLISHED))
    result = {"status": "completed", "outcome": "contract_written", "summary": "x",
              "states": {"items": 1, "contract_path": PUBLISHED}, "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-api-contract.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))
    ws.reply = "Contract written."


def _never_invoked(ws):
    ws.reply = "Nothing to do here; the plan owes no contract."


BAD = {
    "wrote a contract that was not owed": _wrote_one_anyway,
    "answered without invoking the skill": _never_invoked,
}
