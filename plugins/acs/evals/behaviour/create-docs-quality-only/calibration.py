"""Calibration plays for create-docs-quality-only (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--step create-docs --doc-set quality --allocate` mints the set's delivery
ticket, the author bootstraps and tailors the two templates, the coordinator
commits and pushes the set's branch, gh fails, and the result document goes
through the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-docs.py")
TEMPLATES = os.path.join(PLUGIN, "templates", "quality")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-docs"
BRANCH = "task/EVAL-1-product-quality-doc-set"
QUALITY = "docs/quality"

STRATEGY = """# Test strategy

## Testing philosophy

Unit tests first, with pytest.

## Coverage policy

See coverage-policy.md: 90% or the pipeline fails.

## Suite inventory

- unit: `python3 -m pytest` over `tests/`. No end-to-end suite yet.

## CI gates

- Run pytest with pytest-cov and `--cov-fail-under=90` on every PR.

## Flaky-test policy

A flaky test is quarantined and ticketed the same day.
"""
POLICY = """# Coverage policy

## Target and hard-fail rule

At least 90% line coverage (PRD NFR2); missing it hard-fails the pipeline.

## Exclusions

None today.

## Measurement per stack

Python: pytest with pytest-cov, `--cov=src --cov-fail-under=90`.

## Escalation

A PR below target is not merged until coverage is restored.
"""

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the quality docs PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _template(name):
    with open(os.path.join(TEMPLATES, name), encoding="utf-8") as fh:
        return fh.read()


def _start(ws, doc_set="quality"):
    ws.skill("create-docs")
    started = ws.acs("step", "start", "--step", "create-docs", "--doc-set", doc_set, "--allocate")
    assert started.returncode == 0, started.stderr


def _write(ws, strategy=STRATEGY, policy=POLICY, extra=()):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    ws.write(QUALITY + "/test-strategy.md", strategy)
    ws.write(QUALITY + "/coverage-policy.md", policy)
    for rel, text in extra:
        ws.write(rel, text)
    ws.sh("git add docs && git commit -qm 'EVAL-1 Add product quality doc set'")


def _finish(ws, findings=(GH_FINDING,), pr=None):
    states = {"doc_set": {"set": "quality", "path": QUALITY,
                          "files": ["test-strategy.md", "coverage-policy.md"]}}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "quality set reviewed; branch pushed; gh failed, no PR",
        "states": states, "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _push(ws):
    ws.sh("git push -q -u origin %s" % BRANCH)


def IDEAL(ws):
    _start(ws)
    _write(ws)
    _push(ws)
    _finish(ws)
    ws.reply = ("quality: EVAL-1 written on %s and pushed. gh pr create failed (no GitHub "
                "access), so no PR was opened; recorded as a finding." % BRANCH)


def _allocated_only(ws):
    _start(ws)


def _untailored_templates(ws):
    _start(ws)
    _write(ws, strategy=_template("test-strategy.md"), policy=_template("coverage-policy.md"))
    _push(ws)
    _finish(ws)


def _also_wrote_operations(ws):
    _start(ws)
    _write(ws, extra=[("docs/operations/release-process.md", "# Release process\n")])
    _push(ws)
    _finish(ws)


def _invented_pr(ws):
    _start(ws)
    _write(ws)
    _push(ws)
    _finish(ws, findings=(), pr={"number": 8, "branch": BRANCH,
                                 "url": "https://github.com/example/shop/pull/8"})


def _never_pushed(ws):
    _start(ws)
    _write(ws)
    _finish(ws)


BAD = {
    "allocated the ticket and wrote nothing": _allocated_only,
    "copied the templates without tailoring them": _untailored_templates,
    "wrote an operations file nobody asked for": _also_wrote_operations,
    "recorded a PR that cannot exist": _invented_pr,
    "committed but never pushed the delivery branch": _never_pushed,
}
