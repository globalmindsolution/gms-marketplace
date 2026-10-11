"""Calibration plays for manage-roadmap-create-from-prd (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
resumes the ticketless run the scaffold opened, the author writes roadmap.md in
the skill's shape from the confirmed plan, the coordinator derives every status
(`acs.py roadmap status --write`) and gives the new document its first version
front matter (`acs.py design init --status proposed`), and the result document,
listing it in `states.files`, goes through the real post-hook. Nothing is
branched, committed or pushed (ADR-0127, ADR-0145)."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-manage-roadmap.py")
STEP = ".acs/state-machine/example-shop/runs/plan-the-roadmap-from-the-prd-dc0b/steps/manage-roadmap"
ROADMAP = "docs/product/roadmap.md"
PRD = "docs/product/prd.md"


def milestone(name, version, slug, title, why, status="planned"):
    return ("### {} — v{}\n\n- Status: {}\n- Features: [{}](features/{}/prd.md)\n"
            "- Epics: none yet\n\n{}\n\n").format(name, version, status, title, slug, why)


def roadmap(storefront="planned", rows=True, saved_carts=False):
    text = "# Roadmap — shop\n\n## Milestones\n\n"
    text += milestone("Storefront", "2.4.0", "customer-listing", "Customer listing",
                      "The product listing every merchant starts from.", storefront)
    text += milestone("Checkout", "2.5.0", "card-checkout", "Card checkout",
                      "Shoppers pay by card through the external gateway.")
    text += milestone("Order tracking", "2.6.0", "order-tracking", "Order tracking",
                      "Shoppers follow an order from payment to delivery.")
    if saved_carts:
        text += milestone("Saved carts", "2.7.0", "saved-carts", "Saved carts", "Keep a cart.")
    text += "## Release versions\n\n| Version | Milestone | Epics | Status |\n|---|---|---|---|\n"
    if rows:
        text += ("| v2.4.0 | Storefront | — | {} |\n| v2.5.0 | Checkout | — | planned |\n"
                 "| v2.6.0 | Order tracking | — | planned |\n").format(storefront)
        if saved_carts:
            text += "| v2.7.0 | Saved carts | — | planned |\n"
    return text


def _start(ws):
    ws.skill("manage-roadmap")
    started = ws.acs("step", "start", "--step", "manage-roadmap", "--args", "")
    assert started.returncode == 0, started.stderr


def _finish(ws, files=(ROADMAP,), pr=None):
    states = {"roadmap": {"path": ROADMAP, "mode": "create"}, "files": list(files)}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "Roadmap planned and reviewed; left as a local change",
        "states": states, "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _write(ws, text=None, version=True):
    ws.write(ROADMAP, text if text is not None else roadmap())
    status = ws.acs("roadmap", "status", "--write")
    assert status.returncode == 0, status.stderr
    if version:
        done = ws.acs("design", "init", "--status", "proposed", ROADMAP)
        assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    _write(ws)
    _finish(ws)
    ws.reply = ("Create mode: docs/product/roadmap.md written -- Storefront v2.4.0, Checkout "
                "v2.5.0, Order tracking v2.6.0, all planned. Uncommitted: review it, then run "
                "/acs:create-pr to commit it and open the PR.")


def _asserted_delivered(ws):
    """Wrote `delivered` for the shipped feature, though no ticket says so --
    and skipped the derivation that would have reset it."""
    _start(ws)
    ws.write(ROADMAP, roadmap(storefront="delivered"))
    ws.acs("design", "init", "--status", "proposed", ROADMAP)
    _finish(ws)


def _no_release_rows(ws):
    _start(ws)
    _write(ws, roadmap(rows=False))
    _finish(ws)


def _scheduled_saved_carts(ws):
    _start(ws)
    _write(ws, roadmap(saved_carts=True))
    _finish(ws)


def _unversioned(ws):
    _start(ws)
    _write(ws, version=False)
    _finish(ws)


def _edited_the_prd(ws):
    _start(ws)
    _write(ws)
    ws.acs("design", "bump", PRD)
    _finish(ws)


def _committed(ws):
    _start(ws)
    _write(ws)
    ws.sh("git add -A docs && git commit -qm 'Roadmap'")
    _finish(ws)


def _pushed(ws):
    _start(ws)
    _write(ws)
    ws.sh("git checkout -q -b docs/roadmap && git add -A docs && git commit -qm 'Roadmap'")
    ws.sh("git push -q -u origin docs/roadmap")
    _finish(ws)


def _recorded_no_files(ws):
    _start(ws)
    _write(ws)
    _finish(ws, files=())


def _invented_pr(ws):
    _start(ws)
    _write(ws)
    _finish(ws, pr={"number": 1, "url": "https://github.com/example/shop/pull/1"})


BAD = {
    "asserted a delivered status no ticket bears out": _asserted_delivered,
    "left the Release versions table without rows": _no_release_rows,
    "scheduled the unscheduled Could-have": _scheduled_saved_carts,
    "left the new roadmap without version front matter": _unversioned,
    "bumped the PRD it never edits": _edited_the_prd,
    "committed the roadmap": _committed,
    "pushed a branch": _pushed,
    "recorded no files in states.files": _recorded_no_files,
    "recorded a PR that cannot exist": _invented_pr,
    "started the run and wrote nothing": _start,
}
