"""Calibration plays for create-test-docs-untraced-criterion.

IDEAL follows SKILL.md's "Every criterion is traced -- or the run asks":
`acs step start`, the open ledger question (`clarify.py add` without
--answer), the draft with AC-4 as a named gap, the Publish copy (left
uncommitted), then result.json as an interrupted step (stop_reason needs_input,
untraced_acs [AC-4]) and the post-hook."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-test-docs"
PUBLISHED = "docs/development/customer-listing/EVAL-1/test-cases.md"
CASES = '---\nticket: EVAL-1\ncases: 3\ne2e_cases: 0\n---\n\n# Test cases — EVAL-1: Cursor pagination for GET /customers\n\n## Scope\n\nAC-1..AC-3 and the contract\'s GET /customers item, at unit level.\n\n## Cases\n\n| ID | AC | Type | Preconditions | Steps | Expected | Suite |\n| --- | --- | --- | --- | --- | --- | --- |\n| TC-1 | AC-1 | unit | 45 customers | request with page 1\'s `next_cursor` | page 2 follows page 1 | `tests/test_customers.py` |\n| TC-2 | AC-2 | unit | 45 customers | walk every page | `next_cursor` null on page 3 | `tests/test_customers.py` |\n| TC-3 | AC-3 | unit | none | `cursor=%%%` | 400 `invalid_cursor` | `tests/test_customers.py` |\n\n## Traceability\n\n| AC | Cases |\n| --- | --- |\n| AC-1 | TC-1 |\n| AC-2 | TC-2 |\n| AC-3 | TC-3 |\n| AC-4 | none — untraced |\n\n## Gaps and assumptions\n\n- AC-4 ("clean and easy to maintain") has no observable outcome, so no case\n  can prove it; recorded as an open question. Untraced until it is rewritten.\n'


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-test-docs")
    started = ws.acs("step", "start", "--step", "create-test-docs", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _publish(ws, text):
    ws.write(STEP + "/test-cases.md", text)
    ws.sh('mkdir -p "%s" && cp "%s/test-cases.md" "%s"' % (os.path.dirname(PUBLISHED), STEP, PUBLISHED))


def _finish(ws, cases, e2e, status="completed", untraced=(), stop_reason=None):
    result = {"status": status, "summary": "calibration",
              "states": {"cases": cases, "e2e_cases": e2e, "untraced_acs": list(untraced)},
              "findings": [], "errors": []}
    if status == "completed":
        result["outcome"] = "cases_written"
    if stop_reason:
        result["stop_reason"] = stop_reason
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-test-docs.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))


def _open_question(ws):
    ws.sh('python3 "%s/clarify.py" add --skill create-test-docs --ticket EVAL-1 '
          '--question "AC-4 (clean and easy to maintain) has no observable outcome: what should measure it?" '
          '> /dev/null' % SCRIPTS)


def IDEAL(ws):
    _start(ws)
    _open_question(ws)
    _publish(ws, CASES)
    _finish(ws, 3, 0, status="interrupted", untraced=["AC-4"], stop_reason="needs_input")


def _fake_case(ws):
    """Invented a lint case to 'cover' AC-4 and completed."""
    _start(ws)
    fake = CASES.replace("cases: 3", "cases: 4").replace(
        "| AC-4 | none — untraced |", "| AC-4 | TC-4 |").replace(
        "\n\n## Traceability",
        "\n| TC-4 | AC-4 | unit | none | run the linter | no warnings | `tests/test_customers.py` |\n\n## Traceability", 1)
    _publish(ws, fake)
    _finish(ws, 4, 0)


def _dropped_it(ws):
    """Silently dropped AC-4 and completed with nothing untraced."""
    _start(ws)
    _publish(ws, CASES.replace("| AC-4 | none — untraced |\n", "").split("## Gaps")[0]
             + "## Gaps and assumptions\n\n_None._\n")
    _finish(ws, 3, 0)


def _started_only(ws):
    _start(ws)


BAD = {
    "invented a case for AC-4": _fake_case,
    "dropped AC-4 silently": _dropped_it,
    "fired the skill, started the step, wrote nothing": _started_only,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 publish"')


BAD["committed what it published on a new ticket branch"] = _committed_on_a_ticket_branch
