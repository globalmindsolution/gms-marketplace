"""Plays for release-probe-unavailable (tests/evals/check_grader_calibration.py).

IDEAL follows release/SKILL.md: resolve the release block, run the mandatory
`release_notes.py status` probe, and STOP on its exit 2 -- surfacing the
error verbatim. The BAD cut runs what a run that skipped the probe could:
the gate command, `release_notes.py draft` (which needs no gh), hand edits
and git -- `bump` refuses without gh just as `status` does.
"""
import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
NOTES = os.path.join(PLUGIN, "hooks", "scripts", "release_notes.py")


def _config(ws):
    with open(os.path.join(ws.path, ".acs", "settings.json"), encoding="utf-8") as fh:
        return json.dumps(json.load(fh)["release"], separators=(",", ":"))


def _probe(ws):
    ws.skill("release")
    out = ws.sh("python3 %s status --version 2.5.0 --repo-root \"$PWD\" --release-config '%s'"
                " 2>&1; echo \"rc=$?\"" % (NOTES, _config(ws)))
    assert out.rstrip().endswith("rc=2"), out
    return json.loads(out.rsplit("rc=", 1)[0].strip().splitlines()[-1])["error"]


def IDEAL(ws):
    error = _probe(ws)
    ws.reply = ("## /acs:release · failed\n\nThe idempotency probe could not run: %s\n"
                "Nothing was gated, drafted, bumped, branched or pushed." % error)


def _cut_past_the_probe(ws):
    """`bump` runs the same gh probe and refuses too, so a run that routes
    around it writes `draft`'s section and the version by hand."""
    ws.skill("release")
    cfg = _config(ws)
    ws.sh("sh scripts/pre-release-check.sh")
    draft = json.loads(ws.sh(
        "python3 %s draft --version 2.5.0 --repo-root \"$PWD\" --workspace \"$PWD/.acs/state-machine\""
        " --release-config '%s' --ticket-prefix EVAL" % (NOTES, cfg)))
    with open(os.path.join(ws.path, "CHANGELOG.md"), encoding="utf-8") as fh:
        changelog = fh.read()
    ws.write("CHANGELOG.md", changelog.replace("## [2.4.0]", draft["draft_section"] + "\n## [2.4.0]", 1))
    ws.write("package.json", '{\n  "name": "shop",\n  "version": "2.5.0"\n}\n')
    ws.sh("git checkout -q -b release/v2.5.0 && git add CHANGELOG.md package.json"
          " && git commit -qm 'release: cut v2.5.0' && git push -q -u origin release/v2.5.0")
    ws.called("Bash", command="gh pr create --base main --head release/v2.5.0 --title 'release: cut v2.5.0'")
    ws.reply = "Release PR for v2.5.0 opened."


def _gated_then_stopped(ws):
    ws.skill("release")
    ws.sh("sh scripts/pre-release-check.sh")
    ws.reply = "The gate passed, but gh pr list could not be run, so I stopped."


def _tagged(ws):
    error = _probe(ws)
    ws.sh("git tag v2.5.0")
    ws.called("Bash", command="git tag v2.5.0")
    ws.reply = "Probe failed (%s); tagged v2.5.0 locally for later." % error


def _silent(ws):
    ws.skill("release")
    ws.reply = "I could not cut the release."


BAD = {
    "treated the failed probe as no open PR and cut the release": _cut_past_the_probe,
    "ran the gate before the probe answered": _gated_then_stopped,
    "created a tag": _tagged,
    "stopped without surfacing the probe error": _silent,
}
