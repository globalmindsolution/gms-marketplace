"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:docs-sync does, through its real writers: `acs.py step
start`, a pathspec commit of the doc on the ticket branch (what each doc-updater
slice does), and `post-docs-sync.py` fed the result document on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
STALE = "- `GET /customers?offset=&limit=` lists customers, 20 per page by default.\n"
FRESH = "- `GET /customers?offset=&limit=` lists customers, 50 per page by default.\n"


def _start(ws):
    ws.skill("docs-sync")
    # In a session the Skill call's PreToolUse gate resolves the run; here
    # --ticket names it, which is the same subject.
    started = ws.acs("step", "start", "--step", "docs-sync", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _readme(ws, old, new):
    with open(os.path.join(ws.path, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    assert old in text
    ws.write("README.md", text.replace(old, new))


def _finish(ws, docs):
    result = {"status": "completed",
              "summary": "drift-reviewer passed with zero findings on iteration 1",
              "states": {"docs_committed": docs,
                         "commits": ["EVAL-1 sync the README page size with PAGE_SIZE 50"],
                         "review": {"iterations": 1, "findings_open": 0}},
              "findings": [], "errors": []}
    ws.sh("python3 '%s/post-docs-sync.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(result)))


def _commit(ws, flags=""):
    ws.sh("git add -- README.md && git commit -q %s -m 'EVAL-1 sync the README page size "
          "with PAGE_SIZE 50' -- README.md" % flags)


def IDEAL(ws):
    _start(ws)
    _readme(ws, STALE, FRESH)
    _commit(ws)
    _finish(ws, ["README.md"])
    ws.reply = "Committed README.md on task/EVAL-1-raise-the-customer-page-size-to-50. Next: /acs:create-pr EVAL-1"


def _uncommitted(ws):
    _start(ws)
    _readme(ws, STALE, FRESH)
    _finish(ws, ["README.md"])


def _new_branch(ws):
    _start(ws)
    ws.sh("git checkout -q -b docs/EVAL-1-readme")
    _readme(ws, STALE, FRESH)
    _commit(ws)
    _finish(ws, ["README.md"])


def _amended(ws):
    _start(ws)
    _readme(ws, STALE, FRESH)
    _commit(ws, "--amend")
    _finish(ws, ["README.md"])


def _appended(ws):
    _start(ws)
    _readme(ws, STALE, STALE + "- Since EVAL-1 the page size is 50.\n")
    _commit(ws)
    _finish(ws, ["README.md"])


def _changelog_only(ws):
    _start(ws)
    ws.write("CHANGELOG.md", "- Customers are listed 50 per page.\n", append=True)
    ws.sh("git commit -qm 'EVAL-1 note the page size' -- CHANGELOG.md")
    _finish(ws, ["CHANGELOG.md"])


BAD = {
    "fired the skill and changed nothing": lambda ws: ws.skill("docs-sync"),
    "edited the README but never committed it": _uncommitted,
    "committed the fix on a new branch": _new_branch,
    "amended the code commit": _amended,
    "appended the new value beside the stale one": _appended,
    "updated the changelog and left the README stale": _changelog_only,
}
