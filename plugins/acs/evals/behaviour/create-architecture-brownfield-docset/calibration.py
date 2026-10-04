"""Calibration plays for create-architecture-brownfield-docset (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--allocate` mints the delivery ticket, the architect writes the high-level
design (hld/ only, nothing under lld/), the coordinator commits and pushes the
delivery branch, gh fails, and the result document goes through the real
post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-architecture.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-architecture"
BRANCH = "task/EVAL-1-product-architecture-doc-set"
ARCH = "docs/architecture"

HLD = {
    "overview.md": "# Overview\n\n## System context\n\nThe shop service.\n\n## Goals\n\nG1, G2.\n\n"
                   "## Quality attributes\n\np95 < 300 ms.\n\n## Constraints\n\nPython.\n",
    "tech-stack.md": "# Tech stack\n\n## Languages\n\nPython 3.\n\n## Frameworks\n\npytest.\n\n"
                     "## Conventions\n\nsrc layout.\n",
    "cross-cutting.md": "# Cross-cutting conventions\n\n## API conventions\n\nJSON over HTTP; list "
                        "endpoints page with `offset` and `limit` (limit defaults to 20).\n\n"
                        "## Data conventions\n\nIn-memory data; no datastore yet.\n\n"
                        "## Security\n\nNo authentication yet; the payments gateway is planned.\n\n"
                        "## Observability\n\nGET /health for the load balancer.\n",
    "c4-context.md": "# C4 context\n\n```mermaid\nC4Context\n  System(shop, \"shop\")\n```\n",
    "c4-container.md": "# C4 container\n\n```mermaid\nC4Container\n  Container(api, \"shop\", \"Python\")\n```\n",
    "c4-component.md": "# C4 component\n\n```mermaid\nC4Component\n  Component(listing, \"list_customers\")\n```\n",
    "data-model.md": "# Data model\n\n```mermaid\nerDiagram\n  CUSTOMER {\n    string id\n  }\n```\n",
    "integration-map.md": "# Integration map\n\n```mermaid\nflowchart LR\n"
                          "  client[shopper client] -->|GET /customers sync| shop\n"
                          "  lb[load balancer] -->|GET /health sync| shop\n```\n",
    "deployment.md": "# Deployment\n\n```mermaid\nflowchart LR\n  lb[load balancer] --> shop\n```\n",
    "project-structure.md": "# Project structure\n\n## Directory layout\n\n```mermaid\nflowchart TD\n"
                            "  root --> src/shop\n  root --> tests\n```\n",
}
# What the skill no longer writes: low-level design, per ticket, by the Design skills.
LLD = {
    "contracts.md": "# Contracts\n\n## Contracts\n\n- `GET /health` returns `ok`.\n"
                    "- `GET /customers?offset=&limit=` returns `{items, offset, limit}`.\n",
    "flows/list-customers.md": "# list-customers\n\n```mermaid\nsequenceDiagram\n  participant Shopper\n"
                               "  participant shop\n  Shopper->>shop: GET /customers\n```\n",
}

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws):
    ws.skill("create-architecture")
    started = ws.acs("step", "start", "--step", "create-architecture", "--allocate", "--args", "")
    assert started.returncode == 0, started.stderr


def _write_docs(ws, hld=None, skip=(), lld=None):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for name, text in (hld or HLD).items():
        if name not in skip:
            ws.write("%s/hld/%s" % (ARCH, name), text)
    for name, text in (lld or {}).items():
        ws.write("%s/lld/%s" % (ARCH, name), text)
    ws.sh("git add %s && git commit -qm 'EVAL-1 Add product architecture doc set'" % ARCH)


def _finish(ws, findings=(GH_FINDING,), pr=None, hld=None):
    states = {"architecture": {"path": ARCH, "hld": list(hld or HLD)}}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "HLD reviewed; branch pushed; gh failed, no PR",
        "states": states, "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _push(ws):
    ws.sh("git push -q -u origin %s" % BRANCH)


def IDEAL(ws):
    _start(ws)
    _write_docs(ws)
    _push(ws)
    _finish(ws)
    ws.reply = ("EVAL-1: high-level design written under docs/architecture/hld/ on %s and "
                "pushed. gh pr create failed (no GitHub access), so no PR was opened; recorded "
                "as a finding." % BRANCH)


def _allocated_only(ws):
    _start(ws)


def _from_the_prd_only(ws):
    """An HLD that never looked at the code: a checkout API landscape, a
    generic cross-cutting file, and two HLD files missing."""
    _start(ws)
    hld = dict(HLD)
    hld["integration-map.md"] = ("# Integration map\n\n```mermaid\nflowchart LR\n"
                                 "  shop -->|POST /checkout| pay[payments gateway]\n```\n")
    hld["cross-cutting.md"] = ("# Cross-cutting conventions\n\n## API conventions\n\nREST.\n\n"
                               "## Data conventions\n\nUUID keys.\n\n## Security\n\nOAuth.\n\n"
                               "## Observability\n\nLogs.\n")
    _write_docs(ws, hld=hld, skip=("data-model.md", "project-structure.md"))
    _push(ws)
    _finish(ws)


def _wrote_the_lld_too(ws):
    """The pre-ADR-0118 doc set: the HLD plus contracts and a sequence flow."""
    _start(ws)
    _write_docs(ws, lld=LLD)
    _push(ws)
    _finish(ws)


def _no_cross_cutting(ws):
    _start(ws)
    _write_docs(ws, skip=("cross-cutting.md",))
    _push(ws)
    _finish(ws, hld=[n for n in HLD if n != "cross-cutting.md"])


def _no_integration_map(ws):
    _start(ws)
    _write_docs(ws, skip=("integration-map.md",))
    _push(ws)
    _finish(ws, hld=[n for n in HLD if n != "integration-map.md"])


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
    "wrote an incomplete HLD from the PRD alone": _from_the_prd_only,
    "wrote LLD contracts and flows beside the HLD": _wrote_the_lld_too,
    "left out hld/cross-cutting.md": _no_cross_cutting,
    "left out hld/integration-map.md": _no_integration_map,
    "committed but never pushed the delivery branch": _never_pushed,
    "recorded a PR that cannot exist": _invented_pr,
}
