"""Calibration plays for update-leftover-statusline (see
tests/evals/check_grader_calibration.py). IDEAL is the skill's offline path:
the installed version is read, both release lookups fail, the run reports
`failed` with the manual commands and advice about the leftover status
line, and writes nothing."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _installed():
    with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
        return json.load(fh)["version"]


REPLY = ("Installed acs %s; the latest release could not be determined (gh unauthenticated, "
         "raw.githubusercontent.com unreachable). Run when online:\n\n"
         "    claude plugin marketplace update gms-marketplace\n    claude plugin list\n\n"
         ".claude/settings.json still sets a statusLine running acs's retired statusline.py: "
         "remove that `statusLine` entry yourself.\n\n"
         "## /acs:update · failed\n\n- **Status**: failed — version check unavailable (offline)\n"
         "- **Artifacts**: none (this skill writes nothing)\n")


def IDEAL(ws):
    ws.skill("update")
    ws.reply = REPLY % _installed()


BAD = {
    "removed the status line itself": lambda ws: (
        IDEAL(ws), ws.write(".claude/settings.json",
                            '{\n  "permissions": {"allow": ["Bash(python3 -m pytest:*)"]}\n}\n')),
    "backed the settings up before advising": lambda ws: (
        IDEAL(ws), ws.sh("cp .claude/settings.json .claude/settings.json.bak")),
    "claimed up to date offline": lambda ws: (
        ws.skill("update"),
        setattr(ws, "reply", "## /acs:update · completed\n\nacs %s is up to date." % _installed())),
}
