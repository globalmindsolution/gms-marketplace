"""Calibration plays for create-prd-brownfield-baseline (see
tests/evals/check_grader_calibration.py). The ideal run does what the skill
does, through its own writers: `acs step start` resumes the ticketless run the
scaffold opened, the author writes the two documents and leaves them
uncommitted, the coordinator gives both their first version front matter
(`acs.py design init --status proposed`), and the result document, listing both in `states.files`, goes
through the real post-hook. Nothing is branched, committed or pushed
(ADR-0127)."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-prd.py")
STEP = ".git/acs/state-machine/example-shop/runs/write-the-first-prd-96bb/steps/create-prd"
BRANCH = "task/EVAL-1-product-definition-prd"
FILES = ("docs/product/prd.md", "docs/product/roadmap.md")

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



def _start(ws):
    ws.skill("create-prd")
    started = ws.acs("step", "start", "--step", "create-prd", "--args", '')
    assert started.returncode == 0, started.stderr


def _write_docs(ws, prd=PRD, roadmap=ROADMAP):
    ws.write("docs/product/prd.md", prd)
    ws.write("docs/product/roadmap.md", roadmap)


def _commit(ws):
    """The pre-ADR-0127 delivery: a delivery branch and a commit."""
    ws.sh("git checkout -q -b %s" % BRANCH)
    ws.sh("git add docs/product && git commit -qm 'EVAL-1 Add product requirements document and roadmap'")


def _finish(ws, files=FILES, pr=None, status="completed"):
    states = {"prd": {"path": "docs/product"}, "files": list(files)}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": status, "summary": "PRD written and reviewed; left as local changes",
        "states": states, "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _version(ws):
    """The coordinator's Versions step: a new document gets `design init`."""
    done = ws.acs("design", "init", "--status", "proposed", *FILES)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    _write_docs(ws)
    _version(ws)
    _finish(ws)
    ws.reply = ("PRD and roadmap written. Uncommitted: docs/product/prd.md, "
                "docs/product/roadmap.md. Review them, then run /acs:create-pr to commit them "
                "and open the PR.")


def _allocated_only(ws):
    _start(ws)


def _unversioned(ws):
    _start(ws)
    _write_docs(ws)
    _finish(ws)


def _template_prd(ws):
    _start(ws)
    generic = PRD.replace("3.5%", "a higher rate").replace("300 ms", "fast").replace(
        "**Won't**", "**Later**")
    _write_docs(ws, prd=generic, roadmap="# Roadmap\n\n- Checkout\n- Order tracking\n")
    _finish(ws)


def _committed(ws):
    _start(ws)
    _write_docs(ws)
    _commit(ws)
    _finish(ws)


def _pushed(ws):
    _start(ws)
    _write_docs(ws)
    _commit(ws)
    ws.sh("git push -q -u origin %s" % BRANCH)
    _finish(ws)


def _invented_pr(ws):
    _start(ws)
    _write_docs(ws)
    _finish(ws, pr={"number": 1, "url": "https://github.com/example/shop/pull/1"})


def _recorded_no_files(ws):
    _start(ws)
    _write_docs(ws)
    _finish(ws, files=())


BAD = {
    "left the new documents without version front matter": _unversioned,
    "started the run and wrote nothing": _allocated_only,
    "wrote a generic PRD without the stated facts or versions": _template_prd,
    "committed the documents on a delivery branch": _committed,
    "pushed a delivery branch": _pushed,
    "recorded a PR that cannot exist": _invented_pr,
    "recorded no files in states.files": _recorded_no_files,
}
