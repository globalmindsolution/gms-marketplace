"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:docs-sync does on a changeset with no doc impact, through
its real writers: `acs.py step start`, no commit (every area's doc-updater
reports no delta), and `post-docs-sync.py` fed a completed result with an empty
docs_committed on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))


def _start(ws):
    ws.skill("docs-sync")
    started = ws.acs("step", "start", "--step", "docs-sync", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws, docs):
    result = {"status": "completed",
              "summary": "no doc impact: the diff extracts a private helper with no behaviour "
                         "change; drift-reviewer passed with zero findings on iteration 1",
              "states": {"files": docs,
                         "review": {"iterations": 1, "findings_open": 0}},
              "findings": [], "errors": []}
    ws.sh("python3 '%s/post-docs-sync.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(result)))


def IDEAL(ws):
    _start(ws)
    _finish(ws, [])
    ws.reply = ("## /acs:docs-sync · EVAL-1 · completed\n\n- **Results**: no doc files "
                "written — no doc impact (internal refactor); 1 review iteration, "
                "0 open findings\n- **Next**: `/acs:create-pr EVAL-1`")


def _changelog_entry(ws):
    _start(ws)
    ws.write("CHANGELOG.md", "\n## [Unreleased]\n\n- Refactor: page builder helper.\n",
             append=True)
    _finish(ws, ["CHANGELOG.md"])
    ws.reply = "Updated CHANGELOG.md."


def _refactor_note(ws):
    _start(ws)
    ws.write("docs/internals.md", "# Internals\n\n`_page()` builds every page.\n")
    _finish(ws, ["docs/internals.md"])
    ws.reply = "Wrote docs/internals.md."


def _readme_edited_uncommitted(ws):
    _start(ws)
    with open(os.path.join(ws.path, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    ws.write("README.md", text + "\nPages are built by an internal helper.\n")
    _finish(ws, [])
    ws.reply = "No doc changes needed."


def _committed_the_code(ws):
    """Committed /acs:code's change to "help" -- only /acs:create-pr commits."""
    _start(ws)
    ws.sh("git add -A && git commit -qm 'EVAL-1 extract the customer page builder'")
    _finish(ws, [])
    ws.reply = "No doc changes needed."


def _new_branch(ws):
    _start(ws)
    ws.sh("git checkout -q -b docs/EVAL-1")
    _finish(ws, [])
    ws.reply = "No doc changes needed."


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("docs-sync"),
    "wrote a changelog entry for a refactor": _changelog_entry,
    "wrote a speculative internals doc": _refactor_note,
    "left a speculative README edit behind": _readme_edited_uncommitted,
    "switched to a new branch": _new_branch,
    "committed the code change": _committed_the_code,
}
