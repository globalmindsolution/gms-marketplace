"""Calibration plays for analyze-requirements-needs-input-undefined-format.

IDEAL follows references/not-ready-for-planning.md through the plugin's own
writers: `acs step start`, the blocking question recorded OPEN with
`clarify.py add` (no --answer), the not-ready draft, the ticket branch and the
Publish copy with its commit, then result.json as an interrupted step with
stop_reason needs_input, and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
BRANCH = "story/EVAL-1-customer-export-for-finance"
ANALYSIS = "---\nticket: EVAL-1\nready_for_planning: false\napi_surface: true\nneeds_design_recommendation: false\n---\n\n# Analysis — EVAL-1: Customer export for finance\n\n## Problem restated\n\nFinance needs every customer in a file their accounting system imports.\n\n## Impact map\n\n| Path | Component | Change | Evidence |\n|---|---|---|---|\n| src/shop/__init__.py | shop | new export built on `list_customers` | src/shop/__init__.py:8 |\n| README.md | docs | API section documents the export | README.md:5 |\n\n## Questions\n\n- C-1 which accounting system and import format — OPEN: blocks; every\n  format we could pick (CSV, OFX, a vendor schema) may be the wrong one.\n\n## Assumptions\n\n- Export columns follow the fields `list_customers` returns.\n\n## Risks\n\n- A new public endpoint (README.md's API section).\n\n## Refined acceptance criteria\n\nAC-2 cannot be tested until C-1 names the target format.\n\n## Verdict\n\nNot ready for planning: C-1 is open and blocks the build.\n"

def _finish(ws, status="completed", ready=True, api_surface=True, questions_open=0,
            stop_reason=None):
    result = {"status": status, "summary": "calibration",
              "states": {"ready_for_planning": ready, "api_surface": api_surface,
                         "questions_open": questions_open},
              "findings": [], "errors": []}
    if stop_reason:
        result["stop_reason"] = stop_reason
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def _publish(ws, text, branch, commit=True):
    ws.write(STEP + "/analysis.md", text)
    ws.sh('git rev-parse --verify --quiet "%s" >/dev/null && git checkout -q "%s" || git checkout -q -b "%s"'
          % (branch, branch, branch))
    cmd = 'mkdir -p docs/tickets/EVAL-1 && cp "%s/analysis.md" docs/tickets/EVAL-1/analysis.md' % STEP
    if commit:
        cmd += ' && git add docs/tickets/EVAL-1 && git commit -qm "EVAL-1 Analyze"'
    ws.sh(cmd)


def _clarify(ws, question, answer=None, source=None, rationale=None):
    cmd = ('python3 "%s/clarify.py" add --skill analyze-requirements --ticket EVAL-1 --question "%s"'
           % (SCRIPTS, question))
    if answer is not None:
        cmd += ' --answer "%s"' % answer
    if source:
        cmd += ' --source %s --rationale "%s"' % (source, rationale)
    ws.sh(cmd + " > /dev/null")


def _start(ws):
    ws.skill("analyze-requirements")
    started = ws.acs("step", "start", "--step", "analyze-requirements", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def IDEAL(ws):
    _start(ws)
    _clarify(ws, "Which accounting system does finance use, and what file format does it import?")
    _publish(ws, ANALYSIS, BRANCH)
    _finish(ws, status="interrupted", ready=False, questions_open=1, stop_reason="needs_input")


def _guessed_csv(ws):
    """Assumed CSV, declared the ticket ready and completed."""
    _start(ws)
    _clarify(ws, "Which file format does finance import?", "CSV", "assumption", "most common")
    ready = (ANALYSIS.replace("ready_for_planning: false", "ready_for_planning: true")
             .replace("OPEN: blocks", "assumed CSV"))
    _publish(ws, ready, BRANCH)
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _built_a_csv_export(ws):
    """Stopped correctly, but also wrote the export it could not specify."""
    IDEAL(ws)
    ws.write("src/shop/export.py", "def export_csv():\n    return ''\n")


BAD = {
    "guessed CSV and declared it ready": _guessed_csv,
    "fired the skill, started the step, wrote nothing": _started_only,
    "implemented an export anyway": _built_a_csv_export,
}
