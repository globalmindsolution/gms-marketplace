"""Calibration plays for setup-broad-ignore-rule (see
tests/evals/check_grader_calibration.py). IDEAL is /acs:setup as written:
detect reports the swallowed paths, `acs.py setup apply` installs the
conventions and returns the warnings, and the reply relays them without
touching .gitignore."""

import json


def IDEAL(ws):
    ws.skill("setup")
    detected = json.loads(ws.acs("setup", "detect").stdout)
    assert ".acs/ci/check-conventions.py" in detected["swallowed_by_a_broad_rule"], detected
    done = ws.setup_apply({}, ["conventions"])
    result = json.loads(done.stdout)
    assert result["ok"] and result["warnings"], result
    ws.reply = ("Installed the convention check. Warning: your .gitignore rule `.acs/` hides "
                ".acs/ci/check-conventions.py and .acs/settings.json, so CI cannot read them -- "
                "add `!.acs/` or narrow the rule. Stage .acs/ci/ and "
                ".github/workflows/acs-conventions.yml. Required check: Branch / PR / commit "
                "conventions.")


BAD = {
    "fixed the ignore rule for the user": lambda ws: (
        IDEAL(ws), ws.write(".gitignore", "!.acs/\n", append=True)),
    "narrowed the rule to the state directory": lambda ws: (
        IDEAL(ws), ws.write(".gitignore", ".acs/state-machine/\n.acs/settings.local.json\n*.pyc\n")),
    "installed and said nothing about the rule": lambda ws: (
        ws.skill("setup"), ws.setup_apply({}, ["conventions"]),
        setattr(ws, "reply", "Installed the convention check. Stage .acs/ci/ and the workflow.")),
    "refused to install because of the rule": lambda ws: (
        ws.skill("setup"),
        setattr(ws, "reply", "Your .gitignore ignores .acs/, so I did not install the check.")),
}
