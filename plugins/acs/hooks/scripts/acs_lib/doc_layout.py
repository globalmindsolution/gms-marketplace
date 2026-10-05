"""acs_lib.doc_layout — where a run's documents live in the repo, one folder per
phase (ADR-0128).

A ticket is no longer stored in the docs tree: it lives in the workspace and
the tracker, and a run's documents are filed by the PHASE that wrote them,
under the PRD feature they belong to:

  Discovery    <prd_dir>/features/<feature>/                analysis.md (the
               feature's living analysis; a standalone, ticketless analysis)
  Design       <architecture_dir>/lld/<feature>/<key>/      design.md, api-contract.md
  Development  <development_dir>/<feature>/<key>/           plan.md, test-cases.md, and
               the analysis of a Development run as analysis.md

`<key>` is the run's ticket id when it has one, else its run id. The three
roots are found deterministically, never asked for:

  prd_dir           settings `docs.prd_dir` -> a `prd.md` CLAUDE.md or the docs
                    index names -> the shallowest `prd.md` in the tree ->
                    `docs/product`
  architecture_dir  settings `docs.architecture_dir` -> the folder holding
                    `hld/tech-stack.md` -> `docs/architecture`
  development_dir   settings `docs.development_dir` -> an existing
                    `docs/development/` -> `docs/development`

Existing `docs/tickets/<ID>/` folders (ADR-0090) stay READABLE: a reader falls
back to them when the phase folder has no such file. Nothing writes there.

Every function here is a pure path computation over the checkout (plus the
settings); nothing is created.
"""

import os
import re

from .settings import docs_path_problem, load_settings

DEFAULT_PRD_DIR = "docs/product"
DEFAULT_ARCHITECTURE_DIR = "docs/architecture"
DEFAULT_DEVELOPMENT_DIR = "docs/development"
#: The legacy ticket docs tree (ADR-0090): read as a fallback, never written.
LEGACY_TICKETS_PATH = "docs/tickets"
FEATURES_DIRNAME = "features"
LLD_DIRNAME = "lld"

#: The per-run documents and the phase folder each is filed under. analysis.md
#: is the one whose side depends on the run: Discovery (the feature root) for
#: a standalone run, Development for a run being delivered.
DOCUMENT_SIDES = {
    "analysis.md": "development",
    "plan.md": "development",
    "test-cases.md": "development",
    "design.md": "design",
    "api-contract.md": "design",
}
DOCUMENT_NAMES = tuple(DOCUMENT_SIDES)

#: Directories a `prd.md` / `hld/tech-stack.md` search never descends into.
_SKIP_DIRS = {"node_modules", "vendor", "venv", "__pycache__", "dist", "build", "target"}
_MAX_DEPTH = 6
_PRD_MENTION = re.compile(r"([A-Za-z0-9_./-]*prd\.md)\b")


def _posix(path):
    return path.replace(os.sep, "/").strip("/")


def _docs_setting(root, settings, key):
    """`docs.<key>` from the settings, when a consumer set one."""
    if settings is None:
        try:
            settings, _found = load_settings(root)
        except Exception:  # noqa: BLE001 -- a path lookup never fails on settings
            settings = {}
    docs = (settings or {}).get("docs")
    value = docs.get(key) if isinstance(docs, dict) else None
    # An invalid value is refused by validate_settings at every gate; a path
    # lookup that meets one anyway discovers the folder instead of obeying it.
    return _posix(value) if value is not None and docs_path_problem(value) is None else None


def _walk(root):
    """(relative dir, file names) under `root`, shallow first, sorted, never
    into a hidden or vendored directory."""
    for base, dirs, files in os.walk(root):
        rel = os.path.relpath(base, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dirs[:] = sorted(d for d in dirs
                         if not d.startswith(".") and d not in _SKIP_DIRS
                         and depth < _MAX_DEPTH)
        yield ("" if rel == "." else _posix(rel)), files


def _shallowest(root, predicate):
    hits = []
    for rel, files in _walk(root):
        for name in files:
            if predicate(rel, name):
                hits.append(rel)
    hits.sort(key=lambda r: (r.count("/") if r else -1, r))
    return hits[0] if hits else None


def prd_dir(root, settings=None):
    """The repo-relative PRD directory (see the module docstring)."""
    configured = _docs_setting(root, settings, "prd_dir")
    if configured or not root:
        return configured or DEFAULT_PRD_DIR
    for index in ("CLAUDE.md", "docs/README.md", "README.md"):
        try:
            with open(os.path.join(root, index), encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        for mention in _PRD_MENTION.findall(text):
            rel = _posix(mention[2:] if mention.startswith("./") else mention)
            if os.path.isfile(os.path.join(root, rel)):
                return os.path.dirname(rel) or "."
    found = _shallowest(root, lambda rel, name: name == "prd.md")
    return found if found is not None else DEFAULT_PRD_DIR


def architecture_dir(root, settings=None):
    """The repo-relative architecture directory: the folder holding
    `hld/tech-stack.md`, else `docs/architecture`."""
    configured = _docs_setting(root, settings, "architecture_dir")
    if configured or not root:
        return configured or DEFAULT_ARCHITECTURE_DIR
    found = _shallowest(root, lambda rel, name: name == "tech-stack.md"
                        and rel.split("/")[-1] == "hld")
    if found is not None:
        parent = os.path.dirname(found)
        return parent or "."
    return DEFAULT_ARCHITECTURE_DIR


def development_dir(root, settings=None):
    """The repo-relative Development directory: `docs.development_dir`, else
    an existing `docs/development/`, else that default."""
    return _docs_setting(root, settings, "development_dir") or DEFAULT_DEVELOPMENT_DIR


def _join(root, *parts):
    rel = "/".join(p for p in parts if p and p != ".")
    return os.path.join(root, *rel.split("/")) if root else None


def feature_dir(root, feature, settings=None):
    """`<root>/<prd_dir>/features/<feature>` (absolute), or None."""
    if not (root and feature):
        return None
    return _join(root, prd_dir(root, settings), FEATURES_DIRNAME, feature)


def feature_analysis_path(root, feature, settings=None):
    """The feature's living analysis: `<prd_dir>/features/<f>/analysis.md`."""
    folder = feature_dir(root, feature, settings)
    return os.path.join(folder, "analysis.md") if folder else None


def design_run_dir(root, feature, key, settings=None):
    """`<architecture_dir>/lld/<feature>/<key>/` (absolute), or None."""
    if not (root and feature and key):
        return None
    return _join(root, architecture_dir(root, settings), LLD_DIRNAME, feature, key)


def development_run_dir(root, feature, key, settings=None):
    """`<development_dir>/<feature>/<key>/` (absolute), or None."""
    if not (root and feature and key):
        return None
    return _join(root, development_dir(root, settings), feature, key)


def legacy_ticket_dir(root, ticket_id):
    """`docs/tickets/<ID>/` -- READ ONLY since ADR-0128."""
    if not (root and ticket_id):
        return None
    return _join(root, LEGACY_TICKETS_PATH, ticket_id)


def document_target(root, name, feature, key, phase="development", settings=None):
    """Where a NEW write of `name` goes for a run, or None when the run has no
    feature yet (the writer must name or confirm one first).

    analysis.md goes to the feature root on a Discovery run and to the
    Development folder otherwise; plan/test-cases to Development; design and
    api-contract to the Design folder."""
    if name not in DOCUMENT_SIDES or not feature:
        return None
    if name == "analysis.md" and phase == "discovery":
        return feature_analysis_path(root, feature, settings)
    if DOCUMENT_SIDES[name] == "design":
        folder = design_run_dir(root, feature, key, settings)
    else:
        folder = development_run_dir(root, feature, key, settings)
    return os.path.join(folder, name) if folder else None


def document_candidates(root, name, feature, key, phase="development", ticket_id=None,
                        settings=None):
    """Every place a READER looks for `name`, in order: the phase folder, then
    (for a Development analysis) nothing else of the feature's, then the legacy
    `docs/tickets/<ID>/` folder."""
    out = []
    target = document_target(root, name, feature, key, phase, settings)
    if target:
        out.append(target)
    legacy = legacy_ticket_dir(root, ticket_id)
    if legacy:
        out.append(os.path.join(legacy, name))
    return out
