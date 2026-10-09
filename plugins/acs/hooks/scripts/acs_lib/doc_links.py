"""acs_lib.doc_links — a ticket's links to the documents that exist for it (ADR-0140).

A ticket alone does not carry the design context its implementation needs, and
a local path is not something a tracker can open. This module answers, for a
ticket (or a ticketless feature run), "which repo documents are about this
work?" -- found in the STANDARD LAYOUT (`acs_lib.doc_layout`), so a ticket
minted before ADR-0140 finds them as well -- and turns each into a link to the
remote's DEFAULT BRANCH:

  prd          `<prd_dir>/prd.md` and each feature's own PRD (`<prd_dir>/features/<f>/prd.md`)
  analysis     the feature's living analysis (`<prd_dir>/features/<f>/analysis/`)
  hld          `hld/overview.md`, plus every HLD view whose text names the feature
  lld          the feature's living LLD (`lld/<f>/{api,data,flows,components}/**`)
  design       `lld/*/<id>/tech-design.md` and `api-contract.md`, for the ticket
               and for its parent epic
  development  `<development_dir>/*/<id>/` -- analysis/**, plan.md, test-cases.md

Everything for the feature, with no selection step. A ticket with no features
falls back to its id (`lld/*/<id>/`, `<development_dir>/*/<id>/`, the parent's
records) plus the PRD file itself.

An entry is {kind, path, title, status, version, published, url}. `published`
means the file is in `origin/<default>`'s tree; only then, and only when the
remote has a web host acs knows how to spell, is `url` set. Anything else is
listed as pending -- "not on `<default>` yet" -- and a later refresh (after a
merge) turns it into a link, so no link ever 404s.

The `## References` section a ticket's tracker issue carries is the text
between two markers, rendered by `render_block` and swapped in by
`apply_block`; nothing outside the markers is ever rewritten.
"""

import json
import os
import re
import subprocess
import tempfile
from urllib.parse import quote

from ._common import GateError, _git
from . import changes, doc_layout, yamlsubset
from .doc_sets import LLD_LIVING
from .forge import _render_command, finding
from .repo import remote_segments

START_MARKER = "<!-- acs:references -->"
END_MARKER = "<!-- /acs:references -->"
HEADING = "## References"
#: The kinds, in the order a ticket lists them.
KINDS = ("prd", "analysis", "hld", "lld", "design", "development")
NO_REFERENCES = "_No documents for this ticket's features yet._"
#: `web_base_reason` when the origin's host is not one acs can link to.
NO_WEB_REMOTE = "no-web-remote"
#: A fetch is best effort and must never hold a run up.
FETCH_TIMEOUT = 30
#: The per-change records a design folder holds (the tech design's legacy
#: name is read where the current one is absent).
DESIGN_RECORDS = ("tech-design.md", "api-contract.md")
DEVELOPMENT_RECORDS = ("plan.md", "test-cases.md")

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


# ---------------------------------------------------------------------------
# The remote: web base, default branch, what is published
# ---------------------------------------------------------------------------

def _family(host):
    """`github`, `gitlab`, `bitbucket` or None for a web host."""
    host = (host or "").lower()
    labels = host.split(".")
    if host == "github.com" or host.endswith(".ghe.com") or "github" in labels:
        return "github"
    if "gitlab" in labels:
        return "gitlab"
    if "bitbucket" in labels:
        return "bitbucket"
    return None


def web_base_for_url(url):
    """`https://<host>/<owner>/<repo>` for a remote URL in any spelling (https,
    ssh, scp-style, with `user@` and `.git`), or None when the host is not a
    GitHub (or GitHub Enterprise), GitLab or Bitbucket one."""
    segments = remote_segments(url) if url else []
    if len(segments) < 3 or "." not in segments[0]:
        return None
    host, path = segments[0].lower(), segments[1:]
    family = _family(host)
    if family is None:
        return None
    if path and path[0].isdigit():
        path = path[1:]  # ssh://host:22/owner/repo -- the port, not a path
    if len(path) < 2:
        return None
    if family != "gitlab":
        path = path[-2:]  # GitLab nests groups; the others are owner/repo
    return "https://%s/%s" % (host, "/".join(path))


def web_base(root):
    """The checkout's origin as a web base (see `web_base_for_url`), or None."""
    return web_base_for_url(_git(["config", "--get", "remote.origin.url"], root)) if root else None


def blob_url(base, ref, path, anchor=None):
    """The web URL of `path` at `ref`, or None without a base or a ref."""
    if not (base and ref and path):
        return None
    family = _family(base.split("/")[2] if base.count("/") >= 2 else "")
    infix = {"gitlab": "/-/blob/", "bitbucket": "/src/"}.get(family, "/blob/")
    url = base + infix + quote(ref, safe="/") + "/" + quote(path, safe="/")
    return url + ("#" + anchor if anchor else "")


def default_branch(root):
    """The remote's default branch: `origin/HEAD`'s target, else a `main` or
    `master` that exists (remote first, then local), else None -- never simply
    the branch checked out. `setup_wizard.default_branch` delegates here."""
    if not root:
        return None
    ref = _git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], root)
    if ref:
        return ref.split("/", 1)[1] if "/" in ref else ref
    for name in ("main", "master"):
        for candidate in ("refs/remotes/origin/%s" % name, "refs/heads/%s" % name):
            if _git(["rev-parse", "--verify", "--quiet", candidate], root):
                return name
    return None


def fetch_default(root):
    """Best-effort `git fetch --quiet origin <default>` (no prompt, bounded):
    True when it succeeded, False otherwise -- never raises."""
    if not root or not _git(["config", "--get", "remote.origin.url"], root):
        return False
    branch = default_branch(root)
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        proc = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "origin"]
                              + ([branch] if branch else []),
                              cwd=root, capture_output=True, env=env, timeout=FETCH_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def published(root, paths, fetch=False):
    """{"published": {path: bool}, "remote_checked", "default_branch", "ref"}:
    which of `paths` are in `origin/<default>`'s tree. `fetch` refreshes that
    ref first (best effort; `remote_checked` says whether it worked). With no
    `origin/<default>` ref nothing counts as published."""
    checked = fetch_default(root) if fetch else False
    branch = default_branch(root) if root else None
    ref = "refs/remotes/origin/%s" % branch if branch else None
    found = {p: False for p in paths}
    if ref and _git(["rev-parse", "--verify", "--quiet", ref + "^{tree}"], root):
        try:
            blobs = changes.blobs(root, ref, list(dict.fromkeys(paths)))
        except GateError:
            blobs = {}
        found = {p: bool(blobs.get(p)) for p in paths}
    else:
        ref = None
    return {"published": found, "remote_checked": checked, "default_branch": branch,
            "ref": ref}


# ---------------------------------------------------------------------------
# Headings and anchors
# ---------------------------------------------------------------------------

def github_anchor(heading, seen):
    """GitHub's anchor for a heading: lowercase, everything but word
    characters, spaces and hyphens dropped, spaces turned into hyphens, and
    `-1`, `-2`, ... on a repeat. `seen` counts the anchors already used in
    the document and is updated."""
    text = _LINK_RE.sub(r"\1", heading or "").strip().lower()
    base = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
    count = seen.get(base, 0)
    seen[base] = count + 1
    return base if count == 0 else "%s-%d" % (base, count)


def headings(text):
    """[(level, text, anchor)] for every ATX heading outside a code fence, in
    document order (front matter skipped)."""
    out, seen, fence = [], {}, None
    for line in _body(text).splitlines():
        opened = _FENCE_RE.match(line)
        if opened:
            fence = None if fence == opened.group(1) else (fence or opened.group(1))
            continue
        if fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            out.append((len(match.group(1)), match.group(2), github_anchor(match.group(2), seen)))
    return out


# ---------------------------------------------------------------------------
# Reading one document
# ---------------------------------------------------------------------------

def _body(text):
    try:
        _front, body = yamlsubset.split_front_matter(text)
    except Exception:  # noqa: BLE001 -- a malformed block is still a document
        return text
    return body


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def _meta(path):
    """(title, status, version): the ADR-0122 front matter when present, the
    first H1 (else the file name) as the title."""
    text = _read(path)
    try:
        front, body = yamlsubset.split_front_matter(text)
    except Exception:  # noqa: BLE001 -- listed without a status, never refused
        front, body = None, _strip_block(text)
    front = front if isinstance(front, dict) else {}
    title = None
    for level, heading, _anchor in headings(body):
        if level == 1:
            title = heading
            break
    status = front.get("status") if isinstance(front.get("status"), str) else None
    version = front.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        version = None
    return title or os.path.basename(path), status, version


def _strip_block(text):
    """The text after a leading `---` block that did not parse."""
    if text.startswith("---"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            return parts[1].split("\n", 1)[1] if "\n" in parts[1] else ""
    return text


# ---------------------------------------------------------------------------
# Collection from the standard layout
# ---------------------------------------------------------------------------

def _abs(root, rel):
    return os.path.join(root, *[p for p in rel.split("/") if p and p != "."])


def _join(*parts):
    return "/".join(p.strip("/") for p in parts if p and p != ".")


def _md_files(root, rel, recursive):
    folder = _abs(root, rel)
    if not os.path.isdir(folder):
        return []
    out = []
    for base, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".")) if recursive else []
        for name in files:
            if name.endswith(".md") and not name.lower().endswith(".evidence.md"):
                out.append(os.path.relpath(os.path.join(base, name), root).replace(os.sep, "/"))
    return out


def _subdirs(root, rel):
    folder = _abs(root, rel)
    if not os.path.isdir(folder):
        return []
    return sorted(d for d in os.listdir(folder)
                  if not d.startswith(".") and os.path.isdir(os.path.join(folder, d)))


def _entry(kind, file, anchor=None, title=None):
    return {"kind": kind, "file": file, "anchor": anchor, "title": title}


def _prd_entries(root, prd_rel, prd, features):
    """The product PRD (the hub) once, then each feature's own PRD
    (`features/<f>/prd.md`, ADR-0142) that exists; `names` maps a feature to
    the title its PRD opens with, for the HLD documents that name it."""
    out, names = [_entry("prd", prd_rel)], {}
    for feature in features:
        rel = _join(prd, doc_layout.FEATURES_DIRNAME, feature, doc_layout.FEATURE_PRD_FILENAME)
        if not os.path.isfile(_abs(root, rel)):
            continue
        title = _meta(_abs(root, rel))[0]
        out.append(_entry("prd", rel, None, title))
        names[feature] = re.sub(r"(?i)^\W*(feature|prd)\s*[:—–-]\s*", "", title).strip()
    return out, names


def _names_feature(text, feature, name):
    lowered = text.lower()
    for term in filter(None, (feature, name)):
        if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(term.lower()), lowered):
            return True
    return False


def _hld_entries(root, arch, features, names):
    hld = _join(arch, "hld")
    out = []
    overview = _join(hld, "overview.md")
    if os.path.isfile(_abs(root, overview)):
        out.append(_entry("hld", overview))
    for rel in _md_files(root, hld, recursive=False):
        if os.path.basename(rel).lower() in ("overview.md", "readme.md"):
            continue
        text = _read(_abs(root, rel))
        if any(_names_feature(text, f, names.get(f)) for f in features):
            out.append(_entry("hld", rel))
    return out


def _feature_entries(root, dirs, features):
    """prd, analysis, hld and lld for `features`."""
    prd, arch = dirs["prd"], dirs["architecture"]
    prd_file = _join(prd, "prd.md")
    out, names = [], {}
    if os.path.isfile(_abs(root, prd_file)):
        out, names = _prd_entries(root, prd_file, prd, features)
    for feature in features:
        folder = _join(prd, doc_layout.FEATURES_DIRNAME, feature)
        legacy = _join(folder, doc_layout.LEGACY_ANALYSIS_FILENAME)
        if os.path.isfile(_abs(root, legacy)):
            out.append(_entry("analysis", legacy))
        out += [_entry("analysis", rel) for rel in
                _md_files(root, _join(folder, doc_layout.ANALYSIS_DIRNAME), recursive=False)]
        for sub in sorted(LLD_LIVING):
            out += [_entry("lld", rel) for rel in _md_files(
                root, _join(arch, doc_layout.LLD_DIRNAME, feature, sub), recursive=True)]
    return out + _hld_entries(root, arch, features, names)


def _design_entries(root, arch, key):
    lld = _join(arch, doc_layout.LLD_DIRNAME)
    out = []
    for feature in _subdirs(root, lld):
        folder = _join(lld, feature, key)
        if not os.path.isdir(_abs(root, folder)):
            continue
        for name in DESIGN_RECORDS:
            for candidate in (name,) + doc_layout.legacy_names(name):
                rel = _join(folder, candidate)
                if os.path.isfile(_abs(root, rel)):
                    out.append(_entry("design", rel))
                    break
    return out


def _development_entries(root, dev, key):
    out = []
    for feature in _subdirs(root, dev):
        folder = _join(dev, feature, key)
        if not os.path.isdir(_abs(root, folder)):
            continue
        out += [_entry("development", rel) for rel in _md_files(
            root, _join(folder, doc_layout.ANALYSIS_DIRNAME), recursive=True)]
        for name in (doc_layout.LEGACY_ANALYSIS_FILENAME,) + DEVELOPMENT_RECORDS:
            rel = _join(folder, name)
            if os.path.isfile(_abs(root, rel)):
                out.append(_entry("development", rel))
    return out


def _sort_key(ref):
    folder, _slash, name = ref["path"].rpartition("/")
    return (KINDS.index(ref["kind"]),
            folder + "/" + ("\0" if name.lower() == "readme.md" else name))


def dedupe(refs):
    """Each (kind, path) once, ordered by kind then path (a README first in its folder)."""
    unique = {}
    for ref in refs:
        unique.setdefault((ref["kind"], ref["path"]), ref)
    return sorted(unique.values(), key=_sort_key)


def _collect(root, settings, ticket_id=None, parent=None, features=()):
    dirs = {kind: doc_layout.resolve_dir(root, kind, settings)["path"]
            for kind in doc_layout.KINDS}
    features = list(dict.fromkeys(f for f in features or () if f))
    entries = []
    if features:
        entries += _feature_entries(root, dirs, features)
    elif ticket_id:
        prd_file = _join(dirs["prd"], "prd.md")
        if os.path.isfile(_abs(root, prd_file)):
            entries.append(_entry("prd", prd_file))
    for key in (ticket_id, parent):
        if key:
            entries += _design_entries(root, dirs["architecture"], key)
    if ticket_id:
        entries += _development_entries(root, dirs["development"], ticket_id)
    return entries


def report(ctx, ticket=None, features=None, parent=None, fetch=False):
    """{"references", "default_branch", "web_base", "web_base_reason",
    "remote_checked"} for a ticket (its features, its own records and its
    parent epic's), or -- with no ticket -- for `features` (plus `parent`'s
    records when one is named)."""
    root = (ctx or {}).get("checkout_root")
    settings = (ctx or {}).get("settings")
    if ticket is not None:
        ticket = ticket if isinstance(ticket, dict) else {}
        features = ticket.get("features") or []
        entries = _collect(root, settings, ticket.get("id"), ticket.get("parent"), features)
    else:
        entries = _collect(root, settings, None, parent, features or [])
    files = list(dict.fromkeys(e["file"] for e in entries))
    state = published(root, files, fetch=fetch) if root else {
        "published": {}, "remote_checked": False, "default_branch": None}
    base = web_base(root)
    refs = []
    for entry in entries:
        title, status, version = _meta(_abs(root, entry["file"]))
        on_default = bool(state["published"].get(entry["file"]))
        refs.append({
            "kind": entry["kind"],
            "path": entry["file"] + ("#" + entry["anchor"] if entry["anchor"] else ""),
            "title": entry["title"] or title,
            "status": status,
            "version": version,
            "published": on_default,
            "url": blob_url(base, state["default_branch"], entry["file"], entry["anchor"])
            if on_default else None,
        })
    return {"references": dedupe(refs), "default_branch": state["default_branch"],
            "web_base": base, "web_base_reason": None if base else NO_WEB_REMOTE,
            "remote_checked": state["remote_checked"]}


def references_for_ticket(ctx, ticket, fetch=False):
    """The reference entries for a ticket (see `report`)."""
    return report(ctx, ticket=ticket, fetch=fetch)["references"]


def references_for_features(ctx, features, parent=None, fetch=False):
    """The same set for a ticketless feature run: no ticket's own records."""
    return report(ctx, features=features, parent=parent, fetch=fetch)["references"]


# ---------------------------------------------------------------------------
# The ## References block
# ---------------------------------------------------------------------------

def _describe(ref):
    meta = []
    if ref.get("version") is not None:
        meta.append("v%s" % ref["version"])
    if ref.get("status"):
        meta.append(str(ref["status"]))
    return ref.get("kind") + (", " + " ".join(meta) if meta else "")


def render_block(refs, default_branch):
    """The markdown between the markers: one bullet per entry -- a link when
    it is published, its path and a pending note when it is not."""
    if not refs:
        return NO_REFERENCES
    lines = []
    for ref in refs:
        if ref.get("url"):
            title = str(ref.get("title") or ref.get("path")).replace("[", "\\[").replace("]", "\\]")
            lines.append("- [%s](%s): %s" % (title, ref["url"], _describe(ref)))
        elif ref.get("published"):
            lines.append("- `%s`: %s" % (ref.get("path"), _describe(ref)))
        else:
            lines.append("- `%s`: %s, pending: not on %s yet" % (
                ref.get("path"), ref.get("kind"),
                "`%s`" % default_branch if default_branch else "the default branch"))
    return "\n".join(lines)


def current_block(markdown):
    """The text between the markers, or None when there are none."""
    text = markdown or ""
    start = text.find(START_MARKER)
    end = text.find(END_MARKER, start + 1) if start != -1 else -1
    if start == -1 or end == -1:
        return None
    return text[start + len(START_MARKER):end].strip("\n")


def apply_block(markdown, block):
    """`markdown` with `block` between the markers. Markers present: only what
    is between them changes. No markers but a `## References` heading: they go
    right under it. Neither: a `## References` section is added before the
    trailing `acs-ticket:` line, else at the end. Idempotent."""
    text = markdown or ""
    inner = "\n%s\n" % (block or "").strip("\n")
    start = text.find(START_MARKER)
    if start != -1:
        end = text.find(END_MARKER, start)
        if end != -1:
            return text[:start + len(START_MARKER)] + inner + text[end:]
        cut = start + len(START_MARKER)
        return text[:start] + START_MARKER + inner + END_MARKER + text[cut:]
    section = START_MARKER + inner + END_MARKER + "\n"
    heading = re.search(r"(?m)^## References[ \t]*$", text)
    if heading:
        rest = text[heading.end():].lstrip("\n")
        return text[:heading.end()] + "\n\n" + section + ("\n" + rest if rest else "")
    lines = text.splitlines(True)
    tail = [i for i, line in enumerate(lines) if line.strip()]
    if tail and lines[tail[-1]].startswith("acs-ticket:"):
        head = "".join(lines[:tail[-1]]).rstrip("\n")
        return (head + "\n\n" if head else "") + HEADING + "\n\n" + section + "\n" \
            + "".join(lines[tail[-1]:])
    head = text.rstrip("\n")
    return (head + "\n\n" if head else "") + HEADING + "\n\n" + section


def write_body_block(path, refs, default_branch):
    """Apply the block to the body file at `path`; True when it changed."""
    with open(path, encoding="utf-8") as fh:
        body = fh.read()
    updated = apply_block(body, render_block(refs, default_branch))
    if updated == body:
        return False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(updated)
    return True


def refresh_issue(gh, key, block, dry_run=False):
    """Read issue `key`'s body, swap the marker block for `block`, and write it
    back when it changed. NON-CRITICAL (ADR-0088): a failed or unreadable gh
    call is one `info` finding, never a stop. Returns {changed, edited,
    findings}."""
    findings = []
    out = {"changed": False, "edited": False, "findings": findings}
    view = ["gh", "issue", "view", str(key), "--json", "body"]
    code, stdout, stderr = gh(view)
    body = None
    if code == 0:
        try:
            body = json.loads(stdout or "").get("body")
        except (ValueError, AttributeError):
            body = None
    if not isinstance(body, str):
        detail = (stderr or stdout or "").strip() if code != 0 else \
            "gh printed no issue body (got %r)" % (stdout or "")[:200]
        findings.append(finding("info", "references", "reading issue %s's body failed" % key,
                                command=_render_command(view), error=detail, replayable=True))
        return out
    updated = apply_block(body, block)
    out["changed"] = updated != body
    if not out["changed"] or dry_run:
        return out
    fd, tmp = tempfile.mkstemp(prefix="acs-issue-body-", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(updated)
        edit = ["gh", "issue", "edit", str(key), "--body-file", tmp]
        code, stdout, stderr = gh(edit)
        if code != 0:
            findings.append(finding(
                "info", "references", "updating issue %s's References section failed" % key,
                command=_render_command(["gh", "issue", "edit", str(key), "--body-file",
                                         "<body>"]),
                error=(stderr or stdout or "").strip(), replayable=False))
        else:
            out["edited"] = True
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return out


__all__ = ["START_MARKER", "END_MARKER", "KINDS", "NO_REFERENCES", "NO_WEB_REMOTE",
           "web_base_for_url", "web_base", "blob_url", "default_branch", "fetch_default",
           "published", "github_anchor", "headings", "report",
           "references_for_ticket", "references_for_features", "dedupe", "render_block",
           "current_block", "apply_block", "write_body_block", "refresh_issue"]
