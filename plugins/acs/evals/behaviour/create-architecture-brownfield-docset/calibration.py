"""Calibration plays for create-architecture-brownfield-docset (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
resumes the ticketless run the scaffold opened, the architect writes the
high-level design (hld/ only, nothing under lld/) and leaves it uncommitted,
and the result document, listing every written path in `states.files`, goes
through the real post-hook. Nothing is branched, committed or pushed
(ADR-0127). Every hld/ file gets its version front matter through `acs design
init --status implemented` -- the set documents the code as built (ADR-0122)."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-architecture.py")
STEP = ".acs/state-machine/example-shop/runs/document-the-current-architecture-9451/steps/create-architecture"
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



def _start(ws):
    ws.skill("create-architecture")
    started = ws.acs("step", "start", "--step", "create-architecture", "--args", "")
    assert started.returncode == 0, started.stderr


def _write_docs(ws, hld=None, skip=(), lld=None, versioned=True):
    written = []
    for name, text in (hld or HLD).items():
        if name not in skip:
            written.append("%s/hld/%s" % (ARCH, name))
            ws.write(written[-1], text)
    for name, text in (lld or {}).items():
        ws.write("%s/lld/%s" % (ARCH, name), text)
    if versioned:
        # A new file documenting the code as built: `design init --status
        # implemented`; the run is ticketless, so no `--ticket` (ADR-0122, 0127).
        done = ws.acs("design", "init", "--status", "implemented", *written)
        assert done.returncode == 0, done.stderr


def _finish(ws, pr=None, hld=None, files=None):
    hld = list(hld or HLD)
    states = {"architecture": {"path": ARCH, "hld": hld},
              "files": ["%s/hld/%s" % (ARCH, n) for n in hld] if files is None else files}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "HLD reviewed; left as local changes",
        "states": states, "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _push(ws):
    """The pre-ADR-0127 delivery: a delivery branch, a commit and a push."""
    ws.sh("git checkout -q -b %s main" % BRANCH)
    ws.sh("git add %s && git commit -qm 'EVAL-1 Add product architecture doc set'" % ARCH)
    ws.sh("git push -q -u origin %s" % BRANCH)


def IDEAL(ws):
    _start(ws)
    _write_docs(ws)
    _finish(ws)
    ws.reply = ("High-level design written under docs/architecture/hld/ and left uncommitted "
                "(10 files, listed in states.files). Review them, then run /acs:create-pr to "
                "commit them and open the PR.")


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
    _finish(ws)


def _wrote_the_lld_too(ws):
    """The pre-ADR-0118 doc set: the HLD plus contracts and a sequence flow."""
    _start(ws)
    _write_docs(ws, lld=LLD)
    _finish(ws)


def _no_cross_cutting(ws):
    _start(ws)
    _write_docs(ws, skip=("cross-cutting.md",))
    _finish(ws, hld=[n for n in HLD if n != "cross-cutting.md"])


def _no_integration_map(ws):
    _start(ws)
    _write_docs(ws, skip=("integration-map.md",))
    _finish(ws, hld=[n for n in HLD if n != "integration-map.md"])


def _unversioned(ws):
    """Wrote the HLD with no version front matter on any file."""
    _start(ws)
    _write_docs(ws, versioned=False)
    _finish(ws)


def _delivered_it_itself(ws):
    _start(ws)
    _write_docs(ws)
    _push(ws)
    _finish(ws)


def _invented_pr(ws):
    _start(ws)
    _write_docs(ws)
    _finish(ws, pr={"number": 7, "url": "https://github.com/example/shop/pull/7"})


def _recorded_no_files(ws):
    _start(ws)
    _write_docs(ws)
    _finish(ws, files=[])


BAD = {
    "started the run and wrote nothing": _allocated_only,
    "wrote an incomplete HLD from the PRD alone": _from_the_prd_only,
    "wrote LLD contracts and flows beside the HLD": _wrote_the_lld_too,
    "left out hld/cross-cutting.md": _no_cross_cutting,
    "left out hld/integration-map.md": _no_integration_map,
    "wrote the HLD without version front matter": _unversioned,
    "committed and pushed a delivery branch": _delivered_it_itself,
    "recorded a PR that cannot exist": _invented_pr,
    "recorded no files in states.files": _recorded_no_files,
}
