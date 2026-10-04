"""Calibration plays for create-architecture-greenfield-from-prd (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--allocate` mints the delivery ticket, the architects design the doc set from
the PRD and the confirmed answers, the coordinator commits and pushes the
delivery branch, gh fails, and the result document goes through the real
post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-architecture.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-architecture"
BRANCH = "task/EVAL-1-product-architecture-doc-set"
ARCH = "docs/architecture"

CONTAINER = """# C4 container

```mermaid
C4Container
  Person(owner, "Pet owner")
  Container(api, "booking-api", "Python 3.12", "booking page and JSON API")
  Container(worker, "reminder-worker", "Python 3.12", "hourly SMS reminders")
  ContainerDb(db, "postgres", "PostgreSQL 16", "groomers, services, owners, appointments")
  System_Ext(sms, "SMS gateway")
  Rel(owner, api, "books")
  Rel(api, db, "reads/writes")
  Rel(worker, db, "reads tomorrow's appointments")
  Rel(worker, sms, "sends SMS")
```
"""
HLD = {
    "overview.md": "# Overview\n\n## System context\n\ngroomr.\n\n## Goals\n\nG1, G2.\n\n"
                   "## Quality attributes\n\n2 s p95; 99.5%.\n\n## Constraints\n\nGDPR, EU region.\n\n"
                   "Flows: [book-appointment](../lld/flows/book-appointment.md), "
                   "[send-reminder](../lld/flows/send-reminder.md)\n",
    "c4-context.md": "# C4 context\n\n```mermaid\nC4Context\n  System(groomr, \"groomr\")\n"
                     "  System_Ext(sms, \"SMS gateway\")\n```\n",
    "c4-container.md": CONTAINER,
    "c4-component.md": "# C4 component\n\n```mermaid\nC4Component\n"
                       "  Component(slots, \"slot finder\")\n```\n",
    "data-model.md": "# Data model\n\n```mermaid\nerDiagram\n  GROOMER ||--o{ APPOINTMENT : takes\n"
                     "  PET_OWNER ||--o{ APPOINTMENT : books\n```\n",
    "deployment.md": "# Deployment\n\n```mermaid\nflowchart LR\n  host[EU container host] --> "
                     "api[booking-api]\n  host --> worker[reminder-worker]\n  host --> db[postgres]\n```\n",
    "tech-stack.md": "# Tech stack\n\n## Languages\n\nPython 3.12.\n\n## Frameworks\n\nPostgreSQL 16."
                     "\n\n## Conventions\n\nsrc layout.\n",
    "project-structure.md": "# Project structure\n\n## Directory layout\n\n```mermaid\nflowchart TD\n"
                            "  root --> booking_api\n  root --> reminder_worker\n```\n",
}
CONTRACTS = "# Contracts\n\n## Contracts\n\n- `POST /appointments` books a free slot.\n"
BOOK = ("# book-appointment\n\n```mermaid\nsequenceDiagram\n  participant Owner\n"
        "  participant booking-api\n  participant postgres\n  Owner->>booking-api: POST /appointments\n"
        "  booking-api->>postgres: insert if slot free\n```\n")
REMIND = ("# send-reminder\n\n```mermaid\nsequenceDiagram\n  participant reminder-worker\n"
          "  participant postgres\n  participant SMS as SMS gateway\n"
          "  reminder-worker->>postgres: tomorrow's appointments\n  reminder-worker->>SMS: send\n```\n")

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the docs-only PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws):
    ws.skill("create-architecture")
    started = ws.acs("step", "start", "--step", "create-architecture", "--allocate", "--args", "")
    assert started.returncode == 0, started.stderr


def _deliver(ws, hld=None, remind=REMIND, extra=()):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for name, text in (hld or HLD).items():
        ws.write("%s/hld/%s" % (ARCH, name), text)
    ws.write(ARCH + "/lld/contracts.md", CONTRACTS)
    ws.write(ARCH + "/lld/flows/book-appointment.md", BOOK)
    ws.write(ARCH + "/lld/flows/send-reminder.md", remind)
    for rel, text in extra:
        ws.write(rel, text)
    ws.sh("git add -A && git commit -qm 'EVAL-1 Add product architecture doc set'")
    ws.sh("git push -q -u origin %s" % BRANCH)


def _finish(ws, findings=(GH_FINDING,)):
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "greenfield doc set reviewed; gh failed, no PR",
        "states": {"architecture": {"path": ARCH, "hld": sorted(HLD),
                                    "lld": ["contracts.md", "flows/book-appointment.md",
                                            "flows/send-reminder.md"]}},
        "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws)
    ws.reply = ("EVAL-1 (greenfield): architecture doc set written on %s and pushed. gh pr create "
                "failed, so no PR was opened. Next, once merged: /acs:create-ticket for the "
                "repository scaffold, then /acs:ship." % BRANCH)


def _monolith(ws):
    """One invented container and a prose flow: not the confirmed design."""
    _start(ws)
    hld = dict(HLD)
    hld["c4-container.md"] = ("# C4 container\n\n```mermaid\nC4Container\n"
                              "  Container(app, \"groomr\", \"Python\")\n```\n")
    _deliver(ws, hld=hld, remind="# send-reminder\n\nThe app texts owners the day before.\n")
    _finish(ws)


def _scaffolded_too(ws):
    _start(ws)
    _deliver(ws, extra=[("booking_api/app.py", ""), ("docker-compose.yml", "services: {}\n")])
    _finish(ws)


def _missing_hld(ws):
    _start(ws)
    _deliver(ws, hld={k: v for k, v in HLD.items()
                      if k not in ("data-model.md", "project-structure.md")})
    _finish(ws)


BAD = {
    "designed a single invented container": _monolith,
    "scaffolded code beside the docs": _scaffolded_too,
    "left out two HLD files": _missing_hld,
    "allocated the ticket and wrote nothing": _start,
}
