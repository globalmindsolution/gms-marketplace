"""Calibration plays for manage-roadmap-status-refresh (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
resumes the ticketless run the scaffold opened, the coordinator runs
`acs.py roadmap status --write` -- no subagent, no question -- which derives
Checkout `delivered` from EVAL-1's merged commit and leaves the rest
`planned`, moves no version (a status refresh is not a new version, ADR-0145),
and the result document, listing the roadmap in `states.files`, goes through
the real post-hook."""

import json
import os
import re

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-manage-roadmap.py")
STEP = ".acs/state-machine/example-shop/runs/refresh-the-roadmap-status-45d8/steps/manage-roadmap"
ROADMAP = "docs/product/roadmap.md"


def _read(ws, rel):
    with open(os.path.join(ws.path, rel), encoding="utf-8") as fh:
        return fh.read()


def _start(ws):
    ws.skill("manage-roadmap")
    started = ws.acs("step", "start", "--step", "manage-roadmap", "--args", "status")
    assert started.returncode == 0, started.stderr


def _status(ws):
    done = ws.acs("roadmap", "status", "--write")
    assert done.returncode == 0, done.stderr


def _finish(ws, files=(ROADMAP,), pr=None):
    states = {"roadmap": {"path": ROADMAP, "mode": "status"}, "files": list(files)}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "Roadmap status refreshed from the tickets",
        "states": states, "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _status(ws)
    _finish(ws)
    ws.reply = ("Status refresh: Checkout v2.5.0 delivered (EVAL-1 merged); Storefront and "
                "Order tracking still planned; version unchanged. Uncommitted: "
                "docs/product/roadmap.md.")


def _asserted_everything_delivered(ws):
    """Wrote the statuses by hand -- the shipped storefront too."""
    _start(ws)
    ws.write(ROADMAP, re.sub(r"\bplanned\b", "delivered", _read(ws, ROADMAP)))
    _finish(ws)


def _only_the_status_line(ws):
    """Moved the Status line but left the Release versions cell behind."""
    _start(ws)
    ws.write(ROADMAP, _read(ws, ROADMAP).replace(
        "### Checkout — v2.5.0\n\n- Status: planned", "### Checkout — v2.5.0\n\n- Status: delivered"))
    _finish(ws)


def _bumped(ws):
    _start(ws)
    _status(ws)
    ws.acs("design", "bump", ROADMAP)
    _finish(ws)


def _spawned_the_loop(ws):
    _start(ws)
    ws.called("Agent", subagent_type="acs:manage-roadmap-surveyor")
    _status(ws)
    _finish(ws)


def _committed(ws):
    _start(ws)
    _status(ws)
    ws.sh("git commit -qam 'Roadmap status'")
    _finish(ws)


def _recorded_no_files(ws):
    _start(ws)
    _status(ws)
    _finish(ws, files=())


def _invented_pr(ws):
    _start(ws)
    _status(ws)
    _finish(ws, pr={"number": 1, "url": "https://github.com/example/shop/pull/1"})


BAD = {
    "asserted every milestone delivered": _asserted_everything_delivered,
    "moved the Status line but not the Release versions cell": _only_the_status_line,
    "bumped the version for a status refresh": _bumped,
    "spawned the surveyor for a status refresh": _spawned_the_loop,
    "committed the roadmap": _committed,
    "recorded no files in states.files": _recorded_no_files,
    "recorded a PR that cannot exist": _invented_pr,
    "started the run and wrote nothing": _start,
}
