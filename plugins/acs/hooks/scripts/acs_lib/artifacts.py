"""acs_lib.artifacts — the human-facing ticket documents, and where they live.

Until the skills-independence refactor every ticket document sat in the
state-machine workspace next to the run ledger: ticket.json, design.md, the
plan under phases/code/. The documents a human reads and edits now live in the
repo's docs tree, `<checkout>/<settings.artifacts.tickets_path>/<ID>/`
(default docs/tickets; an explicit null keeps everything in the partition as
before), and the ledger stays where it was: <skill>-state.json,
pipeline-state.json, phase artifacts, verdicts, locks, active-agents,
clarifications.json and tickets-index.json never leave the partition.

  ticket.md      today's ticket.json as YAML front matter (every field but
                 `status`) over a markdown body: `## Description`,
                 `## Acceptance criteria` (a numbered list) and
                 `## Clarifications` (a read-only mirror of clarifications.json)
  design.md, analysis.md, api-contract.md, plan.md, test-cases.md
                 the producer skills' documents, resolved by artifact_path:
                 the docs folder first, then the partition, then the legacy
                 location (/acs:code's old plan phase wrote phases/code/plan.md)

`status` is never stored in ticket.md. derive_status computes it from the
ledger and the archive -- open / in_progress / in_review / done -- the same
way the hooks used to flip it, so a load_ticket caller still sees the field.

WHICH FILE A TICKET LIVES IN. load_ticket reads ticket.md when the ticket's
docs folder holds one, else ticket.json, else the file a ticket.json.moved
pointer names. save_ticket writes ticket.md only when the docs tree is ACTIVE
for this checkout -- tickets_path is not null, the process cwd resolves to a
checkout whose workspace owns the partition, and <checkout>/<tickets_path>/
exists (`acs.py artifacts migrate` creates it) -- and the ticket already lives
there or has no ticket.json yet. A ticket that still has a ticket.json keeps
being written as ticket.json until migrate moves it, so every ticket has
exactly one home and no copy goes stale behind a reader. The workspace check
is what keeps an in-process caller whose cwd is some OTHER checkout (a test
runner, a metrics run from a sibling repo) out of that checkout's docs tree.

Front matter is written in the subset acs_lib.yamlsubset reads back: quoted
strings, integers, booleans, null, block lists and 2-space nested mappings. A
float reads back as a string and an empty mapping as null -- no ticket field
carries either.
"""

import os
import re
import sys

from ._common import DELIVERY_TICKET_SKILLS, GateError, now_iso, read_json, write_json, write_text
from . import repo as _repo
from .settings import load_settings
from . import yamlsubset
from .yamlsubset import YamlSubsetError

DEFAULT_TICKETS_PATH = "docs/tickets"
TICKET_MD_FILENAME = "ticket.md"
TICKET_JSON_FILENAME = "ticket.json"
#: Left in the partition by migrate where ticket.json used to be; names the
#: file the ticket moved to, so a reader that cannot resolve the checkout
#: (no cwd in it) still finds the ticket.
MOVED_POINTER_FILENAME = "ticket.json.moved"
#: Every document artifact_path resolves, ticket.md first.
ARTIFACT_NAMES = ("ticket.md", "design.md", "analysis.md", "api-contract.md", "plan.md", "test-cases.md")
#: Where an artifact lived before the docs tree existed, relative to the
#: partition -- read last, so a ticket planned by /acs:code's old plan phase
#: still resolves. Mirrors acs_lib.gate_inputs.LEGACY_ARTIFACT_PATHS.
LEGACY_ARTIFACT_PATHS = {"plan.md": (os.path.join("phases", "code", "plan.md"),)}
#: (partition-relative source, docs-folder name) copied by migrate.
MIGRATED_ARTIFACTS = (("design.md", "design.md"), (os.path.join("phases", "code", "plan.md"), "plan.md"))

_FRONT_MATTER_ORDER = ("id", "title", "type", "priority", "parent", "children", "external",
                       "assignee", "story_points", "needs_design", "docs_only", "size",
                       "stakes", "lane", "due_date", "created_at", "updated_at")
_BODY_FIELDS = ("description", "acceptance_criteria")
_DERIVED_FIELDS = ("status",)
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
_TICKET_DIR_RE = re.compile(r"^([A-Z][A-Z0-9]*-\d+)")
_SECTION_RE = re.compile(r"^## (.+?)\s*$")
_AC_ITEM_RE = re.compile(r"^\d+\.\s+(.*)$")


# ---------------------------------------------------------------------------
# Where the documents live
# ---------------------------------------------------------------------------

def tickets_path(settings):
    """settings.artifacts.tickets_path: the repo-relative folder, or None when
    the consumer opted out with an explicit null."""
    block = (settings or {}).get("artifacts") or {}
    return block["tickets_path"] if "tickets_path" in block else DEFAULT_TICKETS_PATH


def ticket_docs_root(settings, checkout_root):
    """<checkout_root>/<tickets_path>, or None (opted out, or no checkout)."""
    base = tickets_path(settings)
    if not base or not checkout_root:
        return None
    return os.path.join(checkout_root, base)


def ticket_docs_dir(settings, checkout_root, ticket_id):
    """The ticket's docs folder, or None when the tree is opted out (null) or
    there is no checkout to anchor it to."""
    root = ticket_docs_root(settings, checkout_root)
    return os.path.join(root, ticket_id) if root else None


def artifact_path(settings, checkout_root, tdir, ticket_id, name):
    """Where `name` (design.md, analysis.md, api-contract.md, plan.md,
    test-cases.md, ticket.md) lives for a ticket: the first EXISTING copy in
    the docs folder, the partition, then the legacy partition location; when
    none exists, where a writer should put it -- the docs folder when the tree
    is configured, else the partition. os.path.isfile tells the two apart."""
    docs = ticket_docs_dir(settings, checkout_root, ticket_id)
    candidates = [os.path.join(docs, name)] if docs else []
    candidates.append(os.path.join(tdir, name))
    candidates.extend(os.path.join(tdir, rel) for rel in LEGACY_ARTIFACT_PATHS.get(name, ()))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return candidates[0]


def ticket_id_of(tdir):
    """The ticket id a partition directory names (an archived duplicate is
    suffixed with a timestamp, so match the id prefix)."""
    base = os.path.basename(os.path.normpath(tdir))
    match = _TICKET_DIR_RE.match(base)
    return match.group(1) if match else base


def is_archived_partition(tdir):
    return os.path.basename(os.path.dirname(os.path.normpath(tdir))) == "archive"


# ---------------------------------------------------------------------------
# The checkout view a bare load/save call works from
# ---------------------------------------------------------------------------

def _checkout_view(cwd):
    """What the process cwd says about the docs tree: the checkout root, its
    settings, the tree root and the workspace repo dir the tree belongs to.
    None outside a git checkout; tickets_root/repo_dir None when opted out or
    when the workspace cannot be derived. Never raises."""
    root = _repo.checkout_root(cwd)
    if not root:
        return None
    settings, _sources = load_settings(cwd)
    view = {"checkout_root": root, "settings": settings, "tickets_root": None, "repo_dir": None}
    base = tickets_path(settings)
    if not base:
        return view
    try:
        workspace = settings.get("workspace_path")
        workspace = (os.path.abspath(os.path.expanduser(str(workspace))) if workspace
                     else _repo.default_state_root(cwd))
        repo_id = _repo.repo_partition_id(cwd)
    except GateError:
        return view
    if not repo_id:
        return view
    view["tickets_root"] = os.path.join(root, base)
    view["repo_dir"] = _repo.repo_dir(workspace, repo_id)
    return view


def _current_view():
    try:
        return _checkout_view(os.getcwd())
    except OSError:
        return None


def _partition_in_checkout(tdir, view):
    """Does this checkout's workspace own the partition (active or archived)?"""
    if not view or not view.get("repo_dir"):
        return False
    parent = os.path.realpath(os.path.dirname(os.path.normpath(tdir)))
    owner = os.path.realpath(view["repo_dir"])
    if parent == owner:
        return True
    return os.path.basename(parent) == "archive" and os.path.realpath(os.path.dirname(parent)) == owner


def _docs_dir_for(tdir, view, ticket_id=None):
    if not _partition_in_checkout(tdir, view):
        return None
    return os.path.join(view["tickets_root"], ticket_id or ticket_id_of(tdir))


def _tree_active(view):
    return bool(view and view.get("tickets_root") and os.path.isdir(view["tickets_root"]))


# ---------------------------------------------------------------------------
# ticket.md rendering and parsing
# ---------------------------------------------------------------------------

def _quote(text):
    escaped = (text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
               .replace("\t", "\\t").replace("\r", "\\r"))
    return '"%s"' % escaped


def _scalar(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return _quote(str(value))


def _render_mapping(mapping, indent):
    lines = []
    pad = " " * indent
    for key, value in mapping.items():
        if not isinstance(key, str) or not _KEY_RE.match(key):
            raise ValueError("front matter key %r is outside the YAML subset acs writes" % (key,))
        if isinstance(value, dict):
            lines.append("%s%s:" % (pad, key))
            lines.extend(_render_mapping(value, indent + 2))
        elif isinstance(value, list):
            if value:
                lines.append("%s%s:" % (pad, key))
                lines.extend(_render_list(value, indent + 2))
            else:
                lines.append("%s%s: []" % (pad, key))
        else:
            lines.append("%s%s: %s" % (pad, key, _scalar(value)))
    return lines


def _render_list(items, indent):
    lines = []
    dash = " " * indent + "-"
    for item in items:
        if isinstance(item, dict) and item:
            sub = _render_mapping(item, indent + 2)
            lines.append("%s %s" % (dash, sub[0].lstrip()))
            lines.extend(sub[1:])
        elif isinstance(item, list) and item:
            lines.append(dash)
            lines.extend(_render_list(item, indent + 2))
        elif isinstance(item, list):
            lines.append("%s []" % dash)
        elif isinstance(item, dict):
            lines.append("%s null" % dash)
        else:
            lines.append("%s %s" % (dash, _scalar(item)))
    return lines


def render_front_matter(mapping):
    """The lines of a front-matter block (without the `---` fences)."""
    return _render_mapping(mapping, 0)


def _render_clarifications(entries):
    entries = [e for e in (entries or []) if isinstance(e, dict)]
    if not entries:
        return ["_None recorded._"]
    lines = []
    for entry in entries:
        tags = [str(entry.get("status") or "open")]
        if entry.get("source"):
            tags.append(str(entry["source"]))
        lines.append("- **%s** (%s): %s" % (entry.get("id") or "?", ", ".join(tags),
                                            str(entry.get("question") or "").strip()))
        if entry.get("answer"):
            lines.append("  - answer: %s" % str(entry["answer"]).strip())
    return lines


def render_ticket_md(ticket, clarifications=None):
    """ticket.md for a ticket dict: front matter (every field but status,
    description and acceptance_criteria) over the three body sections.
    `clarifications` is the clarifications.json entry list, mirrored read-only."""
    front = {key: ticket[key] for key in _FRONT_MATTER_ORDER if key in ticket}
    for key in sorted(ticket):
        if key not in front and key not in _BODY_FIELDS and key not in _DERIVED_FIELDS:
            front[key] = ticket[key]
    lines = ["---"] + render_front_matter(front) + ["---", ""]
    lines.append("# %s — %s" % (ticket.get("id") or "", ticket.get("title") or ""))
    lines += ["", "## Description", ""]
    description = str(ticket.get("description") or "")
    if description:
        lines.extend(description.splitlines())
    lines += ["", "## Acceptance criteria", ""]
    for number, item in enumerate(ticket.get("acceptance_criteria") or [], 1):
        parts = str(item).splitlines() or [""]
        lines.append("%d. %s" % (number, parts[0]))
        lines.extend("   " + part for part in parts[1:])
    lines += ["", "## Clarifications", ""]
    lines.extend(_render_clarifications(clarifications))
    return "\n".join(lines) + "\n"


def _sections(body):
    sections, current = {}, None
    for line in body.splitlines():
        match = _SECTION_RE.match(line)
        if match:
            current = match.group(1).strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _parse_criteria(lines):
    items = []
    for line in lines:
        match = _AC_ITEM_RE.match(line)
        if match:
            items.append(match.group(1))
        elif items and line.strip() and line[:1].isspace():
            items[-1] += "\n" + line.strip()
    return items


def parse_ticket_md(text):
    """The ticket dict a ticket.md encodes -- front matter fields plus
    description and acceptance_criteria from the body; no status (derive it).
    Raises YamlSubsetError when the front matter is missing or malformed."""
    front, body = yamlsubset.split_front_matter(text)
    if front is None:
        raise YamlSubsetError("ticket.md has no front matter block", 1)
    ticket = dict(front)
    sections = _sections(body)
    ticket["description"] = "\n".join(sections.get("description", [])).strip()
    ticket["acceptance_criteria"] = _parse_criteria(sections.get("acceptance criteria", []))
    return ticket


# ---------------------------------------------------------------------------
# Derived status
# ---------------------------------------------------------------------------

def _ledger_steps(tdir):
    ledger = read_json(os.path.join(tdir, "pipeline-state.json"))
    steps = ledger.get("steps") if isinstance(ledger, dict) else None
    return steps if isinstance(steps, dict) else {}


def _recorded_pr(tdir, skill):
    state = read_json(_repo.state_path(tdir, skill))
    states = state.get("states") if isinstance(state, dict) else None
    return bool(isinstance(states, dict) and states.get("pr"))


def _children_view(tdir, fields):
    """For an epic with children: 'done' when the index says every child is
    done, 'active' when any child has started, else 'open'; None otherwise.
    Mirrors what _epic_auto_done and skill-start's parent flip used to write."""
    if not isinstance(fields, dict) or fields.get("type") != "epic":
        return None
    children = [c for c in (fields.get("children") or []) if isinstance(c, str)]
    if not children:
        return None
    index = read_json(os.path.join(os.path.dirname(os.path.normpath(tdir)), "tickets-index.json"))
    entries = index.get("tickets") if isinstance(index, dict) else None
    entries = entries if isinstance(entries, dict) else {}
    statuses = [(entries.get(child) or {}).get("status") for child in children]
    if all(status == "done" for status in statuses):
        return "done"
    if any(status and status != "open" for status in statuses):
        return "active"
    return "open"


def _own_fields(tdir):
    """The ticket's own type and children when the caller did not pass them:
    the index entry when it has one, else the ticket file itself (parsed, not
    derived -- this is what derive_status is computing)."""
    index = read_json(os.path.join(os.path.dirname(os.path.normpath(tdir)), "tickets-index.json"))
    entries = index.get("tickets") if isinstance(index, dict) else None
    entry = (entries or {}).get(ticket_id_of(tdir)) if isinstance(entries, dict) else None
    if isinstance(entry, dict) and entry.get("type"):
        return entry
    kind, path = ticket_source(tdir)
    doc = None
    if kind == "ticket.json":
        doc = read_json(path)
    elif kind:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = parse_ticket_md(fh.read())
        except (OSError, YamlSubsetError):
            doc = None
    return doc if isinstance(doc, dict) else (entry if isinstance(entry, dict) else {})


def derive_status(tdir, ticket=None):
    """open / in_progress / in_review / done from the ledger and the archive:

      done         the partition is archived, merge-pr completed, or (an epic)
                   every child is done in the index
      in_review    create-pr completed, or a delivery-ticket skill completed
                   with a PR recorded in its states
      in_progress  any step but create-ticket has a status other than skipped,
                   or (an epic) a child has started
      open         otherwise

    `ticket` is the ticket's fields when the caller has them (the epic rule
    needs type and children); else they are read from the index, or from the
    ticket file when the index has no entry."""
    if is_archived_partition(tdir):
        return "done"
    steps = _ledger_steps(tdir)

    def status_of(step):
        entry = steps.get(step)
        return entry.get("status") if isinstance(entry, dict) else None

    if status_of("merge-pr") == "completed":
        return "done"
    children = _children_view(tdir, ticket if isinstance(ticket, dict) else _own_fields(tdir))
    if children == "done":
        return "done"
    if status_of("create-pr") == "completed":
        return "in_review"
    if any(status_of(skill) == "completed" and _recorded_pr(tdir, skill) for skill in DELIVERY_TICKET_SKILLS):
        return "in_review"
    if children == "active":
        return "in_progress"
    started = [step for step, entry in steps.items()
               if step != "create-ticket" and isinstance(entry, dict)
               and entry.get("status") and entry.get("status") != "skipped"]
    return "in_progress" if started else "open"


# ---------------------------------------------------------------------------
# load / save (acs_lib.state routes here)
# ---------------------------------------------------------------------------

def _read_ticket_md(path, tdir):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        ticket = parse_ticket_md(text)
    except (OSError, YamlSubsetError) as exc:
        sys.stderr.write("acs: warning: unreadable/corrupt ticket.md at %s (%s) — treated as absent\n"
                         % (path, exc))
        return None
    ticket["status"] = derive_status(tdir, ticket)
    return ticket


def ticket_source(tdir, view=None):
    """(kind, path) for the file load_ticket would read: ("ticket.md", path)
    from the docs folder, ("ticket.json", path), ("pointer", path) via
    ticket.json.moved, or (None, None)."""
    view = _current_view() if view is None else view
    docs = _docs_dir_for(tdir, view)
    if docs and os.path.isfile(os.path.join(docs, TICKET_MD_FILENAME)):
        return "ticket.md", os.path.join(docs, TICKET_MD_FILENAME)
    json_path = os.path.join(tdir, TICKET_JSON_FILENAME)
    if os.path.isfile(json_path):
        return "ticket.json", json_path
    pointer = read_json(os.path.join(tdir, MOVED_POINTER_FILENAME))
    moved_to = pointer.get("moved_to") if isinstance(pointer, dict) else None
    if isinstance(moved_to, str) and os.path.isfile(moved_to):
        return "pointer", moved_to
    return None, None


def load_ticket(tdir):
    """The ticket dict, status included -- from ticket.md when the docs folder
    holds one, else ticket.json, else the moved pointer's target; None when
    there is nothing readable (reported, never raised)."""
    kind, path = ticket_source(tdir)
    if kind == "ticket.json":
        return read_json(path)
    if kind in ("ticket.md", "pointer"):
        return _read_ticket_md(path, tdir)
    return read_json(os.path.join(tdir, TICKET_JSON_FILENAME))


def _clarifications(tdir):
    ledger = read_json(os.path.join(tdir, "clarifications.json"))
    entries = ledger.get("clarifications") if isinstance(ledger, dict) else None
    return entries if isinstance(entries, list) else []


def md_target(tdir, ticket_id=None, view=None):
    """Where save_ticket writes ticket.md, or None when it writes ticket.json:
    the tree must be active for this checkout and own the partition, and the
    ticket must already live there or have no ticket.json to leave behind."""
    view = _current_view() if view is None else view
    if not _tree_active(view):
        return None
    docs = _docs_dir_for(tdir, view, ticket_id)
    if not docs:
        return None
    target = os.path.join(docs, TICKET_MD_FILENAME)
    if os.path.isfile(target) or not os.path.isfile(os.path.join(tdir, TICKET_JSON_FILENAME)):
        return target
    return None


def save_ticket(tdir, ticket):
    ticket["updated_at"] = now_iso()
    target = md_target(tdir, ticket.get("id") or None)
    if target:
        write_text(target, render_ticket_md(ticket, _clarifications(tdir)))
    else:
        write_json(os.path.join(tdir, TICKET_JSON_FILENAME), ticket)


# ---------------------------------------------------------------------------
# migrate / describe
# ---------------------------------------------------------------------------

def live_partitions(workspace, repo_id):
    """[(ticket_id, tdir)] for every ACTIVE partition (never the archive)
    that holds a ticket.json or the pointer migrate leaves behind."""
    rdir = _repo.repo_dir(workspace, repo_id)
    try:
        names = sorted(os.listdir(rdir))
    except OSError:
        return []
    out = []
    for name in names:
        tdir = os.path.join(rdir, name)
        if not _TICKET_DIR_RE.match(name) or not os.path.isdir(tdir):
            continue
        if any(os.path.isfile(os.path.join(tdir, f)) for f in (TICKET_JSON_FILENAME, MOVED_POINTER_FILENAME)):
            out.append((name, tdir))
    return out


def _copy_text(src, dest):
    with open(src, "r", encoding="utf-8") as fh:
        write_text(dest, fh.read())


def migrate(workspace, repo_id, settings, checkout_root, dry_run=False):
    """Move every live partition's ticket.json into <tickets_path>/<ID>/ticket.md
    once, copy its design.md and legacy plan alongside, and leave a
    ticket.json.moved pointer where ticket.json was. Idempotent: a ticket
    already moved is reported under `already`; a ticket.md already in the
    tree is kept (it is the newer of the two by construction). Creating the
    tree root is what activates the tree for save_ticket. The archive is
    never touched. Refuses (GateError) when opted out or when a partition
    still to move is locked by a session."""
    base = tickets_path(settings)
    if not base:
        raise GateError("artifacts.tickets_path is null — the docs tree is opted out, nothing to migrate")
    if not checkout_root:
        raise GateError("no checkout root to anchor %s to" % base)
    root = os.path.join(checkout_root, base)
    partitions = live_partitions(workspace, repo_id)
    for ticket_id, tdir in partitions:
        if os.path.isfile(os.path.join(tdir, TICKET_JSON_FILENAME)) and os.path.isfile(_repo.lock_path(tdir)):
            raise GateError("refusing to migrate — %s is locked by a session (%s); finish or "
                            "force-unlock it first" % (ticket_id, _repo.lock_path(tdir)))
    report = {"dry_run": bool(dry_run), "tickets_path": base, "docs_root": root,
              "migrated": [], "already": [], "actions": []}

    def act(ticket_id, action, name, path):
        report["actions"].append({"ticket": ticket_id, "action": action, "file": name, "path": path})

    if not dry_run:
        os.makedirs(root, exist_ok=True)
    for ticket_id, tdir in partitions:
        docs = os.path.join(root, ticket_id)
        json_path = os.path.join(tdir, TICKET_JSON_FILENAME)
        md_path = os.path.join(docs, TICKET_MD_FILENAME)
        if os.path.isfile(json_path):
            ticket = read_json(json_path)
            if not isinstance(ticket, dict):
                act(ticket_id, "skip-corrupt", TICKET_JSON_FILENAME, json_path)
                continue
            if os.path.isfile(md_path):
                act(ticket_id, "keep", TICKET_MD_FILENAME, md_path)
            else:
                act(ticket_id, "render", TICKET_MD_FILENAME, md_path)
                if not dry_run:
                    write_text(md_path, render_ticket_md(ticket, _clarifications(tdir)))
            pointer_path = os.path.join(tdir, MOVED_POINTER_FILENAME)
            act(ticket_id, "pointer", MOVED_POINTER_FILENAME, pointer_path)
            act(ticket_id, "remove", TICKET_JSON_FILENAME, json_path)
            if not dry_run:
                write_json(pointer_path, {"ticket_id": ticket_id, "moved_to": md_path,
                                          "relative": os.path.join(base, ticket_id, TICKET_MD_FILENAME),
                                          "migrated_at": now_iso()})
                os.unlink(json_path)
            report["migrated"].append(ticket_id)
        else:
            report["already"].append(ticket_id)
        for rel, name in MIGRATED_ARTIFACTS:
            src, dest = os.path.join(tdir, rel), os.path.join(docs, name)
            if os.path.isfile(src) and not os.path.isfile(dest):
                act(ticket_id, "copy", name, dest)
                if not dry_run:
                    _copy_text(src, dest)
    return report


def describe(ctx, ticket_id, tdir):
    """The `acs.py artifacts show` view: where the ticket and each document
    live, whether the tree is active, and the derived status."""
    view = _checkout_view(ctx["cwd"]) if ctx.get("cwd") else _current_view()
    kind, path = ticket_source(tdir, view)
    ticket = None
    if kind == "ticket.json":
        ticket = read_json(path)
    elif kind:
        ticket = _read_ticket_md(path, tdir)
    if not isinstance(ticket, dict):
        raise GateError("no readable ticket for %s (looked for ticket.md in the docs folder, "
                        "ticket.json and %s under %s)" % (ticket_id, MOVED_POINTER_FILENAME, tdir))
    settings, root = ctx.get("settings"), ctx.get("checkout_root")
    found = {}
    for name in ARTIFACT_NAMES[1:]:
        candidate = artifact_path(settings, root, tdir, ticket_id, name)
        found[name] = candidate if os.path.isfile(candidate) else None
    return {"ticket_id": ticket_id, "partition": tdir,
            "docs_dir": ticket_docs_dir(settings, root, ticket_id),
            "active": _tree_active(view), "source": kind, "source_path": path,
            "status": ticket.get("status"), "artifacts": found, "ticket": ticket}
