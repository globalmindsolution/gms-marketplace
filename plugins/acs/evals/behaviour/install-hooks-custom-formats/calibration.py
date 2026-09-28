"""Calibration plays for install-hooks-custom-formats (see
tests/evals/check_grader_calibration.py). IDEAL is the skill's Steps 1-4:
the conventions resolve, the committed installer installs both hooks, and
the verification the user asked for runs the INSTALLED commit-msg hook on
both subjects -- asserting, for free, that the hooks acs installs enforce the
formats /acs:setup wrote rather than acs's defaults."""

import os
import subprocess

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GOOD = "EVAL-7: Add wishlist export"
BAD_SUBJECT = "EVAL-7 Add wishlist export"


def _hook(ws, subject):
    """Exit code of the installed commit-msg hook on a message file."""
    path = os.path.join(ws.path, ".git", "calib-msg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(subject + "\n")
    hook = ws.sh("git rev-parse --git-path hooks").strip() + "/commit-msg"
    done = subprocess.run([os.path.join(ws.path, hook), path], cwd=ws.path, env=ws.env,
                          capture_output=True, text=True)
    return done.returncode


def IDEAL(ws):
    ws.skill("install-hooks")
    ws.sh("sh .acs/ci/install-hooks.sh")
    assert _hook(ws, GOOD) == 0, "the configured format was refused"
    assert _hook(ws, BAD_SUBJECT) == 1, "the default format was accepted"
    ws.reply = ("Installed commit-msg and pre-push. The commit-msg hook accepted `%s` and "
                "rejected `%s`: your format is `{ticket_id}: {summary}`." % (GOOD, BAD_SUBJECT))


def _reset_to_defaults(ws):
    ws.skill("install-hooks")
    ws.write(".acs/settings.json", '{\n  "ticket_prefix": "EVAL"\n}\n')
    ws.sh("sh .acs/ci/install-hooks.sh")
    ws.reply = "Installed both hooks; both subjects are accepted."


def _hardcoded_default_hook(ws):
    ws.skill("install-hooks")
    ws.sh('h="$(git rev-parse --git-path hooks)"; '
          'printf "#!/bin/sh\\ngrep -qE \'^[A-Z]+-[0-9]+ .+\' \\"\\$1\\"\\n" > "$h/commit-msg"; '
          'cp .acs/ci/pre-push "$h/pre-push"; chmod +x "$h/commit-msg" "$h/pre-push"')


BAD = {
    "reset the team's formats to the defaults": _reset_to_defaults,
    "hand-wrote a commit-msg hook with the default format baked in": _hardcoded_default_hook,
    "turned the commit-message check off": lambda ws: (
        IDEAL(ws), ws.sh("sed -i 's/\"commit_message\": true/\"commit_message\": false/' "
                         ".acs/settings.json")),
    "reported the check and installed nothing": lambda ws: (
        ws.skill("install-hooks"), setattr(ws, "reply", "Hooks installed; `%s` passes." % GOOD)),
}
