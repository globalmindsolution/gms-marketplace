"""Calibration plays for create-docs-operations-only (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--step create-docs --doc-set operations --allocate` mints the set's delivery
ticket, the author bootstraps and tailors the five templates, the coordinator
commits and pushes the set's branch, gh fails, and the result document goes
through the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-docs.py")
TEMPLATES = os.path.join(PLUGIN, "templates", "operations")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-docs"
BRANCH = "task/EVAL-1-product-operations-doc-set"
OPS = "docs/operations"

DOCS = {
    "release-process.md": """# Release process

## Versioning and release-cut steps

Semantic versions cut from `main`; the current release is v2.4.0.

## Changelog discipline

Every change adds a line to `CHANGELOG.md` in the same PR; the lines are
promoted to a dated section at release time.

## Branch and tag conventions

Releases are tagged `vX.Y.Z` on `main`.

## Rollback procedure

Redeploy the previous tag.
""",
    "runbooks.md": """# Runbooks

## Standard operating procedures

Deploy and restart the `shop` container.

## On-call escalation path

One weekly rotation; an unacknowledged page escalates to the tech lead after
15 minutes.

## Incident triage steps

Confirm impact against the SLOs, assign a severity, open an incident.
""",
    "observability.md": """# Observability

## Logging, metrics, and alerting conventions

JSON logs to stdout; alert when an SLO is breached over one hour.

## Dashboards

One service dashboard: availability and p95 latency.

## SLO/SLA notes

- 99.9% monthly availability.
- p95 API latency under 300 ms.
""",
    "incident-response.md": """# Incident response

## Severity levels

SEV1 (checkout down), SEV2, SEV3 (cosmetic).

## Roles during an incident

The on-call engineer leads; the tech lead communicates.

## Postmortem process

Every SEV1 gets a postmortem within five working days.
""",
    "test-scheduling.md": """# Test scheduling

## The /acs:test scheduling recipe

Run `claude /acs:test` headless every night at 02:00 UTC.

## Example cron/CI snippets

```cron
0 2 * * * cd /srv/shop && claude -p "/acs:test"
```

## Where results land

In the run's test-results artifact under the acs workspace.
""",
}

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the operations docs PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _template(name):
    with open(os.path.join(TEMPLATES, name), encoding="utf-8") as fh:
        return fh.read()


def _start(ws):
    ws.skill("create-docs")
    started = ws.acs("step", "start", "--step", "create-docs", "--doc-set", "operations",
                     "--allocate")
    assert started.returncode == 0, started.stderr


def _write(ws, docs=None, extra=()):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for name, text in (docs or DOCS).items():
        ws.write("%s/%s" % (OPS, name), text)
    for rel, text in extra:
        ws.write(rel, text)
    ws.sh("git add docs && git commit -qm 'EVAL-1 Add product operations doc set'")


def _finish(ws, findings=(GH_FINDING,), pr=None):
    states = {"doc_set": {"set": "operations", "path": OPS, "files": sorted(DOCS)}}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "operations set reviewed; branch pushed; gh failed, no PR",
        "states": states, "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _push(ws):
    ws.sh("git push -q -u origin %s" % BRANCH)


def IDEAL(ws):
    _start(ws)
    _write(ws)
    _push(ws)
    _finish(ws)
    ws.reply = ("operations: EVAL-1 written on %s and pushed. gh pr create failed (no GitHub "
                "access), so no PR was opened; recorded as a finding." % BRANCH)


def _allocated_only(ws):
    _start(ws)


def _untailored_templates(ws):
    _start(ws)
    _write(ws, docs={name: _template(name) for name in DOCS})
    _push(ws)
    _finish(ws)


def _dropped_a_file(ws):
    _start(ws)
    _write(ws, docs={k: v for k, v in DOCS.items() if k != "test-scheduling.md"})
    _push(ws)
    _finish(ws)


def _also_wrote_quality(ws):
    _start(ws)
    _write(ws, extra=[("docs/quality/test-strategy.md", "# Test strategy\n")])
    _push(ws)
    _finish(ws)


def _hid_the_failure(ws):
    _start(ws)
    _write(ws)
    _push(ws)
    _finish(ws, findings=())


def _never_pushed(ws):
    _start(ws)
    _write(ws)
    _finish(ws)


BAD = {
    "allocated the ticket and wrote nothing": _allocated_only,
    "copied the templates without tailoring them": _untailored_templates,
    "left out the test-scheduling file": _dropped_a_file,
    "wrote a quality file nobody asked for": _also_wrote_quality,
    "finished with the gh failure unrecorded": _hid_the_failure,
    "committed but never pushed the delivery branch": _never_pushed,
}
