"""Calibration plays for create-design-card-checkout.

IDEAL does what /acs:create-design's coordinator does, through the plugin's
own writers where they exist: `acs step start`, `clarify.py add` for the
answers the prompt relayed, the designer's draft in the step directory, the
Publish copy into docs/tickets/EVAL-1/ (left uncommitted: no ticket branch
exists yet, and the skill never commits to the default branch), then
result.json and the post-hook.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-design"
PUBLISHED = "docs/tickets/EVAL-1/design.md"

DESIGN = r"""# Design — EVAL-1: Checkout with card payments

## Context & constraints

Shoppers pay by card at checkout (PRD F2). The shop charges through the
external payments gateway (docs/architecture/hld/c4-context.md) and records
the order only after the charge succeeds. Security: card data never touches
the shop; only a gateway token is handled. Performance: p95 API latency under
300 ms (PRD NFR1), which the gateway call dominates.

## Options considered

### Option A — synchronous charge in the request

POST /checkout calls the gateway inline and records the order on success.
Simple and immediately consistent; the request waits on the gateway.

### Option B — queued charge worker

POST /checkout enqueues a charge and returns 202; a worker charges and records
the order. Resilient to gateway outages, but adds a queue, a worker and an
asynchronous status the shopper must poll.

## Decision & rationale

Option A: synchronous charge with an idempotency key. It meets NFR1 at today's
volume without a new component; Option B's queue is not justified yet.

### Decision records

- Charge cards synchronously at checkout with an idempotency key.
  /acs:code commits these as ADRs under docs/adr/ as part of its
  documentation updates.

## Architecture

A new `checkout` module in src/shop calls the gateway client with the
shopper's token and an idempotency key; a declined charge maps to 402
`card_declined`.

```mermaid
sequenceDiagram
  participant S as Shopper
  participant C as shop checkout
  participant G as Payments gateway
  S->>C: POST /checkout (token, idempotency key)
  C->>G: charge(token, amount, key)
  G-->>C: approved | declined
  C-->>S: 201 order | 402 card_declined
```

### Architecture conformance

Required architecture changes: docs/architecture/lld/flows.md gains the
checkout sequence above.

## Impact & risks

Payments are load-bearing: a double charge is the worst failure, mitigated by
the idempotency key. A gateway outage fails checkout outright.

## Rollout/migration

Single-step deploy behind no flag; no stored shape changes, so rollback is a
redeploy of the previous version.
"""

ANSWERS = [
    ("Synchronous charge or a queued worker?", "Simplest option that meets p95 < 300 ms; no queue yet"),
    ("May card data reach our servers?", "No; only the gateway card token"),
]


def _start(ws):
    ws.skill("create-design")
    started = ws.acs("step", "start", "--step", "create-design", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws):
    result = {"status": "completed", "summary": "calibration",
              "states": {"design_path": PUBLISHED,
                         "decision": "Charge cards synchronously at checkout with an idempotency key (Option A)"},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-design.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def _publish(ws, text):
    ws.write(STEP + "/design.md", text)
    ws.sh('mkdir -p docs/tickets/EVAL-1 && cp "%s/design.md" "%s"' % (STEP, PUBLISHED))


def IDEAL(ws):
    _start(ws)
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill create-design --ticket EVAL-1 '
              '--question "%s" --answer "%s"' % (SCRIPTS, question, answer))
    _publish(ws, DESIGN)
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _one_option(ws):
    """Published a design that states a single answer and has no diagram."""
    _start(ws)
    head, rest = DESIGN.split("### Option B", 1)
    one = head + "## Decision" + rest.split("## Decision", 1)[1]
    _publish(ws, one.split("```mermaid")[0] + "### Architecture conformance\n\nConforms.\n\n"
             "## Impact & risks\n\nLow.\n\n## Rollout/migration\n\nDeploy.\n")
    _finish(ws)


def _built_it(ws):
    """Skipped the design and implemented checkout instead."""
    _start(ws)
    ws.write("src/shop/checkout.py", "def checkout(token):\n    return {'order': 1}\n")


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "one option, no flow diagram": _one_option,
    "implemented checkout instead of designing it": _built_it,
}
