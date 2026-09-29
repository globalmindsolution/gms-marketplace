"""Calibration plays for create-architecture-regenerate-after-shift (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--allocate` mints the delivery ticket, the architects regenerate the existing
doc set in place against the new code (stale worker, Redis and flow out; the
orders API and its flow in; list-customers kept), the coordinator commits and
pushes the delivery branch, gh fails, and the result document goes through
the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-architecture.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-architecture"
BRANCH = "task/EVAL-1-product-architecture-doc-set"
A = "docs/architecture"

REGENERATED = {
    "hld/overview.md": "# Overview\n\n## System context\n\nThe `shop` API serves shoppers.\n\n"
                       "## Goals\n\nG1, G2.\n\n## Quality attributes\n\np95 < 300 ms.\n\n"
                       "## Constraints\n\nPython 3.\n\nFlows: [list-customers](../lld/flows/"
                       "list-customers.md), [list-orders](../lld/flows/list-orders.md)\n",
    "hld/c4-container.md": "# C4 container\n\n```mermaid\nC4Container\n"
                           "  Container(api, \"shop\", \"Python 3\", \"storefront API\")\n```\n",
    "hld/c4-component.md": "# C4 component\n\n```mermaid\nC4Component\n"
                           "  Component(listing, \"list_customers\", \"shop\")\n"
                           "  Component(orders, \"list_orders\", \"shop\")\n```\n",
    "hld/deployment.md": "# Deployment\n\n```mermaid\nflowchart LR\n  lb[load balancer] --> shop\n```\n",
    "hld/tech-stack.md": "# Tech stack\n\n## Languages\n\nPython 3.\n\n## Frameworks\n\npytest.\n\n"
                         "## Conventions\n\nsrc layout.\n",
    "hld/project-structure.md": "# Project structure\n\n## Directory layout\n\n```mermaid\n"
                                "flowchart TD\n  root --> src/shop\n  root --> tests\n```\n",
    "lld/contracts.md": "# Contracts\n\n## Contracts\n\n- `GET /health` returns `ok`.\n"
                        "- `GET /customers?offset=&limit=` returns `{items, offset, limit}`.\n"
                        "- `GET /orders?customer_id=&offset=&limit=` returns one customer's orders.\n",
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


def _deliver(ws, docs=None, drop=("lld/flows/nightly-export.md",)):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for rel, text in (REGENERATED if docs is None else docs).items():
        ws.write("%s/%s" % (A, rel), text)
    for rel in drop:
        ws.sh("git rm -q %s/%s" % (A, rel))
    ws.sh("git add %s && git commit -qm 'EVAL-1 Regenerate product architecture doc set'" % A)
    ws.sh("git push -q -u origin %s" % BRANCH)


def _finish(ws, findings=(GH_FINDING,)):
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "doc set regenerated after the shift; gh failed, no PR",
        "states": {"architecture": {
            "path": A,
            "hld": ["overview.md", "c4-context.md", "c4-container.md", "c4-component.md",
                    "data-model.md", "deployment.md", "tech-stack.md", "project-structure.md"],
            "lld": ["contracts.md", "flows/list-customers.md", "flows/list-orders.md"]}},
        "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws)
    ws.reply = ("EVAL-1 (re-run): doc set regenerated on %s -- export-worker, Redis and "
                "nightly-export removed, list-orders added. Pushed; gh pr create failed, so no "
                "PR was opened." % BRANCH)


def _added_only(ws):
    """Added the orders API but left the stale worker and flow in place."""
    _start(ws)
    docs = {k: v for k, v in REGENERATED.items()
            if k in ("lld/flows/list-orders.md",)}
    docs["lld/contracts.md"] = (REGENERATED["lld/contracts.md"]
                                + "- `exports` Redis queue, pushed nightly (see nightly-export).\n")
    _deliver(ws, docs=docs, drop=())
    _finish(ws)


def _dropped_every_flow(ws):
    """Regenerated from scratch and lost the still-valid list-customers flow."""
    _start(ws)
    _deliver(ws, drop=("lld/flows/nightly-export.md", "lld/flows/list-customers.md"))
    _finish(ws)


def _never_pushed(ws):
    _start(ws)
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for rel, text in REGENERATED.items():
        ws.write("%s/%s" % (A, rel), text)
    _finish(ws)


BAD = {
    "added the orders API but kept the stale worker": _added_only,
    "dropped the still-valid list-customers flow": _dropped_every_flow,
    "regenerated but never committed or pushed": _never_pushed,
    "allocated the ticket and changed nothing": _start,
}
