"""Calibration plays for create-ticket-question-not-work.

IDEAL reads the existing ticket and answers; no skill runs. The bad plays
fire create-ticket (which mints EVAL-2 as its mandatory first action) or
answer without the facts."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")


def IDEAL(ws):
    ws.sh("cat .git/acs/state-machine/example-shop/EVAL-1/ticket.json > /dev/null")
    ws.reply = ("Yes: EVAL-1, \"Cursor pagination for GET /customers\" (story), already "
                "covers it. It has 3 acceptance criteria.")


def _minted(ws):
    ws.skill("create-ticket")
    ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
           "--title", "(ticket under analysis)", "--args", "cursor pagination question")
    ws.reply = "I created EVAL-2 for cursor pagination with 3 acceptance criteria."


def _guessed(ws):
    ws.reply = "I don't see a ticket for that; you may want to create one."


BAD = {
    "ran create-ticket on a question": _minted,
    "answered without reading the workspace": _guessed,
}
