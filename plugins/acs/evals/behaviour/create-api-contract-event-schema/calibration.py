"""Calibration plays for create-api-contract-event-schema (see
tests/evals/check_grader_calibration.py).

IDEAL does what /acs:create-api-contract's coordinator and its subagents do as
a Design skill (ADR-0134) in a repo that keeps one JSON Schema per event:
`acs step start` (no plan), the survey notes, ONE gap analyst for
order-events.md, ONE un-sliced writer adding the order.shipped item to that
document in place and bumping it through `acs.py design bump`, the derived
preamble joined with the writer's fragment, the review, the Publish copy of
the run record, then result.json with outcome contract_written and the real
post-hook. Documents only: no schema is written -- the plan and /acs:code do
that from the approved contract.
"""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract"
L = "docs/architecture/lld/order-tracking"
DOC = L + "/api/order-events.md"
RECORD = L + "/EVAL-1/api-contract.md"
SCHEMA = "schemas/events/order.shipped.json"

SHIPPED = """
### event order.shipped (planned)

- **Kind and status**: event, NEW.
- **Request**: none; published by `mark_shipped` when an order ships.
- **Response**: the envelope as order.created -- `event_id` (uuid4),
  `occurred_at` (RFC 3339), `schema_version` 1 -- and the payload `order_id`,
  `carrier`, `tracking_number`, `shipped_at`.
- **Errors**: none; at-least-once delivery, consumers deduplicate by
  `event_id` (C-1).
- **Traces**: AC-1, AC-2, AC-3.
"""

FRAGMENT = """## Scope & sources

order.shipped joins the order events (EVAL-1). Sources: requirements.md, the
analysis README, src/shop/events.py, schemas/events/order.created.json.

## Interfaces

| Document | Version | Status | Items |
|---|---|---|---|
| docs/architecture/lld/order-tracking/api/order-events.md | 2 | proposed | event order.shipped NEW |

## Compatibility & versioning

A new event, schema_version 1; additive.

## Traceability

| Item | Criterion |
|---|---|
| order.shipped payload | AC-1 |
| envelope | AC-2 |
| at-least-once delivery | AC-3 |

## Gaps

None.
"""

PREAMBLE = ('---\nticket: EVAL-1\nitems: 1\n'
            'interfaces: ["docs/architecture/lld/order-tracking/api/order-events.md"]\n---\n\n'
            "# API contract — EVAL-1: Publish order.shipped when an order ships\n")


def _start(ws):
    ws.skill("create-api-contract")
    started = ws.acs("step", "start", "--step", "create-api-contract", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    ws.sh('python3 "%s/clarify.py" add --skill create-api-contract --ticket EVAL-1 '
          '--question "Delivery guarantee?" --answer "At-least-once; dedupe by event_id"'
          % SCRIPTS)
    ws.write(STEP + "/iter-1/authoring.md",
             "## Interface inventory\n\norder-events: CHANGED, api/order-events.md, "
             "src/shop/events.py:6.\n\n## Item list\n\nevent order.shipped NEW (AC-1..AC-3).\n")
    ws.write(STEP + "/iter-1/gaps-order-events.md",
             "## Unimplemented\n\n_None._\n\n## Undocumented\n\n_None._\n\n"
             "## Drifted\n\n_None._\n\n## Unverified\n\n_None._\n")


def _revise(ws, http=False, bump=True):
    path = os.path.join(ws.path, DOC)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    item = SHIPPED if not http else SHIPPED.replace("### event order.shipped (planned)",
                                                   "### POST /events/order.shipped (planned)")
    ws.write(DOC, text.replace("\n## Error model", item + "\n## Error model", 1))
    if bump:
        done = ws.acs("design", "bump", "--ticket", "EVAL-1", DOC)
        assert done.returncode == 0, done.stderr


def _record(ws, publish=True):
    ws.write(STEP + "/api-contract-write.md", FRAGMENT)
    ws.write(STEP + "/api-contract-preamble.md", PREAMBLE)
    joined = ws.acs("notes", "merge", "--no-markers", "--out", STEP + "/api-contract.md",
                    STEP + "/api-contract-preamble.md", STEP + "/api-contract-write.md")
    assert joined.returncode == 0, joined.stderr
    if publish:
        ws.sh('mkdir -p "%s" && cp "%s/api-contract.md" "%s"'
              % (os.path.dirname(RECORD), STEP, RECORD))


def _finish(ws, files=None):
    result = {"status": "completed", "outcome": "contract_written", "summary": "calibration",
              "states": {"contract_path": RECORD, "feature": ["order-tracking"],
                         "files": [DOC, RECORD] if files is None else files,
                         "types": ["api-contract"], "interfaces": [DOC], "items": 1,
                         "traced_acs": ["AC-1", "AC-2", "AC-3"],
                         "gaps": {"undocumented": 0, "unimplemented": 0, "drifted": 0}},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result, indent=2))
    done = subprocess.run([sys.executable, os.path.join(SCRIPTS, "post-create-api-contract.py"),
                           "--result-file", STEP + "/result.json"],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    _revise(ws)
    _record(ws)
    _finish(ws)
    ws.reply = ("## /acs:create-api-contract · EVAL-1 · completed\n\n- **Results**: "
                "order.shipped added to docs/architecture/lld/order-tracking/api/order-events.md "
                "(proposed v2); run record shared; documents only -- its JSON Schema is for "
                "/acs:code, from the plan.\n- **Next**: /acs:create-impl-plan EVAL-1")


def _wrote_the_schema(ws):
    """The pre-ADR-0134 behaviour: the machine-readable contract written here."""
    IDEAL(ws)
    ws.write(SCHEMA, json.dumps({"title": "order.shipped", "type": "object"}, indent=2))


def _invented_an_endpoint(ws):
    _start(ws)
    _revise(ws, http=True)
    _record(ws)
    _finish(ws)


def _edited_the_existing_schema(ws):
    """Folded order.shipped into order.created's schema."""
    IDEAL(ws)
    path = os.path.join(ws.path, "schemas/events/order.created.json")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    ws.write("schemas/events/order.created.json",
             text.replace('"title": "order.created"', '"title": "order.created or order.shipped"'))


def _no_version_bump(ws):
    _start(ws)
    _revise(ws, bump=False)
    _record(ws)
    _finish(ws)


def _never_published(ws):
    _start(ws)
    _revise(ws)
    _record(ws, publish=False)
    _finish(ws, files=[DOC])


def _never_finished(ws):
    _start(ws)
    _revise(ws)
    _record(ws)


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("create-api-contract"),
    "wrote the event's JSON Schema": _wrote_the_schema,
    "invented an HTTP endpoint for the event": _invented_an_endpoint,
    "edited the existing event schema": _edited_the_existing_schema,
    "rewrote the document without a version bump": _no_version_bump,
    "never published the run record": _never_published,
    "never ran the post-hook": _never_finished,
}
