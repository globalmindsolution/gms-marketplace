"""acs_lib.prd_link — a ticket's link to the PRD it is created from (ADR-0144).

Product work is made from the PRD, never ahead of it: every epic, story and
bug /acs:create-ticket or /acs:breakdown-ticket mints links the PRD -- its
`features` (feature slugs) and, for the work that delivers specific
requirements, its `requirements`, each `<slug>/R<n>` naming a requirement of
that feature's own PRD (`<prd_dir>/features/<slug>/prd.md`, ADR-0142). A
**task** is technical work -- a CI upgrade, a refactor, a dependency bump --
and may link nothing; what it does link must resolve.

This module only reads the repo. `check_link` returns the problems with a
proposed link (an empty list when it is sound). The rules by ticket type:

  epic, story, bug  the repo has a PRD; at least one feature
  story             at least one requirement too: a story is user-facing
                    value, and the value is a requirement of the PRD
  task              nothing required; a PRD only when it links something
  any type          each linked feature has its own PRD, which is not
                    `deprecated`; every requirement names one of the
                    ticket's features and an `R<n>` its PRD's
                    `## Requirements` section declares

A link to work the PRD does not describe is not minted: the PRD is amended
first (/acs:create-prd), then the ticket is created from it.
"""

import os
import re

from ._common import GateError
from . import doc_layout, yamlsubset

#: `wishlist/R2`: a feature slug and one of its PRD's requirement ids.
REQUIREMENT_RE = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)/(R\d+)$")
#: The ticket types that are product work, made from the PRD; a task may be
#: technical work no PRD feature describes.
LINKED_TYPES = ("epic", "story", "bug")

#: A requirement line of a feature PRD (`- **R1** — ...`), as prd_feature_check.py reads it.
_REQUIREMENT_LINE = re.compile(r"^\s*[-*]\s+\*\*(R\d+)\*\*")
_H2 = re.compile(r"^##\s+(.+?)\s*$")

NO_PRD = ("product work (an epic, a story or a bug) is created from the PRD, and this "
          "repo has none: write it first with /acs:create-prd, then create the ticket "
          "from its features -- a technical task needs no PRD")


def parse_requirements(text):
    """'wishlist/R1, wishlist/R2' -> ['wishlist/R1', 'wishlist/R2'] (deduplicated,
    in order). Raises GateError naming any entry that is not `<slug>/R<n>`."""
    names = list(dict.fromkeys(n.strip() for n in (text or "").split(",") if n.strip()))
    bad = [n for n in names if not REQUIREMENT_RE.match(n)]
    if bad:
        raise GateError("requirements must be `<feature-slug>/R<n>` ids of a feature "
                        "PRD's requirements; got: %s" % ", ".join(bad))
    return names


def prd_path(root, settings=None):
    """The repo's PRD hub (absolute) when one exists, else None."""
    if not root:
        return None
    path = os.path.join(root, *doc_layout.prd_dir(root, settings).split("/"), "prd.md")
    return path if os.path.isfile(path) else None


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def feature_requirements(text):
    """The `R<n>` ids a feature PRD's `## Requirements` section declares."""
    found, inside = [], False
    for line in text.splitlines():
        head = _H2.match(line)
        if head:
            inside = head.group(1).strip().lower() == "requirements"
            continue
        match = inside and _REQUIREMENT_LINE.match(line)
        if match:
            found.append(match.group(1))
    return found


def _status(text):
    try:
        front, _body = yamlsubset.split_front_matter(text)
    except Exception:  # noqa: BLE001 -- an unparsable block is checked elsewhere
        return None
    return (front or {}).get("status") if isinstance(front, dict) else None


def check_link(root, ttype, features, requirements=(), settings=None):
    """The problems with linking a `ttype` ticket to `features` and
    `requirements` ([] when the link is sound)."""
    features, requirements = list(features or []), list(requirements or [])
    if ttype not in LINKED_TYPES and not (features or requirements):
        return []  # a technical task: nothing to link, nothing to check
    if not prd_path(root, settings):
        return [NO_PRD]
    problems = []
    if not features and ttype in LINKED_TYPES:
        problems.append("a %s links at least one PRD feature (`features`); work the PRD "
                        "does not describe is added to it first with /acs:create-prd" % ttype)
    if ttype == "story" and not requirements:
        problems.append("a story names at least one requirement it delivers "
                        "(`requirements`, e.g. `%s/R1`)" % (features[0] if features else "<slug>"))
    declared = {}
    for slug in features:
        path = doc_layout.feature_prd_path(root, slug, settings)
        text = _read(path) if path else None
        if text is None:
            problems.append("feature %r has no PRD of its own (%s); add the feature to the "
                            "PRD with /acs:create-prd" % (slug, os.path.relpath(path, root)
                                                          if path else slug))
            continue
        if _status(text) == "deprecated":
            problems.append("feature %r is deprecated; a new ticket cannot link it" % slug)
        declared[slug] = feature_requirements(text)
    for rid in requirements:
        match = REQUIREMENT_RE.match(rid)
        if not match:
            problems.append("requirement %r is not `<feature-slug>/R<n>`" % rid)
            continue
        slug, req = match.groups()
        if slug not in features:
            problems.append("requirement %s names feature %r, which the ticket does not "
                            "link" % (rid, slug))
        elif slug in declared and req not in declared[slug]:
            problems.append("requirement %s is not in %s's PRD (it declares: %s)"
                            % (rid, slug, ", ".join(declared[slug]) or "none"))
    return problems


def ensure_link(root, ttype, features, requirements=(), settings=None):
    """Raise GateError listing every problem `check_link` finds."""
    problems = check_link(root, ttype, features, requirements, settings)
    if problems:
        raise GateError("the ticket's PRD link is not sound: " + "; ".join(problems))
