"""Plays for ship-raw-request (tests/evals/check_grader_calibration.py).

IDEAL is ship on a free-text subject, as ship/SKILL.md Step 2 reads it: a new
run from that prompt (`acs run next --args`), then every step of
workflows/ship.yaml through its own writers (`acs step start`, the result
document, the post-hook) on the current run, until create-pr fails at its
critical gh base detection before any push.

analyze-requirements is played the way its coordinator runs it on a ticketless
Development run (ADR-0128) -- no longer skipped for want of a ticket: the
decided feature recorded through `acs.py requirements refine`, the assumption
in the run's own ledger (`clarify.py add`, no `--ticket`), the analysis
published where `acs.py artifacts show` resolves it for this run
(the folder `docs/development/customer-listing/<run-id>/analysis/`, ADR-0133)
and recorded in `states.files`.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
BRANCH = "task/cap-the-customer-page-size-at-100"
BASE_DETECT = "gh repo view --json defaultBranchRef --jq .defaultBranchRef.name"
REQUEST = ("Cap the customer page size at 100. list_customers must refuse a limit above 100 "
           "with a ValueError naming the maximum; a limit of exactly 100 is still served, and "
           "the default page size stays 20.")

CAPPED = '''PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    if limit > MAX_PAGE_SIZE:
        raise ValueError("limit must be at most %d" % MAX_PAGE_SIZE)
    return {"items": [], "offset": offset, "limit": limit}
'''


class _Run(object):
    def __init__(self, ws):
        ws.skill("ship")
        # ship/SKILL.md's loop: `run next --args "$ARGUMENTS"` resolves the
        # free-text subject to a new run, marks it ship-driven (so its
        # analysis is a Development run's) and records the prompt as its
        # requirements.
        made = ws.acs("run", "next", "--args", REQUEST)
        assert made.returncode == 0, made.stderr
        self.ws = ws
        self.run_id = json.loads(made.stdout)["run_id"]
        self.dir = ".acs/state-machine/example-shop/runs/" + self.run_id

    def start(self, step):
        self.ws.skill(step)
        started = self.ws.acs("step", "start", "--step", step)
        assert started.returncode == 0, (step, started.stderr)

    def finish(self, step, status="completed", outcome=None, states=None, errors=None):
        doc = {"status": status, "summary": "%s: calibration" % step,
               "states": states or {}, "findings": [], "errors": errors or []}
        if outcome:
            doc["outcome"] = outcome
        rel = "%s/steps/%s/result.json" % (self.dir, step)
        self.ws.write(rel, json.dumps(doc))
        self.ws.sh('python3 "%s/post-%s.py" --result-file %s' % (SCRIPTS, step, rel))

    def step(self, step, **kw):
        self.start(step)
        self.finish(step, **kw)


FEATURE = "customer-listing"

README = """---
ready_for_planning: true
needs_design_recommendation: false
feature: customer-listing
---

# Analysis — Cap the customer page size at 100

## Scope and summary

`list_customers` serves any `limit`; a caller can ask for an unbounded page.
Cap it at 100: a larger limit raises ValueError naming the maximum, exactly
100 is served, and the default page size stays 20.

## Contexts

| Context | File | Purpose |
|---|---|---|
| Customer listing | [customer-listing.md](customer-listing.md) | how a client pages through customers |

## Refined acceptance criteria

The request's three criteria, as written.

## Cross-cutting risks and decisions

_None._

## Questions and assumptions

- C-1 feature — assumed: customer-listing (PRD F1 Customer listing).

Assumptions:

- The cap applies to `list_customers` only; no HTTP surface changes.

## Verdict

Ready for planning; no design needed.
"""

CONTEXT = """---
context: customer-listing
---

# Customer listing

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/__init__.py | shop | `list_customers` refuses `limit > 100` | src/shop/__init__.py:8 |

## Rules and edge cases

_None._

## Risks

_None._

## Open questions

_None._

## API notes

_None._
"""

#: The analysis is a folder (ADR-0133): a README plus one file per context.
ANALYSIS = {"README.md": README, "customer-listing.md": CONTEXT}


def _analyze(run):
    """analyze-requirements on the prompt run, the way its coordinator runs it."""
    ws = run.ws
    run.start("analyze-requirements")
    ws.sh('python3 "%s/clarify.py" add --skill analyze-requirements --question "Which PRD '
          'feature does this belong to?" --answer "%s" --source assumption --rationale '
          '"the request changes the customer listing (PRD F1)" > /dev/null' % (SCRIPTS, FEATURE))
    refined = ws.acs("requirements", "refine", "--from", "-",
                     stdin=json.dumps({"feature": FEATURE, "features": [FEATURE],
                                       "needs_design": False}))
    assert refined.returncode == 0, refined.stderr
    shown = ws.acs("artifacts", "show")
    assert shown.returncode == 0, shown.stderr
    target = os.path.relpath(json.loads(shown.stdout)["paths"]["analysis.md"], ws.path)
    folder = "docs/development/%s/%s/analysis" % (FEATURE, run.run_id)
    assert target.replace(os.sep, "/") == folder + "/README.md", (target, folder)
    step = "%s/steps/analyze-requirements" % run.dir
    for name, text in ANALYSIS.items():
        ws.write(step + "/iter-1/analysis/" + name, text)
    ws.sh('mkdir -p "%s" && cp "%s"/iter-1/analysis/*.md "%s"/' % (folder, step, folder))
    run.finish("analyze-requirements", states={
        "ready_for_planning": True, "questions_open": 0,
        "files": [folder + "/" + name for name in ANALYSIS]})


def _snapshot(ws):
    """`reviewed_sha`: the working-tree snapshot the review judged (ADR-0127)."""
    return json.loads(ws.acs("changes", "snapshot").stdout)["tree"]


def _through_review(ws, source=CAPPED, review=True):
    run = _Run(ws)
    _analyze(run)
    run.step("create-impl-plan")
    run.step("create-test-docs", outcome="no_cases_owed")
    run.start("code")
    ws.write("src/shop/__init__.py", source)
    run.finish("code", outcome="implemented",
               states={"files": ["src/shop/__init__.py"], "tasks_implemented": ["page-size-cap"],
                       "tests": {"passed": 3, "failed": 0}, "docs_updated": []})
    if not review:
        return run
    run.start("review-code")
    verdict = json.dumps({"skill": "review-code", "run_id": run.run_id, "iteration": 1,
                          "reviewed_sha": _snapshot(ws),
                          "passed": True, "findings": []})
    ws.write(run.dir + "/steps/review-code/iter-1/verdict.json", verdict)
    ws.write(run.dir + "/steps/review-code/verdict.json", verdict)
    run.finish("review-code", outcome="passed")
    run.start("create-e2e-tests")
    run.start("docs-sync")
    run.finish("create-e2e-tests", outcome="no_e2e_owed")
    run.finish("docs-sync")
    run.step("run-e2e-tests", outcome="nothing_to_run")
    return run


def _create_pr_fails(ws, run):
    run.start("create-pr")
    error = ws.sh(BASE_DETECT + " 2>&1 || true").strip() or "gh: command not found"
    run.finish("create-pr", status="failed", errors=[{
        "severity": "error", "area": "github", "command": BASE_DETECT, "error": error,
        "hint": "check `gh auth status` and repo access", "replayable": False}])
    return error


def IDEAL(ws):
    run = _through_review(ws)
    error = _create_pr_fails(ws, run)
    ws.reply = ("## /acs:ship · %s · failed\n\ncreate-pr failed: `%s` (%s). Resume with "
                "`/acs:ship --run %s` once gh can reach GitHub." % (run.run_id, BASE_DETECT, error,
                                                                  run.run_id))


def _implemented_by_hand(ws):
    ws.skill("ship")
    ws.sh("git checkout -q -b " + BRANCH)
    ws.write("src/shop/__init__.py", CAPPED)
    ws.sh("git add -A src && git commit -qm 'Cap the customer page size at 100'")
    ws.reply = "Implemented the cap; gh is unavailable so no PR."


def _stopped_after_code(ws):
    _through_review(ws, review=False)
    ws.reply = "Implemented the cap."


def _pushed_and_merged(ws):
    run = _through_review(ws)
    _create_pr_fails(ws, run)
    ws.sh("git switch -q -c %s && git add -A src && git commit -qm 'Cap'" % BRANCH)
    ws.sh("git push -q -u origin " + BRANCH)
    ws.called("Bash", command="gh pr merge %s --squash" % BRANCH)
    ws.reply = "create-pr failed on gh, so I pushed the branch and tried gh pr merge."


def _wrong_cap(ws):
    run = _through_review(ws, source=CAPPED.replace("MAX_PAGE_SIZE = 100", "MAX_PAGE_SIZE = 50"))
    _create_pr_fails(ws, run)
    ws.reply = "create-pr failed on gh."


BAD = {
    "implemented the change outside the pipeline": _implemented_by_hand,
    "stopped after code": _stopped_after_code,
    "pushed and tried to merge": _pushed_and_merged,
    "implemented a different cap": _wrong_cap,
}
