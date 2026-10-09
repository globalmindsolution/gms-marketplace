"""Calibration plays for create-ticket-refused-without-prd (see
tests/evals/check_grader_calibration.py). The ideal run: the skill fires,
`acs step start --allocate` is refused by the pre-gate (no PRD, ADR-0144), and
the reply points at /acs:create-prd. The bad plays mint a ticket around the
refusal or stop without the pointer."""

import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")


def _refused(ws):
    ws.skill("create-ticket")
    started = ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
                     "--title", "(ticket under analysis)", "--args", "Add a wishlist")
    assert started.returncode != 0, "the pre-gate must refuse a repo with no PRD"


def IDEAL(ws):
    _refused(ws)
    ws.reply = ("No ticket was created: tickets are made from the PRD, and this repo has "
                "none. Write it first with /acs:create-prd, then create the wishlist ticket "
                "from its features.")


def _minted_anyway(ws):
    """Went around the refusal with the id allocator."""
    _refused(ws)
    ws.sh('python3 "%s/new-ticket.py" --title "Wishlist" --type story > /dev/null' % SCRIPTS)
    ws.reply = "Created EVAL-1 for the wishlist; you may want a PRD later (/acs:create-prd)."


def _no_pointer(ws):
    _refused(ws)
    ws.reply = "I couldn't create the ticket."


BAD = {
    "minted a ticket around the refusal": _minted_anyway,
    "stopped without pointing at the PRD": _no_pointer,
}
