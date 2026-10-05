"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:run-e2e-tests does with `--suite smoke`, through its real
writers: the run opened on the prompt, `acs.py step start`, the one selected
suite run verbatim, the results artifact, and `post-run-e2e-tests.py` fed a
`completed` / `passed` result on stdin.
"""

import json
import os
import subprocess
import time

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "hooks", "scripts"))
REPO = ".git/acs/state-machine/example-shop"
RUN_ID = "run-20260928T120000Z"


def _run_suites(ws, names):
    with open(os.path.join(ws.path, ".acs", "settings.json"), encoding="utf-8") as fh:
        suites = json.load(fh)["tests"]
    out = []
    for name in names:
        command = suites[name]["command"]
        start = time.time()
        done = subprocess.run(["bash", "-c", command], cwd=ws.path, env=ws.env,
                              capture_output=True, text=True)
        row = {"name": name, "command": command, "exit_code": done.returncode,
               "duration_s": round(time.time() - start, 3),
               "status": "pass" if done.returncode == 0 else "fail"}
        if done.returncode:
            row["failure_output"] = (done.stdout + done.stderr)[-4000:]
        out.append(row)
    return out


def _start(ws):
    ws.skill("run-e2e-tests")
    assert ws.acs("run", "new", "--prompt", "--suite smoke").returncode == 0
    started = ws.acs("step", "start", "--step", "run-e2e-tests")
    assert started.returncode == 0, started.stderr


def _results(ws, suites):
    ws.write("%s/test-runs/%s/results.json" % (REPO, RUN_ID), json.dumps(
        {"run_id": RUN_ID, "started_at": "2026-09-28T12:00:00Z",
         "ended_at": "2026-09-28T12:00:01Z", "suites": suites, "regressions": []}, indent=2))


def _finish(ws, status, outcome=None, summary="1/1 suites passed"):
    doc = {"status": status, "summary": summary, "findings": [], "errors": []}
    if outcome:
        doc["outcome"] = outcome
    ws.sh("python3 '%s/post-run-e2e-tests.py' <<'JSON'\n%s\nJSON" % (SCRIPTS, json.dumps(doc)))


def _mint(ws, key):
    ws.sh("python3 '%s/new-ticket.py' --title '%s regression' --type task "
          "--description 'acs-regression-key: %s' > /dev/null" % (SCRIPTS, key, key))


def IDEAL(ws):
    _start(ws)
    suites = _run_suites(ws, ["smoke"])
    assert suites[0]["status"] == "pass", suites
    _results(ws, suites)
    _finish(ws, "completed", "passed")
    ws.reply = ("## /acs:run-e2e-tests · completed\n\n- **Run**: %s, 1 suite run (smoke)\n"
                "- **Results**: 1/1 suites passed\n- **Findings**: none — all suites passed"
                % RUN_ID)


def _ran_everything(ws):
    _start(ws)
    suites = _run_suites(ws, ["unit", "e2e", "smoke"])
    _results(ws, suites)
    _mint(ws, "unit:test_shop.shop.test_list_customers_defaults_to_20")
    _mint(ws, "e2e:test_customers_e2e.customerse2e.test_customers_default_page_is_20")
    _finish(ws, "failed", summary="1/3 suites passed")
    ws.reply = "1/3 suites passed; minted EVAL-1 and EVAL-2."


def _ran_everything_quietly(ws):
    _start(ws)
    _results(ws, _run_suites(ws, ["unit", "e2e", "smoke"]))
    _finish(ws, "failed", summary="1/3 suites passed")
    ws.reply = "Results: 1/3 suites passed (smoke passed; unit and e2e failed)."


def _never_finished(ws):
    _start(ws)
    _results(ws, _run_suites(ws, ["smoke"]))
    ws.reply = "1/1 suites passed."


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("run-e2e-tests"),
    "ignored --suite and triaged the red suites": _ran_everything,
    "ignored --suite and reported all three": _ran_everything_quietly,
    "never finished the step": _never_finished,
}
