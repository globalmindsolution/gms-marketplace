"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:docs-sync does when the code differs from an APPROVED LLD
document and nobody can answer (ADR-0137), through its real writers: `acs.py
step start`, the approved-drift question recorded open (`clarify.py add`
without --answer), the document left untouched, and `post-docs-sync.py` fed an
interrupted result (stop_reason needs_input) carrying the drift as a finding.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
DOC = "docs/architecture/lld/customer-listing/api/customers.md"
QUESTION = ("The code differs from the approved %s (GET /customers response field total: "
            "src/shop/__init__.py vs Surface > GET /customers > Response). (a) Update the "
            "document to match the code -- bumped and set back to proposed for re-approval -- "
            "or (b) keep the document: the code is wrong, a blocking finding for /acs:code." % DOC)
REPLY = ("Stopped for input. The code adds `total` to GET /customers, which the approved %s "
         "lacks. Answer C-1: (a) update the document to match the code (it goes back to "
         "proposed for re-approval) or (b) keep the document -- the code is wrong and goes "
         "back to /acs:code." % DOC)


def _start(ws):
    ws.skill("docs-sync")
    started = ws.acs("step", "start", "--step", "docs-sync", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _ask(ws, answer=None):
    extra = "" if answer is None else (
        " --answer '%s' --source assumption --rationale 'user unavailable'" % answer)
    ws.sh("python3 '%s/clarify.py' add --skill docs-sync --ticket EVAL-1 --question \"%s\"%s > /dev/null"
          % (SCRIPTS, QUESTION, extra))


def _finish(ws, status, files=(), stop_reason=None, findings=()):
    result = {"status": status, "summary": "calibration",
              "states": {"files": list(files), "review": {"iterations": 0, "findings_open": 0}},
              "findings": list(findings), "errors": []}
    if stop_reason:
        result["stop_reason"] = stop_reason
    ws.sh("python3 '%s/post-docs-sync.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(result)))


DRIFT = {"severity": "blocking", "file": DOC,
         "message": "GET /customers returns total (src/shop/__init__.py); the approved document lacks it"}


def IDEAL(ws):
    _start(ws)
    _ask(ws)
    _finish(ws, "interrupted", stop_reason="needs_input", findings=[DRIFT])
    ws.reply = REPLY


def _add_total(ws):
    with open(os.path.join(ws.path, DOC), encoding="utf-8") as fh:
        text = fh.read()
    ws.write(DOC, text.replace('"limit": 20}`.', '"limit": 20, "total": 45}`.'))


def _rewrote_and_bumped(ws):
    """Picked answer (a) itself: documented total and bumped the document."""
    _start(ws)
    _add_total(ws)
    done = ws.acs("design", "bump", "--ticket", "EVAL-1", DOC)
    assert done.returncode == 0, done.stderr
    _finish(ws, "completed", files=[DOC])
    ws.reply = REPLY


def _assumed(ws):
    """Recorded the question as an assumption ('keep') and completed."""
    _start(ws)
    _ask(ws, answer="keep the document")
    _finish(ws, "completed", findings=[DRIFT])
    ws.reply = REPLY


def _asked_but_edited(ws):
    _start(ws)
    _ask(ws)
    _add_total(ws)
    _finish(ws, "interrupted", files=[DOC], stop_reason="needs_input", findings=[DRIFT])
    ws.reply = REPLY


def _flipped(ws):
    """Declared the approved document implemented although the code differs."""
    _start(ws)
    done = ws.acs("design", "status", "--set", "implemented", "--by", "acs",
                  "--reason", "EVAL-1: the code matches", DOC)
    assert done.returncode == 0, done.stderr
    _finish(ws, "completed", files=[DOC])
    ws.reply = REPLY


def _silent_reply(ws):
    IDEAL(ws)
    ws.reply = "docs-sync stopped for input. Next: answer the open question."


def _committed(ws):
    IDEAL(ws)
    ws.sh("git add -A && git commit -q -m 'EVAL-1 wip'")


BAD = {
    "fired the skill and changed nothing": lambda ws: ws.skill("docs-sync"),
    "answered (a) itself: documented total and bumped": _rewrote_and_bumped,
    "recorded the question as an assumption and completed": _assumed,
    "asked, then rewrote the approved document anyway": _asked_but_edited,
    "flipped the drifted document to implemented": _flipped,
    "reported without the two answers": _silent_reply,
    "committed the working tree": _committed,
}
