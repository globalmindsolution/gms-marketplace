"""Calibration plays for create-docs-unknown-set-refused (see
tests/evals/check_grader_calibration.py). The ideal run: the skill's Start
snippet hands `quality,security` to acs_lib.parse_doc_set_arg, which rejects
the whole request; the coordinator relays the notice and stops."""

import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")


def _notice(ws, argument):
    """What the Start snippet prints to stderr for this argument."""
    code = ("import sys; sys.path.insert(0, %r); import acs_lib as lib; "
            "r = lib.parse_doc_set_arg(sys.argv[1]); "
            "sys.stderr.write('\\n'.join(r.notices)); "
            "sys.exit(2 if r.rejected or r.candidates == [] else 0)" % SCRIPTS)
    done = subprocess.run([sys.executable, "-c", code, argument], cwd=ws.path,
                          capture_output=True, text=True)
    assert done.returncode == 2, done
    return done.stderr


def IDEAL(ws):
    ws.skill("create-docs")
    ws.reply = ("Refused, nothing started: %s. Re-run with the sets you want, e.g. "
                "/acs:create-docs quality." % _notice(ws, "quality,security"))


def _fanned_out_quality(ws):
    ws.skill("create-docs")
    started = ws.acs("step", "start", "--step", "create-docs", "--doc-set", "quality", "--allocate")
    assert started.returncode == 0, started.stderr
    ws.write("docs/quality/test-strategy.md", "# Test strategy\n")
    ws.reply = ("security is not a doc set, so I ran quality alone; the accepted sets are "
                "quality, operations, principles and standards.")


def _improvised_security(ws):
    ws.skill("create-docs")
    ws.write("docs/security/threat-model.md", "# Threat model\n")
    ws.reply = "Wrote docs/security/threat-model.md; the quality set follows next."


def _silent_refusal(ws):
    ws.skill("create-docs")
    ws.reply = "The skill refused the argument."


BAD = {
    "ran the recognised quality set on its own": _fanned_out_quality,
    "improvised a security doc set": _improvised_security,
    "refused without naming the accepted sets": _silent_refusal,
}
