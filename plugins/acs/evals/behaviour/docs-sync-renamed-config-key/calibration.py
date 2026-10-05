"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:docs-sync does, through its real writers: `acs.py step
start`, the two doc edits left uncommitted (what the `general` area's
doc-updater does -- ADR-0127: no branch, no commit), and `post-docs-sync.py`
fed the result document on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
OLD, NEW = "SHOP_PAGE_SIZE", "SHOP_CUSTOMERS_PAGE_SIZE"
MSG = "EVAL-1 sync the page-size variable rename in the configuration docs"


def _start(ws):
    ws.skill("docs-sync")
    started = ws.acs("step", "start", "--step", "docs-sync", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _rename(ws, path):
    with open(os.path.join(ws.path, path), encoding="utf-8") as fh:
        text = fh.read()
    assert "`%s`" % OLD in text
    ws.write(path, text.replace("`%s`" % OLD, "`%s`" % NEW))


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


DOCS = ["README.md", "docs/configuration.md"]


def IDEAL(ws):
    _start(ws)
    for path in DOCS:
        _rename(ws, path)
    _finish(ws, DOCS)
    ws.reply = ("Updated README.md and docs/configuration.md (SHOP_PAGE_SIZE -> "
                "SHOP_CUSTOMERS_PAGE_SIZE), left uncommitted. Next: /acs:create-pr EVAL-1")


def _readme_only(ws):
    _start(ws)
    _rename(ws, "README.md")
    _finish(ws, ["README.md"])


def _both_names(ws):
    _start(ws)
    with open(os.path.join(ws.path, "docs/configuration.md"), encoding="utf-8") as fh:
        text = fh.read()
    row = "| `%s` | `20` | Customers per page for `GET /customers`. |\n" % OLD
    ws.write("docs/configuration.md", text.replace(row, row + row.replace(OLD, NEW)))
    _rename(ws, "README.md")
    _finish(ws, DOCS)


def _committed(ws):
    """The pre-ADR-0127 behaviour: a commit -- only /acs:create-pr commits."""
    _start(ws)
    for path in DOCS:
        _rename(ws, path)
    _commit(ws, DOCS)
    _finish(ws, DOCS)


def _amended(ws):
    _start(ws)
    for path in DOCS:
        _rename(ws, path)
    _commit(ws, DOCS, "--amend")
    _finish(ws, DOCS)


BAD = {
    "fired the skill and changed nothing": lambda ws: ws.skill("docs-sync"),
    "fixed only the README": _readme_only,
    "documented both names as settings": _both_names,
    "committed both docs": _committed,
    "amended main's last commit": _amended,
}
