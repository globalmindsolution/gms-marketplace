"""Calibration plays for analyze-requirements-needs-input-undefined-format.

IDEAL follows references/not-ready-for-planning.md through the plugin's own
writers: `acs step start`, the blocking question recorded OPEN with
`clarify.py add` (no --answer), the not-ready draft folder (ADR-0133), the Publish copy left
uncommitted (ADR-0127), then result.json as an interrupted step with
stop_reason needs_input, and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
BRANCH = "story/EVAL-1-customer-export-for-finance"
README = "---\nticket: EVAL-1\nready_for_planning: false\nneeds_design_recommendation: false\n---\n\n# Analysis — EVAL-1: Customer export for finance\n\n## Scope and summary\n\nFinance needs every customer in a file their accounting system imports.\n\n## Contexts\n\n| Context | File | Purpose |\n|---|---|---|\n| Customer export | [customer-export.md](customer-export.md) | how finance gets every customer in a file |\n\n## Refined acceptance criteria\n\nAC-2 cannot be tested until C-1 names the target format.\n\n## Cross-cutting risks and decisions\n\n- A new public endpoint (README.md's API section).\n\n## Questions and assumptions\n\n- C-1 which accounting system and import format — OPEN: blocks; every\n  format we could pick (CSV, OFX, a vendor schema) may be the wrong one.\n\nAssumptions:\n\n- Export columns follow the fields `list_customers` returns.\n\n## Verdict\n\nNot ready for planning: C-1 is open and blocks the build.\n"

CONTEXT = "---\ncontext: customer-export\n---\n\n# Customer export\n\n## Impact map\n\n| Path | Component | Change | Evidence |\n|---|---|---|---|\n| src/shop/__init__.py | shop | new export built on `list_customers` | src/shop/__init__.py:8 |\n| README.md | docs | API section documents the export | README.md:5 |\n\n## Rules and edge cases\n\n_None._\n\n## Risks\n\n- A new public endpoint (README.md's API section).\n\n## Open questions\n\n_None._\n\n## API notes\n\n_None._\n"

#: The analysis is a folder (ADR-0133): a README plus one file per context.
ANALYSIS = {"README.md": README, "customer-export.md": CONTEXT}

def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _finish(ws, status="completed", ready=True, questions_open=0,
            stop_reason=None):
    result = {"status": status, "summary": "calibration",
              "states": {"ready_for_planning": ready, "questions_open": questions_open},
              "findings": [], "errors": []}
    if stop_reason:
        result["stop_reason"] = stop_reason
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def _publish(ws, files):
    """The draft folder, then the Publish copy of every file, left uncommitted
    on the checked-out branch (ADR-0127, ADR-0133)."""
    for name, text in files.items():
        ws.write(STEP + "/iter-1/analysis/" + name, text)
    ws.sh('mkdir -p docs/development/customer-listing/EVAL-1/analysis && cp "%s"/iter-1/analysis/*.md docs/development/customer-listing/EVAL-1/analysis/' % STEP)


def _edit(files, old, new):
    """Every file of the folder with `old` replaced by `new`."""
    out = {n: t.replace(old, new) for n, t in files.items()}
    assert out != files, old
    return out


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
    _publish(ws, ANALYSIS)
    _finish(ws, status="interrupted", ready=False, questions_open=1, stop_reason="needs_input")


def _guessed_csv(ws):
    """Assumed CSV, declared the ticket ready and completed."""
    _start(ws)
    _clarify(ws, "Which file format does finance import?", "CSV", "assumption", "most common")
    ready = _edit(_edit(ANALYSIS, "ready_for_planning: false", "ready_for_planning: true"),
                  "OPEN: blocks", "assumed CSV")
    _publish(ws, ready)
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


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b "%s" && git add docs && git commit -qm "EVAL-1 Analyze"' % BRANCH)


BAD["committed the analysis on a new ticket branch"] = _committed_on_a_ticket_branch
