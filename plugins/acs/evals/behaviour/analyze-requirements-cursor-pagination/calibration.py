"""Calibration plays for analyze-requirements-cursor-pagination.

IDEAL does what /acs:analyze-requirements' coordinator does, through the
plugin's own writers where they exist: `acs step start`, `clarify.py add` for
each answer the prompt relayed, the draft in the step directory, the Publish
copy into docs/development/customer-listing/EVAL-1/ left uncommitted on main (no branch, no
commit -- ADR-0127), then result.json with `files` and the post-hook. The analyst's and impact reviewer's own phase
files are workspace detail no grader reads, so only the draft is played.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
BRANCH = "story/EVAL-1-cursor-pagination-for-get-customers"
PUBLISHED = "docs/development/customer-listing/EVAL-1/analysis.md"

ANALYSIS = """---
ticket: EVAL-1
ready_for_planning: true
api_surface: true
needs_design_recommendation: false
---

# Analysis — EVAL-1: Cursor pagination for GET /customers

## Problem restated

Offset paging on GET /customers skips or repeats customers when rows are
inserted between page requests. Clients need an opaque cursor that walks every
customer exactly once, while existing offset clients keep working.

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/__init__.py | shop | `list_customers` gains `cursor`, returns `next_cursor` | src/shop/__init__.py:8 |
| tests/test_customers.py | tests | new unit tests for cursor paging | tests/ holds only test_health.py |
| README.md | docs | API section documents `cursor` and `next_cursor` | README.md:7 |

## Questions

- C-1 cursor encoding — answered: URL-safe base64 of the last customer id.
- C-2 offset compatibility — answered: kept, deprecated; cursor wins.
- C-3 limit bounds — answered: default 20, maximum 100.
- C-4 malformed cursor — answered: HTTP 400, `invalid_cursor`.

## Assumptions

_None._

## Risks

- Public API: GET /customers is documented in README.md and called by
  clients; `offset` must keep working (src/shop/__init__.py, README.md).

## Refined acceptance criteria

The three criteria on the ticket are confirmed as written.

## Verdict

Ready for planning; api_surface true; no design needed.
"""

ANSWERS = [
    ("How is the cursor encoded?", "URL-safe base64 of the last customer id"),
    ("Does offset keep working?", "Yes, deprecated; cursor wins when both are given"),
    ("What are the limit bounds?", "Default 20, maximum 100"),
    ("What does a malformed cursor return?", "HTTP 400 with error code invalid_cursor"),
]


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("analyze-requirements")
    started = ws.acs("step", "start", "--step", "analyze-requirements", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws, status="completed", api_surface=True):
    result = {"status": status, "summary": "calibration",
              "states": {"ready_for_planning": status == "completed",
                         "api_surface": api_surface, "questions_open": 0},
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill analyze-requirements --ticket EVAL-1 '
              '--question "%s" --answer "%s"' % (SCRIPTS, question, answer))
    ws.write(STEP + "/analysis.md", ANALYSIS)
    ws.sh('mkdir -p docs/development/customer-listing/EVAL-1 && cp "%s/analysis.md" "%s"' % (STEP, PUBLISHED))
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _prose_on_main(ws):
    """Wrote an analysis by hand and committed it: no front matter, no impact
    map from the code, and the step never finished."""
    _start(ws)
    ws.write(PUBLISHED, "# Analysis of EVAL-1\n\nAdd a cursor to GET /customers. "
                        "Low risk; no API change.\n")
    ws.sh("git add docs && git commit -qm 'analysis'")


def _api_surface_false(ws):
    """Ran the whole flow but declared no API surface, so the contract step
    would be skipped."""
    _start(ws)
    ws.write(STEP + "/analysis.md", ANALYSIS.replace("api_surface: true", "api_surface: false"))
    ws.sh('mkdir -p docs/development/customer-listing/EVAL-1 && cp "%s/analysis.md" "%s"' % (STEP, PUBLISHED))
    _finish(ws, api_surface=False)


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "hand-wrote a prose analysis on main": _prose_on_main,
    "declared api_surface false": _api_surface_false,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b "%s" && git add docs && git commit -qm "EVAL-1 Analyze"' % BRANCH)


BAD["committed the analysis on a new ticket branch"] = _committed_on_a_ticket_branch
