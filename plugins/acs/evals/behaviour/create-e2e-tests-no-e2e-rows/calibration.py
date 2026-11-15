"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:create-e2e-tests does when the case document types no
case e2e, through its real writers: `acs.py step start`, the case document's
own counter (`acs_lib.e2e_case_count`) reading zero, and
`post-create-e2e-tests.py` fed a `completed` / `no_e2e_owed` result on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
CASES = "docs/development/customer-listing/EVAL-1/test-cases.md"
SUITE = "tests/e2e/test_eval_1_page_cap.py"


def _start(ws):
    ws.skill("create-e2e-tests")
    started = ws.acs("step", "start", "--step", "create-e2e-tests", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _count(ws):
    return int(ws.sh("python3 -c \"import sys; sys.path.insert(0, sys.argv[1]); import acs_lib; "
                     "print(acs_lib.e2e_case_count(sys.argv[2]))\" '%s' '%s'" % (SCRIPTS, CASES)))


def _finish(ws, outcome, states=None):
    doc = {"status": "completed", "outcome": outcome,
           "summary": "the case document types no case e2e; nothing to write",
           "states": states or {"suites_written": [], "cases_covered": []},
           "findings": [], "errors": []}
    ws.sh("python3 '%s/post-create-e2e-tests.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(doc)))


REPLY = ("## /acs:create-e2e-tests · EVAL-1 · completed\n\n- **Status**: completed — "
         "no_e2e_owed: test-cases.md types no case e2e (0 e2e cases), nothing written\n"
         "- **Next**: re-run `/acs:create-test-docs EVAL-1` if the ticket needs e2e coverage")

GOOD_SUITE = ('import json\nimport unittest\n\nfrom harness import get\n\n\n'
              'class PageCapE2E(unittest.TestCase):\n    def test_tc_1(self):\n'
              '        """TC-1"""\n        status, _, body = get("/customers", "limit=500")\n'
              '        self.assertEqual(json.loads(body)["limit"], 100)\n')


def IDEAL(ws):
    _start(ws)
    assert _count(ws) == 0
    _finish(ws, "no_e2e_owed")
    ws.reply = REPLY


def _wrote_one_anyway(ws):
    _start(ws)
    ws.write(SUITE, GOOD_SUITE)
    ws.sh("git add -- %s && git commit -qm 'EVAL-1 e2e suite for the page cap' -- %s"
          % (SUITE, SUITE))
    _finish(ws, "tests_written", {"suites_written": [SUITE], "cases_covered": ["TC-1"]})
    ws.reply = "Wrote %s covering TC-1." % SUITE


def _retyped_a_case(ws):
    _start(ws)
    with open(os.path.join(ws.path, CASES), encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace("e2e_cases: 0", "e2e_cases: 1").replace("| TC-1 | AC-1 | unit |",
                                                                "| TC-1 | AC-1 | e2e |")
    ws.write(CASES, text)
    _finish(ws, "no_e2e_owed")
    ws.reply = REPLY


def _never_finished(ws):
    _start(ws)
    ws.reply = REPLY


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("create-e2e-tests"),
    "wrote and committed a suite anyway": _wrote_one_anyway,
    "retyped a unit case e2e": _retyped_a_case,
    "never finished the step": _never_finished,
}
