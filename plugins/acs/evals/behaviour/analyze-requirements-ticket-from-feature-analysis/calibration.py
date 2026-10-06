"""Calibration plays for analyze-requirements-ticket-from-feature-analysis.

IDEAL does what /acs:analyze-requirements' coordinator does on a Development
run whose feature has a living analysis, through the plugin's own writers:
`acs step start` on the ticket, `acs.py artifacts show` naming both the run's
target and the feature's living analysis, the draft (carrying the living
analysis's decisions) as a folder in the step directory (ADR-0133), the
Publish copy to the run's
development folder left uncommitted (ADR-0127), then result.json with `files`
and the post-hook. The living analysis is read, never written.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
PUBLISHED = "docs/development/customer-listing/EVAL-1/analysis"
LIVING = "docs/product/features/customer-listing/analysis"

README = '---\nticket: EVAL-1\nready_for_planning: true\nneeds_design_recommendation: false\n---\n\n# Analysis — EVAL-1: Cursor pagination for GET /customers\n\n## Scope and summary\n\nOffset paging on GET /customers skips or repeats customers; the feature analysis (docs/product/features/customer-listing/analysis/) settled the cursor.\n\n## Contexts\n\n| Context | File | Purpose |\n|---|---|---|\n| Customer listing | [customer-listing.md](customer-listing.md) | how a client pages through customers |\n\n## Refined acceptance criteria\n\nThe three criteria are confirmed as written.\n\n## Cross-cutting risks and decisions\n\n- Public API: GET /customers is documented in README.md.\n\n## Questions and assumptions\n\n- Carried from the feature analysis: cursor encoding, offset kept, maximum page size 250, malformed cursor → 400.\n\nAssumptions: none.\n\n## Verdict\n\nReady for planning; no design needed.\n'

CONTEXT = '---\ncontext: customer-listing\n---\n\n# Customer listing\n\n## Impact map\n\n| Path | Component | Change | Evidence |\n|---|---|---|---|\n| src/shop/__init__.py | shop | `list_customers` gains `cursor`, returns `next_cursor` | src/shop/__init__.py:8 |\n| README.md | docs | API section documents `cursor` | README.md:7 |\n\n## Rules and edge cases\n\n_None._\n\n## Risks\n\n- Public API: GET /customers is documented in README.md.\n\n## Open questions\n\n_None._\n\n## API notes\n\n_None._\n'

#: The analysis is a folder (ADR-0133): a README plus one file per context.
ANALYSIS = {"README.md": README, "customer-listing.md": CONTEXT}


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
    assert layout["paths"]["analysis.md"].replace(os.sep, "/").endswith(
        PUBLISHED + "/README.md"), layout
    assert (layout["feature_analysis"] or "").replace(os.sep, "/").endswith(
        LIVING + "/README.md"), layout


def _finish(ws, status="completed"):
    result = {"status": status, "summary": "calibration",
              "states": {"ready_for_planning": status == "completed",
                         "questions_open": 0,
                         "files": _written(ws)},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def _publish(ws, files, target=PUBLISHED):
    """The draft folder, then the Publish copy of every file (ADR-0133)."""
    for name, text in files.items():
        ws.write(STEP + "/iter-1/analysis/" + name, text)
    ws.sh('mkdir -p "%s" && cp "%s"/iter-1/analysis/*.md "%s"/' % (target, STEP, target))


def _edit(files, old, new):
    """Every file of the folder with `old` replaced by `new`."""
    out = {n: t.replace(old, new) for n, t in files.items()}
    assert out != files, old
    return out


def IDEAL(ws):
    _start(ws)
    _publish(ws, ANALYSIS)
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _ignored_the_feature_analysis(ws):
    """Surveyed from the ticket alone and assumed the conventional maximum."""
    _start(ws)
    _publish(ws, _edit(ANALYSIS, "maximum page size 250", "maximum page size 100 (assumed)"))
    _finish(ws)


def _overwrote_the_living_analysis(ws):
    """Published the ticket's analysis over the feature's, re-versioned."""
    _start(ws)
    for name, text in ANALYSIS.items():
        ws.write(STEP + "/iter-1/analysis/" + name, text)
    living = ("---\nstatus: proposed\nversion: 2\ntickets: [\"EVAL-1\"]\n"
              "feature: customer-listing\n" + README.split("---\n", 2)[1].split("\n", 1)[1]
              + "---\n" + README.split("---\n", 2)[2])
    ws.write(LIVING + "/README.md", living)
    _finish(ws)


def _published_to_the_legacy_folder(ws):
    _start(ws)
    _publish(ws, ANALYSIS, "docs/tickets/EVAL-1/analysis")
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
