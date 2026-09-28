"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:run-e2e-tests does, through its real writers: the run
opened on the prompt (in a session the Skill call's PreToolUse gate does this),
`acs.py step start`, each configured suite run verbatim, the results artifact,
and the regression ticket minted by `new-ticket.py`.

It does NOT call `post-run-e2e-tests.py`: measured 2026-09-28, the post-hook
refuses every result document for a FAILED run -- the skill's outcome
vocabulary is passed | no_harness | nothing_to_run, none describes a failure,
and `validate_result` demands an outcome from a multi-outcome skill whatever the
status. No grader here depends on the step being finalized.
"""

import json
import os
import subprocess
import time

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
REPO = ".acs/state-machine/example-shop"
KEY = "e2e:test_customers_e2e.customerse2e.test_customers_default_page_is_50"


def _settings(ws):
    with open(os.path.join(ws.path, ".acs", "settings.json"), encoding="utf-8") as fh:
        return json.load(fh)["suites"]


def _run_suites(ws, names):
    out = []
    for name in names:
        command = _settings(ws)[name]["command"]
        start = time.time()
        done = subprocess.run(["bash", "-c", command], cwd=ws.path, env=ws.env,
                              capture_output=True, text=True)
        entry = {"name": name, "command": command, "exit_code": done.returncode,
                 "duration_s": round(time.time() - start, 3),
                 "status": "pass" if done.returncode == 0 else "fail"}
        if done.returncode:
            entry["failure_output"] = (done.stdout + done.stderr)[-4000:]
        out.append(entry)
    return out


def _start(ws):
    ws.skill("run-e2e-tests")
    assert ws.acs("run", "new", "--prompt", "run every configured suite").returncode == 0
    started = ws.acs("step", "start", "--step", "run-e2e-tests")
    assert started.returncode == 0, started.stderr


def _mint(ws, key, run_id):
    done = subprocess.run(
        ["python3", os.path.join(SCRIPTS, "new-ticket.py"), "--title", "%s regression" % key,
         "--type", "task", "--description",
         "acs-regression-key: %s\n\nGET /customers defaults to limit 20; the e2e case "
         "expects 50.\n\nResults: %s/test-runs/%s/results.json" % (key, REPO, run_id)],
        cwd=ws.path, env=ws.env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)["ticket_id"]


def _results(ws, run_id, suites, regressions):
    ws.write("%s/test-runs/%s/results.json" % (REPO, run_id), json.dumps(
        {"run_id": run_id, "started_at": "2026-09-28T12:00:00Z",
         "ended_at": "2026-09-28T12:00:01Z", "suites": suites,
         "regressions": regressions}, indent=2))


RUN_ID = "run-20260928T120000Z"


def IDEAL(ws):
    _start(ws)
    suites = _run_suites(ws, ["unit", "e2e"])
    assert [s["status"] for s in suites] == ["pass", "fail"], suites
    _results(ws, RUN_ID, suites, [])
    ticket = _mint(ws, KEY, RUN_ID)
    _results(ws, RUN_ID, suites, [{"key": KEY, "ticket_id": ticket, "action": "minted"}])
    ws.reply = ("## /acs:run-e2e-tests · failed\n\n- **Results**: 1/2 suites passed\n"
                "- **Findings**: 1 regression ticket minted (%s)" % ticket)


def _no_ticket(ws):
    _start(ws)
    _results(ws, RUN_ID, _run_suites(ws, ["unit", "e2e"]), [])
    ws.reply = "1/2 suites passed."


def _suite_fallback(ws):
    _start(ws)
    _results(ws, RUN_ID, _run_suites(ws, ["unit", "e2e"]), [])
    _mint(ws, "e2e:__suite__", RUN_ID)
    ws.reply = "1/2 suites passed."


def _ticket_per_suite(ws):
    _start(ws)
    _results(ws, RUN_ID, _run_suites(ws, ["unit", "e2e"]), [])
    _mint(ws, KEY, RUN_ID)
    _mint(ws, "unit:__suite__", RUN_ID)
    ws.reply = "1/2 suites passed."


def _only_e2e(ws):
    _start(ws)
    _results(ws, RUN_ID, _run_suites(ws, ["e2e"]), [])
    _mint(ws, KEY, RUN_ID)
    ws.reply = "0/1 suites passed."


def _no_artifact(ws):
    _start(ws)
    _run_suites(ws, ["unit", "e2e"])
    subprocess.run(["python3", os.path.join(SCRIPTS, "new-ticket.py"), "--title", "e2e failing",
                    "--type", "task", "--description", "acs-regression-key: %s" % KEY],
                   cwd=ws.path, env=ws.env, capture_output=True, check=True)
    ws.reply = "1/2 suites passed."


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("run-e2e-tests"),
    "recorded the failure but minted no ticket": _no_ticket,
    "used the __suite__ fallback for a parseable failure": _suite_fallback,
    "minted a ticket for the passing suite too": _ticket_per_suite,
    "ran only the e2e suite": _only_e2e,
    "minted a ticket but wrote no results artifact": _no_artifact,
}
