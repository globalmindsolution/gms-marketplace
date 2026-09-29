"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:run-e2e-tests does on this failure, through its real
writers: the run opened on the prompt, `acs.py step start`, both suites run
verbatim, the results artifact, the comment-bump of EVAL-1 through `acs.py
ticket save` (save_ticket + update_index, what Step 4b names), and
`post-run-e2e-tests.py` fed a `failed` result with no outcome.
"""

import json
import os
import subprocess
import time

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
REPO = ".acs/state-machine/example-shop"
RUN_ID = "run-20260928T120000Z"
KEY = "e2e:__suite__"


def _run_suites(ws):
    with open(os.path.join(ws.path, ".acs", "settings.json"), encoding="utf-8") as fh:
        suites = json.load(fh)["suites"]
    out = []
    for name, entry in suites.items():
        start = time.time()
        done = subprocess.run(["bash", "-c", entry["command"]], cwd=ws.path, env=ws.env,
                              capture_output=True, text=True)
        row = {"name": name, "command": entry["command"], "exit_code": done.returncode,
               "duration_s": round(time.time() - start, 3),
               "status": "pass" if done.returncode == 0 else "fail"}
        if done.returncode:
            row["failure_output"] = (done.stdout + done.stderr)[-4000:]
        out.append(row)
    return out


def _start(ws):
    ws.skill("run-e2e-tests")
    assert ws.acs("run", "new", "--prompt", "run every configured suite").returncode == 0
    started = ws.acs("step", "start", "--step", "run-e2e-tests")
    assert started.returncode == 0, started.stderr


def _results(ws, suites, regressions):
    ws.write("%s/test-runs/%s/results.json" % (REPO, RUN_ID), json.dumps(
        {"run_id": RUN_ID, "started_at": "2026-09-28T12:00:00Z",
         "ended_at": "2026-09-28T12:00:01Z", "suites": suites,
         "regressions": regressions}, indent=2))


def _ticket(ws):
    return json.loads(ws.acs("ticket", "show", "--ticket", "EVAL-1").stdout)["ticket"]


def _save(ws, ticket):
    saved = ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-",
                   stdin=json.dumps(ticket))
    assert saved.returncode == 0, saved.stderr


def _bump(ws, suites):
    ticket = _ticket(ws)
    output = [s for s in suites if s["status"] == "fail"][0]["failure_output"]
    ticket["description"] += ("\n\n--- Recurred on %s at 2026-09-28T12:00:01Z ---\n%s\n"
                              "Results: %s/test-runs/%s/results.json"
                              % (RUN_ID, output.strip(), REPO, RUN_ID))
    _save(ws, ticket)


def _finish_failed(ws):
    doc = {"status": "failed", "summary": "1/2 suites passed; e2e failed (e2e:__suite__); "
           "EVAL-1 commented", "findings": [], "errors": []}
    ws.sh("python3 '%s/post-run-e2e-tests.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(doc)))


REPLY = ("## /acs:run-e2e-tests · failed\n\n- **Run**: %s, 2 suites run\n"
         "- **Results**: 1/2 suites passed\n"
         "- **Findings**: 1 regression — e2e:__suite__, existing ticket EVAL-1 commented "
         "(no new ticket)" % RUN_ID)


def IDEAL(ws):
    _start(ws)
    suites = _run_suites(ws)
    assert [s["status"] for s in suites] == ["pass", "fail"], suites
    _results(ws, suites, [])
    _bump(ws, suites)
    _results(ws, suites, [{"key": KEY, "ticket_id": "EVAL-1", "action": "commented"}])
    _finish_failed(ws)
    ws.reply = REPLY


def _minted_duplicate(ws):
    _start(ws)
    suites = _run_suites(ws)
    _results(ws, suites, [])
    ws.sh("python3 '%s/new-ticket.py' --title 'e2e: suite regression' --type task "
          "--description 'acs-regression-key: e2e:__suite__' > /dev/null" % SCRIPTS)
    _finish_failed(ws)
    ws.reply = "1/2 suites passed; minted EVAL-2."


def _replaced_description(ws):
    _start(ws)
    suites = _run_suites(ws)
    _results(ws, suites, [])
    ticket = _ticket(ws)
    ticket["description"] = "acs-regression-key: e2e:__suite__\n\nSeen again on %s." % RUN_ID
    _save(ws, ticket)
    _finish_failed(ws)
    ws.reply = REPLY


def _reopened_as_in_progress(ws):
    _start(ws)
    suites = _run_suites(ws)
    _results(ws, suites, [])
    _bump(ws, suites)
    ticket = _ticket(ws)
    ticket["status"] = "in_progress"
    _save(ws, ticket)
    _finish_failed(ws)
    ws.reply = REPLY


def _recorded_only(ws):
    _start(ws)
    _results(ws, _run_suites(ws), [])
    _finish_failed(ws)
    ws.reply = "1/2 suites passed. The e2e failure is already tracked as EVAL-1, left as is."


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("run-e2e-tests"),
    "minted a duplicate ticket": _minted_duplicate,
    "replaced EVAL-1's description": _replaced_description,
    "moved EVAL-1 to in_progress": _reopened_as_in_progress,
    "recorded the failure but never bumped EVAL-1": _recorded_only,
}
