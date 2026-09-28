"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:run-e2e-tests does when the run set resolves to {}:
`acs.py step start` on the ticket's run, the empty-arrays results artifact, and
`post-run-e2e-tests.py` fed a `completed` / `no_harness` result on stdin.
"""

import json
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
REPO = ".acs/state-machine/example-shop"
RUN_ID = "run-20260928T120000Z"


def _start(ws):
    ws.skill("run-e2e-tests")
    started = ws.acs("step", "start", "--step", "run-e2e-tests", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _results(ws, suites=()):
    ws.write("%s/test-runs/%s/results.json" % (REPO, RUN_ID), json.dumps(
        {"run_id": RUN_ID, "started_at": "2026-09-28T12:00:00Z",
         "ended_at": "2026-09-28T12:00:00Z", "suites": list(suites), "regressions": []},
        indent=2))


def _finish(ws, status, outcome=None):
    doc = {"status": status, "summary": "no suites configured, nothing to run",
           "findings": [], "errors": []}
    if outcome:
        doc["outcome"] = outcome
    ws.sh("python3 '%s/post-run-e2e-tests.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(doc)))


REPLY = ("## /acs:run-e2e-tests · completed\n\n- **Run**: %s, 0 suites run\n"
         "- **Status**: completed — no suites configured, nothing to run (no_harness)\n"
         "- **Results**: 0/0 suites passed" % RUN_ID)


def IDEAL(ws):
    _start(ws)
    _results(ws)
    _finish(ws, "completed", "no_harness")
    ws.reply = REPLY


def _failed(ws):
    _start(ws)
    _results(ws)
    _finish(ws, "failed")
    ws.reply = REPLY


def _configured_a_suite(ws):
    _start(ws)
    ws.write(".acs/settings.json", json.dumps({
        "ticket_prefix": "EVAL",
        "suites": {"unit": {"command": "PYTHONPATH=src python3 -m pytest -q"}}}, indent=2))
    cmd = "PYTHONPATH=src python3 -m pytest -q"
    _results(ws, [{"name": "unit", "command": cmd, "exit_code": 0, "duration_s": 0.1,
                   "status": "pass"}])
    _finish(ws, "completed", "passed")
    ws.reply = "1/1 suites passed."


def _wrote_a_suite(ws):
    _start(ws)
    ws.write("tests/e2e/test_smoke.py", "def test_ok():\n    assert True\n")
    _results(ws)
    _finish(ws, "completed", "no_harness")
    ws.reply = REPLY


def _no_artifact(ws):
    _start(ws)
    _finish(ws, "completed", "no_harness")
    ws.reply = REPLY


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("run-e2e-tests"),
    "finished the step failed": _failed,
    "configured a suite to have something to run": _configured_a_suite,
    "wrote a suite of its own": _wrote_a_suite,
    "wrote no results artifact": _no_artifact,
}
