"""Calibration plays for create-requirements-brownfield-draft (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--allocate` mints the delivery ticket, the authors write the confirmed DRAFT
area files with their evidence sidecars, the coordinator commits and pushes
the delivery branch, gh fails, and the result document goes through the real
post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-requirements.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-requirements"
BRANCH = "task/EVAL-1-product-requirements-doc-set"
REQ = "docs/requirements"

LISTING = """DRAFT — human-confirm-required

# Customer listing

## Behaviour

- `GET /customers` MUST return `{items, offset, limit}` {#listing-shape}
- The listing MUST default `limit` to 20 per page {#listing-page-size}
- The listing MUST start at `offset` 0 when none is given {#listing-offset}
- [OPEN] No maximum `limit` is enforced; none could be grounded in code.
"""
EVIDENCE = """# customer-listing evidence

- listing-shape: src/shop/__init__.py:9
- listing-page-size: src/shop/__init__.py:1
- listing-offset: src/shop/__init__.py:8
"""
HEALTH = "DRAFT — human-confirm-required\n\n# Health check\n\n- `GET /health` MUST return `ok` {#health-ok}\n"
HEALTH_EVIDENCE = "# health-check evidence\n\n- health-ok: src/shop/__init__.py:5\n"
PERF = "DRAFT — human-confirm-required\n\n# Performance\n\n- API p95 latency MUST stay under 300 ms {#p95}\n"

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws):
    ws.skill("create-requirements")
    started = ws.acs("step", "start", "--step", "create-requirements", "--allocate")
    assert started.returncode == 0, started.stderr


def _write(ws, listing=LISTING, evidence=EVIDENCE, perf=PERF):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    ws.write(REQ + "/functional/customer-listing.md", listing)
    if evidence is not None:
        ws.write(REQ + "/functional/customer-listing.evidence.md", evidence)
    ws.write(REQ + "/functional/health-check.md", HEALTH)
    ws.write(REQ + "/functional/health-check.evidence.md", HEALTH_EVIDENCE)
    ws.write(REQ + "/non-functional/performance.md", perf)
    ws.write(REQ + "/README.md", "# Requirements\n\n## Decision log\n\n| Date | Run |\n|---|---|\n"
                                 "| 2026-09-28 | EVAL-1 brownfield bootstrap |\n")
    ws.sh("git add %s && git commit -qm 'EVAL-1 Add product requirements doc set'" % REQ)


def _finish(ws, findings=(GH_FINDING,), pr=None):
    states = {"requirements": {"path": REQ, "files": [
        REQ + "/functional/customer-listing.md", REQ + "/functional/health-check.md",
        REQ + "/non-functional/performance.md"]}}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "requirements written; branch pushed; gh failed, no PR",
        "states": states, "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _push(ws):
    ws.sh("git push -q -u origin %s" % BRANCH)


def IDEAL(ws):
    _start(ws)
    _write(ws)
    _push(ws)
    _finish(ws)
    ws.reply = ("EVAL-1: DRAFT requirements written on %s and pushed. gh pr create failed "
                "(no GitHub access), so no PR was opened; recorded as a finding." % BRANCH)


def _allocated_only(ws):
    _start(ws)


def _uncited_prose(ws):
    """Plausible requirements written without the DRAFT marker, without
    reading the code, and with no evidence sidecar."""
    _start(ws)
    _write(ws, listing="# Customer listing\n\nCustomers should be listable.\n", evidence=None,
           perf="# Performance\n\nThe API should be fast.\n")
    _push(ws)
    _finish(ws)


def _never_pushed(ws):
    _start(ws)
    _write(ws)
    _finish(ws)


def _hid_the_failure(ws):
    _start(ws)
    _write(ws)
    _push(ws)
    _finish(ws, findings=())


BAD = {
    "allocated the ticket and wrote nothing": _allocated_only,
    "wrote unmarked, uncited prose": _uncited_prose,
    "committed but never pushed the delivery branch": _never_pushed,
    "finished with the gh failure unrecorded": _hid_the_failure,
}
