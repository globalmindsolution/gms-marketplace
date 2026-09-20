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

from ._common import (GateError, ReconciliationRequired, TICKET_ID_RE,
    now_iso, read_json, write_json)
from .repo import (_guarded_repo_write, index_path, repo_dir, repo_guard,
    scan_local_ticket_evidence, ticket_dir)
from . import artifacts

def load_ticket(tdir):
    """The ticket dict, status included. Routed through acs_lib.artifacts:
    ticket.md from the docs tree when the ticket lives there (status derived
    from the ledger), else ticket.json -- so every partition built with a
    ticket.json keeps reading exactly as before."""
    return artifacts.load_ticket(tdir)


def save_ticket(tdir, ticket):
    """Stamp updated_at and write the ticket where it lives: ticket.md when
    the docs tree is active for this checkout and the ticket is (or is new to)
    the tree, else ticket.json as before. acs_lib.artifacts decides which."""
    artifacts.save_ticket(tdir, ticket)


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
    if kw.get("doc_set"):
        # A /acs:create-docs delivery ticket names the set it delivers, so a
        # resume knows what it is resuming without parsing the title.
        doc["doc_set"] = kw["doc_set"]
    return doc



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
        if ticket.get("doc_set"):
            entry["doc_set"] = ticket["doc_set"]
        if archived is not None:
            entry["archived"] = archived
        write_json(path, data)
        return data

    return _guarded_repo_write(workspace, repo_id, "tickets-index.json.lock", _write)


# ---------------------------------------------------------------------------
# Locking (.lock per ticket partition; re-entrant per checkout)
# ---------------------------------------------------------------------------

