"""Calibration plays for create-requirements-amend-absent-area (see
tests/evals/check_grader_calibration.py). The ideal run: Start finds the
populated set (amend mode) and allocates with `--title "Amend requirements:
..."`, one author writes the absent order-listing area with its evidence
sidecar, the coordinator commits and pushes the delivery branch, gh fails,
and the result document goes through the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-requirements.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-requirements"
BRANCH = "task/EVAL-1-amend-requirements-add-the-missing-order-listing-area"
REQ = "docs/requirements"
TITLE = "Amend requirements: add the missing order-listing area"

ORDERS = """DRAFT — human-confirm-required

# Order listing

## Behaviour

- `GET /orders` MUST require `customer_id` {#orders-customer}
- `GET /orders` MUST return `{customer_id, items, offset, limit}` {#orders-shape}
- The listing MUST default `limit` to 20 per page {#orders-page-size}
- [OPEN] No maximum `limit` is enforced; none could be grounded in code.
"""
EVIDENCE = """# order-listing evidence

- orders-customer: src/shop/orders.py:6
- orders-shape: src/shop/orders.py:8
- orders-page-size: src/shop/orders.py:4
"""

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws, title=TITLE):
    ws.skill("create-requirements")
    args = ["step", "start", "--step", "create-requirements", "--allocate"]
    if title:
        args += ["--title", title]
    started = ws.acs(*args)
    assert started.returncode == 0, started.stderr


def _deliver(ws, branch=BRANCH, extra=(), evidence=EVIDENCE):
    ws.sh("git checkout -q -b %s main" % branch)
    ws.write(REQ + "/functional/order-listing.md", ORDERS)
    if evidence:
        ws.write(REQ + "/functional/order-listing.evidence.md", evidence)
    ws.write(REQ + "/README.md", "| 2026-09-28 | EVAL-1 amend: order-listing added |\n",
             append=True)
    for rel, text, append in extra:
        ws.write(rel, text, append=append)
    ws.sh("git add %s && git commit -qm 'EVAL-1 Amend requirements: add order listing'" % REQ)
    ws.sh("git push -q -u origin %s" % branch)


def _finish(ws, findings=(GH_FINDING,)):
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "order-listing area added; gh failed, no PR",
        "states": {"requirements": {"path": REQ,
                                    "files": [REQ + "/functional/order-listing.md"]}},
        "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws)
    ws.reply = ("EVAL-1 (amend): added functional/order-listing.md (DRAFT, code-cited); existing "
                "area files untouched. Pushed %s; gh pr create failed, so no PR was opened." % BRANCH)


def _remarked_existing(ws):
    """Re-ran the whole set as a bootstrap: every file re-marked DRAFT."""
    _start(ws)
    path = os.path.join(ws.path, REQ, "functional", "customer-listing.md")
    with open(path, encoding="utf-8") as fh:
        listing = fh.read()
    _deliver(ws, extra=[(REQ + "/functional/customer-listing.md",
                         "DRAFT — human-confirm-required\n\n" + listing, False)])
    _finish(ws)


def _tweaked_the_nfr(ws):
    _start(ws)
    _deliver(ws, extra=[(REQ + "/non-functional/performance.md",
                         "- `GET /orders` p95 MUST stay under 300 ms {#orders-p95}\n", True)])
    _finish(ws)


def _extra_area(ws):
    _start(ws)
    _deliver(ws, extra=[(REQ + "/non-functional/pagination.md",
                         "DRAFT — human-confirm-required\n\n# Pagination\n", False)])
    _finish(ws)


def _uncited(ws):
    _start(ws)
    _deliver(ws, evidence=None)
    _finish(ws)


def _default_title(ws):
    _start(ws, title=None)
    _deliver(ws, branch="task/EVAL-1-product-requirements-doc-set")
    _finish(ws)


BAD = {
    "re-marked an existing area file DRAFT": _remarked_existing,
    "appended to the existing performance file": _tweaked_the_nfr,
    "added an area nobody confirmed": _extra_area,
    "wrote the new area with no evidence sidecar": _uncited,
    "allocated without the Amend requirements title": _default_title,
}
