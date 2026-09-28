"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:create-e2e-tests does on the acceptance-criteria
fallback, through its real writers: `acs.py step start`, `acs.py artifacts
show` reporting no test-cases.md, `acs.py filemap set`, the suite in the
repo's own harness, a pathspec commit on the ticket branch, and
`post-create-e2e-tests.py` fed the result document on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
SUITE = "tests/e2e/test_eval_1_customer_listing.py"
E2E = "PYTHONPATH=src python3 -m unittest discover -s tests/e2e -p 'test_*.py'"

GOOD_SUITE = '''import json
import unittest

from harness import get


class CustomerListingE2E(unittest.TestCase):
    def test_ac_1_default_page(self):
        """AC-1"""
        status, headers, body = get("/customers")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(body), {"items": [], "offset": 0, "limit": 20})

    def test_ac_2_offset_and_limit(self):
        """AC-2"""
        status, _, body = get("/customers", "offset=40&limit=10")
        page = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual((page["offset"], page["limit"]), (40, 10))
'''


def _start(ws):
    ws.skill("create-e2e-tests")
    started = ws.acs("step", "start", "--step", "create-e2e-tests", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    shown = json.loads(ws.acs("artifacts", "show", "--ticket", "EVAL-1").stdout)
    assert shown["artifacts"]["test-cases.md"] is None, shown
    ws.acs("filemap", "set", "--skill", "create-e2e-tests", "--iteration", "1",
           "--task", "1", "--file", "tests/e2e/")


def _finish(ws, suites, cases):
    result = {"status": "completed", "outcome": "tests_written",
              "summary": "no test-cases.md: 2 flows derived from the acceptance criteria; "
                         "suite-runner passed on iteration 1",
              "states": {"suites_written": suites, "cases_covered": cases},
              "findings": [], "errors": []}
    ws.sh("python3 '%s/post-create-e2e-tests.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(result)))


def _commit(ws, path):
    ws.sh("git add -- %s && git commit -qm 'EVAL-1 e2e suite for the customer listing' -- %s"
          % (path, path))


REPLY = ("Wrote %s covering AC-1 and AC-2; it passes. No test-cases.md existed, so the "
         "flows were derived from the acceptance criteria. Next: /acs:run-e2e-tests "
         "--for-ticket EVAL-1" % SUITE)


def IDEAL(ws):
    _start(ws)
    ws.write(SUITE, GOOD_SUITE)
    ws.sh(E2E)  # the suite-runner's one run: green
    _commit(ws, SUITE)
    _finish(ws, [SUITE], ["AC-1", "AC-2"])
    ws.reply = REPLY


def _wrote_the_case_document(ws):
    _start(ws)
    ws.write("docs/tickets/EVAL-1/test-cases.md",
             "| ID | AC | Type |\n| --- | --- | --- |\n| TC-1 | AC-1 | e2e |\n| TC-2 | AC-2 | e2e |\n")
    ws.write(SUITE, GOOD_SUITE.replace("AC-1", "TC-1").replace("AC-2", "TC-2"))
    _commit(ws, SUITE)
    _finish(ws, [SUITE], ["TC-1", "TC-2"])
    ws.reply = "Wrote test-cases.md and %s covering TC-1 and TC-2." % SUITE


def _covered_one(ws):
    _start(ws)
    ws.write(SUITE, GOOD_SUITE)
    _commit(ws, SUITE)
    _finish(ws, [SUITE], ["AC-1"])
    ws.reply = REPLY


def _uncommitted(ws):
    _start(ws)
    ws.write(SUITE, GOOD_SUITE)
    _finish(ws, [SUITE], ["AC-1", "AC-2"])
    ws.reply = REPLY


def _refused_without_cases(ws):
    _start(ws)
    doc = {"status": "completed", "outcome": "no_e2e_owed", "summary": "no test-cases.md",
           "states": {"suites_written": [], "cases_covered": []}, "findings": [], "errors": []}
    ws.sh("python3 '%s/post-create-e2e-tests.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(doc)))
    ws.reply = "No test-cases.md exists, so there are no e2e cases to write."


BAD = {
    "fired the skill and wrote nothing": lambda ws: ws.skill("create-e2e-tests"),
    "wrote the case document itself and invented TC ids": _wrote_the_case_document,
    "covered only one criterion": _covered_one,
    "wrote the suite but never committed it": _uncommitted,
    "treated a missing case document as nothing owed": _refused_without_cases,
}
