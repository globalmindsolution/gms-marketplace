"""Calibration plays for create-prd-greenfield-no-code (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
resumes the ticketless run the scaffold opened, the author writes the two
documents from the elicited answers alone (the hub, the roadmap and one PRD per
feature, ADR-0142) and leaves them uncommitted, the coordinator gives every
document its first version front matter (`acs.py design init
--status proposed`), and the result document, listing both in `states.files`, goes through the real
post-hook. Nothing is branched, committed or pushed (ADR-0127)."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-prd.py")
STEP = ".acs/state-machine/example-shop/runs/define-the-groomr-product-0a66/steps/create-prd"
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

### Must have

- [Online booking](features/online-booking/prd.md) — pet owners book a slot (supports G1)
- [SMS reminders](features/sms-reminders/prd.md) — a text the day before (supports G2)

### Should have

- [Deposits](features/deposits/prd.md) — a deposit at booking (supports G2)

### Could have

- [Loyalty stamp card](features/loyalty-stamp-card/prd.md) — repeat visits earn stamps (supports G1)

### Won't have

- A marketplace ranking groomers against each other (supports G1)

## Non-functional requirements

- Booking page loads in under 2 s at p95 on a 4G phone.
- 99.5% monthly availability.

## Constraints & assumptions

- EU customers only; personal data stays in an EU region under GDPR.
- SMS goes through a third-party SMS gateway.

## Out of scope

- Native mobile apps; payments beyond deposits.
"""

def feature_prd(name, slug, goal, requirement):
    return """# %s

## Summary

%s.

## Goals served

- %s

## Requirements

- **R1** — %s

## Acceptance criteria

- Given the feature is live, when it is used, then %s.

## Dependencies

None.

## Out of scope

Anything not named above.
""" % (name, requirement.capitalize(), goal, requirement, requirement)


FEATURES = (
    ("online-booking", "Online booking", "G1", "a pet owner books an open slot from a phone"),
    ("sms-reminders", "SMS reminders", "G2", "an SMS goes out the day before an appointment"),
    ("deposits", "Deposits", "G2", "a deposit is taken at booking"),
    ("loyalty-stamp-card", "Loyalty stamp card", "G1", "repeat visits earn stamps"),
)
FEATURE_FILES = tuple("docs/product/features/%s/prd.md" % f[0] for f in FEATURES)
FILES = ("docs/product/prd.md", "docs/product/roadmap.md") + FEATURE_FILES

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



def _start(ws):
    ws.skill("create-prd")
    started = ws.acs("step", "start", "--step", "create-prd", "--args", '')
    assert started.returncode == 0, started.stderr


def _deliver(ws, prd=PRD, roadmap=ROADMAP, extra=(), commit=False, features=True):
    ws.write("docs/product/prd.md", prd)
    ws.write("docs/product/roadmap.md", roadmap)
    for slug, name, goal, requirement in (FEATURES if features else ()):
        ws.write("docs/product/features/%s/prd.md" % slug,
                 feature_prd(name, slug, goal, requirement))
    for rel, text in extra:
        ws.write(rel, text)
    if commit:
        # The pre-ADR-0127 delivery: a delivery branch, a commit and a push.
        ws.sh("git checkout -q -b %s main" % BRANCH)
        ws.sh("git add -A && git commit -qm 'EVAL-1 Add product requirements document and roadmap'")
        ws.sh("git push -q -u origin %s" % BRANCH)


def _finish(ws):
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "greenfield PRD written and reviewed; left as local changes",
        "states": {"prd": {"path": "docs/product"},
                   "files": list(FILES)},
        "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _version(ws):
    """The coordinator's Versions step: a new document gets `design init`."""
    done = ws.acs("design", "init", "--status", "proposed", *FILES)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    _deliver(ws)
    _version(ws)
    _finish(ws)
    ws.reply = ("Greenfield: groomr PRD and roadmap written. Uncommitted: docs/product/prd.md, "
                "docs/product/roadmap.md and a features/<slug>/prd.md per feature. Review them, then run /acs:create-pr to commit them "
                "and open the PR.")


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


def _delivered_it_itself(ws):
    _start(ws)
    _deliver(ws, commit=True)
    _finish(ws)


def _single_file_prd(ws):
    """The layout this replaced: every feature inside prd.md, no feature PRDs."""
    _start(ws)
    _deliver(ws, features=False)
    _finish(ws)


def _unlinked_index(ws):
    """Feature PRDs written, but the hub's index does not link them."""
    _start(ws)
    _deliver(ws, prd=PRD.replace("](features/", "](#"))
    _finish(ws)


def _feature_prd_missing_sections(ws):
    _start(ws)
    _deliver(ws, extra=[("docs/product/features/online-booking/prd.md",
                         "# Online booking\n\n## Summary\n\nBook online.\n")])
    _finish(ws)


def _unversioned(ws):
    _start(ws)
    _deliver(ws)
    _finish(ws)


BAD = {
    "kept every feature in prd.md, writing no feature PRDs": _single_file_prd,
    "wrote feature PRDs the hub's index does not link": _unlinked_index,
    "wrote a feature PRD missing five sections": _feature_prd_missing_sections,
    "left the new documents without version front matter": _unversioned,
    "filled the skeleton with vague placeholders": _vague_prd,
    "shipped a PRD missing three sections": _missing_sections,
    "scaffolded code beside the PRD": _started_building,
    "wrote a roadmap with no Release versions table": _no_release_table,
    "started the run and wrote nothing": _start,
    "committed and pushed a delivery branch": _delivered_it_itself,
}
