"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:docs-sync does, through its real writers: `acs.py step
start`, the design's decision record written as the next ADR and committed
with a pathspec commit on the ticket branch (what the `adr` area's
doc-updater does), and `post-docs-sync.py` fed the result document on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
ADR = "docs/adr/0003-store-customers-in-sqlite.md"
ADR_TEXT = """# 3. Store customers in SQLite through the stdlib sqlite3 module

Date: 2026-09-28

## Status

Accepted

## Context

list_customers returned a hard-coded empty list; customers must persist, with
no new third-party dependency (ADR 0002).

## Decision

Customers are stored in SQLite through the stdlib sqlite3 module
(src/shop/store.py). See docs/tickets/EVAL-1/design.md.

## Consequences

A single-writer database file; revisit before running several processes.
"""
MSG = "EVAL-1 record the SQLite store decision as ADR 0003"


def _start(ws):
    ws.skill("docs-sync")
    started = ws.acs("step", "start", "--step", "docs-sync", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _commit(ws, paths, flags=""):
    joined = " ".join(paths)
    ws.sh("git add -- %s && git commit -q %s -m '%s' -- %s" % (joined, flags, MSG, joined))


def _finish(ws, docs):
    result = {"status": "completed",
              "summary": "drift-reviewer passed with zero findings on iteration 1",
              "states": {"files": docs,
                         "review": {"iterations": 1, "findings_open": 0}},
              "findings": [], "errors": []}
    ws.sh("python3 '%s/post-docs-sync.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(result)))


def IDEAL(ws):
    _start(ws)
    ws.write(ADR, ADR_TEXT)
    _finish(ws, [ADR])
    ws.reply = "Wrote %s, left uncommitted. Next: /acs:create-pr EVAL-1" % ADR


def _no_adr(ws):
    _start(ws)
    with open(os.path.join(ws.path, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    ws.write("README.md", text + "\nCustomers are stored in SQLite.\n")
    _finish(ws, ["README.md"])


def _edited_accepted_adr(ws):
    _start(ws)
    path = "docs/adr/0002-serve-http-with-stdlib-wsgi.md"
    with open(os.path.join(ws.path, path), encoding="utf-8") as fh:
        text = fh.read()
    ws.write(path, text + "\nCustomers are now stored in SQLite (stdlib sqlite3).\n")
    _finish(ws, [path])


def _committed(ws):
    """The pre-ADR-0127 behaviour: a commit -- only /acs:create-pr commits."""
    _start(ws)
    ws.write(ADR, ADR_TEXT)
    _commit(ws, [ADR])
    _finish(ws, [ADR])


def _misnumbered(ws):
    _start(ws)
    path = "docs/adr/0001-store-customers-in-sqlite.md"
    ws.write(path, ADR_TEXT)
    _finish(ws, [path])


BAD = {
    "fired the skill and changed nothing": lambda ws: ws.skill("docs-sync"),
    "updated the README and skipped the ADR": _no_adr,
    "appended the decision to accepted ADR 0002": _edited_accepted_adr,
    "committed the ADR": _committed,
    "numbered the ADR over an existing one": _misnumbered,
}
