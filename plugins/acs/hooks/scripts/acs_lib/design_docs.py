"""acs_lib.design_docs — the version front matter of a design document (ADR-0122).

Every HLD and LLD document opens with a front-matter block that says where the
design stands against the code:

    ---
    status: proposed        # proposed | approved | implemented | deprecated
    version: 3              # bumped on every change to the document
    tickets: ["SHOP-12"]    # the tickets that changed it, oldest first
    feature: wishlist       # LLD documents only: the PRD feature slug
    status_by: "Ana <ana@example.com>"   # who made the last status move (ADR-0130)
    status_at: "2026-10-05T09:12:00Z"   # when, ISO-8601 UTC
    status_reason: "superseded by v2"   # why -- only when one was given
    ---

A Design skill writes `proposed`; the team's approval of the design PR makes it
`approved`; `/acs:docs-sync`, once the gap analysis finds the code matching,
makes it `implemented`; superseded content is `deprecated`. A status is set here,
through a legal transition, never by hand-editing the block -- the value a later
skill reads is derived from this record, not asserted by an agent.

`set_status_many` moves several documents atomically: every target is checked
first (it exists, its block is valid, the move is legal) and none is written
when any is refused. `list_documents` is the deterministic lister behind
`acs.py design list` and /acs:set-doc-status: the Discovery documents (PRD,
roadmap, each feature's living analysis folder) and the Design documents (HLD, each feature's living
LLD), grouped by phase and doc set, each with the moves it may make. A
change's tech design (ADR-0135, `lld/<f>/<key>/tech-design.md`) is the one
per-run record listed: the hand-off the team approves before implementation,
shown in its feature's LLD group and labelled with its key.
"""

import os
import posixpath
import re

from ._common import GateError, TICKET_ID_RE, _ISO_INSTANT, now_iso
from . import doc_layout, yamlsubset
from .artifacts import render_front_matter
from .doc_sets import LLD_LIVING, doc_order, doc_set

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

#: Who, when and why of the last status move (ADR-0130); written by set_status.
STATUS_META_KEYS = ("status_by", "status_at", "status_reason")
KEY_ORDER = ("status", "version", "tickets", "feature") + STATUS_META_KEYS
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
    for key in ("status_by", "status_reason"):
        if key in front and not (isinstance(front[key], str) and front[key].strip()):
            found.append("%s must be a non-empty string; got %r" % (key, front[key]))
    if "status_at" in front and not (isinstance(front["status_at"], str)
                                     and _ISO_INSTANT.match(front["status_at"])):
        found.append("status_at must be an ISO-8601 instant; got %r" % (front["status_at"],))
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
    if front["status"] != "proposed":
        # Re-opened: the last move's who/when/why describe a status it left.
        for key in STATUS_META_KEYS:
            front.pop(key, None)
    front["status"] = "proposed"
    write(path, front, body)
    return front


def _check_status(status):
    if status not in STATUSES:
        raise GateError("status must be one of %s; got %r" % ("|".join(STATUSES), status))


def _transition(path, status):
    """(front, body) of a document that may move to `status`; GateError otherwise."""
    if not os.path.isfile(path):
        raise GateError("%s: no such document" % path)
    front, body = _load_valid(path)
    if status not in TRANSITIONS[front["status"]]:
        raise GateError("%s: %s -> %s is not a legal transition (from %s: %s)"
                        % (path, front["status"], status, front["status"],
                           ", ".join(TRANSITIONS[front["status"]])))
    return front, body


def _apply(path, front, body, status, ticket, by, at, reason):
    front["status"] = status
    front["tickets"] = _with_ticket(front["tickets"], ticket)
    meta = {"status_by": " ".join(str(by or "").split()), "status_at": at or now_iso(),
            "status_reason": " ".join(str(reason or "").split())}
    for key, value in meta.items():
        # A key not given this time is dropped, never left describing an older move.
        if value:
            front[key] = value
        else:
            front.pop(key, None)
    found = problems(path, front)
    if found:
        raise GateError("%s: %s" % (path, "; ".join(found)))
    write(path, front, body)
    return front


def set_status(path, status, ticket=None, by=None, at=None, reason=None):
    """Move the document to `status` along a legal transition, recording who
    (`status_by`), when (`status_at`, ISO-8601 UTC, now by default) and -- only
    when given -- why (`status_reason`)."""
    _check_status(status)
    front, body = _transition(path, status)
    return _apply(path, front, body, status, ticket, by, at, reason)


def set_status_many(paths, status, ticket=None, by=None, at=None, reason=None):
    """Move every document in `paths` to `status`, or none of them.

    Every target is validated first (exists, valid block, legal move); one
    refusal raises a GateError naming each refused document and why, and no
    document is written. The moves share one `status_at`. A document already
    at `status` is left byte-for-byte as it is and reported `unchanged`: a
    no-op must not rewrite who moved it, when, or why."""
    _check_status(status)
    if at is not None and not _ISO_INSTANT.match(str(at)):
        raise GateError("status_at must be an ISO-8601 instant; got %r" % (at,))
    paths = list(dict.fromkeys(paths))
    loaded, refused = [], []
    for path in paths:
        try:
            loaded.append((path,) + _transition(path, status))
        except GateError as exc:
            refused.append(str(exc))
    if refused:
        raise GateError("refused %d of %d document(s), nothing was written -- %s"
                        % (len(refused), len(paths), " | ".join(refused)))
    at = at or now_iso()
    out = []
    for path, front, body in loaded:
        if front.get("status") == status:
            out.append(dict(front, path=path, unchanged=True))
        else:
            out.append(dict(_apply(path, front, body, status, ticket, by, at, reason),
                            path=path))
    return out


# ---------------------------------------------------------------------------
# The lister (`acs.py design list`, /acs:set-doc-status)
# ---------------------------------------------------------------------------

PHASES = ("discovery", "design")
#: The per-run document the lister shows (ADR-0135).
TECH_DESIGN = "tech-design.md"


def _md_files(folder, recursive):
    if not os.path.isdir(folder):
        return []
    if not recursive:
        return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                      if n.endswith(".md") and os.path.isfile(os.path.join(folder, n)))
    out = []
    for base, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        out.extend(os.path.join(base, n) for n in files if n.endswith(".md"))
    return sorted(out)


def _subdirs(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(d for d in os.listdir(folder)
                  if not d.startswith(".") and os.path.isdir(os.path.join(folder, d)))


def candidates(root, settings=None):
    """[(phase, absolute path)] of every document the lister considers."""
    prd = os.path.join(root, *doc_layout.prd_dir(root, settings).split("/"))
    arch = os.path.join(root, *doc_layout.architecture_dir(root, settings).split("/"))
    out = [("discovery", os.path.join(prd, name)) for name in ("prd.md", "roadmap.md")
           if os.path.isfile(os.path.join(prd, name))]
    features = os.path.join(prd, doc_layout.FEATURES_DIRNAME)
    for f in _subdirs(features):
        # A feature's living analysis: its folder's files (ADR-0133), and the
        # single analysis.md of before it while one is still there.
        legacy = os.path.join(features, f, doc_layout.LEGACY_ANALYSIS_FILENAME)
        if os.path.isfile(legacy):
            out.append(("discovery", legacy))
        out += [("discovery", p) for p in _md_files(
            os.path.join(features, f, doc_layout.ANALYSIS_DIRNAME), recursive=False)]
    out += [("design", p) for p in _md_files(os.path.join(arch, "hld"), recursive=False)]
    lld = os.path.join(arch, doc_layout.LLD_DIRNAME)
    for feature in _subdirs(lld):
        # The living subfolders; lld/<f>/<id>/ holds one change's records, of
        # which only the tech design is versioned for the team's approval.
        for sub in _subdirs(os.path.join(lld, feature)):
            if sub in LLD_LIVING:
                out += [("design", p) for p in
                        _md_files(os.path.join(lld, feature, sub), recursive=True)]
            else:
                tech = os.path.join(lld, feature, sub, TECH_DESIGN)
                if os.path.isfile(tech):
                    out.append(("design", tech))
    return out


def _tech_design_key(rel):
    """The run key of a change's tech design (`.../lld/<f>/<key>/tech-design.md`),
    else None."""
    parts = rel.split("/")
    if len(parts) >= 4 and parts[-1] == TECH_DESIGN and parts[-4] == doc_layout.LLD_DIRNAME \
            and parts[-2] not in LLD_LIVING:
        return parts[-2]
    return None


def _entry(root, path):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    try:
        front, _body = read(path)
    except GateError as exc:
        return rel, None, {"path": rel, "status": None, "version": None,
                           "problems": [str(exc)], "allowed": []}
    found = problems(path, front or None)
    status = (front or {}).get("status")
    allowed = [] if found else [s for s in TRANSITIONS[status] if s != status]
    return rel, front, {"path": rel, "status": status if status in STATUSES else None,
                        "version": (front or {}).get("version"), "problems": found,
                        "allowed": allowed}


def _readme_first(entry):
    """Path order, with a folder's README.md before everything else in it."""
    folder, name = posixpath.split(entry["path"])
    return folder + "/" + ("\0" if name.lower() == "readme.md" else name)


def list_documents(root, phase=None, feature=None, settings=None):
    """{"ok", "groups": [{phase, key, label, feature?, docs: [entry]}]}, Discovery
    then Design, each phase's groups in doc-set order, docs by path. An entry is
    {path (repo-relative), status, version, problems, allowed}; `allowed` is
    the legal moves other than the current status ([] when the document has
    problems -- giving one its first block is `design init`'s job). A README is
    listed only when it carries a status."""
    if phase is not None and phase not in PHASES:
        raise GateError("phase must be one of %s; got %r" % ("|".join(PHASES), phase))
    groups = {}
    for doc_phase, path in candidates(root, settings):
        if phase and doc_phase != phase:
            continue
        rel, front, entry = _entry(root, path)
        if os.path.basename(path).lower() == "readme.md" and not (front or {}).get("status"):
            continue
        key, label = doc_set(rel)
        run_key = _tech_design_key(rel)
        if run_key:
            # A change's tech design joins its feature's LLD group.
            key = key.rsplit("/", 1)[0]
            label = "LLD %s" % key.split("/", 1)[1]
            entry = dict(entry, key=run_key, label="%s tech design" % run_key)
        head = key.split("/")
        doc_feature = head[1] if len(head) > 1 and head[0] == "lld" else \
            head[2] if key.startswith("prd/features/") else None
        if feature and doc_feature != feature.lower():
            continue
        group = groups.setdefault((doc_phase, key), dict(
            {"phase": doc_phase, "key": key, "label": label, "docs": []},
            **({"feature": doc_feature} if doc_feature else {})))
        group["docs"].append(entry)
    ordered = sorted(groups, key=lambda pk: (PHASES.index(pk[0]), doc_order(pk[1])))
    out = []
    for pk in ordered:
        # By path, a folder's README first (an analysis folder opens with it).
        groups[pk]["docs"].sort(key=_readme_first)
        out.append(groups[pk])
    return {"ok": True, "groups": out}
