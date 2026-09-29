"""Calibration plays for create-docs-standards-no-principles (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--step create-docs --doc-set standards --allocate` mints the set's delivery
ticket, the author (given `principles-optional`, no principles set on disk)
bootstraps and tailors the three templates, the coordinator commits and
pushes the set's branch, gh fails, and the result document goes through the
real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-docs.py")
TEMPLATES = os.path.join(PLUGIN, "templates", "standards")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-docs"
BRANCH = "task/EVAL-1-product-standards-doc-set"
STD = "docs/standards"

DOCS = {
    "coding-standards.md": """# Coding standards

## Language and style conventions

Python 3.12; prefer plain functions and the standard library.

## Error handling

Reject bad input by raising `ValueError` naming the argument; never a bare
`except:`.

## Testing conventions

pytest, one `tests/test_<module>.py` per module, coverage at least 90%.
""",
    "conventions.md": """# Conventions

## Naming conventions

snake_case modules, functions and variables; PascalCase classes;
UPPER_SNAKE_CASE constants such as `PAGE_SIZE`.

## Project layout

`src/shop/` for code, `tests/` for tests.

## Formatting

ruff format and ruff check at 100-character lines, run by pre-commit.
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


def _template(name):
    with open(os.path.join(TEMPLATES, name), encoding="utf-8") as fh:
        return fh.read()


def _start(ws):
    ws.skill("create-docs")
    started = ws.acs("step", "start", "--step", "create-docs", "--doc-set", "standards",
                     "--allocate")
    assert started.returncode == 0, started.stderr


def _write(ws, docs=None, extra=()):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    for name, text in (docs or DOCS).items():
        ws.write("%s/%s" % (STD, name), text)
    for rel, text in extra:
        ws.write(rel, text)
    ws.sh("git add docs && git commit -qm 'EVAL-1 Add product standards doc set'")


def _finish(ws, findings=(GH_FINDING,), pr=None):
    states = {"doc_set": {"set": "standards", "path": STD, "files": sorted(DOCS)}}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "standards set reviewed; branch pushed; gh failed, no PR",
        "states": states, "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _push(ws):
    ws.sh("git push -q -u origin %s" % BRANCH)


def IDEAL(ws):
    _start(ws)
    _write(ws)
    _push(ws)
    _finish(ws)
    ws.reply = ("standards: EVAL-1 written on %s and pushed (no principles set: grounding N/A). "
                "gh pr create failed, so no PR was opened; recorded as a finding." % BRANCH)


def _refused_for_missing_principles(ws):
    ws.skill("create-docs")
    ws.reply = "standards needs the principles set first; run /acs:create-docs principles."


def _untailored_templates(ws):
    _start(ws)
    _write(ws, docs={name: _template(name) for name in DOCS})
    _push(ws)
    _finish(ws)


def _wrote_principles_too(ws):
    _start(ws)
    _write(ws, extra=[("docs/principles/principles.md", "# Engineering principles\n")])
    _push(ws)
    _finish(ws)


def _invented_pr(ws):
    _start(ws)
    _write(ws)
    _push(ws)
    _finish(ws, findings=(), pr={"number": 9, "branch": BRANCH,
                                 "url": "https://github.com/example/shop/pull/9"})


BAD = {
    "refused for the missing principles set": _refused_for_missing_principles,
    "copied the templates without tailoring them": _untailored_templates,
    "wrote a principles set nobody asked for": _wrote_principles_too,
    "recorded a PR that cannot exist": _invented_pr,
}
