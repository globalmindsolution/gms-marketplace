"""Calibration plays for create-prd-repo-template (see
tests/evals/check_grader_calibration.py). The ideal run resolves the templates
(`acs.py prd template`: the repo's feature template, the built-in hub), writes
the hub with the built-in eight sections and each feature PRD with the repo
template's seven -- Rollout included -- versions them, and finishes through the
real post-hook. Nothing is branched, committed or pushed (ADR-0127, ADR-0147)."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-prd.py")
STEP = ".acs/state-machine/example-shop/runs/define-the-groomr-product-with-our-d6de/steps/create-prd"

PRD = """# PRD — groomr

## Vision

Every independent dog groomer takes bookings online without phone tag.

## Problem statement

Groomers lose hours a week to phone booking; no-shows cost a fifth of slots.

## Target users & personas

- **Groomer** — runs a small salon.
- **Pet owner** — books from a phone.

## Goals & success metrics

- G1: 500 bookings a week across all salons by 2027-03-31
- G2: a no-show rate below 5% of appointments by 2027-06-30

## Features (prioritized)

### Must have

- [Online booking](features/online-booking/prd.md) — book a slot (supports G1)
- [SMS reminders](features/sms-reminders/prd.md) — a text the day before (supports G2)

### Won't have

- A marketplace ranking groomers (supports G1)

## Non-functional requirements

- The booking page loads in under 2 s at p95; 99.5% monthly availability.

## Constraints & assumptions

- EU customers only; data stays in the EU.

## Out of scope

- Native mobile apps; payments.
"""

FEATURES = (("online-booking", "Online booking", "G1", "a pet owner books a slot",
             "A beta group of 20 salons first, then every salon."),
            ("sms-reminders", "SMS reminders", "G2", "an SMS goes out the day before",
             "Behind a feature flag, switched on salon by salon."))
FILES = ("docs/product/prd.md",) + tuple("docs/product/features/%s/prd.md" % f[0] for f in FEATURES)


def feature(name, goal, req, rollout, with_rollout=True, rollout_last=False):
    parts = ["# %s\n" % name, "## Summary\n\n%s.\n" % name, "## Goals served\n\n- %s\n" % goal,
             "## Requirements\n\n- **R1** — %s\n" % req,
             "## Acceptance criteria\n\n- Given it is live, %s (R1).\n" % req,
             "## Dependencies\n\nNone.\n"]
    tail = ["## Out of scope\n\nAnything not named above.\n"]
    roll = ["## Rollout\n\n%s\n" % rollout] if with_rollout else []
    return "\n".join(parts + (tail + roll if rollout_last else roll + tail))


def _start(ws):
    ws.skill("create-prd")
    started = ws.acs("step", "start", "--step", "create-prd", "--args", "")
    assert started.returncode == 0, started.stderr
    found = ws.acs("prd", "template")
    assert found.returncode == 0, found.stderr


def _write(ws, prd=PRD, **kw):
    ws.write("docs/product/prd.md", prd)
    for slug, name, goal, req, rollout in FEATURES:
        ws.write("docs/product/features/%s/prd.md" % slug, feature(name, goal, req, rollout, **kw))
    done = ws.acs("design", "init", "--status", "proposed", *FILES)
    assert done.returncode == 0, done.stderr


def _finish(ws):
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "greenfield PRD written from the repo's templates",
        "states": {"prd": {"path": "docs/product"}, "files": list(FILES)},
        "findings": [], "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def IDEAL(ws):
    _start(ws)
    _write(ws)
    _finish(ws)
    ws.reply = ("Greenfield: groomr PRD written from your feature template -- each feature PRD "
                "has its Rollout section. Uncommitted: docs/product/prd.md and two feature PRDs; "
                "review them, then /acs:create-pr.")


def _used_the_builtin(ws):
    _start(ws)
    _write(ws, with_rollout=False)
    _finish(ws)


def _rollout_out_of_order(ws):
    _start(ws)
    _write(ws, rollout_last=True)
    _finish(ws)


def _rollout_in_the_hub(ws):
    _start(ws)
    _write(ws, prd=PRD + "\n## Rollout\n\nBeta first.\n")
    _finish(ws)


def _committed(ws):
    _start(ws)
    _write(ws)
    ws.sh("git add -A docs && git commit -qm 'PRD'")
    _finish(ws)


BAD = {
    "wrote the built-in six sections, ignoring the repo template": _used_the_builtin,
    "put Rollout after Out of scope": _rollout_out_of_order,
    "gave the hub a Rollout section too": _rollout_in_the_hub,
    "committed the documents": _committed,
    "started the run and wrote nothing": _start,
}
