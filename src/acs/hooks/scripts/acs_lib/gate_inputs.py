"""acs_lib.gate_inputs — the artifact input checks the Build/Test gates share.

A gate's INPUT is a document a producer skill wrote: plan.md (create-impl-plan),
analysis.md (analyze-ticket), test-cases.md (create-test-docs). This module
resolves where such a document lives -- the docs-tree ticket folder first
(<checkout_root>/<settings.artifacts.tickets_path>/<ID>/, skipped when
tickets_path is null), then the workspace partition, then the legacy location
/acs:code's old plan phase wrote -- and renders the refusal that points at the
producer. Private to the gates: acs_lib.artifacts owns the public resolver.
"""

import os
import re

from ._common import GateError
from . import workflow, yamlsubset
from .yamlsubset import YamlSubsetError


def _ticket_wctx(ctx, ticket_id, tdir, ticket):
    """The ticket-context dict the workflow predicates and artifact resolver
    take (acs_lib.workflow.ticket_context's shape), built from what
    _resolve_ticket_for_gate already loaded rather than re-reading it."""
    wctx = dict(ctx)
    wctx.update({"ticket_id": ticket_id, "tdir": tdir, "ticket": ticket})
    return wctx


#: Where an artifact lived before the docs tree existed, relative to the
#: workspace partition -- read last, so a ticket planned by /acs:code's old
#: plan phase still passes the plan input check.
LEGACY_ARTIFACT_PATHS = {"plan.md": (os.path.join("phases", "code", "plan.md"),)}


def _ticket_artifact(ctx, ticket_id, tdir, ticket, name):
    """The first existing copy of a ticket artifact: the docs-tree folder
    (<checkout_root>/<settings.artifacts.tickets_path>/<ID>/<name>, skipped
    when tickets_path is null), then the partition (<tdir>/<name>), then the
    legacy partition location. None when nowhere. Private to the gates:
    acs_lib.artifacts owns the public resolver."""
    found = workflow.ticket_artifact_path(_ticket_wctx(ctx, ticket_id, tdir, ticket), name)
    if found:
        return found
    for rel in LEGACY_ARTIFACT_PATHS.get(name, ()):
        candidate = os.path.join(tdir, rel)
        if os.path.isfile(candidate):
            return candidate
    return None


def _require_artifact(ctx, ticket_id, tdir, ticket, name, producer):
    """Input check: the artifact `producer` writes must exist; the refusal
    points at the skill that produces it, never at a run ledger."""
    path = _ticket_artifact(ctx, ticket_id, tdir, ticket, name)
    if path is None:
        raise GateError(
            "no %s found for %s (looked in the ticket's docs folder and in %s) — "
            "run /acs:%s %s first." % (name, ticket_id, tdir, producer, ticket_id))
    return path


def _refuse_epic(ticket_id, skill, verb):
    """Epics are designed and fanned out, never worked as one ticket."""
    raise GateError(
        "ticket %s is an epic — epics are never %s directly; run "
        "/acs:create-design %s first if the epic has no design yet, then break it down "
        "into child tickets with /acs:create-ticket %s (epic fan-out), then run /acs:%s "
        "on a child." % (ticket_id, verb, ticket_id, ticket_id, skill))


_TC_ID_RE = re.compile(r"\bTC-\d+\b")
_E2E_TOKEN_RE = re.compile(r"(?<![\w-])e2e(?![\w-])", re.IGNORECASE)


def e2e_case_count(path):
    """How many e2e cases a test-cases.md lists: its front matter's
    `e2e_cases` when that is an integer, else the number of body lines that
    name a `TC-n` id and are typed e2e (a table row with an `e2e` cell, or a
    list item carrying the token). A corrupt front matter is a GateError."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        front, body = yamlsubset.split_front_matter(text)
    except YamlSubsetError as exc:
        raise GateError("%s: front matter: %s" % (path, exc))
    declared = (front or {}).get("e2e_cases")
    if isinstance(declared, int) and not isinstance(declared, bool):
        return declared
    count = 0
    for line in body.splitlines():
        if not _TC_ID_RE.search(line):
            continue
        if line.lstrip().startswith("|"):
            count += any(cell.strip().lower() == "e2e" for cell in line.split("|"))
        else:
            count += bool(_E2E_TOKEN_RE.search(line))
    return count
