"""Calibration plays for create-tech-design-card-checkout.

IDEAL does what /acs:create-tech-design's coordinator does, through the plugin's
own writers where they exist: `acs step start`, `clarify.py add` for the
answers the prompt relayed, the designer's draft in the step directory, its
version front matter (`acs.py design init`), the Publish copy into docs/architecture/lld/checkout-with-card-payments/EVAL-1/ (left uncommitted: no ticket branch
exists yet, and the skill never commits to the default branch), then
result.json and the post-hook.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-tech-design"
PUBLISHED = "docs/architecture/lld/checkout-with-card-payments/EVAL-1/tech-design.md"

DESIGN = r"""# Tech design — EVAL-1: Checkout with card payments

## Decision & options

**Decision:** charge cards synchronously at checkout with an idempotency key (Option A).

### Context

Shoppers pay by card at checkout (PRD F2). The shop charges through the
external payments gateway (docs/architecture/hld/c4-context.md) and records
the order only after the charge succeeds.

### Options considered

#### Option A — synchronous charge in the request

POST /checkout calls the gateway inline and records the order on success.
Simple and immediately consistent; the request waits on the gateway.

#### Option B — queued charge worker

POST /checkout enqueues a charge and returns 202; a worker charges and records
the order. Resilient to gateway outages, but adds a queue, a worker and an
asynchronous status the shopper must poll.

### Rationale

Option A meets NFR1 at today's volume without a new component; Option B's
queue is not justified yet (C-1).

### Decision records

- Charge cards synchronously at checkout with an idempotency key.
  /acs:docs-sync writes these as ADRs under docs/architecture/adr/ once the
  changeset exists.

## HLD views affected

- [hld/c4-context.md](../../../hld/c4-context.md) — unversioned: `Rel(shop,
  pay, "charges cards")` — conforms, no change.

## LLD

The feature's LLD folder `docs/architecture/lld/checkout-with-card-payments/`.

### API

none yet — run /acs:create-api-contract EVAL-1: POST /checkout and its 402
`card_declined` error need specifying.

### Data

none yet — run /acs:create-data-design EVAL-1: the order record gains the
idempotency key.

### Flows

none yet — run /acs:create-flows EVAL-1: the checkout charge sequence through
the gateway.

### Components

n/a — no new component; the checkout module is internal to the shop service.

## NFRs

Security: card data never touches the shop; only a gateway token is handled.
Performance: p95 API latency under 300 ms (PRD NFR1), which the gateway call
dominates.

## Risks

Payments are load-bearing: a double charge is the worst failure, mitigated by
the idempotency key. A gateway outage fails checkout outright.

### Rollout & migration

Single-step deploy behind no flag; no stored shape changes, so rollback is a
redeploy of the previous version.

## Open questions

none
"""

ANSWERS = [
    ("Synchronous charge or a queued worker?", "Simplest option that meets p95 < 300 ms; no queue yet"),
    ("May card data reach our servers?", "No; only the gateway card token"),
]


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-tech-design")
    started = ws.acs("step", "start", "--step", "create-tech-design", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws):
    result = {"status": "completed", "summary": "calibration",
              "states": {"design_path": PUBLISHED,
                         "decision": "Charge cards synchronously at checkout with an idempotency key (Option A)"},
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-tech-design.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def _publish(ws, text, versioned=True):
    ws.write(STEP + "/tech-design.md", text)
    if versioned:
        ws.acs("design", "init", "--status", "proposed", "--ticket", "EVAL-1",
               "--feature", "checkout-with-card-payments", STEP + "/tech-design.md")
    ws.sh('mkdir -p docs/architecture/lld/checkout-with-card-payments/EVAL-1 && cp "%s/tech-design.md" "%s"' % (STEP, PUBLISHED))


def IDEAL(ws):
    _start(ws)
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill create-tech-design --ticket EVAL-1 '
              '--question "%s" --answer "%s"' % (SCRIPTS, question, answer))
    _publish(ws, DESIGN)
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _one_option(ws):
    """Published a design that states a single answer and drops the LLD
    snapshots it should point at."""
    _start(ws)
    head, rest = DESIGN.split("#### Option B", 1)
    one = head + "### Rationale" + rest.split("### Rationale", 1)[1]
    one = one.split("### API")[0] + "## NFRs" + one.split("## NFRs", 1)[1]
    _publish(ws, one)
    _finish(ws)


def _unversioned(ws):
    """Published the hand-off with no version front matter: nothing the team
    can approve with /acs:set-doc-status."""
    _start(ws)
    _publish(ws, DESIGN, versioned=False)
    _finish(ws)


def _old_shape(ws):
    """Published the pre-ADR-0135 design.md shape under the new name."""
    _start(ws)
    old = DESIGN.replace("## Decision & options", "## Context & constraints").replace(
        "## HLD views affected", "## Architecture")
    _publish(ws, old)
    _finish(ws)


def _built_it(ws):
    """Skipped the design and implemented checkout instead."""
    _start(ws)
    ws.write("src/shop/checkout.py", "def checkout(token):\n    return {'order': 1}\n")


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "one option, no LLD snapshots": _one_option,
    "published without version front matter": _unversioned,
    "the old design.md section shape": _old_shape,
    "implemented checkout instead of designing it": _built_it,
}


def _committed_on_a_ticket_branch(ws):
    """Everything right, then a ticket branch and a commit -- only
    /acs:create-pr branches and commits (ADR-0127)."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed the design on a new ticket branch"] = _committed_on_a_ticket_branch
