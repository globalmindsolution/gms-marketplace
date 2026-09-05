"""release_notes_tickets — which tickets a release contains, and what each is
called (extracted from release_notes.py by MAR-531).

The two enumeration sources (merged PRs, and the git log as its fallback), the
PR reference resolver, and the category/title/suffix rendering for one entry.
This is the ticket-enumeration seam the splitting ticket names.
"""


import os
import re

from release_notes_config import _read_json_or_none
from release_notes_git import _parse_iso, _run_git

FIX_WORD_RE = re.compile(r"\b(fix|fixes|fixed|bug|bugfix|repair|regression)\b", re.I)
CATEGORIES = ("Added", "Fixed", "Changed")
_GENERIC_TICKET_PREFIX_RE = r"[A-Z][A-Z0-9]{1,9}"
_PR_SUFFIX_RE = re.compile(r"\s*\(#\d+\)\s*$")


def _ticket_subject_re(ticket_prefix=None):
    """Anchored-at-start `[?<PREFIX>-N]?<sep>` matcher; `ticket_prefix=None` uses the generic shape."""
    prefix_pattern = re.escape(ticket_prefix) if ticket_prefix else _GENERIC_TICKET_PREFIX_RE
    return re.compile(r"^\[?(%s-\d+)\]?[\s:]" % prefix_pattern)


# ---------------------------------------------------------------------------
# draft — archive enumeration, categorization, rendering
# ---------------------------------------------------------------------------

def enumerate_merged_tickets(workspace, tag_time, repo_root=None, base_branch=None,
                              since_tag=None, ticket_prefix=None):
    """Merged-since-boundary tickets from <workspace>/archive/*/ (R6: merge time = last runs[].ended_at),
    extended with a repo-local git-history fallback for tickets a `/acs:merge-pr` archive entry
    never recorded. The archive block's inputs/filters/ordering/output stay byte-identical apart
    from the added `source` field; the fallback only runs when `repo_root` and `base_branch` are
    both supplied, and never overrides an archive-derived id.
    """
    archive_dir = os.path.join(workspace, "archive")
    result = []
    if os.path.isdir(archive_dir):
        tag_dt = _parse_iso(tag_time) if tag_time else None
        for name in sorted(os.listdir(archive_dir)):
            tdir = os.path.join(archive_dir, name)
            if not os.path.isdir(tdir):
                continue

            merge_state = _read_json_or_none(os.path.join(tdir, "merge-pr-state.json"))
            if not isinstance(merge_state, dict):
                continue
            states = merge_state.get("states")
            if not isinstance(states, dict) or states.get("merged") is not True:
                continue
            runs = merge_state.get("runs")
            if not isinstance(runs, list) or not runs or not isinstance(runs[-1], dict):
                continue
            merge_dt = _parse_iso(runs[-1].get("ended_at"))
            if merge_dt is None:
                continue
            if tag_dt is not None and merge_dt <= tag_dt:
                continue

            ticket_json = _read_json_or_none(os.path.join(tdir, "ticket.json"))
            if not isinstance(ticket_json, dict):
                continue
            result.append({
                "id": ticket_json.get("id", name),
                "title": ticket_json.get("title", ""),
                "parent": ticket_json.get("parent"),
                "description": ticket_json.get("description", ""),
                "docs_only": bool(ticket_json.get("docs_only", False)),
                "source": "archive",
            })

    if repo_root and base_branch:
        archive_ids = {t["id"] for t in result}
        result.extend(enumerate_git_log_tickets(
            repo_root, base_branch, since_tag, ticket_prefix=ticket_prefix,
            exclude_ids=archive_ids,
        ))
    return result


def enumerate_git_log_tickets(repo_root, base_branch, since_tag, ticket_prefix=None, exclude_ids=()):
    """Repo-local fallback: recover merged tickets a `/acs:merge-pr` archive entry never recorded.

    Reads `base_branch` commit subjects since `since_tag` (or the full branch history when
    `since_tag` is None, the bootstrap case), matches each subject's leading ticket-ref token,
    keeps the first (newest) commit per id, and skips any id already found via the archive. A
    non-zero `git` exit returns `[]` — enumeration must never raise.
    """
    revision_range = "%s..%s" % (since_tag, base_branch) if since_tag else base_branch
    result = _run_git(repo_root, ["log", "--format=%s", revision_range])
    if result.returncode != 0:
        return []

    pattern = _ticket_subject_re(ticket_prefix)
    seen = set(exclude_ids)
    tickets = []
    for subject in result.stdout.splitlines():
        match = pattern.match(subject)
        if not match:
            continue
        ticket_id = match.group(1)
        if ticket_id in seen:
            continue
        seen.add(ticket_id)

        remainder = _PR_SUFFIX_RE.sub("", subject[match.end():]).strip()
        title = remainder or ticket_id
        tickets.append({
            "id": ticket_id, "title": title, "parent": None, "description": "",
            "docs_only": False, "source": "git-log",
        })
    return tickets


def resolve_pr_ref(workspace, repo_root, ticket_id, base_branch):
    """Primary: archive/<id>/create-pr-state.json. Fallback: git log subject `(#N)` suffix."""
    create_pr_state = _read_json_or_none(
        os.path.join(workspace, "archive", ticket_id, "create-pr-state.json"),
    )
    if isinstance(create_pr_state, dict):
        states = create_pr_state.get("states")
        pr = states.get("pr") if isinstance(states, dict) else None
        if isinstance(pr, dict) and pr.get("number") is not None:
            return pr.get("number"), pr.get("url")

    result = _run_git(repo_root, ["log", "--oneline", "--grep=%s" % ticket_id, base_branch])
    if result.returncode == 0:
        boundary = re.compile(r"\b" + re.escape(ticket_id) + r"\b")
        for line in result.stdout.splitlines():
            if not boundary.search(line):
                continue
            match = re.search(r"\(#(\d+)\)\s*$", line)
            if match:
                return int(match.group(1)), None
    return None, None


def categorize(ticket):
    text = "%s %s" % (ticket.get("title") or "", ticket.get("description") or "")
    if FIX_WORD_RE.search(text):
        return "Fixed"
    if ticket.get("docs_only"):
        return "Changed"
    return "Added"


def _resolve_ticket_title(workspace, ticket_id):
    for candidate in (
        os.path.join(workspace, "archive", ticket_id, "ticket.json"),
        os.path.join(workspace, ticket_id, "ticket.json"),
    ):
        data = _read_json_or_none(candidate)
        if isinstance(data, dict) and data.get("title"):
            return data["title"]
    return ticket_id


def _pr_suffix(ticket):
    if ticket.get("pr_number"):
        return " (#%s)" % ticket["pr_number"]
    return ""
