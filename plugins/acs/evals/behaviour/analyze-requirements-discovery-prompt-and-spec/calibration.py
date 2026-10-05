"""Calibration plays for analyze-requirements-discovery-prompt-and-spec.

IDEAL does what /acs:analyze-requirements' coordinator does on a Discovery
run, through the plugin's own writers: `acs step start --args` over the
invocation (the attached spec and the prompt -- no ticket), `clarify.py add`
for each relayed answer into the run's own ledger, `acs.py requirements
refine` for the feature and the confirmed needs_design, the versioned draft
folder in the step directory (a README plus one context file -- ADR-0133), the Publish copy to the feature's living analysis
left uncommitted (ADR-0127), then result.json with `files` and the post-hook.
The analyst's and impact reviewer's phase files are workspace detail no
grader reads, so only the draft is played.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
ARGS = ('attachments/order-tracking-spec.md "also: guest orders (placed without an '
        'account) are trackable through the link in their order confirmation email"')
LIVING = "docs/product/features/order-tracking/analysis"

README = """---
status: proposed
version: 1
tickets: []
feature: order-tracking
ready_for_planning: true
needs_design_recommendation: true
---

# Analysis — order-tracking: Order tracking from carrier updates

## Scope and summary

Carriers push shipment status changes; the shop stores every change per
order, serves the latest on GET /orders/{id}, emails the shopper on each
change, lets a shopper opt out per order, and lets guest orders track
through the confirmation-email link.

## Contexts

| Context | File | Purpose |
|---|---|---|
| Carrier updates | [carrier-updates.md](carrier-updates.md) | how a carrier's status change reaches the order and the shopper |

## Refined acceptance criteria

The spec's four criteria stand as written; guest-order tracking is proposed
as a fifth — open.

## Cross-cutting risks and decisions

- New inbound surface from third parties (authentication); a new stored shape.

## Questions and assumptions

- C-1 how carriers deliver updates — answered: signed webhooks.
- C-2 design needed — answered: yes; recorded, not started.

Assumptions: none.

## Verdict

Ready for planning once designed; needs a design.
"""

CONTEXT = """---
context: carrier-updates
feature: order-tracking
status: proposed
version: 1
tickets: []
---

# Carrier updates

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/__init__.py | shop | new webhook intake, status store, order status | src/shop/__init__.py:1 |
| docs/architecture/lld/flows.md | docs | new inbound carrier flow | docs/architecture/lld/flows.md:3 |

## Rules and edge cases

_None._

## Risks

- New inbound surface from third parties (authentication); a new stored shape.

## Open questions

_None._

## API notes

_None._
"""

#: The analysis is a folder (ADR-0133): a README plus one file per context.
ANALYSIS = {"README.md": README, "carrier-updates.md": CONTEXT}

ANSWERS = [
    ("How do carriers deliver status updates?", "Signed webhooks, one secret per carrier"),
    ("Which statuses exist?", "label_created, in_transit, out_for_delivery, delivered, exception"),
    ("Does this feature need a design before it is built?", "Yes, confirmed"),
    ("Which PRD feature is this analysis filed under?", "order-tracking"),
]


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("analyze-requirements")
    started = ws.acs("step", "start", "--step", "analyze-requirements", "--args", ARGS)
    assert started.returncode == 0, started.stderr
    context = json.loads(started.stdout)
    assert context.get("ticket_id") is None, context.get("ticket_id")
    return os.path.relpath(os.path.join(context["partition"], "steps", "analyze-requirements"),
                           ws.path)


def _clarify(ws):
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill analyze-requirements '
              '--question "%s" --answer "%s" > /dev/null' % (SCRIPTS, question, answer))


def _refine(ws, data):
    refined = ws.acs("requirements", "refine", "--from", "-", stdin=json.dumps(data))
    assert refined.returncode == 0, refined.stderr


def _finish(ws, step, status="completed"):
    result = {"status": status, "summary": "calibration",
              "states": {"ready_for_planning": status == "completed",
                         "questions_open": 0,
                         "files": _written(ws)},
              "findings": [], "errors": []}
    ws.write(step + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, step))


def _publish(ws, step, files, target=LIVING):
    """The draft folder, then the Publish copy of every file."""
    for name, text in files.items():
        ws.write(step + "/iter-1/analysis/" + name, text)
    ws.sh('mkdir -p "%s" && cp "%s"/iter-1/analysis/*.md "%s"/' % (target, step, target))


def _edit(files, old, new):
    """Every file of the folder with `old` replaced by `new`."""
    out = {n: t.replace(old, new) for n, t in files.items()}
    assert out != files, old
    return out


def IDEAL(ws):
    step = _start(ws)
    _clarify(ws)
    _refine(ws, {"feature": "order-tracking", "needs_design": True})
    # The graders' path is the one the plugin itself resolves for this run.
    shown = ws.acs("artifacts", "show")
    assert shown.returncode == 0, shown.stderr
    layout = json.loads(shown.stdout)
    assert layout["phase"] == "discovery", layout["phase"]
    assert layout["paths"]["analysis.md"].replace(os.sep, "/").endswith(
        LIVING + "/README.md"), layout["paths"]
    _publish(ws, step, ANALYSIS)
    _finish(ws, step)


def _started_only(ws):
    _start(ws)


def _minted_a_ticket(ws):
    """Detoured through a ticket to have somewhere to publish."""
    ws.sh('python3 "%s/new-ticket.py" --title "Order tracking" --type story '
          '--features order-tracking > /dev/null' % SCRIPTS)
    IDEAL(ws)


def _published_as_a_development_run(ws):
    """Filed it as a delivery run's analysis, not the feature's."""
    step = _start(ws)
    _clarify(ws)
    _refine(ws, {"feature": "order-tracking", "needs_design": True})
    _publish(ws, step, ANALYSIS, "docs/development/order-tracking/run/analysis")
    _finish(ws, step)


def _unversioned_ticket_front_matter(ws):
    """The pre-ADR-0128 front matter: no version keys, a made-up ticket key."""
    step = _start(ws)
    _clarify(ws)
    _refine(ws, {"feature": "order-tracking", "needs_design": True})
    text = _edit(ANALYSIS, "status: proposed\nversion: 1\ntickets: []\nfeature: order-tracking\n",
                 "ticket: order-tracking\n")
    _publish(ws, step, text)
    _finish(ws, step)


def _spec_only(ws):
    """Analyzed the attachment and dropped the prompt's guest orders."""
    step = _start(ws)
    _clarify(ws)
    _refine(ws, {"feature": "order-tracking", "needs_design": True})
    text = _edit(_edit(ANALYSIS, ", and lets guest orders track\nthrough the confirmation-email link",
                       ""), "; guest-order tracking is proposed\nas a fifth — open", "")
    assert not any("guest" in t.lower() for t in text.values())
    _publish(ws, step, text)
    _finish(ws, step)


def _committed(ws):
    IDEAL(ws)
    ws.sh("git add docs && git commit -qm 'order tracking analysis'")


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "minted a ticket first": _minted_a_ticket,
    "published to a development folder": _published_as_a_development_run,
    "unversioned front matter naming a ticket": _unversioned_ticket_front_matter,
    "dropped the prompt's guest orders": _spec_only,
    "committed the living analysis": _committed,
}
