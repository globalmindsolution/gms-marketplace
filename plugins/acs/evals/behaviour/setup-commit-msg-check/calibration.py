"""Calibration plays for setup-commit-msg-check (see
tests/evals/check_grader_calibration.py). IDEAL is /acs:setup's Step 3 with
the user's answers: only the non-default toggle in `settings`, the
conventions install in `ci`, through `acs.py setup apply`."""

TOGGLE = {"enforcement": {"checks": {"commit_message": True}}}


def IDEAL(ws):
    ws.skill("setup")
    done = ws.setup_apply(TOGGLE, ["conventions"])
    assert done.returncode == 0, done.stdout + done.stderr


BAD = {
    "installed the check but left the commit-message check off": lambda ws: (
        ws.skill("setup"), ws.setup_apply({}, ["conventions"])),
    "wrote the default formats out explicitly by hand": lambda ws: (
        IDEAL(ws), ws.write(".acs/settings.json",
                            '{\n  "formats": {"branch_name": "{type}/{ticket_id}-{slug}"},\n'
                            '  "enforcement": {"checks": {"commit_message": true}}\n}\n')),
    "turned the toggle on but installed no CI": lambda ws: (
        ws.skill("setup"), ws.setup_apply(TOGGLE, [])),
    "also installed the tests gate": lambda ws: (
        ws.skill("setup"),
        ws.setup_apply(dict(TOGGLE, tests={"command": "python3 -m pytest -q "
                                                      "--cov=src --cov-fail-under=$ACS_COVERAGE"}),
                       ["conventions", "tests"])),
}
