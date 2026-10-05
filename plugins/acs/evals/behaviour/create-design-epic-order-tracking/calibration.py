"""Calibration plays for create-design-epic-order-tracking.

IDEAL does what /acs:create-design's coordinator does, through the plugin's
own writers: `acs step start`, the relayed answers recorded with `clarify.py
add`, the designer's draft, the Publish copy into docs/tickets/EVAL-1/ (left
uncommitted: no ticket branch exists), result.json and the post-hook, and a
reply naming the fan-out."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-design"
PUBLISHED = "docs/tickets/EVAL-1/design.md"
DESIGN = '# Design — EVAL-1: Order tracking\n\n## Context & constraints\n\nShoppers track an order from payment to delivery (PRD F3). Two carriers.\nSecurity: carrier callbacks are authenticated per carrier. Performance: p95\nunder 300 ms (NFR1).\n\n## Options considered\n\n### Option A — carriers push signed webhooks\n\nNear-real-time; one inbound endpoint to secure.\n\n### Option B — scheduled polling of carrier APIs\n\nNo inbound surface; minutes of lag and load that grows with volume.\n\n## Decision & rationale\n\nOption A: signed carrier webhooks.\n\n### Decision records\n\n- Receive carrier status through signed webhooks.\n\n## Architecture\n\n```mermaid\nsequenceDiagram\n  participant K as Carrier\n  participant T as shop tracking\n  K->>T: POST /webhooks/carrier/{carrier} (signed)\n  T-->>K: 204\n```\n\n### Architecture conformance\n\nRequired architecture changes: docs/architecture/lld/flows.md gains the\ntracking sequence.\n\n## Impact & risks\n\nA forged callback misleads shoppers; mitigated by signature checks.\n\n## Rollout/migration\n\nThe epic fans out into three child slices, one reviewable PR each:\n\n| Slice | Type | Scope |\n|---|---|---|\n| 1. Carrier status webhooks | story | intake and storage |\n| 2. Order status page | story | GET /orders/{id}/status |\n| 3. Status-change emails | task | notify the shopper |\n'

def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-design")
    started = ws.acs("step", "start", "--step", "create-design", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _publish(ws, text):
    ws.write(STEP + "/design.md", text)
    ws.sh('mkdir -p docs/tickets/EVAL-1 && cp "%s/design.md" "%s"' % (STEP, PUBLISHED))


def _finish(ws, decision):
    result = {"status": "completed", "summary": "calibration",
              "states": {"design_path": PUBLISHED, "decision": decision},
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-design.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))

DECISION = "Receive carrier status through signed webhooks (Option A)"


def IDEAL(ws):
    _start(ws)
    ws.sh('python3 "%s/clarify.py" add --skill create-design --ticket EVAL-1 '
          '--question "Webhooks or polling?" --answer "Simplest option meeting p95 < 300 ms" > /dev/null'
          % SCRIPTS)
    _publish(ws, DESIGN)
    _finish(ws, DECISION)
    ws.reply = ("Design published for epic EVAL-1. Next: /acs:create-ticket EVAL-1 --fan-out, "
                "then /acs:code on each child.")


def _minted_children(ws):
    """Designed, then fanned the epic out itself."""
    IDEAL(ws)
    ws.sh('python3 "%s/new-ticket.py" --title "Carrier status webhooks" --type story '
          '--parent EVAL-1 --needs-design false > /dev/null' % SCRIPTS)


def _story_style(ws):
    """One option, no slices, and the story next step."""
    _start(ws)
    one = DESIGN.split("### Option B")[0] + DESIGN.split("## Decision & rationale")[1].join(
        ["## Decision & rationale", ""])
    _publish(ws, one.split("## Rollout/migration")[0] + "## Rollout/migration\n\nSingle deploy.\n")
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
