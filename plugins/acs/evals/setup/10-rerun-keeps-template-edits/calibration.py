"""Calibration plays for 10-rerun-keeps-template-edits (ADR-0148)."""

import os




def IDEAL(ws):
    ws.skill("setup")
    done = ws.setup_apply({"ticket_prefix": "PAY"}, [], templates=True)
    assert done.returncode == 0, done.stderr
    ws.reply = ("Setup is in place. Your edited prd-feature-default.md template was kept "
                "(customised); nothing else changed.")


def _reset_the_template(ws):
    """Deleted the edited copy and re-scaffolded: the built-in comes back."""
    ws.skill("setup")
    os.remove(os.path.join(ws.path, ".acs/templates/prd-feature-default.md"))
    ws.setup_apply({"ticket_prefix": "PAY"}, [], templates=True)


def _dropped_the_prefix(ws):
    ws.skill("setup")
    ws.setup_apply({}, [], templates=True)
    ws.write(".acs/settings.json", "{}\n")


BAD = {
    "reset the team's template to the built-in": _reset_the_template,
    "lost the custom ticket prefix": _dropped_the_prefix,
}
