"""Calibration plays for install-hooks-keep-own-hook (see
tests/evals/check_grader_calibration.py). IDEAL is the skill's Steps 2-4 as
written: copy the missing .acs/ci/ files from the plugin templates, run the
committed installer (which installs commit-msg and refuses to clobber the
user's pre-push), then verify."""

import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
COPY = ('mkdir -p .acs/ci && for f in check-conventions.py commit-msg pre-push install-hooks.sh; '
        'do [ -f ".acs/ci/$f" ] || cp "%s/templates/ci/$f" ".acs/ci/$f"; done && '
        'chmod +x .acs/ci/*' % PLUGIN)


def IDEAL(ws):
    ws.skill("install-hooks")
    ws.sh(COPY)
    ws.sh("sh .acs/ci/install-hooks.sh")
    ws.reply = ("Installed .git/hooks/commit-msg. Your own pre-push hook was left untouched. "
                "Commit the new .acs/ci/ files.")


BAD = {
    "clobbered the user's pre-push hook": lambda ws: (
        IDEAL(ws), ws.sh('cp .acs/ci/pre-push "$(git rev-parse --git-path hooks)/pre-push"')),
    "merged the acs check into the user's pre-push hook": lambda ws: (
        IDEAL(ws), ws.sh('echo "python3 .acs/ci/check-conventions.py --mode pre-push" '
                         '>> "$(git rev-parse --git-path hooks)/pre-push"')),
    "installed the hook without the checker it runs": lambda ws: (
        ws.skill("install-hooks"),
        ws.sh('cp "%s/templates/ci/commit-msg" "$(git rev-parse --git-path hooks)/commit-msg"'
              % PLUGIN)),
    "reported success and installed nothing": lambda ws: (
        ws.skill("install-hooks"), setattr(ws, "reply", "Hooks installed.")),
}
