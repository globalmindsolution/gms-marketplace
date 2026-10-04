"""acs_lib.design_docs — the version front matter of a design document (ADR-0122).

Every HLD and LLD document opens with a front-matter block that says where the
design stands against the code:

    ---
    status: proposed        # proposed | approved | implemented | deprecated
    version: 3              # bumped on every change to the document
    tickets: ["SHOP-12"]    # the tickets that changed it, oldest first
    feature: wishlist       # LLD documents only: the PRD feature slug
    ---

A Design skill writes `proposed`; the team's approval of the design PR makes it
`approved`; `/acs:docs-sync`, once the gap analysis finds the code matching,
makes it `implemented`; superseded content is `deprecated`. A status is set here,
through a legal transition, never by hand-editing the block -- the value a later
skill reads is derived from this record, not asserted by an agent.
"""

import os
import re

from ._common import GateError, TICKET_ID_RE
from . import yamlsubset
from .artifacts import render_front_matter

STATUSES = ("proposed", "approved", "implemented", "deprecated")

#: status -> the statuses it may move to. A change to an approved or
#: implemented design re-opens it as `proposed` (with a version bump);
#: `deprecated` is final.
TRANSITIONS = {
    "proposed": ("proposed", "approved", "deprecated"),
    "approved": ("proposed", "approved", "implemented", "deprecated"),
    "implemented": ("proposed", "implemented", "deprecated"),
    "deprecated": ("deprecated",),
}

KEY_ORDER = ("status", "version", "tickets", "feature")
_FEATURE_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def is_lld(path):
    """An LLD document lives under an `lld/` directory of the architecture set."""
    return "lld" in os.path.normpath(path).split(os.sep)


def read(path):
    """(front, body) of a design document; front is None when it has none."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        return yamlsubset.split_front_matter(text)
    except yamlsubset.YamlSubsetError as exc:
        raise GateError("%s: front matter does not parse: %s" % (path, exc))


def problems(path, front):
    """What is wrong with `front` for the document at `path` ([] when nothing)."""
    if front is None:
        return ["no version front matter (status, version, tickets)"]
    found = []
    if front.get("status") not in STATUSES:
        found.append("status must be one of %s; got %r" % ("|".join(STATUSES), front.get("status")))
    version = front.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        found.append("version must be an integer >= 1; got %r" % (version,))
    tickets = front.get("tickets")
    if not isinstance(tickets, list) or not all(
            isinstance(t, str) and TICKET_ID_RE.fullmatch(t) for t in tickets):
        found.append("tickets must be a list of ticket ids; got %r" % (tickets,))
    if is_lld(path):
        if not isinstance(front.get("feature"), str) or not _FEATURE_RE.match(front["feature"]):
            found.append("an LLD document names its PRD feature slug in `feature`; got %r"
                         % (front.get("feature"),))
    return found


def check(path):
    """{"path", "status", "version", "problems"} for one document."""
    front, _body = read(path)
    front = front or None
    return {"path": path, "status": (front or {}).get("status"),
            "version": (front or {}).get("version"), "problems": problems(path, front)}


def write(path, front, body):
    """Write `front` (in KEY_ORDER, then any other keys) over `body`."""
    ordered = {key: front[key] for key in KEY_ORDER if key in front}
    ordered.update({k: v for k, v in front.items() if k not in ordered})
    text = "\n".join(["---"] + render_front_matter(ordered) + ["---", ""]) + "\n" + body.lstrip("\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _with_ticket(tickets, ticket):
    tickets = list(tickets or [])
    if ticket and ticket not in tickets:
        tickets.append(ticket)
    return tickets


def init(path, status, ticket=None, feature=None):
    """Give a document its first front matter. A document that already has one
    is left alone (returns False)."""
    if status not in STATUSES:
        raise GateError("status must be one of %s; got %r" % ("|".join(STATUSES), status))
    front, body = read(path)
    if front:
        return False
    front = {"status": status, "version": 1, "tickets": _with_ticket([], ticket)}
    if feature:
        front["feature"] = feature
    found = problems(path, front)
    if found:
        raise GateError("%s: %s" % (path, "; ".join(found)))
    write(path, front, body)
    return True


def _load_valid(path):
    front, body = read(path)
    found = problems(path, front)
    if found:
        raise GateError("%s: %s (run `acs.py design init` first)" % (path, "; ".join(found)))
    return front, body


def bump(path, ticket=None):
    """A change to the document: version + 1, the ticket recorded, and an
    approved or implemented design re-opened as `proposed`."""
    front, body = _load_valid(path)
    if front["status"] == "deprecated":
        raise GateError("%s: a deprecated design is not changed" % path)
    front["version"] += 1
    front["tickets"] = _with_ticket(front["tickets"], ticket)
    front["status"] = "proposed"
    write(path, front, body)
    return front


def set_status(path, status, ticket=None):
    """Move the document to `status` along a legal transition."""
    if status not in STATUSES:
        raise GateError("status must be one of %s; got %r" % ("|".join(STATUSES), status))
    front, body = _load_valid(path)
    if status not in TRANSITIONS[front["status"]]:
        raise GateError("%s: %s -> %s is not a legal transition (from %s: %s)"
                        % (path, front["status"], status, front["status"],
                           ", ".join(TRANSITIONS[front["status"]])))
    front["status"] = status
    front["tickets"] = _with_ticket(front["tickets"], ticket)
    write(path, front, body)
    return front
