"""Calibration plays for create-api-contract-event-schema.

IDEAL does what /acs:create-api-contract's coordinator does in a repo that
keeps contracts (mode `schemas/events`), through the plugin's own writers
where they exist: `acs step start`, the draft, the new event schema beside
order.created.json, the Publish copy, all left uncommitted on main (ADR-0127),
then result.json with outcome contract_written and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract"
PUBLISHED = "docs/architecture/lld/order-tracking/EVAL-1/api-contract.md"
SCHEMA = "schemas/events/order.shipped.json"
CONTRACT = '---\nticket: EVAL-1\nitems: 1\ncontract_files: [schemas/events/order.shipped.json]\n---\n\n# API contract — EVAL-1: Publish order.shipped when an order ships\n\n## Scope & sources\n\nThe event docs/development/order-tracking/EVAL-1/plan.md adds. Sources: the plan, the analysis,\nsrc/shop/events.py, schemas/events/order.created.json.\n\n## Surface\n\n### Event order.shipped\n\nPublished on the shop event bus by `mark_shipped`. Envelope as order.created:\n`event_id` (uuid4), `occurred_at` (RFC 3339), `schema_version` 1. Payload:\n`order_id`, `carrier`, `tracking_number`, `shipped_at`.\n\n## Error model\n\nPublishing is at-least-once: a consumer may see an event twice and\ndeduplicates by `event_id`. There is no error response; a malformed event\nfails validation against its schema before publish.\n\n## Compatibility & versioning\n\nNew event, `schema_version` 1. Additive fields only within version 1.\n\n## Examples\n\n`{"event": "order.shipped", "event_id": "5f0c...", "schema_version": 1, ...}`\n\n## Traceability\n\n| Item | AC | Plan item |\n|---|---|---|\n| order.shipped payload | AC-1 | task 1 |\n| envelope | AC-2 | task 1 |\n| at-least-once delivery | AC-3 | task 1 |\n\n## Contract files\n\nMode `schemas/events`: added schemas/events/order.shipped.json in the format\norder.created.json already uses.\n'
SHIPPED = json.dumps({"title": "order.shipped", "type": "object",
                      "required": ["event", "event_id", "occurred_at", "schema_version", "payload"],
                      "properties": {"event": {"const": "order.shipped"},
                                     "event_id": {"type": "string", "format": "uuid"}}}, indent=2)


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-api-contract")
    started = ws.acs("step", "start", "--step", "create-api-contract", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws, files):
    result = {"status": "completed", "outcome": "contract_written", "summary": "calibration",
              "states": {"items": 1, "contract_path": PUBLISHED,
                         "traced_acs": ["AC-1", "AC-2", "AC-3"], "contract_files": files},
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-api-contract.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def _publish(ws, text, extra=()):
    ws.write(STEP + "/api-contract.md", text)
    ws.sh('mkdir -p "%s" && cp "%s/api-contract.md" "%s"' % (os.path.dirname(PUBLISHED), STEP, PUBLISHED))


def IDEAL(ws):
    _start(ws)
    ws.write(SCHEMA, SHIPPED)
    _publish(ws, CONTRACT, [SCHEMA])
    _finish(ws, [SCHEMA])


def _invented_asyncapi(ws):
    """Ignored the repo's schemas and introduced an AsyncAPI document."""
    _start(ws)
    ws.write("docs/api/asyncapi.yaml", "asyncapi: 2.6.0\n")
    _publish(ws, CONTRACT.replace("schemas/events/order.shipped.json", "docs/api/asyncapi.yaml")
             .replace("Mode `schemas/events`", "Mode `docs/api`"), ["docs/api/asyncapi.yaml"])
    _finish(ws, ["docs/api/asyncapi.yaml"])


def _http_shaped(ws):
    """Specified the event as an HTTP webhook and skipped the schema."""
    _start(ws)
    http = CONTRACT.replace("### Event order.shipped", "### POST /events/order.shipped")
    _publish(ws, http.split("## Contract files")[0] + "## Contract files\n\nNone.\n")
    _finish(ws, [])


def _started_only(ws):
    _start(ws)


BAD = {
    "introduced an AsyncAPI document in docs/api": _invented_asyncapi,
    "an HTTP-shaped item and no schema": _http_shaped,
    "fired the skill, started the step, wrote nothing": _started_only,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed what it published on a new ticket branch"] = _committed_on_a_ticket_branch
