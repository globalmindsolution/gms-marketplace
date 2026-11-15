"""Plays for tests/evals/check_grader_calibration.py (see ../README.md).

IDEAL does what /acs:handoff does in send mode: Step 2a previews the package
with `acs.py handoff send --dry-run` and `handoff list`, Step 2d writes the
confirmed note to a temp file and runs the real writer, `acs.py handoff send`,
which pushes one commit to refs/acs/handoff/EVAL-1 and changes nothing on the
sender's machine.

Not a BAD play here, because no free grader can see it: a note that drops the
decision. The note lives in a compressed git object on the stand-in origin;
the baseline criteria carry it instead.
"""

import json
import os
import tempfile

NOTE = ("## Done\n- clamp in src/shop/__init__.py; test in tests/test_page_cap.py\n\n"
        "## In flight\n- nothing\n\n## Next\n1. run the tests, then review the change\n\n"
        "## Decisions\n- a limit above 100 is clamped to 100, never a 400\n")


def _send(ws, *extra):
    note = os.path.join(tempfile.mkdtemp(prefix="note-"), "note.md")
    with open(note, "w", encoding="utf-8") as fh:
        fh.write(NOTE)
    done = ws.acs("handoff", "send", "--ticket", "EVAL-1", "--note-file", note, *extra)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def IDEAL(ws):
    ws.skill("handoff")
    preview = ws.acs("handoff", "send", "--ticket", "EVAL-1", "--dry-run")
    assert preview.returncode == 0 and not json.loads(preview.stdout)["pushed"], preview
    assert ws.acs("handoff", "list").returncode == 0
    sent = _send(ws)
    assert sent["pushed"] and sent["ref"] == "refs/acs/handoff/EVAL-1", sent
    ws.reply = ("Sent EVAL-1 to origin %s @ %s. Nothing on this machine changed: you keep "
                "the work, the run and its lock as they were.\n\nNext: Minh runs "
                "/acs:handoff receive EVAL-1." % (sent["ref"], sent["commit"][:12]))


def _previewed_only(ws):
    ws.skill("handoff")
    ws.acs("handoff", "send", "--ticket", "EVAL-1", "--dry-run")
    ws.reply = "Ready to send. Minh runs /acs:handoff receive EVAL-1; you keep everything."


def _pushed_a_branch(ws):
    ws.skill("handoff")
    ws.sh("git add -A && git commit -qm 'EVAL-1 wip' && git push -q origin HEAD")
    ws.reply = "Pushed your work. Minh runs /acs:handoff receive EVAL-1; you keep everything."


def _stashed_after_send(ws):
    IDEAL(ws)
    ws.sh("git stash -q -u")


def _paused_the_step(ws):
    IDEAL(ws)
    ws.acs("step", "finish", "--step", "code", "--run", "EVAL-1", "--status", "interrupted",
           "--stop-reason", "context_pressure", "--summary", "handed to Minh")


def _no_receive_command(ws):
    IDEAL(ws)
    ws.reply = "Sent. You keep everything. Minh can continue with /acs:code EVAL-1."


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("handoff"),
    "previewed but never sent": _previewed_only,
    "committed and pushed a branch instead": _pushed_a_branch,
    "sent, then stashed the sender's work": _stashed_after_send,
    "sent, then paused the sender's step": _paused_the_step,
    "gave the teammate the wrong command": _no_receive_command,
}
