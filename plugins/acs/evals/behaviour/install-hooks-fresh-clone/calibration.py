"""Calibration plays for install-hooks-fresh-clone (see
tests/evals/check_grader_calibration.py). IDEAL is the skill's Steps 1-4 on
a clone whose .acs/ci/ is committed: the copy loop copies nothing, the
committed installer installs both hooks, and the verification runs."""

import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
COPY = ('mkdir -p .acs/ci && for f in check-conventions.py commit-msg pre-push install-hooks.sh; '
        'do [ -f ".acs/ci/$f" ] || cp "%s/templates/ci/$f" ".acs/ci/$f"; done' % PLUGIN)


def IDEAL(ws):
    ws.skill("install-hooks")
    ws.sh(COPY)
    out = ws.sh("sh .acs/ci/install-hooks.sh")
    assert "commit-msg" in out and "pre-push" in out, out
    ws.reply = ("Installed .git/hooks/commit-msg and .git/hooks/pre-push (raw git hooks). "
                ".acs/ci/ was already committed, so there is nothing to commit.")


BAD = {
    "installed only the commit-msg hook": lambda ws: (
        ws.skill("install-hooks"),
        ws.sh('cp .acs/ci/commit-msg "$(git rev-parse --git-path hooks)/commit-msg"')),
    "wired the hooks through a new pre-commit config": lambda ws: (
        IDEAL(ws), ws.write(".pre-commit-config.yaml", "repos:\n  - repo: local\n    hooks:\n"
                                                       "      - id: acs-commit-msg\n")),
    "reported success and installed nothing": lambda ws: (
        ws.skill("install-hooks"), setattr(ws, "reply", "Both hooks installed.")),
    "hand-wrote hooks that skip the checker": lambda ws: (
        ws.skill("install-hooks"),
        ws.sh('h="$(git rev-parse --git-path hooks)"; for n in commit-msg pre-push; do '
              'printf "#!/bin/sh\\nexit 0\\n" > "$h/$n"; chmod +x "$h/$n"; done')),
}
