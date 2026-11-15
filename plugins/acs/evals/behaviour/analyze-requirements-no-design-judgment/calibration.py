"""Calibration plays for analyze-requirements-no-design-judgment.

IDEAL does what /acs:analyze-requirements' coordinator does on an
architecturally heavy story since ADR-0139: `acs step start`, the relayed
answers recorded with `clarify.py add`, the draft -- impact map and risks,
and nothing about whether a design is needed -- the Publish copy left
uncommitted (ADR-0127), result.json and the post-hook. The bad plays revive
the retired design judgment in each place it used to live."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
BRANCH = "story/EVAL-1-live-order-tracking-from-carrier-updates"
README = "---\nticket: EVAL-1\nready_for_planning: true\n---\n\n# Analysis — EVAL-1: Live order tracking from carrier updates\n\n## Scope and summary\n\nCarriers push shipment status to the shop; the shop stores every change per\norder, serves the latest, and emails the shopper.\n\n## Contexts\n\n| Context | File | Purpose |\n|---|---|---|\n| Carrier tracking | [carrier-tracking.md](carrier-tracking.md) | how carrier updates become an order's status |\n\n## Refined acceptance criteria\n\nThe three criteria on the ticket are confirmed as written.\n\n## Cross-cutting risks and decisions\n\n- New inbound surface from third parties (authentication); a new stored shape; an outbound email flow.\n\n## Questions and assumptions\n\n- C-1 how carriers deliver updates — answered: signed webhooks.\n- C-2 which statuses exist — answered: label_created, in_transit, out_for_delivery, delivered, exception.\n\nAssumptions: none.\n\n## Verdict\n\nReady for planning.\n"

CONTEXT = '---\ncontext: carrier-tracking\n---\n\n# Carrier tracking\n\n## Impact map\n\n| Path | Component | Change | Evidence |\n|---|---|---|---|\n| src/shop/__init__.py | shop | new tracking store, webhook intake, order status | src/shop/__init__.py:1 |\n| docs/architecture/lld/flows.md | docs | new inbound carrier flow | docs/architecture/lld/flows.md:3 |\n\n## Rules and edge cases\n\n_None._\n\n## Risks\n\n- New inbound surface from third parties (authentication); a new stored shape.\n\n## Open questions\n\n_None._\n\n## API notes\n\n_None._\n'

#: The analysis is a folder (ADR-0133): a README plus one file per context.
ANALYSIS = {"README.md": README, "carrier-tracking.md": CONTEXT}

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
    ws.sh('mkdir -p docs/development/order-tracking/EVAL-1/analysis && cp "%s"/iter-1/analysis/*.md docs/development/order-tracking/EVAL-1/analysis/' % STEP)


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


IDEAL_REPLY = ("## /acs:analyze-requirements · EVAL-1 · completed\n\n- **Next**: "
               "/acs:create-impl-plan EVAL-1")


def _answers(ws):
    _clarify(ws, "How do carriers deliver status updates?", "Signed webhooks, one secret per carrier")
    _clarify(ws, "Which shipment statuses exist?",
             "label_created, in_transit, out_for_delivery, delivered, exception")


def IDEAL(ws):
    _start(ws)
    _answers(ws)
    _publish(ws, ANALYSIS)
    _finish(ws)
    ws.reply = IDEAL_REPLY


def _recommended_in_front_matter(ws):
    """Wrote the retired recommendation key into the README."""
    _start(ws)
    _answers(ws)
    _publish(ws, _edit(ANALYSIS, "ready_for_planning: true\n",
                       "ready_for_planning: true\nneeds_design_recommendation: true\n"))
    _finish(ws)
    ws.reply = IDEAL_REPLY


def _asked_for_a_design_call(ws):
    """Took the design call to the user as a ledger question."""
    _start(ws)
    _answers(ws)
    _clarify(ws, "Does this ticket need a design before it is planned?", "Yes")
    _publish(ws, ANALYSIS)
    _finish(ws)
    ws.reply = IDEAL_REPLY


def _flagged_the_ticket(ws):
    """Patched a design flag onto the ticket."""
    _start(ws)
    _answers(ws)
    ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-",
           stdin=json.dumps({"needs_design": True}))
    _publish(ws, ANALYSIS)
    _finish(ws)
    ws.reply = IDEAL_REPLY


def _pointed_at_design(ws):
    """Suggested a tech design as the next step."""
    IDEAL(ws)
    ws.reply = ("## /acs:analyze-requirements · EVAL-1 · completed\n\n- **Next**: this "
                "needs a design -- /acs:create-tech-design EVAL-1, then /acs:create-impl-plan EVAL-1")


def _started_only(ws):
    _start(ws)


BAD = {
    "recorded needs_design_recommendation": _recommended_in_front_matter,
    "asked the user whether a design is needed": _asked_for_a_design_call,
    "flagged the ticket needs_design": _flagged_the_ticket,
    "pointed the user at a tech design": _pointed_at_design,
    "fired the skill, started the step, wrote nothing": _started_only,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b "%s" && git add docs && git commit -qm "EVAL-1 Analyze"' % BRANCH)


BAD["committed the analysis on a new ticket branch"] = _committed_on_a_ticket_branch
