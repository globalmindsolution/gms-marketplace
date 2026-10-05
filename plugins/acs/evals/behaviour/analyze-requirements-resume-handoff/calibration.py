"""Calibration plays for analyze-requirements-resume-handoff.

IDEAL does what a resumed /acs:analyze-requirements does, through the
plugin's own writers: `acs step start` (which now reports reconcile and the
handoff summary), `clarify.py list` (the ledger answers everything, so Stage
2 is skipped and nothing is re-recorded), the draft, the Publish copy left
uncommitted (ADR-0127), then result.json and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
BRANCH = "story/EVAL-1-cursor-pagination-for-get-customers"
ANALYSIS = '---\nticket: EVAL-1\nready_for_planning: true\napi_surface: true\nneeds_design_recommendation: false\n---\n\n# Analysis — EVAL-1: Cursor pagination for GET /customers\n\n## Problem restated\n\nOffset paging on GET /customers skips or repeats customers when rows are\ninserted between page requests. Clients need an opaque cursor.\n\n## Impact map\n\n| Path | Component | Change | Evidence |\n|---|---|---|---|\n| src/shop/__init__.py | shop | `list_customers` gains `cursor`, returns `next_cursor` | src/shop/__init__.py:8 |\n| README.md | docs | API section documents `cursor` and `next_cursor` | README.md:7 |\n\n## Questions\n\n- C-1 cursor encoding — answered: URL-safe base64 of the last customer id.\n- C-2 offset compatibility — answered: kept, deprecated; cursor wins.\n- C-3 maximum page size — answered: `limit` defaults to 20, maximum 250.\n- C-4 malformed cursor — answered: HTTP 400, `invalid_cursor`.\n\n## Assumptions\n\n_None._\n\n## Risks\n\n- Public API: GET /customers is documented in README.md; `offset` must keep working.\n\n## Refined acceptance criteria\n\nThe three criteria on the ticket are confirmed as written.\n\n## Verdict\n\nReady for planning; api_surface true; no design needed.\n'

def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _finish(ws, status="completed", ready=True, api_surface=True, questions_open=0,
            stop_reason=None):
    result = {"status": status, "summary": "calibration",
              "states": {"ready_for_planning": ready, "api_surface": api_surface,
                         "questions_open": questions_open},
              "findings": [], "errors": []}
    if stop_reason:
        result["stop_reason"] = stop_reason
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def _publish(ws, text):
    """The Publish copy, left uncommitted on the checked-out branch (ADR-0127)."""
    ws.write(STEP + "/analysis.md", text)
    ws.sh('mkdir -p docs/development/customer-listing/EVAL-1 && cp "%s/analysis.md" docs/development/customer-listing/EVAL-1/analysis.md' % STEP)


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
    assert json.loads(started.stdout)["reconcile"] is True


def IDEAL(ws):
    _start(ws)
    ws.sh('python3 "%s/clarify.py" list --ticket EVAL-1 > /dev/null' % SCRIPTS)
    _publish(ws, ANALYSIS)
    _finish(ws)


def _ignored_the_ledger(ws):
    """Started over: asked the limit question again, assumed 100."""
    _start(ws)
    _clarify(ws, "What is the maximum page size?", "100", "assumption", "conventional default")
    _publish(ws, ANALYSIS.replace("maximum 250", "maximum 100"))
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _draft_never_published(ws):
    """Wrote the draft and closed the step, but never published it."""
    _start(ws)
    ws.write(STEP + "/analysis.md", ANALYSIS)
    _finish(ws)


BAD = {
    "re-asked the answered question and assumed 100": _ignored_the_ledger,
    "reconciled, then wrote nothing": _started_only,
    "closed the step with the draft unpublished": _draft_never_published,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b "%s" && git add docs && git commit -qm "EVAL-1 Analyze"' % BRANCH)


BAD["committed the analysis on a new ticket branch"] = _committed_on_a_ticket_branch
