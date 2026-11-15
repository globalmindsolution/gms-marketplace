"""acs_lib.artifacts — the ticket document, its derived status, and the LEGACY
docs/tickets/<ID>/ tree (read-only since ADR-0128).

A ticket lives in the workspace and the tracker only: `<partition>/ticket.json`
is its one home, and every save writes it there. Until ADR-0128 a ticket could
also live in the repo as `docs/tickets/<ID>/ticket.md` (ADR-0090) beside the
producer skills' documents; nothing writes that tree any more. A ticket that
was migrated there still READS -- load_ticket falls back to its ticket.md (and
to the ticket.json.moved pointer) until the first save writes ticket.json back
into the partition, which then wins. A run's documents live in the phase
folders `acs_lib.doc_layout` / `acs_lib.run_docs` resolve, with this tree as
their read fallback.

  ticket.md      the legacy rendering: ticket.json as YAML front matter (every
                 field but `status`) over a markdown body: `## Description`,
                 `## Acceptance criteria` (a numbered list) and
                 `## Clarifications` (a read-only mirror of clarifications.json)

`status` is never stored in ticket.md. derive_status computes it from the
ledger and the archive -- open / in_progress / in_review / done -- the same
way the hooks used to flip it, so a load_ticket caller still sees the field.

THE BODY ROUND-TRIPS VERBATIM. A description is arbitrary markdown and
normally carries its own `## ` headings -- the shipped task/story/epic
description templates are entirely `## `-headed, and one of them opens with
`## Description` -- so the body is not split by scanning forward for the next
`## `. parse_ticket_md finds the two sections that FOLLOW the description
from the end of the body (see _body_sections); neither of them can emit a
`## ` line, so the description survives whatever it contains.

Front matter is written in the subset acs_lib.yamlsubset reads back: quoted
strings, integers, booleans, null, block lists and 2-space nested mappings. A
float reads back as a string and an empty mapping as null -- no ticket field
carries either.
"""

import os
import re
import sys

from ._common import LEGACY_DELIVERY_TICKET_SKILLS, GateError, now_iso, read_json, write_json
from . import repo as _repo
from .settings import load_settings
from . import yamlsubset
from .yamlsubset import YamlSubsetError

#: Where the ticket documents live, relative to the checkout root. Fixed: the
#: hooks own these files and must find them without asking anyone (ADR-0102).
TICKETS_PATH = "docs/tickets"
TICKET_MD_FILENAME = "ticket.md"
TICKET_JSON_FILENAME = "ticket.json"
#: Left in the partition by migrate where ticket.json used to be; names the
#: file the ticket moved to, so a reader that cannot resolve the checkout
#: (no cwd in it) still finds the ticket.
MOVED_POINTER_FILENAME = "ticket.json.moved"
#: Every document artifact_path resolves, ticket.md first.
#: `design.md` is the tech design's name before ADR-0135, kept so a caller
#: naming it still resolves.
ARTIFACT_NAMES = ("ticket.md", "tech-design.md", "design.md", "analysis.md", "api-contract.md",
                  "plan.md", "test-cases.md")
#: Where an artifact lived before the docs tree existed, relative to the
#: partition -- read last, so a ticket planned by /acs:code's old plan phase
#: still resolves. Mirrors acs_lib.gate_inputs.LEGACY_ARTIFACT_PATHS.
LEGACY_ARTIFACT_PATHS = {"plan.md": (os.path.join("phases", "code", "plan.md"),)}
#: A document's name before it was renamed (ADR-0135), read in the docs
#: folder and the partition after the current name.
LEGACY_ARTIFACT_NAMES = {"tech-design.md": ("design.md",)}
#: (partition-relative source, docs-folder name) copied by migrate.
MIGRATED_ARTIFACTS = (("design.md", "design.md"), (os.path.join("phases", "code", "plan.md"), "plan.md"))

#: A bug's severity sits by its priority; its report (ADR-0138) after the
#: dates a planner reads, before the timestamps.
_FRONT_MATTER_ORDER = ("id", "title", "type", "priority", "severity", "parent", "children",
                       "features", "references", "external", "assignee", "story_points",
                       "docs_only", "due_date", "reproduction", "expected", "actual",
                       "environment", "created_at", "updated_at")
_BODY_FIELDS = ("description", "acceptance_criteria")
_DERIVED_FIELDS = ("status",)
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
_TICKET_DIR_RE = re.compile(r"^([A-Z][A-Z0-9]*-\d+)")
_SECTION_RE = re.compile(r"^## (.+?)\s*$")
_AC_ITEM_RE = re.compile(r"^\d+\.\s+(.*)$")
#: The body sections render_ticket_md writes, in order. The description is
#: VERBATIM markdown that routinely carries its own `## ` headings (every
#: shipped description template is `## `-headed), so the two sections after it
#: are located from the END of the body -- see _body_sections.
DESCRIPTION_HEADING = "Description"
CRITERIA_HEADING = "Acceptance criteria"
CLARIFICATIONS_HEADING = "Clarifications"


# ---------------------------------------------------------------------------
# Where the documents live
# ---------------------------------------------------------------------------

def ticket_docs_root(checkout_root):
    """<checkout_root>/docs/tickets, or None when there is no checkout."""
    return os.path.join(checkout_root, TICKETS_PATH) if checkout_root else None


def ticket_docs_dir(checkout_root, ticket_id):
    """The ticket's docs folder, or None when there is no checkout to anchor
    it to."""
    root = ticket_docs_root(checkout_root)
    return os.path.join(root, ticket_id) if root else None


def artifact_path(checkout_root, tdir, ticket_id, name):
    """The LEGACY resolver for a ticket's document (ADR-0128 files a run's
    documents by phase -- `acs_lib.run_docs`): the first EXISTING copy in the
    old docs folder (docs/tickets/<ID>/), the partition, then the legacy
    partition location; when none exists, the partition path. A renamed
    document is looked for under its old name too, in both places, once the
    new name is found in neither (LEGACY_ARTIFACT_NAMES). It never names a path in the docs tree a
    writer has not already put there."""
    docs = ticket_docs_dir(checkout_root, ticket_id)
    candidates = []
    for n in (name,) + LEGACY_ARTIFACT_NAMES.get(name, ()):
        candidates += ([os.path.join(docs, n)] if docs else []) + [os.path.join(tdir, n)]
    candidates.extend(os.path.join(tdir, rel) for rel in LEGACY_ARTIFACT_PATHS.get(name, ()))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(tdir, name)


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
    None outside a git checkout; tickets_root/repo_dir None when the
    workspace cannot be derived. Never raises."""
    root = _repo.checkout_root(cwd)
    if not root:
        return None
    settings, _sources = load_settings(cwd)
    view = {"checkout_root": root, "settings": settings, "tickets_root": None, "repo_dir": None}
    try:
        workspace = _repo.default_state_root(cwd)
        repo_id = _repo.repo_partition_id(cwd)
    except GateError:
        return view
    if not repo_id:
        return view
    view["tickets_root"] = ticket_docs_root(root)
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


def _one_line(value):
    """A clarification field folded onto one line. The mirror is the LAST body
    section and parsing finds the section headings from the end, so no line it
    emits may start with `## ` -- a recorded answer that contains a markdown
    heading would otherwise look like the start of a section."""
    return " ".join(str(value or "").split())


def _render_clarifications(entries):
    entries = [e for e in (entries or []) if isinstance(e, dict)]
    if not entries:
        return ["_None recorded._"]
    lines = []
    for entry in entries:
        tags = [_one_line(entry.get("status") or "open")]
        if entry.get("source"):
            tags.append(_one_line(entry["source"]))
        lines.append("- **%s** (%s): %s" % (_one_line(entry.get("id")) or "?", ", ".join(tags),
                                            _one_line(entry.get("question"))))
        if entry.get("answer"):
            lines.append("  - answer: %s" % _one_line(entry["answer"]))
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
    lines += ["", "## %s" % DESCRIPTION_HEADING, ""]
    description = str(ticket.get("description") or "")
    if description:
        lines.extend(description.splitlines())
    lines += ["", "## %s" % CRITERIA_HEADING, ""]
    for number, item in enumerate(ticket.get("acceptance_criteria") or [], 1):
        parts = str(item).splitlines() or [""]
        lines.append("%d. %s" % (number, parts[0]))
        lines.extend("   " + part for part in parts[1:])
    lines += ["", "## %s" % CLARIFICATIONS_HEADING, ""]
    lines.extend(_render_clarifications(clarifications))
    return "\n".join(lines) + "\n"


def _heading_lines(lines, name):
    """Every index in `lines` holding the `## <name>` heading (case-folded)."""
    want, found = name.lower(), []
    for index, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if match and match.group(1).strip().lower() == want:
            found.append(index)
    return found


def _trim_blank(lines):
    """The lines without the blank ones render_ticket_md puts around a section."""
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def _body_sections(body):
    """(description lines, acceptance-criteria lines) for a ticket.md body.

    The description is arbitrary markdown copied in verbatim -- every shipped
    description template is itself `## `-headed, and one of them opens with
    `## Description` -- so a forward scan that started a new section on every
    `## ` line would cut the description at its first heading (or restart it),
    silently dropping the rest of a committed document on the next save.

    The boundaries are therefore resolved from the END of the body: the LAST
    `## Clarifications`, the LAST `## Acceptance criteria` before it, and the
    FIRST `## Description` before that. Neither trailing section can emit a
    `## ` line of its own -- a criterion's first line is numbered and its
    continuations are indented, and the clarifications mirror is one folded
    line per entry -- so those last matches are exactly the headings
    render_ticket_md wrote, whatever the description contains."""
    lines = body.splitlines()
    clarifications = _heading_lines(lines, CLARIFICATIONS_HEADING)
    end = clarifications[-1] if clarifications else len(lines)
    criteria = [i for i in _heading_lines(lines, CRITERIA_HEADING) if i < end]
    ac_start = criteria[-1] if criteria else end
    description = [i for i in _heading_lines(lines, DESCRIPTION_HEADING) if i < ac_start]
    body_lines = lines[description[0] + 1:ac_start] if description else []
    return _trim_blank(body_lines), lines[ac_start + 1:end]


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
    description, criteria = _body_sections(body)
    ticket["description"] = "\n".join(description)
    ticket["acceptance_criteria"] = _parse_criteria(criteria)
    return ticket


# ---------------------------------------------------------------------------
# Derived status
# ---------------------------------------------------------------------------

def _run_dir_for_partition(tdir):
    """The run over this ticket, from its partition path alone.

    A ticket is a run SUBJECT now, not the partition a run writes into (§4.2):
    the ledger lives at `<repo>/runs/<run-id>/run.json`, and a ticket-subject
    run's id IS the ticket id. Derived from the path because the callers here
    have a partition and nothing else -- an active partition is
    `<repo>/<ID>`, an archived one `<repo>/archive/<ID>`."""
    from .run import run_dir
    normalized = os.path.normpath(tdir)
    ticket_id = os.path.basename(normalized)
    parent = os.path.dirname(normalized)
    if os.path.basename(parent) == "archive":
        parent = os.path.dirname(parent)
    return run_dir(parent, ticket_id)


def _ledger_steps(tdir):
    from .run import RUN_FILENAME
    ledger = read_json(os.path.join(_run_dir_for_partition(tdir), RUN_FILENAME))
    steps = ledger.get("steps") if isinstance(ledger, dict) else None
    return steps if isinstance(steps, dict) else {}


def _recorded_pr(tdir, skill):
    from .step import state_path as _step_state_path
    state = read_json(_step_state_path(_run_dir_for_partition(tdir), skill))
    states = state.get("states") if isinstance(state, dict) else None
    return bool(isinstance(states, dict) and states.get("pr"))


def _children_view(tdir, fields):
    """For an epic with children: 'done' when the index says every child is
    done, 'active' when any child has started, else 'open'; None otherwise.
    Mirrors what _epic_auto_done and the retired skill-start.py's parent flip
    used to write."""
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


#: Steps that make or restructure tickets rather than work on one: neither
#: starts the ticket (ADR-0138 -- a breakdown mints an epic's children, and
#: the epic turns in_progress when a CHILD starts).
TICKET_MAKING_STEPS = ("create-ticket", "breakdown-ticket")


def derive_status(tdir, ticket=None):
    """open / in_progress / in_review / done from the ledger and the archive:

      done         the partition is archived, merge-pr completed, or (an epic)
                   every child is done in the index
      in_review    create-pr completed, or a delivery-ticket skill completed
                   with a PR recorded in its states
      in_progress  any step but the ticket-making ones (TICKET_MAKING_STEPS)
                   has a status other than skipped, or (an epic) a child has
                   started
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
    # A delivery ticket minted before ADR-0127 recorded its own PR.
    if any(status_of(skill) == "completed" and _recorded_pr(tdir, skill)
           for skill in LEGACY_DELIVERY_TICKET_SKILLS):
        return "in_review"
    if children == "active":
        return "in_progress"
    started = [step for step, entry in steps.items()
               if step not in TICKET_MAKING_STEPS and isinstance(entry, dict)
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
    """(kind, path) for the file load_ticket would read: ("ticket.json", path)
    in the partition first -- the only file a save writes (ADR-0128) -- then
    the legacy ("ticket.md", path) in the docs folder, ("pointer", path) via
    ticket.json.moved, or (None, None)."""
    json_path = os.path.join(tdir, TICKET_JSON_FILENAME)
    if os.path.isfile(json_path):
        return "ticket.json", json_path
    view = _current_view() if view is None else view
    docs = _docs_dir_for(tdir, view)
    if docs and os.path.isfile(os.path.join(docs, TICKET_MD_FILENAME)):
        return "ticket.md", os.path.join(docs, TICKET_MD_FILENAME)
    pointer = read_json(os.path.join(tdir, MOVED_POINTER_FILENAME))
    moved_to = pointer.get("moved_to") if isinstance(pointer, dict) else None
    if isinstance(moved_to, str) and os.path.isfile(moved_to):
        return "pointer", moved_to
    return None, None


#: The ticket statuses in the order a ticket moves through them.
_STATUS_RANK = ("open", "in_progress", "in_review", "done")


def _with_derived_status(tdir, ticket):
    """A ticket.json's stored status, raised to the one its ledger derives.

    Until ADR-0128 a ticket in the docs tree had its status DERIVED (ticket.md
    stores none); every ticket is a ticket.json now, which stores one -- but
    only `--allocate`, create-pr and merge-pr ever wrote it, so a ticket whose
    run had started still read `open`. The later of the two is the answer: a
    status a hook recorded is never lowered, and a started run is never
    reported as not started."""
    if not isinstance(ticket, dict):
        return ticket
    stored = ticket.get("status")
    try:
        derived = derive_status(tdir, ticket)
    except Exception:  # noqa: BLE001 -- a status read never fails a load
        return ticket
    if stored not in _STATUS_RANK or _STATUS_RANK.index(derived) > _STATUS_RANK.index(stored):
        ticket = dict(ticket, status=derived)
    return ticket


def load_ticket(tdir):
    """The ticket dict, status included -- from the partition's ticket.json,
    else the legacy ticket.md in the docs folder, else the moved pointer's
    target; None when there is nothing readable (reported, never raised)."""
    kind, path = ticket_source(tdir)
    if kind == "ticket.json":
        return _with_derived_status(tdir, read_json(path))
    if kind in ("ticket.md", "pointer"):
        return _read_ticket_md(path, tdir)
    return read_json(os.path.join(tdir, TICKET_JSON_FILENAME))




def save_ticket(tdir, ticket):
    """Persist the ticket as `<partition>/ticket.json`, its one home since
    ADR-0128: a ticket is no longer stored in the repo's docs tree, so a save
    never writes docs/tickets/<ID>/ticket.md -- not for a new ticket, and not
    for one migrated there under ADR-0090 (its ticket.md stays as the legacy
    copy, and the ticket.json written here wins from now on)."""
    ticket["updated_at"] = now_iso()
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




def migrate(workspace, repo_id, checkout_root, dry_run=False):
    """RETIRED by ADR-0128. It moved every live partition's ticket.json into
    docs/tickets/<ID>/ticket.md; a ticket is no longer stored in the docs tree,
    so there is nothing to move and nothing is written. The report says so."""
    if not checkout_root:
        raise GateError("no checkout root to anchor %s to" % TICKETS_PATH)
    return {"dry_run": bool(dry_run), "retired": True, "tickets_path": TICKETS_PATH,
            "docs_root": os.path.join(checkout_root, TICKETS_PATH),
            "migrated": [], "already": [ticket_id for ticket_id, _t
                                         in live_partitions(workspace, repo_id)],
            "actions": [],
            "reason": "since ADR-0128 a ticket lives only in the workspace and the tracker; "
                      "docs/tickets/ is read as a legacy fallback and never written"}


def describe(ctx, ticket_id, tdir):
    """The `acs.py artifacts show` view of a ticket with no run named: its
    latest run's documents (acs_lib.run_docs), the ticket and its status."""
    from . import run_docs
    repo = _repo.repo_dir(ctx["workspace"], ctx["repo_id"])
    return run_docs.describe(ctx, rdir=run_docs.latest_run_for_ticket(repo, ticket_id),
                             ticket_id=ticket_id)
