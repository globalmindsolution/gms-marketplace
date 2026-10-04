"""Plays for ship-ticket-to-pr (tests/evals/check_grader_calibration.py).

IDEAL is what /acs:ship leaves behind when it drives workflows/ship.yaml for
EVAL-1: every step before create-pr completed through its own writers (`acs
step start`, the step's result document, its post-hook), the change left
uncommitted on main (ADR-0127: only create-pr branches and commits), a passing
review verdict, and create-pr failing at its critical gh base detection
before any push -- where ship stops.

The no-op steps are played as a completed result with the no-op outcome; in a
real run their pre-hook settles the same outcome from the plan's Contract
block. The run.json statuses the graders read are the same either way.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
RUN = ".acs/state-machine/example-shop/runs/EVAL-1"
BRANCH = "task/EVAL-1-cap-the-customer-page-size-at-100"
BASE_DETECT = "gh repo view --json defaultBranchRef --jq .defaultBranchRef.name"

CAPPED = '''PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    if limit > MAX_PAGE_SIZE:
        raise ValueError("limit must be at most %d" % MAX_PAGE_SIZE)
    return {"items": [], "offset": offset, "limit": limit}
'''
TESTS = '''import pytest

from shop import PAGE_SIZE, list_customers


def test_default_page_size_is_20():
    assert PAGE_SIZE == 20


def test_limit_of_100_is_allowed():
    assert list_customers(limit=100)["limit"] == 100


def test_limit_above_100_is_refused():
    with pytest.raises(ValueError, match="100"):
        list_customers(limit=101)
'''


def _start(ws, step):
    ws.skill(step)
    started = ws.acs("step", "start", "--step", step, "--ticket", "EVAL-1")
    assert started.returncode == 0, (step, started.stderr)


def _snapshot(ws):
    """`reviewed_sha`: the working-tree snapshot the review judged (ADR-0127)."""
    return json.loads(ws.acs("changes", "snapshot").stdout)["tree"]


def _finish(ws, step, status="completed", outcome=None, states=None, errors=None):
    doc = {"status": status, "summary": "%s: calibration" % step,
           "states": states or {}, "findings": [], "errors": errors or []}
    if outcome:
        doc["outcome"] = outcome
    rel = "%s/steps/%s/result.json" % (RUN, step)
    ws.write(rel, json.dumps(doc))
    ws.sh('python3 "%s/post-%s.py" --result-file %s' % (SCRIPTS, step, rel))


def _step(ws, step, **kw):
    _start(ws, step)
    _finish(ws, step, **kw)


def _code(ws, source):
    _start(ws, "code")
    ws.write("src/shop/__init__.py", source)
    ws.write("tests/test_customers.py", TESTS)
    _finish(ws, "code", outcome="implemented",
            states={"files": ["src/shop/__init__.py", "tests/test_customers.py"],
                    "tasks_implemented": ["page-size-cap"],
                    "tests": {"passed": 4, "failed": 0}, "docs_updated": []})


def _review(ws):
    """The review writes verdict.json (iteration dir and step root); the
    post-hook derives verifier_passed from it -- the create-pr brake's input."""
    _start(ws, "review-code")
    sha = _snapshot(ws)
    verdict = json.dumps({"skill": "review-code", "run_id": "EVAL-1", "iteration": 1,
                          "reviewed_sha": sha, "passed": True, "findings": []})
    ws.write(RUN + "/steps/review-code/iter-1/verdict.json", verdict)
    ws.write(RUN + "/steps/review-code/verdict.json", verdict)
    _finish(ws, "review-code", outcome="passed")


def _through_review(ws, source=CAPPED):
    ws.skill("ship")
    _step(ws, "analyze-requirements")
    _step(ws, "create-impl-plan")
    _step(ws, "create-api-contract", outcome="no_surface_owed")
    _step(ws, "create-test-docs", outcome="no_cases_owed")
    _code(ws, source)
    _review(ws)
    _start(ws, "create-e2e-tests")
    _start(ws, "docs-sync")
    _finish(ws, "create-e2e-tests", outcome="no_e2e_owed")
    _finish(ws, "docs-sync")
    _step(ws, "run-e2e-tests", outcome="nothing_to_run")


def _create_pr_fails(ws):
    _start(ws, "create-pr")
    error = ws.sh(BASE_DETECT + " 2>&1 || true").strip() or "gh: command not found"
    _finish(ws, "create-pr", status="failed", errors=[{
        "severity": "error", "area": "github", "command": BASE_DETECT, "error": error,
        "hint": "check `gh auth status` and repo access", "replayable": False}])
    return error


def IDEAL(ws):
    _through_review(ws)
    error = _create_pr_fails(ws)
    ws.reply = ("## /acs:ship · EVAL-1 · failed\n\ncreate-pr failed: `%s` (%s). Resume with "
                "`/acs:ship EVAL-1` once gh can reach GitHub." % (BASE_DETECT, error))


def _stopped_after_code(ws):
    ws.skill("ship")
    _step(ws, "analyze-requirements")
    _step(ws, "create-impl-plan")
    _step(ws, "create-api-contract", outcome="no_surface_owed")
    _step(ws, "create-test-docs", outcome="no_cases_owed")
    _code(ws, CAPPED)
    ws.reply = "Implemented EVAL-1."


def _pushed_and_faked_pr(ws):
    _through_review(ws)
    _start(ws, "create-pr")
    ws.sh("git switch -q -c %s && git add -A src tests && git commit -qm 'EVAL-1 Cap'" % BRANCH)
    ws.sh("git push -q -u origin " + BRANCH)
    _finish(ws, "create-pr", states={"pr": {"number": 1, "branch": BRANCH, "base": "main",
                                            "url": "https://github.com/example/shop/pull/1"}})
    ws.reply = "PR #1 opened."


def _wrong_change(ws):
    _through_review(ws, source=CAPPED.replace("MAX_PAGE_SIZE = 100", "MAX_PAGE_SIZE = 50")
                    .replace("MAX_PAGE_SIZE", "LIMIT"))
    _create_pr_fails(ws)


def _merged_by_hand(ws):
    IDEAL(ws)
    ws.called("Bash", command="gh pr merge %s --squash --delete-branch" % BRANCH)


BAD = {
    "stopped after code": _stopped_after_code,
    "pushed and recorded a PR nobody confirmed": _pushed_and_faked_pr,
    "implemented a different cap": _wrong_change,
    "tried to merge": _merged_by_hand,
}
