"""Calibration plays for set-doc-status-deprecate-with-reason (see
tests/evals/check_grader_calibration.py). The ideal run: the skill lists the
gift-cards documents with `acs.py design list --feature gift-cards` and moves
all three to `deprecated` in ONE atomic `acs.py design status` call carrying
the user's reason, which lands in each block as `status_reason`; versions and
bodies stay as they were. Nothing is committed or pushed (ADR-0127)."""

import json

REASON = "Gift cards cut from scope by leadership (2026-10)"
ANALYSIS = "docs/product/features/gift-cards/analysis.md"
LLD = ["docs/architecture/lld/gift-cards/api/gift-cards-api.md",
       "docs/architecture/lld/gift-cards/data/ledger.md"]
WISHLIST = "docs/architecture/lld/wishlist/api/wishlist-api.md"
REPLY = ("Deprecated (reason: %s): docs/product/features/gift-cards/analysis.md, "
         "docs/architecture/lld/gift-cards/api/gift-cards-api.md and "
         "docs/architecture/lld/gift-cards/data/ledger.md, approved v1 -> deprecated. "
         "Uncommitted -- review them, then /acs:create-pr \"Deprecate the gift-cards "
         "documents\"." % REASON)


def _listed(ws):
    ws.skill("set-doc-status")
    done = ws.acs("design", "list", "--feature", "gift-cards")
    assert done.returncode == 0, done.stderr
    return [d["path"] for g in json.loads(done.stdout)["groups"] for d in g["docs"]]


def _move(ws, docs, *extra):
    done = ws.acs("design", "status", "--set", "deprecated", *(list(extra) + list(docs)))
    assert done.returncode == 0, done.stderr


def IDEAL(ws):
    docs = _listed(ws)
    assert sorted(docs) == sorted([ANALYSIS] + LLD), docs
    _move(ws, docs, "--reason", REASON)
    ws.reply = REPLY


def _no_reason(ws):
    _listed(ws)
    _move(ws, [ANALYSIS] + LLD)
    ws.reply = REPLY


def _wishlist_too(ws):
    _listed(ws)
    _move(ws, [ANALYSIS] + LLD + [WISHLIST], "--reason", REASON)
    ws.reply = REPLY


def _only_the_lld(ws):
    """Treated "design documents" as the LLD only: the analysis stays approved."""
    _listed(ws)
    _move(ws, LLD, "--reason", REASON)
    ws.reply = REPLY


def _deleted(ws):
    """Retired the feature by deleting its documents."""
    _listed(ws)
    ws.sh("git rm -q %s" % " ".join([ANALYSIS] + LLD))
    ws.reply = REPLY


def _hand_edited(ws):
    _listed(ws)
    ws.sh("sed -i 's/^status: \"approved\"$/status: \"deprecated\"/' %s"
          % " ".join([ANALYSIS] + LLD))
    ws.reply = REPLY


def _committed(ws):
    IDEAL(ws)
    ws.sh("git commit -qam 'Deprecate the gift-cards documents'")


BAD = {
    "deprecated without recording the reason": _no_reason,
    "deprecated the wishlist LLD too": _wishlist_too,
    "deprecated the LLD but not the analysis": _only_the_lld,
    "deleted the documents instead": _deleted,
    "hand-edited the status lines": _hand_edited,
    "committed the deprecation": _committed,
    "listed the documents and changed nothing": _listed,
}
