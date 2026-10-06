"""acs_lib.tickets — ticket.json, the id counter and tickets-index.json.

Extracted from `acs_lib.state` (§4.7: one module per machine). A ticket is now
one KIND of run subject rather than the partition key, so this module is about
tickets as documents — allocating an id, reading and writing the document,
keeping the index — and knows nothing about runs.
"""

import fnmatch
import os
import re
import sys

from ._common import (BUG_FIELDS, BUG_SEVERITIES, GateError, ReconciliationRequired,
    TICKET_ID_RE, TICKET_TYPES, now_iso, read_json, write_json)
from .repo import (_guarded_repo_write, index_path, repo_dir, repo_guard,
    scan_local_ticket_evidence, ticket_dir)
from . import artifacts

def load_ticket(tdir):
    """The ticket dict, status included. Routed through acs_lib.artifacts:
    the partition's ticket.json, else (legacy, ADR-0090) a ticket.md in the
    docs tree with its status derived from the ledger."""
    return artifacts.load_ticket(tdir)


def save_ticket(tdir, ticket):
    """Stamp updated_at and write the partition's ticket.json -- a ticket's one
    home since ADR-0128 (never the repo's docs tree)."""
    artifacts.save_ticket(tdir, ticket)


#: A PRD feature's slug, as `acs.py slug --text "<feature name>"` makes it.
FEATURE_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse_features(text):
    """'wishlist, checkout' -> ['wishlist', 'checkout'] (deduplicated, in order).
    Raises GateError naming any entry that is not a feature slug."""
    names = list(dict.fromkeys(n.strip() for n in (text or "").split(",") if n.strip()))
    bad = [n for n in names if not FEATURE_SLUG_RE.match(n)]
    if bad:
        raise GateError("features must be PRD feature slugs (lowercase words joined by "
                        "'-', as `acs.py slug` makes them); got: %s" % ", ".join(bad))
    return names


def new_ticket_doc(ticket_id, title, ttype, **kw):
    doc = {
        "id": ticket_id,
        "title": title,
        "type": ttype,
        "description": kw.get("description", ""),
        "acceptance_criteria": kw.get("acceptance_criteria", []),
        "priority": kw.get("priority", "medium"),
        "parent": kw.get("parent"),
        "children": kw.get("children", []),
        "status": kw.get("status", "open"),
        "external": kw.get("external"),
        "assignee": kw.get("assignee"),
        "story_points": kw.get("story_points"),
        "needs_design": kw.get("needs_design", ttype == "epic"),
        "docs_only": kw.get("docs_only", False),
        "due_date": kw.get("due_date"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    if kw.get("features"):
        # The PRD features it traces to (ADR-0120); absent rather than [] when none.
        doc["features"] = list(kw["features"])
    # A bug's report (ADR-0138): each field only when given, never a null.
    for field in BUG_FIELDS:
        if kw.get(field) is not None:
            doc[field] = kw[field]
    return doc


def check_bug_fields(ticket):
    """Raise GateError when `ticket` is outside what ticket.schema.json and
    ADR-0138 allow for its type: a type acs does not know, a bug field on a
    ticket that is not a bug, a severity outside BUG_SEVERITIES, or a bug
    field that is not a string. A bug's fields are all optional."""
    ttype = ticket.get("type")
    if ttype not in TICKET_TYPES:
        raise GateError("type %r is not a ticket type (allowed: %s)"
                        % (ttype, ", ".join(TICKET_TYPES)))
    present = [f for f in BUG_FIELDS if f in ticket]
    if present and ttype != "bug":
        raise GateError("%s only apply to a bug; %s is a %s"
                        % (", ".join(present), ticket.get("id") or "this ticket", ttype))
    if "severity" in ticket and ticket["severity"] not in BUG_SEVERITIES:
        raise GateError("severity %r is not one of %s (it is how bad the bug is, "
                        "separate from priority)"
                        % (ticket["severity"], ", ".join(BUG_SEVERITIES)))
    for field in present:
        if not isinstance(ticket[field], str):
            raise GateError("%s must be a string, not %s"
                            % (field, type(ticket[field]).__name__))



def allocate_ticket_id(workspace, repo_id, prefix, repo_root=None, seed_next=None):
    """Allocate the next <prefix>-<n> id; counter guarded by an O_EXCL spin lock so
    parallel worktree sessions never collide. A partition with no reconciliation
    marker refuses (raises ReconciliationRequired) instead of minting from 1,
    unless seed_next authoritatively confirms/repairs the floor.

    Raises GuardTimeout (via repo_guard) rather than minting an id from an
    unguarded read of counters.json -- two sessions handed the same id is the
    exact collision the guard exists to prevent (MAR-530)."""
    rdir = repo_dir(workspace, repo_id)
    with repo_guard(rdir, "counters.json.lock"):
        counters_path = os.path.join(rdir, "counters.json")
        counters = read_json(counters_path) or {}

        if seed_next is not None:
            if seed_next < 1:
                raise ValueError(
                    "allocate_ticket_id requires seed_next >= 1 (defense-in-depth "
                    "behind the CLIs' own >= 1 checks); got %r" % (seed_next,)
                )
            previous_next = counters.get("next")
            if isinstance(previous_next, int) and seed_next < previous_next:
                sys.stderr.write(
                    "acs: warning: --seed-next %d lowers counters.json's next "
                    "(was %d)\n" % (seed_next, previous_next)
                )
            counters["reconciled"] = True
            counters["seed_source"] = "explicit-user"
            counters["seeded_at"] = now_iso()
            counters.pop("observed_max", None)
            counters["next"] = seed_next + 1
            write_json(counters_path, counters)
            return "%s-%d" % (prefix, seed_next)

        if "next" in counters or counters.get("reconciled") is True:
            next_n = int(counters.get("next", 1))
            counters["next"] = next_n + 1
            write_json(counters_path, counters)
            return "%s-%d" % (prefix, next_n)

        scan = scan_local_ticket_evidence(repo_root, prefix)
        observed_max = scan["observed_max"]
        proposed_next = observed_max + 1 if observed_max is not None else None
        raise ReconciliationRequired(prefix, repo_id, observed_max, scan["seed_source"], proposed_next)


def update_index(workspace, repo_id, ticket, archived=None):
    path = index_path(workspace, repo_id)

    def _write():
        data = read_json(path) or {"tickets": {}}
        data.setdefault("tickets", {})
        entry = data["tickets"].setdefault(ticket["id"], {})
        entry.update({
            "id": ticket["id"],
            "title": ticket.get("title"),
            "type": ticket.get("type"),
            "status": ticket.get("status"),
            "parent": ticket.get("parent"),
            "children": ticket.get("children", []),
            "needs_design": ticket.get("needs_design"),
            "external": ticket.get("external"),
            "due_date": ticket.get("due_date"),
            "updated_at": now_iso(),
        })
        if "features" in ticket:
            entry["features"] = list(ticket.get("features") or [])
        if archived is not None:
            entry["archived"] = archived
        write_json(path, data)
        return data

    return _guarded_repo_write(workspace, repo_id, "tickets-index.json.lock", _write)


# ---------------------------------------------------------------------------
# Locking (.lock per ticket partition; re-entrant per checkout)
# ---------------------------------------------------------------------------
