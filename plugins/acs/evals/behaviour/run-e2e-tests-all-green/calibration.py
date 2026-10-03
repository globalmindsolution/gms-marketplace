"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:run-e2e-tests does on an all-green run, through its real
writers: `acs.py step start` on the ticket's run (in a session the Skill call's
PreToolUse gate opens it from the argument), each configured suite run
verbatim, the results artifact with an empty `regressions`, and
`post-run-e2e-tests.py` fed the result document on stdin.
"""

import json
import os
import subprocess
import time

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
REPO = ".acs/state-machine/example-shop"
RUN_ID = "run-20260928T120000Z"


def _run_suites(ws):
    with open(os.path.join(ws.path, ".acs", "settings.json"), encoding="utf-8") as fh:
        suites = json.load(fh)["tests"]
    out = []
    for name, entry in suites.items():
        start = time.time()
        done = subprocess.run(["bash", "-c", entry["command"]], cwd=ws.path, env=ws.env,
                              capture_output=True, text=True)
        out.append({"name": name, "command": entry["command"], "exit_code": done.returncode,
                    "duration_s": round(time.time() - start, 3),
                    "status": "pass" if done.returncode == 0 else "fail"})
    return out


def _start(ws):
    ws.skill("run-e2e-tests")
    started = ws.acs("step", "start", "--step", "run-e2e-tests", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _results(ws, suites, regressions=()):
    ws.write("%s/test-runs/%s/results.json" % (REPO, RUN_ID), json.dumps(
        {"run_id": RUN_ID, "started_at": "2026-09-28T12:00:00Z",
         "ended_at": "2026-09-28T12:00:01Z", "suites": suites,
         "regressions": list(regressions)}, indent=2))


def _finish(ws, status, outcome=None):
    doc = {"status": status, "summary": "2/2 suites passed", "findings": [], "errors": []}
    if outcome:
        doc["outcome"] = outcome
    ws.sh("python3 '%s/post-run-e2e-tests.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(doc)))


REPLY = ("## /acs:run-e2e-tests · completed\n\n- **Run**: %s, 2 suites run\n"
         "- **Results**: 2/2 suites passed\n- **Findings**: none — all suites passed\n"
         "- **Artifacts**: results artifact at test-runs/%s/results.json (left in place)"
         % (RUN_ID, RUN_ID))


def IDEAL(ws):
    _start(ws)
    suites = _run_suites(ws)
    assert [s["status"] for s in suites] == ["pass", "pass"], suites
    _results(ws, suites)
    _finish(ws, "completed", "passed")
    ws.reply = REPLY


def _minted_anyway(ws):
    _start(ws)
    _results(ws, _run_suites(ws))
    ws.sh("python3 '%s/new-ticket.py' --title 'e2e: suite check' --type task "
          "--description 'acs-regression-key: e2e:__suite__' > /dev/null" % SCRIPTS)
    _finish(ws, "completed", "passed")
    ws.reply = REPLY


def _wrong_outcome(ws):
    _start(ws)
    _results(ws, _run_suites(ws))
    _finish(ws, "completed", "nothing_to_run")
    ws.reply = REPLY


def _never_finished(ws):
    _start(ws)
    _results(ws, _run_suites(ws))
    ws.reply = REPLY


def _no_artifact(ws):
    _start(ws)
    _run_suites(ws)
    _finish(ws, "completed", "passed")
    ws.reply = REPLY


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("run-e2e-tests"),
    "minted a regression ticket on a green run": _minted_anyway,
    "recorded nothing_to_run although suites ran": _wrong_outcome,
    "never finished the step": _never_finished,
    "wrote no results artifact": _no_artifact,
    "claimed a pass without the skill": lambda ws: setattr(ws, "reply", "2/2 suites passed."),
}
