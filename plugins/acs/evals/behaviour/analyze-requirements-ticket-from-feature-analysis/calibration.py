"""Calibration plays for analyze-requirements-ticket-from-feature-analysis.

IDEAL does what /acs:analyze-requirements' coordinator does on a Development
run whose feature has a living analysis, through the plugin's own writers:
`acs step start` on the ticket, `acs.py artifacts show` naming both the run's
target and the feature's living analysis, the draft (carrying the living
analysis's decisions) in the step directory, the Publish copy to the run's
development folder left uncommitted (ADR-0127), then result.json with `files`
and the post-hook. The living analysis is read, never written.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
PUBLISHED = "docs/development/customer-listing/EVAL-1/analysis.md"
LIVING = "docs/product/features/customer-listing/analysis.md"

ANALYSIS = '---\nticket: EVAL-1\nready_for_planning: true\napi_surface: true\nneeds_design_recommendation: false\n---\n\n# Analysis — EVAL-1: Cursor pagination for GET /customers\n\n## Problem restated\n\nOffset paging on GET /customers skips or repeats customers; the feature analysis (docs/product/features/customer-listing/analysis.md) settled the cursor.\n\n## Impact map\n\n| Path | Component | Change | Evidence |\n|---|---|---|---|\n| src/shop/__init__.py | shop | `list_customers` gains `cursor`, returns `next_cursor` | src/shop/__init__.py:8 |\n| README.md | docs | API section documents `cursor` | README.md:7 |\n\n## Questions\n\n- Carried from the feature analysis: cursor encoding, offset kept, maximum page size 250, malformed cursor → 400.\n\n## Assumptions\n\n_None._\n\n## Risks\n\n- Public API: GET /customers is documented in README.md.\n\n## Refined acceptance criteria\n\nThe three criteria are confirmed as written.\n\n## Verdict\n\nReady for planning; api_surface true; no design needed.\n'


def _written(ws):
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("analyze-requirements")
    started = ws.acs("step", "start", "--step", "analyze-requirements", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    shown = ws.acs("artifacts", "show")
    assert shown.returncode == 0, shown.stderr
    layout = json.loads(shown.stdout)
    assert layout["phase"] == "development", layout["phase"]
    assert layout["paths"]["analysis.md"].replace(os.sep, "/").endswith(PUBLISHED), layout
    assert (layout["feature_analysis"] or "").replace(os.sep, "/").endswith(LIVING), layout


def _finish(ws, status="completed"):
    result = {"status": status, "summary": "calibration",
              "states": {"ready_for_planning": status == "completed",
                         "api_surface": True, "questions_open": 0,
                         "files": _written(ws)},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def _publish(ws, text, target=PUBLISHED):
    ws.write(STEP + "/analysis.md", text)
    ws.sh('mkdir -p "%s" && cp "%s/analysis.md" "%s"' % (os.path.dirname(target), STEP, target))


def IDEAL(ws):
    _start(ws)
    _publish(ws, ANALYSIS)
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _ignored_the_feature_analysis(ws):
    """Surveyed from the ticket alone and assumed the conventional maximum."""
    _start(ws)
    _publish(ws, ANALYSIS.replace("maximum page size 250", "maximum page size 100 (assumed)"))
    _finish(ws)


def _overwrote_the_living_analysis(ws):
    """Published the ticket's analysis over the feature's, re-versioned."""
    _start(ws)
    ws.write(STEP + "/analysis.md", ANALYSIS)
    living = ("---\nstatus: proposed\nversion: 2\ntickets: [\"EVAL-1\"]\n"
              "feature: customer-listing\n" + ANALYSIS.split("---\n", 2)[1].split("\n", 1)[1]
              + "---\n" + ANALYSIS.split("---\n", 2)[2])
    ws.write(LIVING, living)
    _finish(ws)


def _published_to_the_legacy_folder(ws):
    _start(ws)
    _publish(ws, ANALYSIS, "docs/tickets/EVAL-1/analysis.md")
    _finish(ws)


def _committed(ws):
    IDEAL(ws)
    ws.sh("git add docs && git commit -qm 'EVAL-1 analysis'")


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "ignored the feature analysis and assumed 100": _ignored_the_feature_analysis,
    "overwrote the feature's living analysis": _overwrote_the_living_analysis,
    "published to the legacy docs/tickets folder": _published_to_the_legacy_folder,
    "committed the analysis": _committed,
}
