"""Calibration plays for create-docs-resume-handed-off-set (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--step create-docs --ticket EVAL-1` rejoins the handed-off partition, the
author completes the truncated test-strategy.md and writes
coverage-policy.md, the coordinator commits and pushes EVAL-1's existing
branch, gh fails, and the result document goes through the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-docs.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-docs"
BRANCH = "task/EVAL-1-product-quality-doc-set"
QUALITY = "docs/quality"

STRATEGY = """# Test strategy

## Testing philosophy

Unit tests first, with pytest; every module has a test file.

## Coverage policy

See coverage-policy.md: 90% line coverage or the pipeline fails.

## Suite inventory

- unit: `python3 -m pytest` over `tests/`. No end-to-end suite yet.

## CI gates

- pytest with pytest-cov and `--cov-fail-under=90` on every PR.

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


def _finish(ws, step=STEP, findings=(GH_FINDING,)):
    ws.write(step + "/result.json", json.dumps({
        "status": "completed", "summary": "quality set resumed and reviewed; gh failed, no PR",
        "states": {"doc_set": {"set": "quality", "path": QUALITY,
                               "files": ["test-strategy.md", "coverage-policy.md"]}},
        "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, step))


def _deliver(ws, strategy=STRATEGY, branch=BRANCH, message="EVAL-1 Add product quality doc set"):
    ws.write(QUALITY + "/test-strategy.md", strategy)
    ws.write(QUALITY + "/coverage-policy.md", POLICY)
    ws.sh("git add docs && git commit -qm '%s'" % message)
    ws.sh("git push -q -u origin %s" % branch)


def IDEAL(ws):
    ws.skill("create-docs")
    resumed = ws.acs("step", "start", "--step", "create-docs", "--ticket", "EVAL-1")
    assert resumed.returncode == 0, resumed.stderr
    _deliver(ws)
    _finish(ws)
    ws.reply = ("Resumed EVAL-1: quality set finished on %s and pushed. gh pr create failed, "
                "so no PR was opened; recorded as a finding." % BRANCH)


def _started_over(ws):
    """Read EVAL-1 as a set name it did not recognise, and allocated anew."""
    ws.skill("create-docs")
    ws.sh("git stash -q -u && git checkout -q main")
    started = ws.acs("step", "start", "--step", "create-docs", "--doc-set", "quality", "--allocate")
    assert started.returncode == 0, started.stderr
    ws.sh("git checkout -q -b task/EVAL-2-product-quality-doc-set main")
    _deliver(ws, branch="task/EVAL-2-product-quality-doc-set",
             message="EVAL-2 Add product quality doc set")
    _finish(ws, step=STEP.replace("EVAL-1", "EVAL-2"))


def _trusted_the_truncated_file(ws):
    ws.skill("create-docs")
    assert ws.acs("step", "start", "--step", "create-docs", "--ticket", "EVAL-1").returncode == 0
    with open(os.path.join(ws.path, QUALITY, "test-strategy.md"), encoding="utf-8") as fh:
        _deliver(ws, strategy=fh.read())
    _finish(ws)


def _never_finished(ws):
    ws.skill("create-docs")
    assert ws.acs("step", "start", "--step", "create-docs", "--ticket", "EVAL-1").returncode == 0
    ws.write(QUALITY + "/test-strategy.md", STRATEGY)
    ws.write(QUALITY + "/coverage-policy.md", POLICY)


BAD = {
    "started the set over on a new ticket": _started_over,
    "shipped the truncated test-strategy.md as done": _trusted_the_truncated_file,
    "wrote the files but never delivered or finished": _never_finished,
}
