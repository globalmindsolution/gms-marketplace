"""Calibration plays for create-api-contract-type-disabled (see
tests/evals/check_grader_calibration.py).

The repo, the ticket and the documents are create-api-contract-cursor-
pagination's, so the bad plays reuse that case's calibration (loaded by path,
without bytecode). The one difference is the setting: design.lld_types drops
`api-contract`, so IDEAL starts the step, finds the type disabled, and
finishes it through the real post-hook with outcome type_disabled, empty
states and nothing written (ADR-0134).
"""

import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract"


def _cursor_case():
    path = os.path.join(HERE, "..", "create-api-contract-cursor-pagination", "calibration.py")
    spec = importlib.util.spec_from_file_location("calibration_cursor_for_type_disabled", path)
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


CURSOR = _cursor_case()


def _start(ws):
    ws.skill("create-api-contract")
    started = ws.acs("step", "start", "--step", "create-api-contract", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    lld = json.loads(started.stdout)["settings"]["design"]["lld_types"]
    assert "api-contract" not in lld, lld


def _finish(ws, outcome="type_disabled"):
    result = {"status": "completed", "outcome": outcome,
              "summary": "the api-contract type is not enabled in design.lld_types",
              "states": {"feature": [], "files": [], "types": [], "interfaces": [],
                         "items": 0, "traced_acs": [],
                         "gaps": {"undocumented": 0, "unimplemented": 0, "drifted": 0}},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result, indent=2))
    done = subprocess.run([sys.executable, os.path.join(SCRIPTS, "post-create-api-contract.py"),
                           "--result-file", STEP + "/result.json"],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _start(ws)
    _finish(ws)
    ws.reply = ("## /acs:create-api-contract · EVAL-1 · completed\n\n- **Status**: completed "
                "-- the api-contract type is not enabled in design.lld_types, so nothing was "
                "written (outcome type_disabled).")


def _designed_anyway(ws):
    """Ignored the setting and ran the whole design."""
    CURSOR.IDEAL(ws)


def _re_enabled_the_type(ws):
    """'Fixed' the setting so it had something to do."""
    path = os.path.join(ws.path, ".acs", "settings.json")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    ws.write(".acs/settings.json", text.replace('["logical-erd"', '["api-contract", "logical-erd"'))
    CURSOR.IDEAL(ws)


def _recorded_contract_written(ws):
    """Wrote nothing, but claimed a written contract."""
    _start(ws)
    _finish(ws, outcome="contract_written")


def _never_finished(ws):
    _start(ws)


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("create-api-contract"),
    "designed the interface although the type is disabled": _designed_anyway,
    "re-enabled the type in the settings": _re_enabled_the_type,
    "recorded contract_written for a no-op": _recorded_contract_written,
    "never ran the post-hook": _never_finished,
}
