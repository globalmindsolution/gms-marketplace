"""Calibration plays for create-prd-amend-scope-cut (see
tests/evals/check_grader_calibration.py). The ideal run: Start finds the PRD
(amend mode) and allocates with `--title "Amend PRD: ..."`, the author edits
the two documents in place -- only the confirmed sections -- the coordinator
commits and pushes the delivery branch, gh fails, and the result document
goes through the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-prd.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-prd"
BRANCH = "task/EVAL-1-amend-prd-cut-order-tracking-from-scope"
PRD = "docs/product/prd.md"
ROADMAP = "docs/product/roadmap.md"

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _read(ws, rel):
    with open(os.path.join(ws.path, rel), encoding="utf-8") as fh:
        return fh.read()


def _start(ws, title="Amend PRD: cut order tracking from scope"):
    ws.skill("create-prd")
    args = ["step", "start", "--step", "create-prd", "--allocate"]
    if title:
        args += ["--title", title]
    started = ws.acs(*args)
    assert started.returncode == 0, started.stderr


def _amend(ws, prd_edit=None, roadmap_edit=None, branch=BRANCH):
    ws.sh("git checkout -q -b %s main" % branch)
    prd = _read(ws, PRD)
    prd = prd.replace("- **Should**: order tracking (G1)\n", "- **Should**: none\n")
    prd = prd.replace("- **Won't**: a marketplace for third-party sellers\n",
                      "- **Won't**: a marketplace for third-party sellers; order tracking "
                      "(cut by leadership, 2026-09)\n")
    prd = prd.replace("- Third-party sellers.\n", "- Third-party sellers.\n- Order tracking.\n")
    if prd_edit:
        prd = prd_edit(prd)
    roadmap = _read(ws, ROADMAP)
    roadmap = roadmap.replace("### Order tracking — v2.6.0\n\nDelivers order tracking (Should) "
                              "and serves G1.\n\n", "")
    roadmap = roadmap.replace("| v2.6.0 | Order tracking | Order tracking |\n", "")
    if roadmap_edit:
        roadmap = roadmap_edit(roadmap)
    ws.write(PRD, prd)
    ws.write(ROADMAP, roadmap)
    ws.sh("git add docs/product && git commit -qm 'EVAL-1 Amend PRD: cut order tracking'")
    ws.sh("git push -q -u origin %s" % branch)


def _finish(ws, findings=(GH_FINDING,)):
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "PRD amended and branch pushed; gh failed, no PR",
        "states": {"prd": {"path": "docs/product", "files": [PRD, ROADMAP]}},
        "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _amend(ws)
    _finish(ws)
    ws.reply = ("EVAL-1 (amend): order tracking moved to Won't and Out of scope; its v2.6.0 "
                "milestone removed. Pushed %s; gh pr create failed, so no PR was opened." % BRANCH)


def _regenerated(ws):
    """A fresh PRD written over the old one: the facts survive, the words do not."""
    _start(ws)
    _amend(ws, prd_edit=lambda t: t.replace(
        "Let small merchants sell online without running any infrastructure.",
        "Small merchants can sell online with no infrastructure to run.").replace(
        "- p95 API latency under 300 ms.", "- The API answers in under 300 ms at p95."))
    _finish(ws)


def _only_deprioritised(ws):
    """Moved it to Could and kept the milestone: not the confirmed cut."""
    _start(ws)
    ws.sh("git checkout -q -b %s main" % BRANCH)
    prd = _read(ws, PRD).replace("- **Should**: order tracking (G1)\n", "- **Should**: none\n"
                                 ).replace("- **Could**: saved carts (G1)\n",
                                           "- **Could**: saved carts (G1), order tracking (G1)\n")
    ws.write(PRD, prd)
    ws.sh("git add docs/product && git commit -qm 'EVAL-1 Amend PRD'")
    ws.sh("git push -q -u origin %s" % BRANCH)
    _finish(ws)


def _dropped_the_release_table(ws):
    _start(ws)
    _amend(ws, roadmap_edit=lambda t: t.split("## Release versions")[0])
    _finish(ws)


def _default_title(ws):
    _start(ws, title=None)
    _amend(ws, branch="task/EVAL-1-product-definition-prd")
    _finish(ws)


BAD = {
    "regenerated the PRD instead of amending it": _regenerated,
    "deprioritised order tracking instead of cutting it": _only_deprioritised,
    "dropped the Release versions table": _dropped_the_release_table,
    "allocated without the Amend PRD title": _default_title,
}
