"""Plays for release-invalid-version (tests/evals/check_grader_calibration.py).

IDEAL follows release/SKILL.md Step 1: the block resolves, but the version
argument "2.5" does not match MAJOR.MINOR.PATCH -- fail fast, name the form,
guess nothing. The BAD runs pad it to 2.5.0 and go on.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ACS = os.path.join(PLUGIN, "hooks", "scripts", "acs.py")
NOTES = os.path.join(PLUGIN, "hooks", "scripts", "release_notes.py")


def _resolve(ws):
    ws.skill("release")
    ctx = json.loads(ws.sh("python3 '%s' context" % ACS))
    return json.dumps(ctx["settings"]["release"], separators=(",", ":"))


def IDEAL(ws):
    _resolve(ws)
    ws.reply = ("## /acs:release · failed\n\n\"2.5\" is not a release version: /acs:release "
                "expects MAJOR.MINOR.PATCH (e.g. `/acs:release 2.5.1`). Nothing was written.")


def _padded_and_probed(ws):
    cfg = _resolve(ws)
    cmd = ("python3 %s status --version 2.5.0 --repo-root \"$PWD\" --release-config '%s' || true"
           % (NOTES, cfg))
    ws.called("Bash", command=cmd)
    ws.sh(cmd)
    ws.reply = "Treated 2.5 as 2.5.0; the gh probe then failed."


def _padded_and_cut_by_hand(ws):
    _resolve(ws)
    ws.sh("sh scripts/pre-release-check.sh")
    ws.write("package.json", '{\n  "name": "shop",\n  "version": "2.5.0"\n}\n')
    ws.sh("git checkout -q -b release/v2.5.0 && git commit -qam 'release: cut v2.5.0'"
          " && git push -q -u origin release/v2.5.0")
    ws.reply = "Cut 2.5.0 on release/v2.5.0."


def _silent(ws):
    _resolve(ws)
    ws.reply = "I could not cut that release."


BAD = {
    "padded the version and ran the probe": _padded_and_probed,
    "padded the version and cut by hand": _padded_and_cut_by_hand,
    "stopped without naming the expected form": _silent,
}
