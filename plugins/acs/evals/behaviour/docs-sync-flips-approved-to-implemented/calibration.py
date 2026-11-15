"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:docs-sync does on an approved LLD document the code fully
matches (ADR-0137), through its real writers: `acs.py step start`, nothing
edited (the gap analyst found every element matching), then -- the drift
review passed -- the flip through `acs.py design status --set implemented --by
acs --reason ...`, and `post-docs-sync.py` fed the result document with the
flipped path in `files` (its front matter changed) and `implemented`.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
DOC = "docs/architecture/lld/customer-listing/data/physical-schema.md"


def _start(ws):
    ws.skill("docs-sync")
    started = ws.acs("step", "start", "--step", "docs-sync", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _flip(ws):
    done = ws.acs("design", "status", "--set", "implemented", "--by", "acs",
                  "--reason", "EVAL-1: the code matches", DOC)
    assert done.returncode == 0, done.stderr


def _finish(ws, files, implemented):
    result = {"status": "completed",
              "summary": "drift-reviewer passed with zero findings on iteration 1",
              "states": {"files": files, "implemented": implemented,
                         "review": {"iterations": 1, "findings_open": 0}},
              "findings": [], "errors": []}
    ws.sh("python3 '%s/post-docs-sync.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(result)))


def IDEAL(ws):
    _start(ws)
    _flip(ws)
    _finish(ws, [DOC], [DOC])
    ws.reply = ("%s: approved -> implemented (the code matches it), left uncommitted. "
                "Next: /acs:create-pr EVAL-1" % DOC)


def _hand_edited(ws):
    """Rewrote the status line itself: no status_by/at/reason recorded."""
    _start(ws)
    path = os.path.join(ws.path, DOC)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    ws.write(DOC, text.replace('status: "approved"', 'status: "implemented"', 1))
    _finish(ws, [DOC], [DOC])


def _bumped(ws):
    """Treated the matching document as stale: bumped it back to proposed v2."""
    _start(ws)
    done = ws.acs("design", "bump", "--ticket", "EVAL-1", DOC)
    assert done.returncode == 0, done.stderr
    _finish(ws, [DOC], [])


def _left_approved(ws):
    _start(ws)
    _finish(ws, [], [])


def _not_recorded(ws):
    _start(ws)
    _flip(ws)
    _finish(ws, [DOC], [])


def _committed(ws):
    _start(ws)
    _flip(ws)
    ws.sh("git add -- %s && git commit -q -m 'EVAL-1 physical schema implemented' -- %s" % (DOC, DOC))
    _finish(ws, [DOC], [DOC])


BAD = {
    "fired the skill and changed nothing": lambda ws: ws.skill("docs-sync"),
    "hand-edited the status line": _hand_edited,
    "bumped the matching document back to proposed": _bumped,
    "left the document approved": _left_approved,
    "flipped it but left states.implemented empty": _not_recorded,
    "committed the flip": _committed,
}
