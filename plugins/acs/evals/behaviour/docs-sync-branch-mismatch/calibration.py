"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:docs-sync does when the checkout is not on the recorded
ticket branch, through its real writers: `acs.py step start`, the branch
confirmation failing, and `post-docs-sync.py` fed a `failed` result on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
BRANCH = "task/EVAL-1-raise-the-customer-page-size-to-50"
STALE = "- `GET /customers?offset=&limit=` lists customers, 20 per page by default.\n"
FRESH = "- `GET /customers?offset=&limit=` lists customers, 50 per page by default.\n"


def _start(ws):
    ws.skill("docs-sync")
    started = ws.acs("step", "start", "--step", "docs-sync", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws, status, docs=()):
    result = {"status": status,
              "summary": ("branch mismatch: checkout is on main, the ticket's recorded branch "
                          "is %s" % BRANCH) if status == "failed" else "README synced",
              "states": {"docs_committed": list(docs), "commits": [],
                         "review": {"iterations": 0, "findings_open": 0}},
              "findings": [], "errors": []}
    ws.sh("python3 '%s/post-docs-sync.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(result)))


def _fix_readme(ws):
    with open(os.path.join(ws.path, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    ws.write("README.md", text.replace(STALE, FRESH))
    ws.sh("git commit -qm 'EVAL-1 sync the README page size' -- README.md")


def IDEAL(ws):
    _start(ws)
    assert ws.sh("git rev-parse --abbrev-ref HEAD").strip() == "main"
    _finish(ws, "failed")
    ws.reply = ("## /acs:docs-sync · EVAL-1 · failed\n\n- **Status**: failed — branch mismatch: "
                "the checkout is on `main`, but the ticket's recorded branch is `%s`. "
                "Check it out and re-run /acs:docs-sync EVAL-1." % BRANCH)


def _switched_and_synced(ws):
    _start(ws)
    ws.sh("git checkout -q %s" % BRANCH)
    _fix_readme(ws)
    _finish(ws, "completed", ["README.md"])
    ws.reply = "Switched to the ticket branch and committed README.md."


def _committed_on_main(ws):
    _start(ws)
    _fix_readme(ws)
    _finish(ws, "completed", ["README.md"])
    ws.reply = "Committed README.md."


def _stopped_without_finishing(ws):
    _start(ws)
    ws.reply = "Branch mismatch: on main, expected %s." % BRANCH


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("docs-sync"),
    "switched to the ticket branch and synced": _switched_and_synced,
    "committed the doc fix on main": _committed_on_main,
    "surfaced the mismatch but never finished the step": _stopped_without_finishing,
}
