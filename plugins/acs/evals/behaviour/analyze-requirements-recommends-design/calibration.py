"""Calibration plays for analyze-requirements-recommends-design.

IDEAL does what /acs:analyze-requirements' coordinator does when its survey
recommends a design and the user has confirmed it: `acs step start`, the
relayed answers recorded with `clarify.py add` (the design question among
them), the confirmed flag applied with `acs.py requirements refine` (which
patches the ticket too), the draft, the
Publish copy left uncommitted (ADR-0127), result.json and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
BRANCH = "story/EVAL-1-live-order-tracking-from-carrier-updates"
ANALYSIS = '---\nticket: EVAL-1\nready_for_planning: true\napi_surface: true\nneeds_design_recommendation: true\n---\n\n# Analysis — EVAL-1: Live order tracking from carrier updates\n\n## Problem restated\n\nCarriers push shipment status to the shop; the shop stores every change per\norder, serves the latest, and emails the shopper.\n\n## Impact map\n\n| Path | Component | Change | Evidence |\n|---|---|---|---|\n| src/shop/__init__.py | shop | new tracking store, webhook intake, order status | src/shop/__init__.py:1 |\n| docs/architecture/lld/flows.md | docs | new inbound carrier flow | docs/architecture/lld/flows.md:3 |\n\n## Questions\n\n- C-1 how carriers deliver updates — answered: signed webhooks.\n- C-2 design needed — answered: yes, confirmed; needs_design set on the ticket.\n\n## Assumptions\n\n_None._\n\n## Risks\n\n- New inbound surface from third parties (authentication); a new stored shape.\n\n## Refined acceptance criteria\n\nThe three criteria on the ticket are confirmed as written.\n\n## Verdict\n\nReady for planning once designed; api_surface true; needs a design.\n'

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
    ws.sh('mkdir -p docs/development/order-tracking/EVAL-1 && cp "%s/analysis.md" docs/development/order-tracking/EVAL-1/analysis.md' % STEP)


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


def _flag(ws):
    saved = ws.acs("requirements", "refine", "--from", "-",
                   stdin=json.dumps({"needs_design": True}))
    assert saved.returncode == 0, saved.stderr


def _ticket_saved_only(ws):
    """The pre-ADR-0128 write: the ticket patched with `acs.py ticket save`,
    the run's requirements left saying no design is needed."""
    _start(ws)
    _clarify(ws, "Does this ticket need a design before it is planned?", "Yes, confirmed")
    saved = ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-",
                   stdin=json.dumps({"needs_design": True}))
    assert saved.returncode == 0, saved.stderr
    _publish(ws, ANALYSIS)
    _finish(ws)


def IDEAL(ws):
    _start(ws)
    _clarify(ws, "How do carriers deliver status updates?", "Signed webhooks, one secret per carrier")
    _clarify(ws, "Does this ticket need a design before it is planned?", "Yes, confirmed")
    _flag(ws)
    _publish(ws, ANALYSIS)
    _finish(ws)


def _recommended_only(ws):
    """Recommended a design in the analysis but never applied the flag."""
    _start(ws)
    _clarify(ws, "Does this ticket need a design before it is planned?", "Yes, confirmed")
    _publish(ws, ANALYSIS)
    _finish(ws)


def _no_recommendation(ws):
    """Judged no design needed."""
    _start(ws)
    _publish(ws, ANALYSIS.replace("needs_design_recommendation: true",
                                  "needs_design_recommendation: false"))
    _finish(ws)


def _started_only(ws):
    _start(ws)


BAD = {
    "recommended a design but left the ticket unflagged": _recommended_only,
    "saw no need for a design": _no_recommendation,
    "fired the skill, started the step, wrote nothing": _started_only,
    "flagged the ticket but not the run's requirements": _ticket_saved_only,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b "%s" && git add docs && git commit -qm "EVAL-1 Analyze"' % BRANCH)


BAD["committed the analysis on a new ticket branch"] = _committed_on_a_ticket_branch
