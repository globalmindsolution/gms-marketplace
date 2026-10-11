"""acs_lib.roadmap — the roadmap document and its derived delivery status (ADR-0145).

`roadmap.md` sits beside the PRD hub and is written only by /acs:manage-roadmap.
Its shape (the skill's `references/roadmap-shape.md` is the authoring side):

    ## Milestones

    ### M1 Booking MVP — v0.1.0

    - Status: planned
    - Features: [Online booking](features/online-booking/prd.md), [SMS reminders](...)
    - Epics: SHOP-12, SHOP-14
    - Target: 2027-03-31

    Why this milestone, in a paragraph.

    ## Release versions

    | Version | Milestone | Epics | Status |
    |---|---|---|---|
    | v0.1.0 | M1 Booking MVP | SHOP-12, SHOP-14 | planned |

A milestone's **Status** is derived, never asserted: `derive` reads the
tickets it tracks — its epics, and every ticket linking one of its features —
from the workspace's tickets index, counts a ticket whose id leads a commit
subject on the default branch as merged (the index is per checkout; the
branch is shared), and `render` rewrites only the Status line and the table's
Status cell. `planned` until a tracked ticket starts, `in progress` once one
has, `delivered` when it tracks at least one ticket and every one is done.
"""

import os
import re

from ._common import _git

STATUSES = ("planned", "in progress", "delivered")

_H2 = re.compile(r"^##\s+(.+?)\s*$")
_MILESTONE = re.compile(r"^###\s+(.+?)\s+[—–-]\s+v(\d+\.\d+\.\d+)\s*$")
_H3 = re.compile(r"^###\s+(.+?)\s*$")
_FIELD = re.compile(r"^\s*[-*]\s+(Status|Features|Epics|Target)\s*:\s*(.*?)\s*$", re.IGNORECASE)
_FEATURE_LINK = re.compile(r"features/([a-z0-9]+(?:-[a-z0-9]+)*)/prd\.md")
_TICKET = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")
_ROW = re.compile(r"^\|(.+)\|\s*$")


def _sections(lines):
    """{H2 title lower-cased: (start index, end index)} of the document."""
    found, current, start = {}, None, 0
    for i, line in enumerate(lines):
        head = _H2.match(line)
        if head:
            if current is not None:
                found[current] = (start, i)
            current, start = head.group(1).strip().lower(), i
    if current is not None:
        found[current] = (start, len(lines))
    return found


def parse(text):
    """{"milestones": [...], "versions": [...], "headings": [...]} of a roadmap.

    A milestone: {name, version, line, status, features, epics, target,
    status_line}; `line`/`status_line` are 0-based indexes into the text's
    lines (status_line None when there is none). A version row: {version,
    milestone, epics, status, line}. `headings` lists every `###` heading of
    the Milestones section with whether it carries a version."""
    lines = text.split("\n")
    sections = _sections(lines)
    milestones, headings = [], []
    lo, hi = sections.get("milestones", (0, 0))
    current = None
    for i in range(lo, hi):
        line = lines[i]
        h3 = _H3.match(line)
        if h3:
            match = _MILESTONE.match(line)
            headings.append({"text": h3.group(1), "line": i, "versioned": bool(match)})
            current = None
            if match:
                current = {"name": match.group(1).strip(), "version": match.group(2), "line": i,
                           "status": None, "status_line": None, "features": [],
                           "epics": [], "target": None}
                milestones.append(current)
            continue
        field = current and _FIELD.match(line)
        if field:
            key, value = field.group(1).lower(), field.group(2)
            if key == "status":
                current["status"], current["status_line"] = value.lower(), i
            elif key == "features":
                current["features"] = list(dict.fromkeys(_FEATURE_LINK.findall(value)))
            elif key == "epics":
                current["epics"] = list(dict.fromkeys(_TICKET.findall(value)))
            else:
                current["target"] = value
    versions = []
    lo, hi = sections.get("release versions", (0, 0))
    for i in range(lo, hi):
        row = _ROW.match(lines[i].strip())
        if not row:
            continue
        cells = [c.strip() for c in row.group(1).split("|")]
        if len(cells) < 4 or set("".join(cells)) <= set("-: ") or cells[0].lower() == "version":
            continue
        versions.append({"version": cells[0].lstrip("v"), "milestone": cells[1],
                         "epics": list(dict.fromkeys(_TICKET.findall(cells[2]))),
                         "status": cells[3].lower(), "line": i})
    return {"milestones": milestones, "versions": versions, "headings": headings}


def merged_ids(repo_root, base_branch, prefix):
    """Ticket ids that lead a commit subject on `base_branch` (best effort: [] on error)."""
    if not (repo_root and base_branch and prefix):
        return set()
    out = _git(["log", "--format=%s", base_branch], repo_root)  # None on any git failure
    pattern = re.compile(r"^\s*(%s-\d+)\b" % re.escape(prefix))
    return {m.group(1) for m in map(pattern.match, (out or "").splitlines()) if m}


def tracked(milestone, index):
    """The ticket ids a milestone tracks: its epics, and every ticket in the
    index linking one of its features."""
    ids = list(milestone["epics"])
    for tid, entry in sorted((index or {}).items()):
        if set(entry.get("features") or ()) & set(milestone["features"]):
            ids.append(tid)
    return list(dict.fromkeys(ids))


def status_of(ticket_ids, index, merged=()):
    """`planned`, `in progress` or `delivered` for a set of tracked tickets."""
    states = []
    for tid in ticket_ids:
        state = ((index or {}).get(tid) or {}).get("status") or "open"
        states.append("done" if tid in merged else state)
    if states and all(s == "done" for s in states):
        return "delivered"
    if any(s != "open" for s in states):
        return "in progress"
    return "planned"


def derive(text, index, merged=()):
    """[{name, version, status, was, tickets: {id: state}}] for every milestone."""
    out = []
    for milestone in parse(text)["milestones"]:
        ids = tracked(milestone, index)
        out.append({"name": milestone["name"], "version": milestone["version"],
                    "status": status_of(ids, index, merged), "was": milestone["status"],
                    "tickets": {tid: ("done" if tid in merged else
                                      ((index or {}).get(tid) or {}).get("status") or "unknown")
                                for tid in ids}})
    return out


def render(text, derived):
    """The text with each milestone's Status line and its Release versions
    Status cell set to the derived status; nothing else is touched."""
    lines = text.split("\n")
    parsed = parse(text)
    by_version = {d["version"]: d["status"] for d in derived}
    for milestone in parsed["milestones"]:
        status = by_version.get(milestone["version"])
        if status is None:
            continue
        if milestone["status_line"] is not None:
            i = milestone["status_line"]
            lines[i] = re.sub(r"(Status\s*:\s*).*$", lambda m: m.group(1) + status, lines[i],
                              flags=re.IGNORECASE)
        else:
            lines.insert(milestone["line"] + 1, "")
            lines.insert(milestone["line"] + 2, "- Status: %s" % status)
            return render("\n".join(lines), derived)  # line numbers moved: parse again
    for row in parsed["versions"]:
        status = by_version.get(row["version"])
        if status is None:
            continue
        cells = lines[row["line"]].split("|")
        if len(cells) >= 6:
            cells[4] = " %s " % status
            lines[row["line"]] = "|".join(cells)
    return "\n".join(lines)


def roadmap_path(prd_path):
    """`roadmap.md` beside the PRD hub."""
    return os.path.join(os.path.dirname(prd_path), "roadmap.md") if prd_path else None
