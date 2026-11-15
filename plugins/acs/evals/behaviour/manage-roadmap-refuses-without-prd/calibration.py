"""Calibration plays for manage-roadmap-refuses-without-prd (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
resumes the ticketless run the scaffold opened, Start finds no PRD, and the
result document -- `failed`, nothing written -- goes through the real
post-hook (ADR-0145)."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-manage-roadmap.py")
STEP = ".acs/state-machine/example-shop/runs/plan-a-roadmap-with-no-prd-ddd9/steps/manage-roadmap"
ROADMAP = "docs/product/roadmap.md"


def _start(ws):
    ws.skill("manage-roadmap")
    started = ws.acs("step", "start", "--step", "manage-roadmap", "--args", "")
    assert started.returncode == 0, started.stderr


def _finish(ws, status="failed", files=()):
    ws.write(STEP + "/result.json", json.dumps({
        "status": status, "summary": "no PRD to plan a roadmap from",
        "states": {"files": list(files)}, "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _finish(ws)
    ws.reply = "There is no PRD to plan a roadmap from; nothing was written. Run /acs:create-prd first."


def _invented_a_roadmap(ws):
    _start(ws)
    ws.write(ROADMAP, "# Roadmap\n\n## Milestones\n\n### Checkout — v2.5.0\n\n- Status: planned\n")
    _finish(ws, status="completed", files=(ROADMAP,))


def _stopped_without_finishing(ws):
    _start(ws)


BAD = {
    "invented a roadmap with no PRD behind it": _invented_a_roadmap,
    "stopped without the mandatory Finish": _stopped_without_finishing,
}
