"""Calibration plays for create-requirements-greenfield-elicited (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--allocate` mints the delivery ticket, the authors write the four elicited
DRAFT area files (no code to cite), the coordinator commits and pushes the
delivery branch, gh fails, and the result document goes through the real
post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-requirements.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-requirements"
BRANCH = "task/EVAL-1-product-requirements-doc-set"
REQ = "docs/requirements"
MARK = "DRAFT — human-confirm-required\n\n"

FILES = {
    "functional/book-appointment.md": MARK + "# Book an appointment\n\n"
        "- A pet owner MUST be able to book a free slot, in 15-minute steps, within the groomer's "
        "opening hours (elicited, C-1).\n- The system MUST NOT double-book a groomer (C-1).\n"
        "- A pet owner MAY reschedule up to 24 hours before (C-1).\n",
    "functional/appointment-reminders.md": MARK + "# Appointment reminders\n\n"
        "- The system MUST send exactly one SMS the day before, between 09:00 and 18:00 salon "
        "local time (C-1).\n- The SMS SHOULD carry a reschedule link (C-1).\n",
    "non-functional/performance.md": MARK + "# Performance\n\n"
        "- The booking page MUST load in under 2 s at p95 on a 4G phone (PRD NFR).\n",
    "non-functional/privacy.md": MARK + "# Privacy\n\n"
        "- Personal data MUST be stored only in an EU region (C-1).\n"
        "- A pet owner's data MUST be deleted within 30 days of their request (C-1).\n",
}

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws):
    ws.skill("create-requirements")
    started = ws.acs("step", "start", "--step", "create-requirements", "--allocate")
    assert started.returncode == 0, started.stderr


def _deliver(ws, files=None, extra=()):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for rel, text in (files or FILES).items():
        ws.write("%s/%s" % (REQ, rel), text)
    for rel, text in extra:
        ws.write(rel, text)
    ws.sh("git add -A && git commit -qm 'EVAL-1 Add product requirements doc set'")
    ws.sh("git push -q -u origin %s" % BRANCH)


def _finish(ws, findings=(GH_FINDING,)):
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "greenfield requirements written; gh failed, no PR",
        "states": {"requirements": {"path": REQ,
                                    "files": ["%s/%s" % (REQ, rel) for rel in sorted(FILES)]}},
        "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws)
    ws.reply = ("EVAL-1 (greenfield): four DRAFT area files written from your answers on %s and "
                "pushed. gh pr create failed, so no PR was opened." % BRANCH)


def _unmarked(ws):
    """Written as authoritative: no DRAFT marker on any file."""
    _start(ws)
    _deliver(ws, files={rel: text.replace(MARK, "") for rel, text in FILES.items()})
    _finish(ws)


def _generic_clauses(ws):
    """Plausible booking requirements, not the elicited ones."""
    _start(ws)
    files = dict(FILES)
    files["functional/book-appointment.md"] = MARK + "# Booking\n\n- Owners MUST be able to book.\n"
    files["functional/appointment-reminders.md"] = MARK + "# Reminders\n\n- Reminders MUST be sent.\n"
    _deliver(ws, files=files)
    _finish(ws)


def _dropped_privacy(ws):
    _start(ws)
    _deliver(ws, files={k: v for k, v in FILES.items() if k != "non-functional/privacy.md"})
    _finish(ws)


def _started_building(ws):
    _start(ws)
    _deliver(ws, extra=[("booking/slots.py", "SLOT_MINUTES = 15\n")])
    _finish(ws)


BAD = {
    "wrote the files without the DRAFT marker": _unmarked,
    "wrote generic clauses instead of the elicited ones": _generic_clauses,
    "left out the privacy item": _dropped_privacy,
    "wrote code beside the requirements": _started_building,
    "allocated the ticket and wrote nothing": _start,
}
