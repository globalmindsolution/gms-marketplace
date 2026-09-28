"""Calibration plays for create-docs-all-some-eligible (see
tests/evals/check_grader_calibration.py). The ideal run: Start resolves
`all` to the one eligible batch [["standards"]] (quality and principles on
disk, operations in flight on EVAL-1), `acs step start --step create-docs
--doc-set standards --allocate` mints EVAL-2, the author writes the three
standards files grounded in the principles set, the coordinator commits and
pushes EVAL-2's branch, gh fails, and the result document goes through the
real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-docs.py")
STEP = ".acs/state-machine/example-shop/runs/EVAL-2/steps/create-docs"
OPS_STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-docs"
BRANCH = "task/EVAL-2-product-standards-doc-set"
STD = "docs/standards"

DOCS = {
    "coding-standards.md": """# Coding standards

## Language and style conventions

Python 3.12, standard library first (principle 2).

## Error handling

Fail loudly on bad input (principle 1): raise `ValueError` naming the
argument; never clamp silently.

## Testing conventions

pytest, one `tests/test_<module>.py` per module.
""",
    "conventions.md": """# Conventions

## Naming conventions

snake_case, PascalCase classes, UPPER_SNAKE_CASE constants.

## Project layout

`src/shop/`, `tests/`.

## Formatting

ruff format and ruff check, 100-character lines, via pre-commit.
""",
    "review-checklist.md": """# Review checklist

## Pre-review checklist

- Tests and ruff pass locally.

## Reviewer checklist

- The change follows coding-standards.md and conventions.md.
""",
}

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the standards docs PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws, doc_set="standards"):
    started = ws.acs("step", "start", "--step", "create-docs", "--doc-set", doc_set, "--allocate")
    assert started.returncode == 0, started.stderr


def _write(ws, docs=None, branch=BRANCH, root=STD, commit="EVAL-2 Add product standards doc set"):
    ws.sh("git checkout -q -b %s main" % branch)
    for name, text in (docs or DOCS).items():
        ws.write("%s/%s" % (root, name), text)
    ws.sh("git add docs && git commit -qm '%s'" % commit)
    ws.sh("git push -q -u origin %s" % branch)


def _finish(ws, step=STEP, doc_set="standards", root=STD, files=None, findings=(GH_FINDING,)):
    ws.write(step + "/result.json", json.dumps({
        "status": "completed", "summary": "%s set reviewed; branch pushed; gh failed, no PR" % doc_set,
        "states": {"doc_set": {"set": doc_set, "path": root, "files": sorted(files or DOCS)}},
        "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, step))


def IDEAL(ws):
    ws.skill("create-docs")
    _start(ws)
    _write(ws)
    _finish(ws)
    ws.reply = ("Batch: standards only. quality and principles are already in the repo; "
                "operations is in flight on EVAL-1 (/acs:create-docs EVAL-1). standards: EVAL-2 "
                "written on %s and pushed; gh pr create failed, so no PR was opened." % BRANCH)


def _nothing_eligible(ws):
    ws.skill("create-docs")
    ws.reply = "Every set is already present or in flight; nothing to do."


def _ignored_the_principles(ws):
    ws.skill("create-docs")
    _start(ws)
    docs = dict(DOCS)
    docs["coding-standards.md"] = docs["coding-standards.md"].replace(
        "Fail loudly on bad input (principle 1): raise `ValueError` naming the\nargument; never "
        "clamp silently.", "Handle errors sensibly.")
    _write(ws, docs=docs)
    _finish(ws)


def _also_started_operations(ws):
    """Ran every set it had facts for: a fresh operations ticket too."""
    IDEAL(ws)
    ws.sh("git checkout -q main")
    _start(ws, "operations")
    _write(ws, docs={"release-process.md": "# Release process\n"},
           branch="task/EVAL-3-product-operations-doc-set", root="docs/operations",
           commit="EVAL-3 Add product operations doc set")


def _resumed_the_in_flight_ticket(ws):
    IDEAL(ws)
    assert ws.acs("step", "start", "--step", "create-docs", "--ticket", "EVAL-1").returncode == 0
    ws.sh("git checkout -q -b task/EVAL-1-product-operations-doc-set main")
    ws.write("docs/operations/release-process.md", "# Release process\n")
    _finish(ws, step=OPS_STEP, doc_set="operations", root="docs/operations",
            files=["release-process.md"])


BAD = {
    "reported nothing eligible and stopped": _nothing_eligible,
    "wrote standards that ignore the principles set": _ignored_the_principles,
    "started a new operations ticket beside EVAL-1": _also_started_operations,
    "resumed and finished the in-flight EVAL-1": _resumed_the_in_flight_ticket,
}
