"""Calibration plays for update-offline (see
tests/evals/check_grader_calibration.py). IDEAL is the skill's offline path:
read the installed version, fail both release lookups, report `failed` with
the manual commands, write nothing."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _installed():
    with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
        return json.load(fh)["version"]


def IDEAL(ws):
    ws.skill("update")
    ws.reply = (
        "Installed acs %s. The latest release could not be determined: `gh release list` "
        "is unauthenticated and raw.githubusercontent.com is unreachable.\n\n"
        "Run these yourself when online:\n\n"
        "    claude plugin marketplace update gms-marketplace\n"
        "    claude plugin list\n\n"
        "## /acs:update · failed\n\n"
        "- **Scope**: installed %s -> latest unknown (marketplace gms-marketplace)\n"
        "- **Status**: failed — version check unavailable (offline)\n"
        "- **Artifacts**: none (this skill writes nothing)\n" % (_installed(), _installed()))


BAD = {
    "claimed up to date without checking": lambda ws: (
        ws.skill("update"),
        setattr(ws, "reply", "## /acs:update · completed\n\nacs %s is up to date. If you want to "
                             "refresh anyway: claude plugin marketplace update gms-marketplace"
                % _installed())),
    "left an update record behind": lambda ws: (
        IDEAL(ws), ws.write(".acs/update-check.json", '{"latest": null}\n')),
    "said it failed but gave no way forward": lambda ws: (
        ws.skill("update"),
        setattr(ws, "reply", "## /acs:update · failed\n\nCould not reach GitHub.")),
}
