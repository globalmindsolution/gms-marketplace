"""Calibration plays for setup-retired-keys (see
tests/evals/check_grader_calibration.py). IDEAL is /acs:setup as written:
detect reports `retired_keys`, the reply names them, and the kept defaults
go through `acs.py setup apply` with nothing in `settings` or `ci`."""

import json


def IDEAL(ws):
    ws.skill("setup")
    detected = json.loads(ws.acs("setup", "detect").stdout)
    keys = sorted({k for row in detected["retired_keys"] for k in row["keys"]})
    assert keys == ["prd_path", "workspace_path"], keys
    done = ws.setup_apply({}, [])
    assert done.returncode == 0, done.stdout + done.stderr
    ws.reply = ("Re-run: .acs/settings.json still carries retired keys `workspace_path` and "
                "`prd_path`; acs ignores both (state lives in .acs/state-machine/, documents "
                "are found, not configured). Defaults kept; no CI installed.")


BAD = {
    "never mentioned the retired keys": lambda ws: (
        ws.skill("setup"), ws.setup_apply({}, []),
        setattr(ws, "reply", "Everything is in order: defaults, no CI.")),
    "rewrote the settings file by hand": lambda ws: (
        IDEAL(ws), ws.write(".acs/settings.json", "{}\n")),
    "installed the convention check too": lambda ws: (
        IDEAL(ws), ws.setup_apply({}, ["conventions"])),
}
