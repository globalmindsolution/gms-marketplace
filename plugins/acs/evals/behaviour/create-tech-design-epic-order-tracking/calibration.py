"""Calibration plays for create-tech-design-epic-order-tracking.

IDEAL does what /acs:create-tech-design's coordinator does, through the plugin's
own writers: `acs step start`, the relayed answers recorded with `clarify.py
add`, the designer's draft with its version front matter, the Publish copy into docs/architecture/lld/order-tracking/EVAL-1/ (left
uncommitted: no ticket branch exists), result.json and the post-hook, and a
reply naming the fan-out."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-tech-design"
PUBLISHED = "docs/architecture/lld/order-tracking/EVAL-1/tech-design.md"
DESIGN = r"""# Tech design — EVAL-1: Order tracking

## Decision & options

**Decision:** receive carrier status through signed webhooks (Option A).

### Context

Shoppers track an order from payment to delivery (PRD F3), fed by two carriers.

### Options considered

#### Option A — carriers push signed webhooks

Near-real-time; one inbound endpoint to secure.

#### Option B — scheduled polling of carrier APIs

No inbound surface; minutes of lag and load that grows with volume.

### Rationale

Option A meets the one-minute criterion with the least moving parts (C-1).

### Decision records

- Receive carrier status through signed webhooks.

## HLD views affected

- [hld/c4-context.md](../../../hld/c4-context.md) — unversioned: the two
  carriers join as external systems — change required: add them with their
  webhook relation.

## LLD

The feature's LLD folder `docs/architecture/lld/order-tracking/`.

### API

none yet — run /acs:create-api-contract EVAL-1: POST /webhooks/carrier/{carrier}
and GET /orders/{id}/status.

### Data

none yet — run /acs:create-data-design EVAL-1: the order status history.

### Flows

none yet — run /acs:create-flows EVAL-1: carrier callback to shopper email.

### Components

none yet — run /acs:create-flows EVAL-1: the tracking intake component.

## NFRs

Security: carrier callbacks are authenticated with a shared secret per
carrier. Performance: p95 under 300 ms (NFR1).

## Risks

A forged callback misleads shoppers; mitigated by signature checks.

### Rollout & migration

The epic fans out into three child slices, one reviewable PR each:

| Slice | Type | Scope |
|---|---|---|
| 1. Carrier status webhooks | story | intake and storage |
| 2. Order status page | story | GET /orders/{id}/status |
| 3. Status-change emails | task | notify the shopper |

## Open questions

none
"""

def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-tech-design")
    started = ws.acs("step", "start", "--step", "create-tech-design", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _publish(ws, text):
    ws.write(STEP + "/tech-design.md", text)
    ws.acs("design", "init", "--status", "proposed", "--ticket", "EVAL-1",
           "--feature", "order-tracking", STEP + "/tech-design.md")
    ws.sh('mkdir -p docs/architecture/lld/order-tracking/EVAL-1 && cp "%s/tech-design.md" "%s"' % (STEP, PUBLISHED))


def _finish(ws, decision):
    result = {"status": "completed", "summary": "calibration",
              "states": {"design_path": PUBLISHED, "decision": decision},
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-tech-design.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))

DECISION = "Receive carrier status through signed webhooks (Option A)"


def IDEAL(ws):
    _start(ws)
    ws.sh('python3 "%s/clarify.py" add --skill create-tech-design --ticket EVAL-1 '
          '--question "Webhooks or polling?" --answer "Simplest option meeting p95 < 300 ms" > /dev/null'
          % SCRIPTS)
    _publish(ws, DESIGN)
    _finish(ws, DECISION)
    ws.reply = ("Tech design published (proposed) for epic EVAL-1. Next: approve it with "
                "/acs:set-doc-status approved order-tracking, then /acs:create-ticket EVAL-1 "
                "--fan-out, then /acs:code on each child.")


def _minted_children(ws):
    """Designed, then fanned the epic out itself."""
    IDEAL(ws)
    ws.sh('python3 "%s/new-ticket.py" --title "Carrier status webhooks" --type story '
          '--parent EVAL-1 --needs-design false > /dev/null' % SCRIPTS)


def _story_style(ws):
    """One option, no slices, and the story next step."""
    _start(ws)
    one = DESIGN.split("#### Option B")[0] + "### Rationale" + DESIGN.split("### Rationale", 1)[1]
    _publish(ws, one.split("### Rollout & migration")[0] + "### Rollout & migration\n\n"
             "Single deploy.\n\n## Open questions\n\nnone\n")
    _finish(ws, DECISION)
    ws.reply = "Design published. Next: /acs:code EVAL-1."


def _started_only(ws):
    _start(ws)


BAD = {
    "minted a child during the design": _minted_children,
    "one option, no slices, story next step": _story_style,
    "fired the skill, started the step, wrote nothing": _started_only,
}


def _committed_on_a_ticket_branch(ws):
    """Everything right, then a ticket branch and a commit -- only
    /acs:create-pr branches and commits (ADR-0127)."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed the design on a new ticket branch"] = _committed_on_a_ticket_branch
