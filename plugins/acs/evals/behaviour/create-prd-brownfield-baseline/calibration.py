"""Calibration plays for create-prd-brownfield-baseline (see
tests/evals/check_grader_calibration.py). The ideal run does what the skill
does, through its own writers: `acs step start --allocate` mints the delivery
ticket, the author writes the two documents, the coordinator commits and
pushes the delivery branch, gh fails, and the result document goes through
the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-prd.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-prd"
BRANCH = "task/EVAL-1-product-definition-prd"

PRD = """# PRD — shop

## Vision

Let small merchants sell online without running any infrastructure.

## Problem statement

Setting up a storefront with payments takes merchants weeks of engineering.

## Target users & personas

- **Merchant** — lists products, fulfils orders.
- **Shopper** — browses, pays, tracks orders.

## Goals & success metrics

| Goal | Metric |
|---|---|
| G1 Checkout that converts | checkout conversion >= 3.5% of shopper sessions by 2027-06-30 |
| G2 Reliable service | 99.9% monthly availability, every calendar month from 2027-01 |

## Features (prioritized)

- **Must**: customer listing (shipped; G2), card checkout (G1)
- **Should**: order tracking (G1)
- **Could**: saved carts (G1)
- **Won't**: a marketplace for third-party sellers

## Non-functional requirements

- p95 API latency under 300 ms.
- Unit test coverage at least 90%.

## Constraints & assumptions

- One Python 3.12 service; card payments only through an external gateway.

## Out of scope

- Native mobile apps; third-party sellers.
"""

ROADMAP = """# Roadmap

### Checkout — v2.5.0

Delivers card checkout.

### Order tracking — v2.6.0

Delivers order tracking.

## Release versions

| Version | Milestone | Epic |
|---|---|---|
| v2.5.0 | Checkout | Card checkout |
| v2.6.0 | Order tracking | Order tracking |
"""

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "command": "gh pr create --base main --head %s --label ACS" % BRANCH,
              "error": "gh: command not found",
              "hint": "check `gh auth status` and repo access"}


def _start(ws):
    ws.skill("create-prd")
    started = ws.acs("step", "start", "--step", "create-prd", "--allocate")
    assert started.returncode == 0, started.stderr


def _write_docs(ws, prd=PRD, roadmap=ROADMAP):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    ws.write("docs/product/prd.md", prd)
    ws.write("docs/product/roadmap.md", roadmap)
    ws.sh("git add docs/product && git commit -qm 'EVAL-1 Add product requirements document and roadmap'")


def _finish(ws, findings=(GH_FINDING,), pr=None, status="completed"):
    states = {"prd": {"path": "docs/product",
                      "files": ["docs/product/prd.md", "docs/product/roadmap.md"]}}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": status, "summary": "PRD written and branch pushed; gh failed, no PR opened",
        "states": states, "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _write_docs(ws)
    ws.sh("git push -q -u origin %s" % BRANCH)
    _finish(ws)
    ws.reply = ("EVAL-1: PRD and roadmap written on %s and pushed. The PR could not be "
                "opened: gh pr create failed (gh unavailable), recorded as a finding." % BRANCH)


def _allocated_only(ws):
    _start(ws)


def _template_prd(ws):
    _start(ws)
    generic = PRD.replace("3.5%", "a higher rate").replace("300 ms", "fast").replace(
        "**Won't**", "**Later**")
    _write_docs(ws, prd=generic, roadmap="# Roadmap\n\n- Checkout\n- Order tracking\n")
    ws.sh("git push -q -u origin %s" % BRANCH)
    _finish(ws)


def _never_pushed(ws):
    _start(ws)
    _write_docs(ws)
    _finish(ws)


def _invented_pr(ws):
    _start(ws)
    _write_docs(ws)
    ws.sh("git push -q -u origin %s" % BRANCH)
    _finish(ws, findings=(), pr={"number": 1, "branch": BRANCH,
                                 "url": "https://github.com/example/shop/pull/1"})


def _hid_the_failure(ws):
    _start(ws)
    _write_docs(ws)
    ws.sh("git push -q -u origin %s" % BRANCH)
    _finish(ws, findings=())


BAD = {
    "allocated the ticket and wrote nothing": _allocated_only,
    "wrote a generic PRD without the stated facts or versions": _template_prd,
    "committed but never pushed the delivery branch": _never_pushed,
    "recorded a PR that cannot exist": _invented_pr,
    "finished with the gh failure unrecorded": _hid_the_failure,
}
