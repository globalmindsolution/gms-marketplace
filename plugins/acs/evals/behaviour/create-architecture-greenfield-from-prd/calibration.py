"""Calibration plays for create-architecture-greenfield-from-prd (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
resumes the ticketless run the scaffold opened, the architect designs the HLD
from the PRD and the confirmed answers -- the high-level design only, nothing
under lld/ -- and leaves it uncommitted, and the result document, listing every
written path in `states.files`, goes through the real post-hook. Nothing is
branched, committed or pushed (ADR-0127). Every hld/ file gets its
version front matter through `acs design init --status proposed`: nothing is
built yet, so the whole design is ahead of the code (ADR-0122)."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-architecture.py")
STEP = ".git/acs/state-machine/example-shop/runs/design-the-groomr-architecture-a90a/steps/create-architecture"
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
INTEGRATION = """# Integration map

```mermaid
flowchart LR
  page[booking page] -->|JSON over HTTPS, sync| api[booking-api]
  worker[reminder-worker] -->|HTTPS, sync| sms[SMS gateway]
```
"""
HLD = {
    "overview.md": "# Overview\n\n## System context\n\ngroomr.\n\n## Goals\n\nG1, G2.\n\n"
                   "## Quality attributes\n\n2 s p95; 99.5%.\n\n## Constraints\n\nGDPR, EU region.\n",
    "c4-context.md": "# C4 context\n\n```mermaid\nC4Context\n  System(groomr, \"groomr\")\n"
                     "  System_Ext(sms, \"SMS gateway\")\n```\n",
    "c4-container.md": CONTAINER,
    "c4-component.md": "# C4 component\n\n```mermaid\nC4Component\n"
                       "  Component(slots, \"slot finder\")\n```\n",
    "data-model.md": "# Data model\n\n```mermaid\nerDiagram\n  GROOMER ||--o{ APPOINTMENT : takes\n"
                     "  PET_OWNER ||--o{ APPOINTMENT : books\n```\n",
    "cross-cutting.md": "# Cross-cutting conventions\n\n## API conventions\n\nJSON over HTTPS; "
                        "RFC 7807 errors.\n\n## Data conventions\n\nUUID keys; created_at/updated_at."
                        "\n\n## Security\n\nPersonal data stays in the EU region (GDPR).\n\n"
                        "## Observability\n\nStructured logs; p95 booking-page latency.\n",
    "integration-map.md": INTEGRATION,
    "deployment.md": "# Deployment\n\n```mermaid\nflowchart LR\n  host[EU container host] --> "
                     "api[booking-api]\n  host --> worker[reminder-worker]\n  host --> db[postgres]\n```\n",
    "tech-stack.md": "# Tech stack\n\n## Languages\n\nPython 3.12.\n\n## Frameworks\n\nPostgreSQL 16."
                     "\n\n## Conventions\n\nsrc layout.\n",
    "project-structure.md": "# Project structure\n\n## Directory layout\n\n```mermaid\nflowchart TD\n"
                            "  root --> booking_api\n  root --> reminder_worker\n```\n",
}
# What the skill no longer writes: low-level design, per ticket, by the Design skills.
LLD = {
    "contracts.md": "# Contracts\n\n## Contracts\n\n- `POST /appointments` books a free slot.\n",
    "flows/send-reminder.md": ("# send-reminder\n\n```mermaid\nsequenceDiagram\n"
                               "  participant reminder-worker\n  participant SMS as SMS gateway\n"
                               "  reminder-worker->>SMS: send\n```\n"),
}



def _start(ws):
    ws.skill("create-architecture")
    started = ws.acs("step", "start", "--step", "create-architecture", "--args", "")
    assert started.returncode == 0, started.stderr


def _deliver(ws, hld=None, lld=None, extra=(), status="proposed", commit=False):
    written = []
    for name, text in (hld or HLD).items():
        written.append("%s/hld/%s" % (ARCH, name))
        ws.write(written[-1], text)
    if status:
        # A new file designed ahead of the code: `design init --status
        # proposed`; the run is ticketless, so no `--ticket` (ADR-0122, 0127).
        done = ws.acs("design", "init", "--status", status, *written)
        assert done.returncode == 0, done.stderr
    for name, text in (lld or {}).items():
        ws.write("%s/lld/%s" % (ARCH, name), text)
    for rel, text in extra:
        ws.write(rel, text)
    if commit:
        # The pre-ADR-0127 delivery: a delivery branch, a commit and a push.
        ws.sh("git checkout -q -b %s main" % BRANCH)
        ws.sh("git add -A && git commit -qm 'EVAL-1 Add product architecture doc set'")
        ws.sh("git push -q -u origin %s" % BRANCH)


def _finish(ws, hld=None):
    hld = list(hld or HLD)
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "greenfield HLD reviewed; left as local changes",
        "states": {"architecture": {"path": ARCH, "hld": hld},
                   "files": ["%s/hld/%s" % (ARCH, n) for n in hld]},
        "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws)
    ws.reply = ("Greenfield: high-level design written under docs/architecture/hld/ and left "
                "uncommitted. Review it, then /acs:create-pr to commit it and open the PR. Next: "
                "/acs:create-ticket for the repository scaffold, then /acs:ship.")


def _monolith(ws):
    """One invented container and an API landscape of one app: not the
    confirmed design."""
    _start(ws)
    hld = dict(HLD)
    hld["c4-container.md"] = ("# C4 container\n\n```mermaid\nC4Container\n"
                              "  Container(app, \"groomr\", \"Python\")\n```\n")
    hld["integration-map.md"] = ("# Integration map\n\n```mermaid\nflowchart LR\n"
                                 "  owner[pet owner] --> app[groomr]\n```\n")
    _deliver(ws, hld=hld)
    _finish(ws)


def _scaffolded_too(ws):
    _start(ws)
    _deliver(ws, extra=[("booking_api/app.py", ""), ("docker-compose.yml", "services: {}\n")])
    _finish(ws)


def _missing_hld(ws):
    _start(ws)
    _deliver(ws, hld={k: v for k, v in HLD.items()
                      if k not in ("data-model.md", "project-structure.md")})
    _finish(ws, hld=[k for k in HLD if k not in ("data-model.md", "project-structure.md")])


def _wrote_the_lld_too(ws):
    """The pre-ADR-0118 doc set: the HLD plus contracts and a sequence flow."""
    _start(ws)
    _deliver(ws, lld=LLD)
    _finish(ws)


def _no_integration_map(ws):
    _start(ws)
    _deliver(ws, hld={k: v for k, v in HLD.items() if k != "integration-map.md"})
    _finish(ws, hld=[k for k in HLD if k != "integration-map.md"])


def _no_cross_cutting(ws):
    _start(ws)
    _deliver(ws, hld={k: v for k, v in HLD.items() if k != "cross-cutting.md"})
    _finish(ws, hld=[k for k in HLD if k != "cross-cutting.md"])


def _unversioned(ws):
    """Wrote the HLD with no version front matter on any file."""
    _start(ws)
    _deliver(ws, status=None)
    _finish(ws)


def _claimed_implemented(ws):
    """Versioned a design for code that does not exist as already built."""
    _start(ws)
    _deliver(ws, status="implemented")
    _finish(ws)


def _delivered_it_itself(ws):
    _start(ws)
    _deliver(ws, commit=True)
    _finish(ws)


BAD = {
    "designed a single invented container": _monolith,
    "scaffolded code beside the docs": _scaffolded_too,
    "left out two HLD files": _missing_hld,
    "wrote LLD contracts and flows beside the HLD": _wrote_the_lld_too,
    "left out hld/integration-map.md": _no_integration_map,
    "left out hld/cross-cutting.md": _no_cross_cutting,
    "started the run and wrote nothing": _start,
    "committed and pushed a delivery branch": _delivered_it_itself,
    "wrote the HLD without version front matter": _unversioned,
    "marked a design with no code behind it implemented": _claimed_implemented,
}
