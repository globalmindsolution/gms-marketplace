"""Calibration plays for create-impl-plan-oversize-split.

IDEAL does what /acs:create-impl-plan does on a split answer, through the
plugin's own writers: `acs step start`, the planner's draft with its split
seams in the step directory, the relayed answer recorded with `clarify.py
add`, then the Finish steps with status failed (nothing published) and the
reply naming the restructure command."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-impl-plan"
PUBLISHED = "docs/development/order-management/EVAL-1/plan.md"
PLAN = '# Plan — EVAL-1: Storefront order management\n\n## Oversize\n\nThis decomposition exceeds one reviewable PR: 5 executor tasks, ten\nacceptance criteria and roughly 1,500 changed lines. Split seams:\n\n1. storage migration + checkout (AC-1, AC-2, AC-10)\n2. order history and detail (AC-3, AC-4)\n3. refunds (AC-5, AC-6)\n4. merchant dashboard and CSV export (AC-7, AC-8)\n5. email notifications (AC-9)\n\nThe user chose to split (C-1); no plan is published.\n\n## Contract\ndelivery_path: complex\nowes:\n  test_cases: true\n  e2e: false\n  reason: "Six new endpoints; no browser flow in this repo"\n\n### Executor tasks & file map\n- task 1: migrations/0001_orders.sql, src/shop/checkout.py, tests/test_checkout.py\n- task 2: src/shop/orders.py, tests/test_orders.py\n- task 3: src/shop/refunds.py, tests/test_refunds.py\n- task 4: src/shop/merchant.py, tests/test_merchant.py\n- task 5: src/shop/notify.py, tests/test_notify.py\n'


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("create-impl-plan")
    started = ws.acs("step", "start", "--step", "create-impl-plan", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    return json.loads(started.stdout)


def _publish(ws, text):
    ws.write(STEP + "/plan.md", text)
    ws.sh('mkdir -p docs/development/order-management/EVAL-1 && cp "%s/plan.md" "%s"' % (STEP, PUBLISHED))


def _declare(ws, files):
    declared = ws.acs("filemap", "set", "--skill", "code", "--iteration", "1", "--task", "1",
                      *[arg for path in files for arg in ("--file", path)])
    assert declared.returncode == 0, declared.stderr
    return json.loads(declared.stdout)["tasks"]


def _finish(ws, status="completed", file_map=None, published=True, summary="calibration"):
    states = {"plan_approved": False, "file_map": file_map or {}}
    if published:
        states["plan_path"] = PUBLISHED
    result = {"status": status, "summary": summary, "states": states,
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-create-impl-plan.py" --result-file "%s/result.json"' % (SCRIPTS, STEP))

SPLIT = "user chose to split; restructure required before implementation"


def _answer(ws):
    ws.sh('python3 "%s/clarify.py" add --skill create-impl-plan --ticket EVAL-1 '
          '--question "The plan exceeds one reviewable PR: accept one large PR, or split?" '
          '--answer "Split the ticket" > /dev/null' % SCRIPTS)


def IDEAL(ws):
    _start(ws)
    ws.write(STEP + "/plan.md", PLAN)
    _answer(ws)
    _finish(ws, status="failed", published=False, summary=SPLIT)
    ws.reply = ("The plan exceeds one reviewable PR and you chose to split. Next: "
                "/acs:create-ticket split EVAL-1 per steps/create-impl-plan/plan.md")


def _one_mega_plan(ws):
    """Ignored the answer and planned one large PR."""
    _start(ws)
    _publish(ws, PLAN.replace("## Oversize", "## Scope"))
    _finish(ws, file_map={})
    ws.reply = "Plan published; next /acs:code EVAL-1."


def _stopped_unrecorded(ws):
    """Stopped on the size without recording the answer or finishing."""
    _start(ws)
    ws.write(STEP + "/plan.md", PLAN)
    ws.reply = "This is too big; consider /acs:create-ticket split EVAL-1."


def _built_it(ws):
    """Split correctly, then started implementing the first slice anyway."""
    IDEAL(ws)
    ws.write("src/shop/checkout.py", "def checkout():\n    pass\n")


BAD = {
    "planned one mega-PR": _one_mega_plan,
    "stopped without recording the answer or Finish": _stopped_unrecorded,
    "implemented a slice after splitting": _built_it,
}
