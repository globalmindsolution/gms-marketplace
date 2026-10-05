"""Plays for review-code-off-by-one-page (see tests/evals/check_grader_calibration.py).

IDEAL is what /acs:review-code does on this changeset, through its real
writers: `acs.py step start --step review-code`, the lens reports and the
adjudication record under steps/review-code/iter-1/, the verdict at the step
root and its iter-1 copy (the one the kernel reads), result.json, and
`post-review-code.py`. Stage 3's gate does not run: stage 2 left a blocking
finding.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_REVIEW = os.path.join(PLUGIN, "hooks", "scripts", "post-review-code.py")
REVIEW = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/review-code"

OFF_BY_ONE = {
    "id": "F-1-1", "status": "confirmed", "severity": "blocking", "kind": "defect",
    "lens": "B", "file": "src/shop/__init__.py", "line": 13,
    "claim": "page_bounds treats a 1-based page as 0-based: page 1 returns customers "
             "20-39 and the first page is unreachable.",
    "evidence": ["start = page * per_page, so page_bounds(1) == (20, 40)",
                 "the only test checks a page's length, not which customers it holds"],
    "resolved_when": "page_bounds(1, n) == (0, n), and a test asserts page 1 returns "
                     "the first per_page customers",
    "traces_to": ["AC-1", "AC-3"],
    "adjudication": {"verdict": "confirmed"},
}

DOCS_ONLY = {
    "id": "F-1-1", "status": "confirmed", "severity": "blocking", "kind": "craft",
    "lens": "E", "file": "README.md", "line": 9,
    "claim": "The README does not document the per_page parameter.",
    "evidence": ["README.md lists ?page= and nothing else"],
    "resolved_when": "README.md documents per_page",
}

FIXED = '''PAGE_SIZE = 20


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    return {"items": [], "offset": offset, "limit": limit}


def page_bounds(page, per_page=PAGE_SIZE):
    """Slice bounds for a 1-based page number."""
    start = (page - 1) * per_page
    return start, start + per_page


def list_customers_page(customers, page=1, per_page=PAGE_SIZE):
    """One page of customers; page 1 is the first page."""
    start, end = page_bounds(page, per_page)
    return customers[start:end]
'''


def _snapshot(ws):
    """`reviewed_sha` is the working-tree snapshot the review judged
    (`acs.py changes snapshot`, ADR-0127) -- not a commit: inside a pipeline
    the reviewed change is uncommitted."""
    done = ws.acs("changes", "snapshot")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)["tree"]


def _review(ws, findings, passed=None, outcome=None, post=True, fix=False):
    ws.skill("review-code")
    start = ws.acs("step", "start", "--step", "review-code")
    assert start.returncode == 0, start.stderr
    if findings is None:
        return
    if fix:
        ws.write("src/shop/__init__.py", FIXED)
        ws.write("tests/test_first_page.py",
                 "from shop import page_bounds\n\n\ndef test_first():\n"
                 "    assert page_bounds(1, 10) == (0, 10)\n")
    blocking = any(f["severity"] == "blocking" for f in findings)
    passed = (not blocking) if passed is None else passed
    outcome = outcome or ("blocking_findings" if blocking else "passed")
    for lens in "ABCDE":
        ws.write(REVIEW + "/iter-1/lens-%s.md" % lens, "# Lens %s\n" % lens)
    ws.write(REVIEW + "/iter-1/adjudication.json", json.dumps(
        {"adjudications": [{"id": f["id"], "verdict": "confirmed"} for f in findings]}))
    verdict = json.dumps({
        "skill": "review-code", "run_id": "EVAL-1", "iteration": 1,
        "reviewed_sha": _snapshot(ws),
        "passed": passed, "findings": findings}, indent=2)
    ws.write(REVIEW + "/verdict.json", verdict)
    ws.write(REVIEW + "/iter-1/verdict.json", verdict)
    ws.write(REVIEW + "/result.json", json.dumps({
        "status": "completed", "outcome": outcome, "iteration": 1,
        "summary": "%d finding(s)" % len(findings), "findings": [], "errors": []}))
    if post:
        # `|| true`: a verdict the kernel refuses is a bad run to grade, not a
        # broken calibration.
        ws.sh("python3 '%s' --result-file '%s/result.json' || true" % (POST_REVIEW, REVIEW))


def IDEAL(ws):
    _review(ws, [OFF_BY_ONE])


BAD = {
    "fired and wrote no verdict": lambda ws: _review(ws, None),
    "passed the changeset": lambda ws: _review(ws, []),
    "flagged only the docs": lambda ws: _review(ws, [DOCS_ONLY]),
    "fixed the defect itself": lambda ws: _review(ws, [OFF_BY_ONE], fix=True),
    "asserted a pass beside its blocking finding":
        lambda ws: _review(ws, [OFF_BY_ONE], passed=True, outcome="passed"),
    "wrote the verdict and never finished the step":
        lambda ws: _review(ws, [OFF_BY_ONE], post=False),
}
