"""Calibration plays for create-prd-amend-scope-cut (see
tests/evals/check_grader_calibration.py). The ideal run: Start finds the PRD
(amend mode) and `acs step start` resumes the ticketless run the scaffold
opened, the author edits the two documents in place -- only the confirmed
sections -- and leaves them uncommitted, the coordinator bumps both changed
documents with `acs.py design bump` (approved v1 -> proposed v2), and the result document, listing both
files in `states.files`, goes through the real post-hook. Nothing is
branched, committed or pushed (ADR-0127)."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-prd.py")
STEP = ".git/acs/state-machine/example-shop/runs/amend-the-prd-after-the-scope-0d30/steps/create-prd"
BRANCH = "task/EVAL-1-amend-prd-cut-order-tracking-from-scope"
PRD = "docs/product/prd.md"
ROADMAP = "docs/product/roadmap.md"


def _read(ws, rel):
    with open(os.path.join(ws.path, rel), encoding="utf-8") as fh:
        return fh.read()


def _start(ws):
    ws.skill("create-prd")
    started = ws.acs("step", "start", "--step", "create-prd", "--args", "cut order tracking from scope")
    assert started.returncode == 0, started.stderr


def _amend(ws, prd_edit=None, roadmap_edit=None):
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


def _bump(ws):
    """The coordinator's Versions step: a changed document gets `design bump`."""
    done = ws.acs("design", "bump", PRD, ROADMAP)
    assert done.returncode == 0, done.stderr


def _finish(ws, files=(PRD, ROADMAP), pr=None):
    states = {"prd": {"path": "docs/product"}, "files": list(files)}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "PRD amended and reviewed; left as local changes",
        "states": states, "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _amend(ws)
    _bump(ws)
    _finish(ws)
    ws.reply = ("Amend mode: order tracking moved to Won't and Out of scope; its v2.6.0 "
                "milestone removed. Uncommitted: docs/product/prd.md, docs/product/roadmap.md. "
                "Review them, then run /acs:create-pr to commit them and open the PR.")


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
    prd = _read(ws, PRD).replace("- **Should**: order tracking (G1)\n", "- **Should**: none\n"
                                 ).replace("- **Could**: saved carts (G1)\n",
                                           "- **Could**: saved carts (G1), order tracking (G1)\n")
    ws.write(PRD, prd)
    _finish(ws)


def _dropped_the_release_table(ws):
    _start(ws)
    _amend(ws, roadmap_edit=lambda t: t.split("## Release versions")[0])
    _finish(ws)


def _committed_on_a_branch(ws):
    """The pre-ADR-0127 delivery: a delivery branch and a commit."""
    _start(ws)
    ws.sh("git checkout -q -b %s main" % BRANCH)
    _amend(ws)
    ws.sh("git add docs/product && git commit -qm 'EVAL-1 Amend PRD: cut order tracking'")
    _finish(ws)


def _committed_on_main(ws):
    _start(ws)
    _amend(ws)
    ws.sh("git commit -qam 'Amend PRD: cut order tracking'")
    _finish(ws)


def _pushed(ws):
    _start(ws)
    ws.sh("git checkout -q -b %s main" % BRANCH)
    _amend(ws)
    ws.sh("git add docs/product && git commit -qm 'EVAL-1 Amend PRD: cut order tracking'")
    ws.sh("git push -q -u origin %s" % BRANCH)
    _finish(ws)


def _not_bumped(ws):
    """Amended the content and left the version at 1, still `approved`."""
    _start(ws)
    _amend(ws)
    _finish(ws)


def _recorded_no_files(ws):
    _start(ws)
    _amend(ws)
    _finish(ws, files=())


def _invented_pr(ws):
    _start(ws)
    _amend(ws)
    _finish(ws, pr={"number": 1, "url": "https://github.com/example/shop/pull/1"})


BAD = {
    "regenerated the PRD instead of amending it": _regenerated,
    "deprioritised order tracking instead of cutting it": _only_deprioritised,
    "dropped the Release versions table": _dropped_the_release_table,
    "committed the amendment on a delivery branch": _committed_on_a_branch,
    "committed the amendment on main": _committed_on_main,
    "pushed a delivery branch": _pushed,
    "recorded no files in states.files": _recorded_no_files,
    "recorded a PR that cannot exist": _invented_pr,
    "started the run and wrote nothing": _start,
    "amended the documents without bumping their version": _not_bumped,
}
