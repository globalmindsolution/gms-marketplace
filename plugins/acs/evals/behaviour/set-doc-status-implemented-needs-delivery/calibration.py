"""Calibration plays for set-doc-status-implemented-needs-delivery (see
tests/evals/check_grader_calibration.py). The ideal run lists the documents,
offers `implemented` only for the feature PRD whose delivery says so, and
moves it with one `acs.py design status` call; the other stays approved
(ADR-0146). Nothing is committed (ADR-0127)."""

CARD = "docs/product/features/card-checkout/prd.md"
TRACKING = "docs/product/features/order-tracking/prd.md"


def _list(ws):
    ws.skill("set-doc-status")
    listed = ws.acs("design", "list", "--phase", "discovery")
    assert listed.returncode == 0, listed.stderr


def _implement(ws, *docs, extra=()):
    done = ws.acs("design", "status", "--set", "implemented", *extra, *docs)
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    _list(ws)
    _implement(ws, CARD)
    ws.reply = ("Card checkout's PRD is now implemented. Order tracking stays approved: "
                "order-tracking/R1 is not delivered yet (EVAL-2 is open). Review the change, "
                "then /acs:create-pr.")


def _forced_both(ws):
    _list(ws)
    _implement(ws, CARD, TRACKING, extra=("--override-delivery", "--reason", "user said built"))


def _hand_edited(ws):
    _list(ws)
    _implement(ws, CARD)
    path = ws.path + "/" + TRACKING
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    ws.write(TRACKING, text.replace("status: \"approved\"", "status: \"implemented\"")
             .replace("status: approved", "status: implemented"))


def _gave_up_on_both(ws):
    """The atomic refusal for the pair, and no retry with the one that may move."""
    _list(ws)
    ws.acs("design", "status", "--set", "implemented", CARD, TRACKING)


def _committed(ws):
    _list(ws)
    _implement(ws, CARD)
    ws.sh("git commit -qam 'Card checkout implemented'")


BAD = {
    "forced order tracking with --override-delivery": _forced_both,
    "hand-edited order tracking's front matter": _hand_edited,
    "stopped at the pair's refusal and moved nothing": _gave_up_on_both,
    "committed the status change": _committed,
    "listed the documents and moved nothing": _list,
}
