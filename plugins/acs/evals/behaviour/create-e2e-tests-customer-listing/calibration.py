"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:create-e2e-tests does, through its real writers: `acs.py
step start`, `acs.py filemap set`, the suite in the repo's own harness, left
uncommitted (ADR-0127: no branch, no commit), and `post-create-e2e-tests.py` fed the
result document on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
BRANCH = "task/EVAL-1-serve-the-customer-listing-over-http"
SUITE = "tests/e2e/test_eval_1_customer_listing.py"
E2E = "PYTHONPATH=src python3 -m unittest discover -s tests/e2e -p 'test_*.py'"

GOOD_SUITE = '''import json
import unittest

from harness import get


class CustomerListingE2E(unittest.TestCase):
    def test_tc_2_default_page(self):
        """TC-2"""
        status, headers, body = get("/customers")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(body), {"items": [], "offset": 0, "limit": 20})

    def test_tc_3_offset_and_limit(self):
        """TC-3"""
        status, _, body = get("/customers", "offset=40&limit=10")
        page = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual((page["offset"], page["limit"]), (40, 10))
'''


def _start(ws):
    ws.skill("create-e2e-tests")
    # In a session the Skill call's PreToolUse gate opens the run from the
    # argument; here --ticket names it, which is the same subject.
    started = ws.acs("step", "start", "--step", "create-e2e-tests", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    ws.acs("filemap", "set", "--skill", "create-e2e-tests", "--iteration", "1",
           "--task", "1", "--file", "tests/e2e/")


def _finish(ws, suites, cases):
    result = {"status": "completed", "outcome": "tests_written",
              "summary": "suite-runner passed on iteration 1",
              "states": {"suites_written": suites, "cases_covered": cases, "files": suites},
              "findings": [], "errors": []}
    ws.sh("python3 '%s/post-create-e2e-tests.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(result)))


def _commit(ws, path, message="EVAL-1 e2e suite for the customer listing"):
    ws.sh("git add -- %s && git commit -qm '%s' -- %s" % (path, message, path))


def IDEAL(ws):
    _start(ws)
    ws.write(SUITE, GOOD_SUITE)
    ws.sh(E2E)  # the suite-runner's one run: green
    _finish(ws, [SUITE], ["TC-2", "TC-3"])
    ws.reply = "Wrote %s covering TC-2 and TC-3; it passes. Next: /acs:run-e2e-tests" % SUITE


def _committed(ws):
    """The pre-ADR-0127 behaviour: a commit -- only /acs:create-pr commits."""
    _start(ws)
    ws.write(SUITE, GOOD_SUITE)
    _commit(ws, SUITE)
    _finish(ws, [SUITE], ["TC-2", "TC-3"])


def _covered_the_unit_case(ws):
    _start(ws)
    ws.write(SUITE, GOOD_SUITE.replace('"""TC-2"""', '"""TC-1, TC-2"""'))
    _finish(ws, [SUITE], ["TC-1", "TC-2", "TC-3"])


def _claimed_without_writing(ws):
    _start(ws)
    _finish(ws, [SUITE], ["TC-2", "TC-3"])


def _new_branch(ws):
    _start(ws)
    ws.sh("git checkout -q -b e2e/EVAL-1")
    ws.write(SUITE, GOOD_SUITE)
    _commit(ws, SUITE)
    _finish(ws, [SUITE], ["TC-2", "TC-3"])


def _changed_product_instead(ws):
    _start(ws)
    ws.write("src/shop/customers_api.py", "PAGE = 20\n")
    ws.write(SUITE, GOOD_SUITE)
    _finish(ws, [SUITE], ["TC-2", "TC-3"])


BAD = {
    "fired the skill and wrote nothing": lambda ws: ws.skill("create-e2e-tests"),
    "committed the suite": _committed,
    "also covered the unit case TC-1": _covered_the_unit_case,
    "claimed coverage without writing a suite": _claimed_without_writing,
    "committed the suite on a new branch": _new_branch,
    "added product code alongside the suite": _changed_product_instead,
}
