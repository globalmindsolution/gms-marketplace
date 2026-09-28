"""Calibration plays for create-docs-principles-no-architecture (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start
--step create-docs --doc-set principles --allocate` mints the set's delivery
ticket, the author (given `architecture-optional`) records the missing
architecture set in its notes and writes the tailored principles.md, the
coordinator commits and pushes the set's branch, gh fails, and the result
document goes through the real post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-create-docs.py")
TEMPLATE = os.path.join(PLUGIN, "templates", "principles", "principles.md")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-docs"
BRANCH = "task/EVAL-1-product-principles-doc-set"

PRINCIPLES = """# Engineering principles

## Principles

1. **Never store card data.**
2. **Standard library first.**
3. **Every change ships with tests** -- unit coverage at or above 90%.

## Rationale

1. Card details go straight to the payments gateway, never to our database or
   logs, which keeps the service out of PCI scope.
2. Each dependency is a supply-chain and upgrade cost; a PR adding one says
   why the standard library could not do the job.
3. The PRD's NFR2 sets the 90% floor; a PR below it is not merged.
"""
NOTES = """# Authoring notes -- principles

## Mode

bootstrap: no docs/principles/ set exists.

## Upstream inventory

- no architecture set: architecture-derived tailoring falls back to the
  repo/PRD; the stack comes from C-1.
- docs/product/prd.md: "NFR2 Unit test coverage at least 90%."
"""

GH_FINDING = {"severity": "critical", "area": "pr",
              "message": "gh pr create failed; the principles docs PR was not opened",
              "error": "gh: command not found", "hint": "check `gh auth status` and repo access"}


def _start(ws):
    ws.skill("create-docs")
    started = ws.acs("step", "start", "--step", "create-docs", "--doc-set", "principles",
                     "--allocate")
    assert started.returncode == 0, started.stderr


def _write(ws, principles=PRINCIPLES, notes=NOTES, extra=()):
    ws.sh("git checkout -q -b %s main" % BRANCH)
    if notes is not None:
        ws.write(STEP + "/iter-1/authoring.md", notes)
    ws.write("docs/principles/principles.md", principles)
    for rel, text in extra:
        ws.write(rel, text)
    ws.sh("git add docs && git commit -qm 'EVAL-1 Add product principles doc set'")


def _finish(ws, findings=(GH_FINDING,), pr=None):
    states = {"doc_set": {"set": "principles", "path": "docs/principles",
                          "files": ["principles.md"]}}
    if pr:
        states["pr"] = pr
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed", "summary": "principles set reviewed; branch pushed; gh failed, no PR",
        "states": states, "findings": list(findings), "errors": []}, indent=2))
    ws.sh("python3 %s --result-file %s/result.json" % (POST, STEP))


def _push(ws):
    ws.sh("git push -q -u origin %s" % BRANCH)


def IDEAL(ws):
    _start(ws)
    _write(ws)
    _push(ws)
    _finish(ws)
    ws.reply = ("No architecture doc set found; tailoring fell back to the PRD and the confirmed "
                "stack. principles: EVAL-1 written on %s and pushed. gh pr create failed, so no "
                "PR was opened; recorded as a finding." % BRANCH)


def _refused_for_missing_architecture(ws):
    """Stopped at Start: 'run /acs:create-architecture first'."""
    ws.skill("create-docs")
    ws.reply = "No architecture set found; run /acs:create-architecture first."


def _template_principles(ws):
    _start(ws)
    with open(TEMPLATE, encoding="utf-8") as fh:
        _write(ws, principles=fh.read())
    _push(ws)
    _finish(ws)


def _wrote_architecture_first(ws):
    _start(ws)
    _write(ws, extra=[("docs/architecture/hld/tech-stack.md", "# Tech stack\n")])
    _push(ws)
    _finish(ws)


def _unrecorded_degradation(ws):
    _start(ws)
    _write(ws, notes=NOTES.replace("- no architecture set: architecture-derived tailoring falls "
                                   "back to the\n  repo/PRD; the stack comes from C-1.\n", ""))
    _push(ws)
    _finish(ws)


def _never_pushed(ws):
    _start(ws)
    _write(ws)
    _finish(ws)


BAD = {
    "refused for the missing architecture set": _refused_for_missing_architecture,
    "copied the template's example principles": _template_principles,
    "wrote an architecture doc to fill the gap": _wrote_architecture_first,
    "never recorded the missing architecture set": _unrecorded_degradation,
    "committed but never pushed the delivery branch": _never_pushed,
}
