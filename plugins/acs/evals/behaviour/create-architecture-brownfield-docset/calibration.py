"""Calibration plays for create-architecture-brownfield-docset (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--allocate` mints the delivery ticket, the architects write the doc set, the
coordinator commits and pushes the delivery branch, gh fails, and the result
document goes through the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-architecture.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-architecture"
BRANCH = "task/EVAL-1-product-architecture-doc-set"
ARCH = "docs/architecture"

HLD = {
    "overview.md": "# Overview\n\n## System context\n\nThe shop service.\n\n## Goals\n\nG1, G2.\n\n"
                   "## Quality attributes\n\np95 < 300 ms.\n\n## Constraints\n\nPython.\n\n"
                   "Flows: [list-customers](../lld/flows/list-customers.md), "
                   "[health-check](../lld/flows/health-check.md)\n",
    "c4-context.md": "# C4 context\n\n```mermaid\nC4Context\n  System(shop, \"shop\")\n```\n",
    "c4-container.md": "# C4 container\n\n```mermaid\nC4Container\n  Container(api, \"shop\", \"Python\")\n```\n",
    "c4-component.md": "# C4 component\n\n```mermaid\nC4Component\n  Component(listing, \"list_customers\")\n```\n",
    "data-model.md": "# Data model\n\n```mermaid\nerDiagram\n  CUSTOMER {\n    string id\n  }\n```\n",
    "deployment.md": "# Deployment\n\n```mermaid\nflowchart LR\n  lb[load balancer] --> shop\n```\n",
    "tech-stack.md": "# Tech stack\n\n## Languages\n\nPython 3.\n\n## Frameworks\n\npytest.\n\n"
                     "## Conventions\n\nsrc layout.\n",
    "project-structure.md": "# Project structure\n\n## Directory layout\n\n```mermaid\nflowchart TD\n"
                            "  root --> src/shop\n  root --> tests\n```\n",
}
CONTRACTS = ("# Contracts\n\n## Contracts\n\n- `GET /health` returns `ok`.\n"
             "- `GET /customers?offset=&limit=` returns `{items, offset, limit}`; "
             "limit defaults to 20.\n")
FLOW = ("# list-customers\n\n```mermaid\nsequenceDiagram\n  participant Shopper\n"
        "  participant shop\n  Shopper->>shop: GET /customers?offset=0&limit=20\n"
        "  shop-->>Shopper: page of customers\n```\n")
HEALTH = ("# health-check\n\n```mermaid\nsequenceDiagram\n  participant LB\n  participant shop\n"
          "  LB->>shop: GET /health\n  shop-->>LB: ok\n```\n")

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws):
    ws.skill("create-architecture")
    started = ws.acs("step", "start", "--step", "create-architecture", "--allocate", "--args", "")
    assert started.returncode == 0, started.stderr


def _write_docs(ws, contracts=CONTRACTS, flow=FLOW, skip=()):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for name, text in HLD.items():
        if name not in skip:
            ws.write("%s/hld/%s" % (ARCH, name), text)
    ws.write(ARCH + "/lld/contracts.md", contracts)
    ws.write(ARCH + "/lld/flows/list-customers.md", flow)
    ws.write(ARCH + "/lld/flows/health-check.md", HEALTH)
    ws.sh("git add %s && git commit -qm 'EVAL-1 Add product architecture doc set'" % ARCH)


def _finish(ws, findings=(GH_FINDING,), pr=None):
    states = {"architecture": {"path": ARCH, "hld": sorted(HLD),
                               "lld": ["contracts.md", "flows/list-customers.md",
                                       "flows/health-check.md"]}}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "doc set reviewed; branch pushed; gh failed, no PR",
        "states": states, "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _push(ws):
    ws.sh("git push -q -u origin %s" % BRANCH)


def IDEAL(ws):
    _start(ws)
    _write_docs(ws)
    _push(ws)
    _finish(ws)
    ws.reply = ("EVAL-1: architecture doc set written on %s and pushed. gh pr create failed "
                "(no GitHub access), so no PR was opened; recorded as a finding." % BRANCH)


def _allocated_only(ws):
    _start(ws)


def _from_the_prd_only(ws):
    """A doc set that never looked at the code: checkout contracts, a
    non-Mermaid flow, and two HLD files missing."""
    _start(ws)
    _write_docs(ws, contracts="# Contracts\n\n## Contracts\n\n- `POST /checkout` charges a card.\n",
                flow="# list-customers\n\nThe shopper asks for customers.\n",
                skip=("data-model.md", "project-structure.md"))
    _push(ws)
    _finish(ws)


def _never_pushed(ws):
    _start(ws)
    _write_docs(ws)
    _finish(ws)


def _invented_pr(ws):
    _start(ws)
    _write_docs(ws)
    _push(ws)
    _finish(ws, findings=(), pr={"number": 7, "branch": BRANCH,
                                 "url": "https://github.com/example/shop/pull/7"})


BAD = {
    "allocated the ticket and wrote nothing": _allocated_only,
    "wrote an incomplete doc set from the PRD alone": _from_the_prd_only,
    "committed but never pushed the delivery branch": _never_pushed,
    "recorded a PR that cannot exist": _invented_pr,
}
