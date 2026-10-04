"""Calibration plays for create-architecture-regenerate-after-shift (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--allocate` mints the delivery ticket, the architect regenerates the existing
HLD in place against the new code (stale worker and Redis out; the orders API
in; the two HLD files the old set lacked created), every file under lld/ is
left exactly as it was, the coordinator commits and pushes the delivery
branch, gh fails, and the result document goes through the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-architecture.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-architecture"
BRANCH = "task/EVAL-1-product-architecture-doc-set"
A = "docs/architecture"

REGENERATED = {
    "hld/overview.md": "# Overview\n\n## System context\n\nThe `shop` API serves shoppers: customers "
                       "and their orders.\n\n## Goals\n\nG1, G2.\n\n## Quality attributes\n\n"
                       "p95 < 300 ms.\n\n## Constraints\n\nPython 3.\n",
    "hld/tech-stack.md": "# Tech stack\n\n## Languages\n\nPython 3.\n\n## Frameworks\n\npytest.\n\n"
                         "## Conventions\n\nsrc layout.\n",
    "hld/cross-cutting.md": "# Cross-cutting conventions\n\n## API conventions\n\nJSON over HTTP; "
                            "lists page with `offset` and `limit`.\n\n## Data conventions\n\n"
                            "In-memory data.\n\n## Security\n\nNo authentication yet.\n\n"
                            "## Observability\n\nGET /health.\n",
    "hld/c4-context.md": "# C4 context\n\n```mermaid\nC4Context\n  Person(shopper, \"Shopper\")\n"
                         "  System(shop, \"shop\", \"storefront API\")\n"
                         "  Rel(shopper, shop, \"browses\")\n```\n",
    "hld/c4-container.md": "# C4 container\n\n```mermaid\nC4Container\n"
                           "  Container(api, \"shop\", \"Python 3\", \"storefront API\")\n```\n",
    "hld/c4-component.md": "# C4 component\n\n```mermaid\nC4Component\n"
                           "  Component(listing, \"list_customers\", \"shop\")\n"
                           "  Component(orders, \"list_orders\", \"shop\")\n```\n",
    "hld/data-model.md": "# Data model\n\n```mermaid\nerDiagram\n  CUSTOMER ||--o{ ORDER : places\n```\n",
    "hld/integration-map.md": "# Integration map\n\n```mermaid\nflowchart LR\n"
                              "  client[shopper client] -->|GET /customers sync| shop\n"
                              "  client -->|GET /orders sync| shop\n"
                              "  lb[load balancer] -->|GET /health sync| shop\n```\n",
    "hld/deployment.md": "# Deployment\n\n```mermaid\nflowchart LR\n  lb[load balancer] --> shop\n```\n",
    "hld/project-structure.md": "# Project structure\n\n## Directory layout\n\n```mermaid\n"
                                "flowchart TD\n  root --> src/shop\n  root --> tests\n```\n",
}
# What the pre-ADR-0118 skill did to the low-level design, and this one never does.
LLD_REWRITE = {
    "lld/contracts.md": "# Contracts\n\n## Contracts\n\n- `GET /health` returns `ok`.\n"
                        "- `GET /customers?offset=&limit=` returns `{items, offset, limit}`.\n"
                        "- `GET /orders?customer_id=&offset=&limit=` returns one customer's orders.\n",
    "lld/flows/list-customers.md": "# list-customers\n\n```mermaid\nsequenceDiagram\n"
                                   "  participant Shopper\n  participant shop as shop API\n"
                                   "  Shopper->>shop: GET /customers?offset=0&limit=20\n"
                                   "  shop-->>Shopper: page of customers\n```\n",
    "lld/flows/list-orders.md": "# list-orders\n\n```mermaid\nsequenceDiagram\n  participant Shopper\n"
                                "  participant shop\n  Shopper->>shop: GET /orders?customer_id=7\n"
                                "  shop-->>Shopper: page of orders\n```\n",
}

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws):
    ws.skill("create-architecture")
    started = ws.acs("step", "start", "--step", "create-architecture", "--allocate", "--args", "")
    assert started.returncode == 0, started.stderr


def _deliver(ws, docs=None, drop=()):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for rel, text in (REGENERATED if docs is None else docs).items():
        ws.write("%s/%s" % (A, rel), text)
    for rel in drop:
        ws.sh("git rm -q %s/%s" % (A, rel))
    ws.sh("git add %s && git commit -qm 'EVAL-1 Regenerate product architecture doc set'" % A)
    ws.sh("git push -q -u origin %s" % BRANCH)


def _finish(ws, findings=(GH_FINDING,), docs=None):
    hld = [rel.split("/", 1)[1] for rel in (REGENERATED if docs is None else docs)
           if rel.startswith("hld/")]
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "HLD regenerated after the shift; gh failed, no PR",
        "states": {"architecture": {"path": A, "hld": hld}},
        "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws)
    ws.reply = ("EVAL-1 (re-run): HLD regenerated in place on %s -- export-worker and Redis "
                "removed, the orders API added, cross-cutting.md and integration-map.md written; "
                "lld/ left as it was. Pushed; gh pr create failed, so no PR was opened." % BRANCH)


def _added_only(ws):
    """Added the orders API to the component view but left the stale worker
    in the container and deployment views."""
    _start(ws)
    docs = {k: v for k, v in REGENERATED.items()
            if k not in ("hld/c4-container.md", "hld/deployment.md")}
    _deliver(ws, docs=docs)
    _finish(ws, docs=docs)


def _rewrote_the_lld(ws):
    """The pre-ADR-0118 behaviour: regenerated the HLD and also rewrote the
    contracts and the list-customers flow in the new vocabulary, added
    list-orders and deleted the stale nightly-export flow."""
    _start(ws)
    docs = dict(REGENERATED)
    docs.update(LLD_REWRITE)
    _deliver(ws, docs=docs, drop=("lld/flows/nightly-export.md",))
    _finish(ws)


def _deleted_the_stale_flow(ws):
    """Regenerated the HLD and tidied one stale LLD flow away."""
    _start(ws)
    _deliver(ws, drop=("lld/flows/nightly-export.md",))
    _finish(ws)


def _no_cross_cutting(ws):
    _start(ws)
    docs = {k: v for k, v in REGENERATED.items() if k != "hld/cross-cutting.md"}
    _deliver(ws, docs=docs)
    _finish(ws, docs=docs)


def _no_integration_map(ws):
    _start(ws)
    docs = {k: v for k, v in REGENERATED.items() if k != "hld/integration-map.md"}
    _deliver(ws, docs=docs)
    _finish(ws, docs=docs)


def _never_pushed(ws):
    _start(ws)
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for rel, text in REGENERATED.items():
        ws.write("%s/%s" % (A, rel), text)
    _finish(ws)


BAD = {
    "added the orders API but kept the stale worker": _added_only,
    "rewrote the LLD contracts and flows": _rewrote_the_lld,
    "deleted the stale nightly-export LLD flow": _deleted_the_stale_flow,
    "left out hld/cross-cutting.md": _no_cross_cutting,
    "left out hld/integration-map.md": _no_integration_map,
    "regenerated but never committed or pushed": _never_pushed,
    "allocated the ticket and changed nothing": _start,
}
