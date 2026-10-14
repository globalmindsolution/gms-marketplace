"""acs_lib.prd_delivery — whether a feature PRD is implemented, derived from its tickets (ADR-0146).

A feature PRD (`<prd_dir>/features/<slug>/prd.md`, ADR-0142) declares its
requirements `R<n>`; a product ticket links the ones it delivers as
`<slug>/R<n>` (ADR-0144). Delivery is read from those links, never asserted:

  requirement  `delivered` when at least one ticket names it and every one
               that does is done -- `done` in the tickets index, or its id
               leading a commit subject on the default branch (the index is
               per checkout; the branch is shared); `in progress` once any has
               started; `planned` while all are open; `uncovered` when no
               ticket names it
  feature      `implemented` when it declares at least one requirement and
               every one is delivered; `in progress` when any requirement has
               a started or done ticket; `planned` when every one has a ticket
               and none has started; `uncovered` otherwise (a requirement no
               ticket names yet)

A later open ticket on a delivered requirement -- a bug filed against it --
takes the requirement, and the feature, back out of `implemented`.

`agreement` compares that reading with the document's own front-matter
`status`: `ready` (approved, and delivery says implemented: the move
/acs:set-doc-status may now offer), `drift` (marked implemented, but
delivery no longer says so), or `consistent`. Nothing here writes a
document: a status moves only through `acs.py design status`, which refuses
`implemented` for a feature PRD whose delivery is not `implemented`.
"""

import os

from . import doc_layout, prd_link, roadmap

FEATURE_STATUSES = ("uncovered", "planned", "in progress", "implemented")


def feature_slugs(root, settings=None):
    """Every feature with a PRD of its own under `<prd_dir>/features/`, sorted."""
    folder = os.path.join(root, *doc_layout.prd_dir(root, settings).split("/"), "features")
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    return [n for n in names if prd_link.REQUIREMENT_RE.match(n + "/R1")
            and os.path.isfile(os.path.join(folder, n, doc_layout.FEATURE_PRD_FILENAME))]


def _ticket_state(tid, index, merged):
    return "done" if tid in merged else ((index or {}).get(tid) or {}).get("status") or "open"


def requirement_state(states):
    """The state of one requirement from the states of the tickets naming it."""
    if not states:
        return "uncovered"
    if all(s == "done" for s in states):
        return "delivered"
    if any(s != "open" for s in states):
        return "in progress"
    return "planned"


def feature_state(requirement_states):
    """The feature's delivery from its requirements' states."""
    if not requirement_states:
        return "uncovered"
    if all(s == "delivered" for s in requirement_states):
        return "implemented"
    if any(s in ("delivered", "in progress") for s in requirement_states):
        return "in progress"
    if "uncovered" in requirement_states:
        return "uncovered"
    return "planned"


def _agreement(doc_status, delivery):
    if doc_status == "implemented" and delivery != "implemented":
        return "drift"
    if doc_status == "approved" and delivery == "implemented":
        return "ready"
    return "consistent"


def derive_feature(root, slug, index, merged=(), settings=None):
    """{feature, path, doc_status, delivery, agreement, requirements: [{id,
    state, tickets: {id: state}}], tickets: [ids linking the feature]}."""
    path = doc_layout.feature_prd_path(root, slug, settings)
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, TypeError, UnicodeDecodeError):
        text = None
    reqs = []
    for req in (prd_link.feature_requirements(text) if text else []):
        rid = "%s/%s" % (slug, req)
        tickets = {tid: _ticket_state(tid, index, merged)
                   for tid, entry in sorted((index or {}).items())
                   if rid in (entry.get("requirements") or ())}
        reqs.append({"id": rid, "state": requirement_state(list(tickets.values())),
                     "tickets": tickets})
    delivery = feature_state([r["state"] for r in reqs])
    doc_status = prd_link._status(text) if text else None
    linked = sorted(tid for tid, entry in (index or {}).items()
                    if slug in (entry.get("features") or ()))
    return {"feature": slug,
            "path": os.path.relpath(path, root).replace(os.sep, "/") if path else None,
            "doc_status": doc_status, "delivery": delivery,
            "agreement": _agreement(doc_status, delivery),
            "requirements": reqs, "tickets": linked}


def derive(root, index, merged=(), settings=None, feature=None):
    """`derive_feature` for one feature, or for every feature PRD."""
    slugs = [feature] if feature else feature_slugs(root, settings)
    return [derive_feature(root, s, index, merged, settings) for s in slugs]


def feature_of(root, path, settings=None):
    """The slug when `path` is a feature PRD (`<prd_dir>/features/<slug>/prd.md`), else None."""
    absolute = os.path.normpath(path if os.path.isabs(path) else os.path.join(root, path))
    for slug in feature_slugs(root, settings):
        if os.path.normpath(doc_layout.feature_prd_path(root, slug, settings)) == absolute:
            return slug
    return None


def evidence(root, settings=None, index=None, git=True):
    """The (index, merged) pair delivery is read from: the tickets index given
    (or none) and, unless `git` is False, the ids merged on the default branch."""
    merged = roadmap.merged_on_default_branch(root, settings) if git else set()
    return index or {}, merged
