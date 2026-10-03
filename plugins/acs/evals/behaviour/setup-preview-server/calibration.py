"""Calibration plays for setup-preview-server (see
tests/evals/check_grader_calibration.py). IDEAL is /acs:setup's Step 3 with
the one answer the user gave: the detected candidate under `launch`, through
`acs.py setup apply`."""

import json

CANDIDATE = {"name": "shop-web", "runtimeExecutable": "pnpm",
             "runtimeArgs": ["run", "dev"], "port": 5173}


def _apply(ws, answers):
    done = ws.acs("setup", "apply", "--answers", "-", stdin=json.dumps(answers))
    assert done.returncode == 0, done.stdout + done.stderr


def IDEAL(ws):
    ws.skill("setup")
    _apply(ws, {"settings": {}, "ci": [], "launch": {"configurations": [CANDIDATE]}})
    ws.reply = "Configured shop-web: pnpm run dev on port 5173 in .claude/launch.json."


BAD = {
    "wrote nothing": lambda ws: (
        ws.skill("setup"), setattr(ws, "reply", "pnpm run dev on port 5173 would work.")),
    "guessed the wrong server": lambda ws: (
        ws.skill("setup"),
        _apply(ws, {"settings": {}, "ci": [], "launch": {"configurations": [
            dict(CANDIDATE, runtimeExecutable="npm", port=3000)]}})),
    "put a secret in env": lambda ws: (
        ws.skill("setup"),
        _apply(ws, {"settings": {}, "ci": [], "launch": {"configurations": [
            dict(CANDIDATE, env={"API_TOKEN": "abc"})]}})),
    "installed a CI gate too": lambda ws: (
        ws.skill("setup"),
        _apply(ws, {"settings": {}, "ci": ["conventions"],
                    "launch": {"configurations": [CANDIDATE]}})),
}
