"""Calibration plays for create-tech-design-story-without-flag.

IDEAL: the Skill call, which the PreToolUse(Skill) hook ADMITS although the
story carries no design flag (ADR-0139) -- played through the real hook,
`dispatch.py pre` with the Skill payload, exit 0 -- then what the coordinator
does through the plugin's own writers: `acs step start`, the answers the
prompt relayed into the ledger, the draft with its version front matter
(`acs.py design init`), the Publish copy into the design record folder (left
uncommitted, ADR-0127), result.json and the post-hook. The bad plays refuse
on the retired flag, revive it, or skip the skill's step."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-tech-design"
FOLDER = "docs/architecture/lld/service-health/EVAL-1"
PUBLISHED = FOLDER + "/tech-design.md"

DESIGN = """# Tech design — EVAL-1: Show the app version on GET /health

## Decision & options

**Decision:** read the version from the installed package metadata (Option A).

### Options considered

#### Option A — package metadata

`importlib.metadata.version("shop")`, falling back to pyproject.toml when the
package is not installed.

#### Option B — parse pyproject.toml at request time

No install needed, but a file read on every health check.

### Rationale

Option A is what an installed service reports (C-1).

## HLD views affected

none — the health endpoint is internal to the shop service.

## LLD

### API

none yet — GET /health gains a `version` field.

### Data

n/a — nothing is stored.

### Flows

n/a — one in-process call.

### Components

n/a — no new component.

## NFRs

Performance: one cached metadata lookup.

## Risks

None load-bearing; `ok` stays exactly as it is.

### Rollout & migration

Plain deploy; rollback is a redeploy.

## Open questions

none
"""

ANSWERS = [
    ("Where does the version come from?", "Installed package metadata; pyproject.toml as fallback"),
    ("Does the body keep ok?", "Yes, unchanged; version is an added field"),
]


def _gate(ws, expected=0):
    ws.skill("create-tech-design")
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Skill",
                          "tool_input": {"skill": "acs:create-tech-design", "args": "EVAL-1"},
                          "cwd": ws.path})
    ws.sh("printf '%%s' '%s' | python3 \"%s/dispatch.py\" pre >/dev/null 2>&1; test $? -eq %d"
          % (payload, SCRIPTS, expected))


def _written(ws):
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    started = ws.acs("step", "start", "--step", "create-tech-design", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _publish(ws):
    ws.write(STEP + "/tech-design.md", DESIGN)
    ws.acs("design", "init", "--status", "proposed", "--ticket", "EVAL-1",
           "--feature", "service-health", STEP + "/tech-design.md")
    ws.sh('mkdir -p "%s" && cp "%s/tech-design.md" "%s"' % (FOLDER, STEP, PUBLISHED))


def _finish(ws):
    result = {"status": "completed", "summary": "calibration",
              "states": {"design_path": PUBLISHED,
                         "decision": "Read the version from the installed package metadata (Option A)",
                         "files": _written(ws)},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-tech-design.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def IDEAL(ws):
    _gate(ws)
    _start(ws)
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill create-tech-design --ticket EVAL-1 '
              '--question "%s" --answer "%s" > /dev/null' % (SCRIPTS, question, answer))
    _publish(ws)
    _finish(ws)
    ws.reply = ("Published the tech design for EVAL-1 to %s (proposed, v1): the version "
                "comes from the installed package metadata. Approve it with "
                "/acs:set-doc-status approved service-health, then /acs:create-impl-plan EVAL-1."
                % PUBLISHED)


def _refused_itself(ws):
    """Read the retired rule into the prose and turned the story away."""
    _gate(ws)
    ws.reply = ("EVAL-1 is not flagged needs_design, and /acs:create-tech-design only runs "
                "for design-significant tickets. Go straight to /acs:code EVAL-1.")


def _flagged_the_ticket(ws):
    """Wrote the retired flag onto the ticket on the way through."""
    ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-",
           stdin=json.dumps({"needs_design": True}))
    IDEAL(ws)


def _hand_written(ws):
    """Wrote the design straight into the repo, never opening the step."""
    _gate(ws)
    ws.sh('mkdir -p "%s"' % FOLDER)
    ws.write(PUBLISHED, DESIGN)
    ws.reply = "Wrote the tech design for EVAL-1 to %s." % PUBLISHED


BAD = {
    "refused the story for want of a design flag": _refused_itself,
    "flagged the ticket needs_design": _flagged_the_ticket,
    "wrote the design by hand without the step": _hand_written,
}
