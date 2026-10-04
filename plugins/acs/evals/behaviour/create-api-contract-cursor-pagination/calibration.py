"""Calibration plays for create-api-contract-cursor-pagination.

IDEAL does what /acs:create-api-contract's coordinator does, through the
plugin's own writers where they exist: `acs step start`, the
contract-author's draft in the step directory (mode
no-machine-readable-contracts, so no contract files), the Publish copy into
docs/architecture/lld/customer-listing/EVAL-1/ left uncommitted on main (ADR-0127: no branch, no
commit), then result.json with outcome contract_written and the post-hook.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract"
PUBLISHED = "docs/architecture/lld/customer-listing/EVAL-1/api-contract.md"

CONTRACT = r"""---
ticket: EVAL-1
items: 1
contract_files: []
---

# API contract — EVAL-1: Cursor pagination for GET /customers

## Scope & sources

The surface docs/development/customer-listing/EVAL-1/plan.md adds: GET /customers gains a `cursor`
query parameter, a `next_cursor` response field and an `invalid_cursor` error.
Sources: the plan, docs/development/customer-listing/EVAL-1/analysis.md, src/shop/__init__.py,
README.md's API section.

## Surface

### GET /customers

- Query: `cursor` (optional, opaque string), `limit` (optional, 1-100,
  default 20), `offset` (optional, deprecated; ignored when `cursor` is given).
- 200 body: `{"items": [...], "limit": 20, "next_cursor": "Y3VzdC0yMA"}`;
  `next_cursor` is `null` on the last page.

## Error model

| Code | HTTP | When |
|---|---|---|
| `invalid_cursor` | 400 | `cursor` is not a cursor this API issued |

## Compatibility & versioning

Backward compatible, in place: `offset` clients keep working (C-2).

## Examples

`GET /customers?cursor=Y3VzdC0yMA&limit=20` -> 200 with the next page.
`GET /customers?cursor=%%%` -> 400 `{"error": "invalid_cursor"}`.

## Traceability

| Item | AC | Plan item |
|---|---|---|
| GET /customers `cursor` | AC-1 | task 1 |
| GET /customers `next_cursor` | AC-2 | task 1 |
| `invalid_cursor` | AC-3 | task 1 |

## Contract files

Mode `no-machine-readable-contracts`: the repo keeps no OpenAPI, schema or
`docs/api/` tree, and this run introduces none.
"""


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-api-contract")
    started = ws.acs("step", "start", "--step", "create-api-contract", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws, outcome, items, published):
    result = {"status": "completed", "outcome": outcome, "summary": "calibration",
              "states": {"items": items,
                         "traced_acs": ["AC-1", "AC-2", "AC-3"] if items else []},
              "findings": [], "errors": []}
    if published:
        result["states"]["contract_path"] = PUBLISHED
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-api-contract.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def _publish(ws, text):
    ws.write(STEP + "/api-contract.md", text)
    ws.sh('cp "%s/api-contract.md" "%s"' % (STEP, PUBLISHED))


def IDEAL(ws):
    _start(ws)
    _publish(ws, CONTRACT)
    _finish(ws, "contract_written", 1, True)


def _no_surface(ws):
    """Declared no surface owed despite the plan: nothing published."""
    _start(ws)
    _finish(ws, "no_surface_owed", 0, False)


def _invented_openapi(ws):
    """Published the contract but also introduced an OpenAPI document the repo
    never used."""
    _start(ws)
    ws.write("docs/api/openapi.yaml", "openapi: 3.0.0\npaths:\n  /customers: {}\n")
    _publish(ws, CONTRACT.replace("contract_files: []", 'contract_files: ["docs/api/openapi.yaml"]'))
    _finish(ws, "contract_written", 1, True)


def _prose_contract(ws):
    """A hand-written note with no front matter, sections or error model."""
    _start(ws)
    ws.write(PUBLISHED, "# Contract\n\nGET /customers takes a cursor.\n")


BAD = {
    "settled no_surface_owed": _no_surface,
    "invented an OpenAPI document": _invented_openapi,
    "a prose note instead of the contract": _prose_contract,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed what it published on a new ticket branch"] = _committed_on_a_ticket_branch
