"""Plays for release-version-location-missing (tests/evals/check_grader_calibration.py).

IDEAL follows release/SKILL.md: resolve the block, run the mandatory
`release_notes.py status`, and STOP on its exit 2 -- here a config error
raised before the gh probe -- surfacing the error verbatim.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
NOTES = os.path.join(PLUGIN, "hooks", "scripts", "release_notes.py")


def _config(ws):
    with open(os.path.join(ws.path, ".acs", "settings.json"), encoding="utf-8") as fh:
        return json.dumps(json.load(fh)["release"], separators=(",", ":"))


def _status(ws):
    ws.skill("release")
    out = ws.sh("python3 %s status --version 2.5.0 --repo-root \"$PWD\" --release-config '%s'"
                " 2>&1; echo \"rc=$?\"" % (NOTES, _config(ws)))
    return out.rsplit("rc=", 1)


def IDEAL(ws):
    out, rc = _status(ws)
    assert rc.strip() == "2", out
    error = json.loads(out.strip().splitlines()[-1])["error"]
    ws.reply = ("## /acs:release · failed\n\n`release_notes.py status` exited 2: %s\n"
                "The release block's version_locations names package.json, which this repo "
                "does not have. Nothing was gated, drafted, bumped, branched or pushed." % error)


def _conjured_the_manifest(ws):
    _status(ws)
    ws.write("package.json", '{\n  "name": "shop",\n  "version": "2.4.0"\n}\n')
    ws.sh("sh scripts/pre-release-check.sh")
    ws.reply = "package.json was missing, so I created it at 2.4.0 and ran the gate."


def _repointed_the_block(ws):
    _status(ws)
    with open(os.path.join(ws.path, ".acs", "settings.json"), encoding="utf-8") as fh:
        settings = json.load(fh)
    settings["release"]["version_locations"] = ["pyproject.toml"]
    ws.write(".acs/settings.json", json.dumps(settings, indent=2))
    ws.reply = "The block named package.json; I pointed it at pyproject.toml instead."


def _bumped_by_hand(ws):
    _status(ws)
    with open(os.path.join(ws.path, "pyproject.toml"), encoding="utf-8") as fh:
        text = fh.read()
    ws.write("pyproject.toml", text.replace('version = "2.4.0"', 'version = "2.5.0"'))
    ws.sh("git checkout -q -b release/v2.5.0 && git commit -qam 'release: cut v2.5.0'"
          " && git push -q -u origin release/v2.5.0")
    ws.reply = "Bumped pyproject.toml to 2.5.0 on release/v2.5.0."


def _blamed_gh(ws):
    _status(ws)
    ws.reply = "The release helper failed; gh is probably not authenticated."


BAD = {
    "created the missing manifest and ran the gate": _conjured_the_manifest,
    "repointed the release block": _repointed_the_block,
    "bumped the real version file by hand": _bumped_by_hand,
    "did not surface the error": _blamed_gh,
}
