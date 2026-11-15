"""Calibration plays for create-architecture-regenerate-after-shift (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
resumes the ticketless run the scaffold opened, the architect regenerates the
existing HLD in place against the new code (stale worker and Redis out; the
orders API in; the two HLD files the old set lacked created), every file under
lld/ is left exactly as it was, the changes stay uncommitted, and the result
document, listing every written path in `states.files`, goes through the real
post-hook. Nothing is branched, committed or pushed (ADR-0127).
Beside the survey, one gap analyst compares the existing HLD with the code and
its notes are joined into iter-1/gaps.md (ADR-0122); the old set predates
version front matter, so every hld/ file the run writes gets its first block
through `acs design init --status implemented`."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-architecture.py")
STEP = ".acs/state-machine/example-shop/runs/regenerate-the-architecture-after-the-shift-1304/steps/create-architecture"
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

GAPS = ("## Unimplemented\n\n- **export-worker container** and its **Redis `exports` queue** "
        "-- hld/c4-container.md, hld/deployment.md; code: absent (src/export_worker deleted by "
        "the latest commit).\n\n## Undocumented\n\n- **orders API** -- `GET "
        "/orders?customer_id=`, src/shop/orders.py:4; HLD: absent.\n\n## Drifted\n\n_None._\n\n"
        "## Unverified\n\n_None._\n")



def _start(ws):
    ws.skill("create-architecture")
    started = ws.acs("step", "start", "--step", "create-architecture", "--args", "")
    assert started.returncode == 0, started.stderr


def _gap_analysis(ws):
    """The gap analyst (slice `repo`) beside the survey, joined by `acs notes
    merge`: the HLD's export-worker and Redis are designed but no longer
    built, and the orders API is built but not designed."""
    ws.write(STEP + "/iter-1/gaps-repo.md", GAPS)
    merged = ws.acs("notes", "merge", "--out", STEP + "/iter-1/gaps.md",
                    STEP + "/iter-1/gaps-repo.md")
    assert merged.returncode == 0, merged.stderr


def _deliver(ws, docs=None, drop=(), gaps=True, versioned=True, commit=False):
    if gaps:
        _gap_analysis(ws)
    written = []
    for rel, text in (REGENERATED if docs is None else docs).items():
        ws.write("%s/%s" % (A, rel), text)
        if rel.startswith("hld/"):
            written.append("%s/%s" % (A, rel))
    if versioned:
        # The old files carry no block yet, so each gets its first one; the
        # set documents the code as built after the shift.
        # The run is ticketless, so no `--ticket` (ADR-0127).
        done = ws.acs("design", "init", "--status", "implemented", *written)
        assert done.returncode == 0, done.stderr
    for rel in drop:
        ws.sh("git rm -q %s/%s" % (A, rel))
    if commit:
        # The pre-ADR-0127 delivery: a delivery branch, a commit and a push.
        ws.sh("git checkout -q -b %s main" % BRANCH)
        ws.sh("git add %s && git commit -qm 'EVAL-1 Regenerate product architecture doc set'" % A)
        ws.sh("git push -q -u origin %s" % BRANCH)


def _finish(ws, docs=None, files=None):
    hld = [rel.split("/", 1)[1] for rel in (REGENERATED if docs is None else docs)
           if rel.startswith("hld/")]
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "HLD regenerated after the shift; left as local changes",
        "states": {"architecture": {"path": A, "hld": hld},
                   "files": ["%s/hld/%s" % (A, n) for n in hld] if files is None else files},
        "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws)
    ws.reply = ("Re-run: HLD regenerated in place -- export-worker and Redis removed, the orders "
                "API added, cross-cutting.md and integration-map.md written; lld/ left as it was. "
                "The changes are uncommitted; review them, then /acs:create-pr.")


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


def _unversioned(ws):
    """Regenerated the HLD but gave no file its version front matter."""
    _start(ws)
    _deliver(ws, versioned=False)
    _finish(ws)


def _no_gap_analysis(ws):
    """Rewrote the HLD blind: no gap analyst compared it with the code first."""
    _start(ws)
    _deliver(ws, gaps=False)
    _finish(ws)


def _delivered_it_itself(ws):
    _start(ws)
    _deliver(ws, commit=True)
    _finish(ws)


def _recorded_no_files(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws, files=[])


BAD = {
    "added the orders API but kept the stale worker": _added_only,
    "rewrote the LLD contracts and flows": _rewrote_the_lld,
    "deleted the stale nightly-export LLD flow": _deleted_the_stale_flow,
    "left out hld/cross-cutting.md": _no_cross_cutting,
    "left out hld/integration-map.md": _no_integration_map,
    "committed and pushed a delivery branch": _delivered_it_itself,
    "recorded no files in states.files": _recorded_no_files,
    "regenerated without version front matter": _unversioned,
    "regenerated with no gap analysis": _no_gap_analysis,
    "started the run and changed nothing": _start,
}
