"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:create-e2e-tests does with no e2e suite configured and no
harness in the repo, through its real writers: `acs.py step start`, the open
question recorded in the clarification ledger (`clarify.py add` without an
answer), and `post-create-e2e-tests.py` fed an `interrupted` / `needs_input`
result on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
SUITE = "tests/e2e/test_eval_1_customer_listing.py"
QUESTION = ("This repo configures no e2e suite and has no e2e harness: which harness and "
            "command should run the e2e suites, and where should they live?")


def _start(ws):
    ws.skill("create-e2e-tests")
    started = ws.acs("step", "start", "--step", "create-e2e-tests", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _finish(ws, doc):
    doc = dict({"summary": "no e2e suite configured and no harness in the repo",
                "states": {"suites_written": [], "cases_covered": []},
                "findings": [], "errors": []}, **doc)
    ws.sh("python3 '%s/post-create-e2e-tests.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(doc)))


def IDEAL(ws):
    _start(ws)
    ws.sh("python3 '%s/clarify.py' add --skill create-e2e-tests --ticket EVAL-1 "
          "--question '%s' > /dev/null" % (SCRIPTS, QUESTION))
    _finish(ws, {"status": "interrupted", "stop_reason": "needs_input"})
    ws.reply = ("## /acs:create-e2e-tests · EVAL-1 · interrupted\n\n- **Status**: interrupted — "
                "needs_input: no e2e harness\n- **Findings**: open question C-1 — %s" % QUESTION)


GOOD_SUITE = ('import json\nimport unittest\n\nfrom shop.web import app\n\n\n'
              'class CustomerListingE2E(unittest.TestCase):\n    def test_tc_1(self):\n'
              '        """TC-1"""\n        self.assertTrue(app)\n')


def _invented_a_harness(ws):
    _start(ws)
    ws.write(".acs/settings.json", json.dumps({"ticket_prefix": "EVAL", "suites": {"e2e": {
        "command": "PYTHONPATH=src python3 -m unittest discover -s tests/e2e"}}}, indent=2))
    ws.write(SUITE, GOOD_SUITE)
    ws.sh("git add -- %s && git commit -qm 'EVAL-1 e2e suite' -- %s" % (SUITE, SUITE))
    _finish(ws, {"status": "completed", "outcome": "tests_written",
                 "states": {"suites_written": [SUITE], "cases_covered": ["TC-1", "TC-2"]}})
    ws.reply = "Wrote %s and configured suites.e2e." % SUITE


def _wrote_uncommitted(ws):
    _start(ws)
    ws.write(SUITE, GOOD_SUITE)
    _finish(ws, {"status": "interrupted", "stop_reason": "needs_input"})
    ws.reply = "Which harness should run the e2e suites?"


def _failed(ws):
    _start(ws)
    _finish(ws, {"status": "failed"})
    ws.reply = "No e2e suite is configured; failing. Which harness should run it?"


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("create-e2e-tests"),
    "invented a harness and wrote a suite": _invented_a_harness,
    "left an uncommitted suite behind": _wrote_uncommitted,
    "finished failed instead of needs_input": _failed,
}
