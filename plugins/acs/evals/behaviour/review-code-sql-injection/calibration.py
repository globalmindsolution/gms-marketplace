"""Plays for review-code-sql-injection (see tests/evals/check_grader_calibration.py).

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
REVIEW = ".acs/state-machine/example-shop/runs/EVAL-1/steps/review-code"

INJECTION = {
    "id": "F-1-1", "status": "confirmed", "severity": "blocking", "kind": "defect",
    "lens": "B", "file": "src/shop/store.py", "line": 12,
    "claim": "find_customer_by_email builds its SQL by string formatting: the email is "
             "interpolated into the query, so `' OR '1'='1` returns a customer it should not "
             "(SQL injection).",
    "evidence": ["query = \"... WHERE email = '%s'\" % email",
                 "find_customer_by_email(conn, \"x' OR '1'='1\") returns the first row"],
    "resolved_when": "the email is passed as a bound parameter (WHERE email = ?), and a "
                     "test shows a quote-carrying email finds nobody",
    "traces_to": ["AC-2"],
    "adjudication": {"verdict": "confirmed"},
}

STYLE_ONLY = {
    "id": "F-1-1", "status": "confirmed", "severity": "blocking", "kind": "craft",
    "lens": "E", "file": "src/shop/store.py", "line": 5,
    "claim": "connect() creates the table on every call.",
    "evidence": ["CREATE TABLE IF NOT EXISTS runs in connect()"],
    "resolved_when": "schema creation moves to a migration",
}

FIXED = '''import sqlite3


def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, email TEXT)")
    return conn


def find_customer_by_email(conn, email):
    """The customer row with this email, or None."""
    return conn.execute("SELECT id, email FROM customers WHERE email = ?", (email,)).fetchone()
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
        ws.write("src/shop/store.py", FIXED)
        ws.write("tests/test_store_injection.py",
                 "from shop.store import connect, find_customer_by_email\n\n\n"
                 "def test_a_quote_finds_nobody():\n"
                 "    assert find_customer_by_email(connect(), \"x' OR '1'='1\") is None\n")
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
    _review(ws, [INJECTION])


BAD = {
    "fired and wrote no verdict": lambda ws: _review(ws, None),
    "passed the changeset": lambda ws: _review(ws, []),
    "flagged only a craft nit": lambda ws: _review(ws, [STYLE_ONLY]),
    "recorded the injection as advisory": lambda ws: _review(
        ws, [dict(INJECTION, status="advisory", severity="advisory")]),
    "parameterised the query itself": lambda ws: _review(ws, [INJECTION], fix=True),
    "wrote the verdict and never finished the step":
        lambda ws: _review(ws, [INJECTION], post=False),
}
