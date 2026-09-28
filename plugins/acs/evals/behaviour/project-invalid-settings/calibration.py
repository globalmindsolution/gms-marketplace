"""Calibration plays for project-invalid-settings (see
tests/evals/check_grader_calibration.py). IDEAL is /acs:project's Start as
written: the settings validation exits 2, the error is relayed verbatim, and
nothing is dispatched."""

import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
START = """
import json, os, sys
sys.path.insert(0, os.path.join(%r, "hooks", "scripts"))
import acs_lib as lib
cwd = os.getcwd()
settings, _sources = lib.load_settings(cwd)
try:
    lib.validate_settings(settings, cwd)
except lib.GateError as exc:
    sys.stderr.write("acs project: %%s\\n" %% exc)
    sys.exit(2)
""" % PLUGIN


def _start(ws):
    done = subprocess.run([sys.executable, "-c", START], cwd=ws.path, env=ws.env,
                          capture_output=True, text=True)
    assert done.returncode == 2, (done.returncode, done.stderr)
    return done.stderr.strip()


def IDEAL(ws):
    ws.skill("project")
    error = _start(ws)
    ws.reply = ("Mode detection stopped before choosing a leg:\n\n    %s\n\n"
                "Fix `merge_strategy` in .acs/settings.json (or remove it to use the default), "
                "then re-run /acs:project.\n\n## /acs:project · failed\n\n"
                "- **Mode**: not decided — settings invalid\n" % error)


def _fixed_and_dispatched(ws):
    ws.skill("project")
    ws.write(".acs/settings.json", '{\n  "ticket_prefix": "EVAL",\n  "merge_strategy": "squash"\n}\n')
    ws.skill("standardize-project")
    start = ws.acs("step", "start", "--step", "standardize-project", "--allocate", "--args", "",
                   stdin="")
    assert start.returncode == 0, start.stderr
    ws.reply = "Fixed merge_strategy (fast-forward is not valid; squash is) and standardized."


BAD = {
    "fixed the user's settings and dispatched the leg": _fixed_and_dispatched,
    "stopped without saying what the error was": lambda ws: (
        ws.skill("project"), _start(ws), setattr(ws, "reply", "/acs:project failed.")),
    "deleted the settings file to get past validation": lambda ws: (
        ws.skill("project"), ws.sh("rm .acs/settings.json"),
        setattr(ws, "reply", "merge_strategy was invalid (not squash|merge|rebase); removed it.")),
}
