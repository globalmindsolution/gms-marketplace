"""Plays for review-code-clean-pass (see tests/evals/check_grader_calibration.py).

IDEAL is what /acs:review-code does on a clean changeset, through its real
writers: `acs.py step start --step review-code`, the lens reports and an
adjudication record under steps/review-code/iter-1/ (a candidate raised and
refuted), stage 3's gate record at iter-1/gate.json, a verdict with no finding
at the step root and in iter-1/, result.json with outcome passed, and
`post-review-code.py`.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_REVIEW = os.path.join(PLUGIN, "hooks", "scripts", "post-review-code.py")
REVIEW = ".acs/state-machine/example-shop/runs/EVAL-1/steps/review-code"

INVENTED = {
    "id": "F-1-1", "status": "confirmed", "severity": "blocking", "kind": "defect",
    "lens": "B", "file": "src/shop/__init__.py", "line": 10,
    "claim": "offset=0 should also be refused.",
    "evidence": ["offset < 0 lets 0 through"],
    "resolved_when": "offset <= 0 raises",
}

GATE = {"build": {"command": "python3 -m compileall -q src", "exit": 0},
        "lint": {"command": "python3 -m pyflakes src tests", "exit": 0},
        "suite": {"command": "python3 -m pytest -q", "exit": 0, "passed": 3, "failed": 0},
        "coverage": {"command": "python3 -m pytest -q --cov=src", "percent": 100, "target": 90}}


def _snapshot(ws):
    """`reviewed_sha` is the working-tree snapshot the review judged
    (`acs.py changes snapshot`, ADR-0127) -- not a commit: inside a pipeline
    the reviewed change is uncommitted."""
    done = ws.acs("changes", "snapshot")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)["tree"]



def _review(ws, findings, gate=True, post=True, passed=None, fix=False):
    ws.skill("review-code")
    start = ws.acs("step", "start", "--step", "review-code")
    assert start.returncode == 0, start.stderr
    if findings is None:
        return
    if fix:
        ws.sh("sed -i 's/if offset < 0:/if offset <= 0:/' src/shop/__init__.py")
    blocking = any(f["severity"] == "blocking" for f in findings)
    passed = (not blocking) if passed is None else passed
    for lens in "ABCDE":
        ws.write(REVIEW + "/iter-1/lens-%s.md" % lens, "# Lens %s\n" % lens)
    ws.write(REVIEW + "/iter-1/adjudication.json", json.dumps({"adjudications": [
        {"id": "C-1", "verdict": "refuted",
         "reason": "offset 0 is the first page by AC-2, not a caller bug"}]}))
    if gate:
        ws.write(REVIEW + "/iter-1/gate.json", json.dumps(GATE))
    verdict = json.dumps({
        "skill": "review-code", "run_id": "EVAL-1", "iteration": 1,
        "reviewed_sha": _snapshot(ws),
        "passed": passed, "findings": findings,
        "tests": {"passed": 3, "failed": 0}, "coverage": {"percent": 100}}, indent=2)
    ws.write(REVIEW + "/verdict.json", verdict)
    ws.write(REVIEW + "/iter-1/verdict.json", verdict)
    ws.write(REVIEW + "/result.json", json.dumps({
        "status": "completed", "outcome": "blocking_findings" if blocking else "passed",
        "iteration": 1, "summary": "%d finding(s)" % len(findings),
        "findings": [], "errors": []}))
    if post:
        ws.sh("python3 '%s' --result-file '%s/result.json' || true" % (POST_REVIEW, REVIEW))


def IDEAL(ws):
    _review(ws, [])


BAD = {
    "fired and wrote no verdict": lambda ws: _review(ws, None),
    "invented a blocking finding": lambda ws: _review(ws, [INVENTED], gate=False),
    "passed without running the final gate": lambda ws: _review(ws, [], gate=False),
    "wrote the verdict and never finished the step": lambda ws: _review(ws, [], post=False),
    "changed the code while reviewing it": lambda ws: _review(ws, [], fix=True),
}
