"""Calibration plays for create-prd-greenfield-no-code (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--allocate` mints the delivery ticket, the author writes the two documents
from the elicited answers alone, the coordinator commits and pushes the
delivery branch, gh fails, and the result document goes through the real
post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-prd.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-prd"
BRANCH = "task/EVAL-1-product-definition-prd"

PRD = """# PRD — groomr

## Vision

Every independent dog groomer takes bookings online without phone tag.

## Problem statement

Independent groomers lose hours a week to phone and text booking, and
no-shows cost them about a fifth of their slots.

## Target users & personas

- **Groomer** — runs a one- or two-person salon; sets hours and services.
- **Pet owner** — books and reschedules from a phone.

## Goals & success metrics

| Goal | Metric |
|---|---|
| G1 Online booking adoption | 500 bookings a week across all salons by 2027-03-31 |
| G2 Fewer no-shows | no-show rate below 5% of appointments by 2027-06-30 |

## Features (prioritized)

- **Must**: online booking (G1), SMS reminders the day before (G2)
- **Should**: deposits at booking (G2)
- **Could**: loyalty stamp card (G1)
- **Won't**: a marketplace ranking groomers

## Non-functional requirements

- Booking page loads in under 2 s at p95 on a 4G phone.
- 99.5% monthly availability.

## Constraints & assumptions

- EU customers only; personal data stays in an EU region under GDPR.
- SMS goes through a third-party SMS gateway.

## Out of scope

- Native mobile apps; payments beyond deposits.
"""

ROADMAP = """# Roadmap

### Booking MVP — v0.1.0

Delivers online booking and SMS reminders.

### Deposits — v0.2.0

Delivers deposits at booking.

## Release versions

| Version | Milestone | Epic |
|---|---|---|
| v0.1.0 | Booking MVP | Online booking; SMS reminders |
| v0.2.0 | Deposits | Deposits |
"""

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws):
    ws.skill("create-prd")
    started = ws.acs("step", "start", "--step", "create-prd", "--allocate")
    assert started.returncode == 0, started.stderr


def _deliver(ws, prd=PRD, roadmap=ROADMAP, extra=()):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    ws.write("docs/product/prd.md", prd)
    ws.write("docs/product/roadmap.md", roadmap)
    for rel, text in extra:
        ws.write(rel, text)
    ws.sh("git add -A && git commit -qm 'EVAL-1 Add product requirements document and roadmap'")
    ws.sh("git push -q -u origin %s" % BRANCH)


def _finish(ws, findings=(GH_FINDING,)):
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "greenfield PRD written; gh failed, no PR",
        "states": {"prd": {"path": "docs/product",
                           "files": ["docs/product/prd.md", "docs/product/roadmap.md"]}},
        "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws)
    ws.reply = ("EVAL-1 (greenfield): groomr PRD and roadmap written on %s and pushed. gh pr "
                "create failed, so no PR was opened; recorded as a finding." % BRANCH)


def _vague_prd(ws):
    """The skeleton filled with placeholders instead of the elicited answers."""
    _start(ws)
    vague = (PRD.replace("500 bookings a week", "more bookings").replace("below 5%", "lower")
             .replace("under 2 s", "fast").replace("99.5%", "high"))
    _deliver(ws, prd=vague)
    _finish(ws)


def _missing_sections(ws):
    _start(ws)
    _deliver(ws, prd=PRD.split("## Non-functional requirements")[0])
    _finish(ws)


def _started_building(ws):
    _start(ws)
    _deliver(ws, extra=[("src/groomr/__init__.py", ""), ("pyproject.toml", "[project]\n")])
    _finish(ws)


def _no_release_table(ws):
    _start(ws)
    _deliver(ws, roadmap=ROADMAP.split("## Release versions")[0])
    _finish(ws)


BAD = {
    "filled the skeleton with vague placeholders": _vague_prd,
    "shipped a PRD missing three sections": _missing_sections,
    "scaffolded code beside the PRD": _started_building,
    "wrote a roadmap with no Release versions table": _no_release_table,
    "allocated the ticket and wrote nothing": _start,
}
