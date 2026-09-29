"""Calibration plays for setup-e2e-gate (see
tests/evals/check_grader_calibration.py). IDEAL is /acs:setup's Step 3 with
the one answer the user gave: the e2e install, nothing in `settings`,
through `acs.py setup apply`."""

import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def IDEAL(ws):
    ws.skill("setup")
    done = ws.setup_apply({}, ["e2e"])
    assert done.returncode == 0, done.stdout + done.stderr


BAD = {
    "installed every gate": lambda ws: (
        ws.skill("setup"),
        ws.setup_apply({"tests": {"command": "python3 -m pytest -q --cov=src "
                                             "--cov-fail-under=$ACS_COVERAGE"}},
                       ["conventions", "tests", "e2e"])),
    "copied the workflow without its runner": lambda ws: (
        ws.skill("setup"),
        ws.sh('mkdir -p .github/workflows && cp "%s/templates/ci/acs-e2e.yml" .github/workflows/'
              % PLUGIN)),
    "rewrote the suite while installing the gate": lambda ws: (
        IDEAL(ws), ws.write(".acs/settings.json",
                            '{\n  "ticket_prefix": "EVAL",\n  "e2e": {"command": "pytest e2e"}\n}\n')),
    "described the gate and installed nothing": lambda ws: (
        ws.skill("setup"), setattr(ws, "reply", "Required check: E2E suite.")),
}
