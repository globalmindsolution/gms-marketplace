"""Calibration plays for set-doc-status-approve-feature (see
tests/evals/check_grader_calibration.py). The ideal run: the skill lists the
versioned documents with `acs.py design list --feature wishlist`, takes the
arguments as the whole choice (status `approved`, the wishlist feature in both
phases), and moves the three documents in ONE atomic `acs.py design status`
call, which records who and when and leaves every version as it was. Nothing
is committed or pushed (ADR-0127)."""

import json

ANALYSIS = "docs/product/features/wishlist/analysis.md"
LLD = ["docs/architecture/lld/wishlist/api/wishlist-api.md",
       "docs/architecture/lld/wishlist/flows/add-item.md"]
CHECKOUT = ["docs/product/features/checkout/analysis.md",
            "docs/architecture/lld/checkout/api/checkout-api.md"]
REPLY = ("Approved (design status, one atomic move): "
         "docs/product/features/wishlist/analysis.md proposed v2 -> approved; "
         "docs/architecture/lld/wishlist/api/wishlist-api.md and "
         "docs/architecture/lld/wishlist/flows/add-item.md proposed v1 -> approved. "
         "Uncommitted -- review them, then /acs:create-pr \"Approve the wishlist design\".")


def _listed(ws, feature="wishlist"):
    ws.skill("set-doc-status")
    done = ws.acs("design", "list", "--feature", feature)
    assert done.returncode == 0, done.stderr
    return [d["path"] for g in json.loads(done.stdout)["groups"] for d in g["docs"]]


def _move(ws, status, docs, *extra):
    done = ws.acs("design", "status", "--set", status, *(list(extra) + list(docs)))
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    docs = _listed(ws)
    assert sorted(docs) == sorted([ANALYSIS] + LLD), docs
    _move(ws, "approved", docs)
    ws.reply = REPLY


def _approved_everything_proposed(ws):
    """Read `approved` as "every proposed document": checkout's too."""
    _listed(ws)
    _move(ws, "approved", [ANALYSIS] + LLD + CHECKOUT)
    ws.reply = REPLY


def _only_the_analysis(ws):
    """Matched the slug in Discovery only: the feature's LLD stays proposed."""
    _listed(ws)
    _move(ws, "approved", [ANALYSIS])
    ws.reply = REPLY


def _hand_edited(ws):
    """Rewrote the `status:` lines by hand: no who, no when."""
    _listed(ws)
    ws.sh("sed -i 's/^status: \"proposed\"$/status: \"approved\"/' %s" % " ".join([ANALYSIS] + LLD))
    ws.reply = REPLY


def _bumped(ws):
    """Recorded a change instead of a decision: version + 1, still proposed."""
    _listed(ws)
    done = ws.acs("design", "bump", ANALYSIS, *LLD)
    assert done.returncode == 0, done.stderr
    ws.reply = REPLY


def _committed(ws):
    IDEAL(ws)
    ws.sh("git commit -qam 'Approve the wishlist design'")


def _pushed(ws):
    IDEAL(ws)
    ws.sh("git checkout -q -b docs/approve-wishlist && git commit -qam 'Approve the wishlist design'"
          " && git push -q -u origin docs/approve-wishlist")


def _listed_and_stopped(ws):
    _listed(ws)


BAD = {
    "approved the checkout documents too": _approved_everything_proposed,
    "approved the analysis but not the LLD": _only_the_analysis,
    "hand-edited the status lines": _hand_edited,
    "bumped the versions instead of approving": _bumped,
    "committed the approval": _committed,
    "pushed a branch with the approval": _pushed,
    "listed the documents and changed nothing": _listed_and_stopped,
}
