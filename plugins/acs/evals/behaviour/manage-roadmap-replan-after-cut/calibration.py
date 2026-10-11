"""Calibration plays for manage-roadmap-replan-after-cut (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
resumes the ticketless run the scaffold opened, the author removes the cut
feature's milestone and its row in place, leaving Storefront and Checkout
byte-for-byte, the coordinator derives the statuses and bumps the changed
roadmap (`acs.py design bump`: approved v1 -> proposed v2), and the result
document, listing it in `states.files`, goes through the real post-hook.
Nothing is branched, committed or pushed (ADR-0127, ADR-0145)."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-manage-roadmap.py")
STEP = ".acs/state-machine/example-shop/runs/re-plan-the-roadmap-after-the-1981/steps/manage-roadmap"
ROADMAP = "docs/product/roadmap.md"
PRD = "docs/product/prd.md"
MILESTONE = ("### Order tracking — v2.6.0\n\n- Status: planned\n"
             "- Features: [Order tracking](features/order-tracking/prd.md)\n- Epics: none yet\n\n"
             "Shoppers follow an order from payment to delivery.\n\n")
ROW = "| v2.6.0 | Order tracking | — | planned |\n"


def _read(ws, rel):
    with open(os.path.join(ws.path, rel), encoding="utf-8") as fh:
        return fh.read()


def _start(ws):
    ws.skill("manage-roadmap")
    started = ws.acs("step", "start", "--step", "manage-roadmap", "--args", "")
    assert started.returncode == 0, started.stderr


def _replan(ws, edit=None, row=True, milestone=True):
    text = _read(ws, ROADMAP)
    if milestone:
        text = text.replace(MILESTONE, "")
    if row:
        text = text.replace(ROW, "")
    if edit:
        text = edit(text)
    ws.write(ROADMAP, text)
    status = ws.acs("roadmap", "status", "--write")
    assert status.returncode == 0, status.stderr


def _bump(ws):
    done = ws.acs("design", "bump", ROADMAP)
    assert done.returncode == 0, done.stderr


def _finish(ws, files=(ROADMAP,), pr=None):
    states = {"roadmap": {"path": ROADMAP, "mode": "replan"}, "files": list(files)}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "Roadmap re-planned and reviewed; left as a local change",
        "states": states, "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _replan(ws)
    _bump(ws)
    _finish(ws)
    ws.reply = ("Replan: the Order tracking milestone and its v2.6.0 row are removed; "
                "Storefront and Checkout unchanged; the roadmap is proposed v2. Uncommitted: "
                "docs/product/roadmap.md -- review it, then run /acs:create-pr to commit it.")


def _kept_the_row(ws):
    _start(ws)
    _replan(ws, row=False)
    _bump(ws)
    _finish(ws)


def _kept_the_milestone(ws):
    _start(ws)
    _replan(ws, milestone=False)
    _bump(ws)
    _finish(ws)


def _regenerated(ws):
    """A fresh roadmap over the old one: the plan survives, the words do not."""
    _start(ws)
    _replan(ws, edit=lambda t: t.replace("The product listing every merchant starts from.",
                                         "Merchants list their products."))
    _bump(ws)
    _finish(ws)


def _not_bumped(ws):
    _start(ws)
    _replan(ws)
    _finish(ws)


def _edited_the_prd(ws):
    _start(ws)
    _replan(ws)
    _bump(ws)
    ws.acs("design", "bump", PRD)
    _finish(ws)


def _committed(ws):
    _start(ws)
    _replan(ws)
    _bump(ws)
    ws.sh("git commit -qam 'Roadmap: cut order tracking'")
    _finish(ws)


def _pushed(ws):
    _start(ws)
    _replan(ws)
    _bump(ws)
    ws.sh("git checkout -q -b docs/roadmap && git commit -qam 'Roadmap: cut order tracking'")
    ws.sh("git push -q -u origin docs/roadmap")
    _finish(ws)


def _recorded_no_files(ws):
    _start(ws)
    _replan(ws)
    _bump(ws)
    _finish(ws, files=())


def _invented_pr(ws):
    _start(ws)
    _replan(ws)
    _bump(ws)
    _finish(ws, pr={"number": 1, "url": "https://github.com/example/shop/pull/1"})


BAD = {
    "removed the milestone but kept its v2.6.0 row": _kept_the_row,
    "removed the row but kept the milestone": _kept_the_milestone,
    "reworded a milestone the change does not touch": _regenerated,
    "re-planned without bumping the version": _not_bumped,
    "bumped the PRD it never edits": _edited_the_prd,
    "committed the roadmap": _committed,
    "pushed a branch": _pushed,
    "recorded no files in states.files": _recorded_no_files,
    "recorded a PR that cannot exist": _invented_pr,
    "started the run and wrote nothing": _start,
}
