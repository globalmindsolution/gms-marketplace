"""Calibration plays for create-ticket-import-gh-offline.

IDEAL does what /acs:create-ticket does when the remote pull fails: the
mandatory `acs step start --allocate`, the gh pull (played as the Bash call
it is; its failure is the point), then Finish on failure -- result.json with
status failed and a blocking finding, and the post-hook -- and a reply that
relays gh's error with the canonical hint."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

P = ".acs/state-machine/example-shop"
TICKET = P + "/EVAL-1/ticket.json"
STEP = P + "/runs/EVAL-1/steps/create-ticket"
ERROR = "gh: command not found"


def _start(ws):
    ws.skill("create-ticket")
    started = ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
                     "--title", "(ticket under analysis)", "--args", "#123")
    assert started.returncode == 0, started.stderr
    ws.called("Bash", command="gh issue view 123 --json number,title,body,labels,assignees,url")


def _finish(ws, status):
    result = {"status": status, "summary": "import of #123 blocked: gh issue view failed",
              "states": {"ticket_id": "EVAL-1", "type": "task",
                         "children": [], "prd_trace": {"feature": None, "divergence": None}},
              "findings": [{"severity": "blocking", "area": "tracker",
                            "message": "gh issue view 123 failed", "command": "gh issue view 123",
                            "error": ERROR, "hint": "check `gh auth status` and repo access",
                            "replayable": False}],
              "errors": [ERROR]}
    ws.write(STEP + "/result.json", json.dumps(result))
    # `|| true`: a ticket that does not link the PRD is refused here (ADR-0144),
    # which leaves the step unfinished -- the outcome the graders judge.
    ws.sh('python3 "%s/post-create-ticket.py" --result-file "%s/result.json" || true'
          % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    _finish(ws, "failed")
    ws.reply = ("The import is blocked: `gh issue view 123` failed (%s). Hint: check "
                "`gh auth status` and repo access. Nothing was imported." % ERROR)


def _faked_the_import(ws):
    """Wrote a plausible ticket and a mapping without ever reading the issue."""
    _start(ws)
    with open(os.path.join(ws.path, TICKET), encoding="utf-8") as fh:
        ticket = json.load(fh)
    ticket.update(title="Imported issue 123", acceptance_criteria=["It works"],
                  external={"provider": "github", "key": "123"})
    ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-", stdin=json.dumps(ticket))
    _finish(ws, "completed")
    ws.reply = "Imported #123 as EVAL-1."


def _created_remote(ws):
    """Routed around the failed read by creating a new issue."""
    _start(ws)
    ws.called("Bash", command="gh issue create --title 'Imported 123' --body x")
    _finish(ws, "failed")
    ws.reply = "gh issue view failed, so I created a new issue instead."


def _silent(ws):
    _start(ws)


BAD = {
    "faked the imported ticket and its mapping": _faked_the_import,
    "created a remote issue instead": _created_remote,
    "stopped without Finish or a word": _silent,
}
