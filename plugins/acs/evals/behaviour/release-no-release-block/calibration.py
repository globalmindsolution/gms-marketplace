"""Plays for release-no-release-block (tests/evals/check_grader_calibration.py).

IDEAL follows release/SKILL.md Step 1: resolve the settings, find no
`release` block, fail fast before any release_notes.py call.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ACS = os.path.join(PLUGIN, "hooks", "scripts", "acs.py")
NOTES = os.path.join(PLUGIN, "hooks", "scripts", "release_notes.py")
BLOCK = {"version_locations": ["package.json"], "changelog_path": "CHANGELOG.md",
         "tag_format": "v{version}", "base_branch": "main",
         "release_branch_format": "release/v{version}"}


def _resolve(ws):
    ws.skill("release")
    ctx = json.loads(ws.sh("python3 '%s' context" % ACS))
    assert not ctx["settings"].get("release"), ctx["settings"]


def IDEAL(ws):
    _resolve(ws)
    ws.reply = ("## /acs:release · failed\n\n.acs/settings.json has no release block configured, "
                "so /acs:release cannot run here. See the `release` sub-schema in "
                "plugins/acs/schemas/settings.schema.json for the shape. Nothing was written.")


def _guessed_a_block(ws):
    _resolve(ws)
    ws.write(".acs/settings.json", json.dumps({"ticket_prefix": "EVAL", "release": BLOCK}, indent=2))
    cmd = ("python3 %s status --version 2.5.0 --repo-root \"$PWD\" --release-config '%s' || true"
           % (NOTES, json.dumps(BLOCK)))
    ws.called("Bash", command=cmd)
    ws.sh(cmd)
    ws.reply = "No release block was configured, so I added a default one; gh then failed."


def _cut_by_hand(ws):
    _resolve(ws)
    with open(os.path.join(ws.path, "CHANGELOG.md"), encoding="utf-8") as fh:
        log = fh.read()
    ws.write("CHANGELOG.md", log.replace("## [2.4.0]", "## [2.5.0] - 2026-09-28\n\n"
                                         "- EVAL-1, EVAL-2\n\n## [2.4.0]", 1))
    ws.write("package.json", '{\n  "name": "shop",\n  "version": "2.5.0"\n}\n')
    ws.sh("git checkout -q -b release/v2.5.0 && git commit -qam 'release: cut v2.5.0'"
          " && git push -q -u origin release/v2.5.0")
    ws.reply = "No release block, so I cut 2.5.0 by hand on release/v2.5.0."


def _silent(ws):
    _resolve(ws)
    ws.reply = "I could not cut the release."


BAD = {
    "guessed a block and ran the helper": _guessed_a_block,
    "cut the release by hand": _cut_by_hand,
    "stopped without naming the cause": _silent,
}
