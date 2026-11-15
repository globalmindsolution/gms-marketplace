"""Calibration plays for 09-scaffold-templates (ADR-0148)."""


def IDEAL(ws):
    ws.skill("setup")
    done = ws.setup_apply({}, [], templates=True)
    assert done.returncode == 0, done.stderr
    ws.reply = ("Copied acs's document templates into .acs/templates/ for your team to edit; "
                "no CI installed. Stage .acs/templates/ with the rest.")


def _skipped(ws):
    ws.skill("setup")
    ws.setup_apply({}, [], templates=False)


def _copied_by_hand(ws):
    """Copied two templates itself: no lock, most templates missing."""
    ws.skill("setup")
    ws.setup_apply({}, [])
    ws.write(".acs/templates/prd-default.md", "## Vision\n")
    ws.write(".acs/templates/pr-default.md", "## Summary\n")


def _with_ci(ws):
    ws.skill("setup")
    ws.setup_apply({}, ["conventions"], templates=True)


BAD = {
    "skipped the templates it was asked for": _skipped,
    "copied a couple of templates by hand": _copied_by_hand,
    "installed a CI gate nobody asked for": _with_ci,
}
