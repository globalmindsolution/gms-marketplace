"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:docs-sync does when the working tree carries no change
for the run (ADR-0127: no branch precondition, the changeset is `acs.py
changes diff`), through its real writers: `acs.py step start`, an empty
changeset, and `post-docs-sync.py` fed a completed result with no files.
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


def _finish(ws, status, docs=(), summary=None):
    result = {"status": status,
              "summary": summary or "no changeset: acs.py changes diff is empty, so no doc is owed",
              "states": {"files": list(docs), "review": {"iterations": 0, "findings_open": 0}},
              "findings": [], "errors": []}
    ws.sh("python3 '%s/post-docs-sync.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(result)))


def _fix_readme(ws, commit=True):
    with open(os.path.join(ws.path, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    ws.write("README.md", text.replace(STALE, FRESH))
    if commit:
        ws.sh("git commit -qm 'EVAL-1 sync the README page size' -- README.md")


def IDEAL(ws):
    _start(ws)
    changes = json.loads(ws.acs("changes", "diff", "--name-only", "--run", "EVAL-1").stdout)
    assert changes["files"] == [], changes
    _finish(ws, "completed")
    ws.reply = ("## /acs:docs-sync · EVAL-1 · completed\n\n- **Results**: no changeset -- "
                "`acs.py changes diff` is empty in this working tree, so no doc is owed; "
                "doc files written: none.")


def _switched_and_synced(ws):
    _start(ws)
    ws.sh("git checkout -q %s" % BRANCH)
    _fix_readme(ws)
    _finish(ws, "completed", ["README.md"], "README synced")
    ws.reply = "Switched to the ticket branch and committed README.md."


def _edited_main_readme(ws):
    _start(ws)
    _fix_readme(ws, commit=False)
    _finish(ws, "completed", ["README.md"], "README synced")
    ws.reply = "Updated README.md to 50 per page."


def _failed_on_a_branch_mismatch(ws):
    """The retired precondition: refused because main is not the recorded branch."""
    _start(ws)
    _finish(ws, "failed", summary="branch mismatch: checkout is on main, expected %s" % BRANCH)
    ws.reply = "Branch mismatch: the checkout is on main, not %s. Check it out and re-run." % BRANCH


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("docs-sync"),
    "switched to the ticket branch and synced": _switched_and_synced,
    "edited main's README to the branch's value": _edited_main_readme,
    "failed the step over a branch mismatch": _failed_on_a_branch_mismatch,
}
