"""Plays for review-code-named-base (see tests/evals/check_grader_calibration.py).

IDEAL is what /acs:review-code does with `--base release/2.4`, through its
real writers: `acs.py step start --step review-code`, the lens reports and the
adjudication record under steps/review-code/iter-1/, the verdict (its
`reviewed_sha` the working-tree snapshot it judged) at the step root and in
iter-1/,
result.json, and `post-review-code.py`. Stage 3's gate does not run: stage 2
left a blocking finding.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST_REVIEW = os.path.join(PLUGIN, "hooks", "scripts", "post-review-code.py")
REVIEW = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/review-code"

BOUNDARY = {
    "id": "F-1-1", "status": "confirmed", "severity": "blocking", "kind": "acceptance",
    "lens": "A", "file": "src/shop/checkout.py", "line": 6,
    "claim": "can_checkout uses age > ADULT_AGE, so a shopper aged exactly 18 is refused "
             "although AC-1 admits 18 or over.",
    "evidence": ["return age > ADULT_AGE; can_checkout(18) is False",
                 "tests/test_checkout.py checks 30 and 12 only"],
    "resolved_when": "can_checkout(18) is True and a test pins the 18 boundary",
    "traces_to": ["AC-1"],
    "adjudication": {"verdict": "confirmed"},
}

TOKEN = {
    "id": "F-1-2", "status": "confirmed", "severity": "blocking", "kind": "defect",
    "lens": "B", "file": "src/shop/export.py", "line": 1,
    "claim": "API_TOKEN is a live secret hard-coded in source.",
    "evidence": ["API_TOKEN = \"exp-dummy-2f9c41d7...\""],
    "resolved_when": "the token is read from the environment",
}


def _snapshot(ws):
    """`reviewed_sha` is the working-tree snapshot the review judged
    (`acs.py changes snapshot`, ADR-0127) -- not a commit: inside a pipeline
    the reviewed change is uncommitted."""
    done = ws.acs("changes", "snapshot")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)["tree"]



def _review(ws, findings, base="release/2.4", post=True, fix=False):
    # `base` names the ref a play claims it reviewed against; only its findings show it.
    ws.skill("review-code")
    start = ws.acs("step", "start", "--step", "review-code")
    assert start.returncode == 0, start.stderr
    if findings is None:
        return
    if fix:
        ws.sh("sed -i 's/return age > ADULT_AGE/return age >= ADULT_AGE/' src/shop/checkout.py")
    blocking = any(f["severity"] == "blocking" for f in findings)
    for lens in "ABCDE":
        ws.write(REVIEW + "/iter-1/lens-%s.md" % lens, "# Lens %s\n" % lens)
    ws.write(REVIEW + "/iter-1/adjudication.json", json.dumps(
        {"adjudications": [{"id": f["id"], "verdict": "confirmed"} for f in findings]}))
    verdict = json.dumps({
        "skill": "review-code", "run_id": "EVAL-1", "iteration": 1,
        "reviewed_sha": _snapshot(ws),
        "passed": not blocking, "findings": findings}, indent=2)
    ws.write(REVIEW + "/verdict.json", verdict)
    ws.write(REVIEW + "/iter-1/verdict.json", verdict)
    ws.write(REVIEW + "/result.json", json.dumps({
        "status": "completed", "outcome": "blocking_findings" if blocking else "passed",
        "iteration": 1, "summary": "%d finding(s)" % len(findings),
        "findings": [], "errors": []}))
    if post:
        ws.sh("python3 '%s' --result-file '%s/result.json' || true" % (POST_REVIEW, REVIEW))


def IDEAL(ws):
    _review(ws, [BOUNDARY])


BAD = {
    "fired and wrote no verdict": lambda ws: _review(ws, None),
    "reviewed against main and dragged in the release branch":
        lambda ws: _review(ws, [BOUNDARY, TOKEN], base="main"),
    "flagged only the release branch's token": lambda ws: _review(ws, [TOKEN], base="main"),
    "passed the changeset": lambda ws: _review(ws, []),
    "fixed the boundary itself": lambda ws: _review(ws, [BOUNDARY], fix=True),
}
