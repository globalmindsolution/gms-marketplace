"""acs_lib.run_docs — a RUN's documents in the repo: where each one is read from
and where a new one is written (ADR-0128, `acs_lib.doc_layout` for the folders).

Resolved by run, not by ticket: the run's feature (refined, else its ticket's
first), its phase (Discovery or Development, `requirements.run_phase`) and its
key (the ticket id, else the run id) place every document:

  analysis.md                Discovery: <prd_dir>/features/<f>/analysis.md
                             Development: <development_dir>/<f>/<key>/analysis.md
  plan.md, test-cases.md     <development_dir>/<f>/<key>/
  design.md, api-contract.md <architecture_dir>/lld/<f>/<key>/

A reader that finds nothing there falls back to the legacy
`docs/tickets/<ID>/<name>`, then the ticket's workspace partition. A run with
no feature yet has no write target (`paths[name]` is None) until one is named
(`acs.py requirements refine`, analyze-requirements' grouped ask).
"""

import os

from ._common import GateError, read_json
from . import doc_layout
from .repo import find_ticket_partition
from .run import load_run

#: Partition-relative places a document lived before the docs tree existed.
_PARTITION_LEGACY = {"plan.md": (os.path.join("phases", "code", "plan.md"),)}


def _ticket_features(ctx, ticket_id):
    from .tickets import load_ticket
    tdir, _archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    ticket = load_ticket(tdir) if os.path.isdir(tdir) else None
    return tdir, ticket if isinstance(ticket, dict) else None


def run_layout(ctx, rdir=None, doc=None, ticket_id=None):
    """Everything `acs.py artifacts show` reports about one run (or, with no
    run, one ticket): its feature, phase, key, the three roots, the per-run
    folders, and per document the existing file and the write target."""
    from . import requirements
    root = ctx.get("checkout_root")
    settings = ctx.get("settings")
    if doc is None and rdir:
        doc = load_run(rdir)
    doc = doc or {}
    subject = doc.get("subject") or {}
    ticket_id = ticket_id or subject.get("ticket_id")
    has_run = bool(rdir and doc.get("run_id"))
    refined = requirements.load_refined(rdir) if has_run else {}
    tdir, ticket = _ticket_features(ctx, ticket_id) if ticket_id else (None, None)
    if has_run:
        feature = requirements.run_feature(ctx, rdir, doc, refined)
        phase = requirements.run_phase(doc, refined)
    else:
        feature = ((ticket or {}).get("features") or [None])[0]
        phase = "development"
    key = ticket_id or doc.get("run_id")
    paths, found = {}, {}
    for name in doc_layout.DOCUMENT_NAMES:
        target = doc_layout.document_target(root, name, feature, key, phase, settings)
        paths[name] = target
        candidates = [target] if target else []
        legacy = doc_layout.legacy_ticket_dir(root, ticket_id)
        if legacy:
            candidates.append(os.path.join(legacy, name))
        if tdir:
            candidates.append(os.path.join(tdir, name))
            candidates += [os.path.join(tdir, rel) for rel in _PARTITION_LEGACY.get(name, ())]
        found[name] = next((c for c in candidates if os.path.isfile(c)), None)
    living = doc_layout.feature_analysis_path(root, feature, settings) if feature else None
    legacy = doc_layout.legacy_ticket_dir(root, ticket_id)
    return {
        "run_id": doc.get("run_id"), "ticket_id": ticket_id, "feature": feature,
        "phase": phase, "key": key,
        "prd_dir": doc_layout.prd_dir(root, settings) if root else None,
        "architecture_dir": doc_layout.architecture_dir(root, settings) if root else None,
        "development_dir": doc_layout.development_dir(root, settings) if root else None,
        "feature_dir": doc_layout.feature_dir(root, feature, settings),
        "feature_analysis": living if living and os.path.isfile(living) else None,
        "docs_dir": doc_layout.development_run_dir(root, feature, key, settings),
        "design_dir": doc_layout.design_run_dir(root, feature, key, settings),
        "legacy_dir": legacy if legacy and os.path.isdir(legacy) else None,
        "paths": paths, "artifacts": found,
        "requirements": (requirements.requirements_path(rdir) if has_run else None),
        "partition": tdir, "ticket": ticket,
    }


def document_path(ctx, name, rdir=None, doc=None, ticket_id=None):
    """(existing, target) for one document of a run: the file a reader opens
    (None when there is none) and where a writer puts a new one (None when the
    run has no feature yet)."""
    layout = run_layout(ctx, rdir, doc, ticket_id)
    return layout["artifacts"].get(name), layout["paths"].get(name)


def describe(ctx, rdir=None, doc=None, ticket_id=None):
    """The `acs.py artifacts show` view of a run (or a ticket with no run)."""
    from . import artifacts
    out = run_layout(ctx, rdir, doc, ticket_id)
    out.update({"source": None, "source_path": None, "status": None})
    if out["ticket_id"]:
        tdir = out["partition"]
        if not (tdir and os.path.isdir(tdir)):
            raise GateError("no partition for ticket %s" % out["ticket_id"])
        kind, path = artifacts.ticket_source(tdir)
        if out["ticket"] is None:
            raise GateError("no readable ticket for %s (looked for ticket.json and "
                            "the legacy ticket.md under %s)" % (out["ticket_id"], tdir))
        out.update({"source": kind, "source_path": path,
                    "status": out["ticket"].get("status")})
    else:
        out.pop("ticket")
        out.pop("partition")
    return out


def latest_run_for_ticket(repo, ticket_id):
    """The newest run whose subject is this ticket, or None."""
    from . import run as run_machine
    rows = run_machine.find_runs_for_subject(repo, "ticket", ticket_id)
    for row in reversed(rows):
        rdir = run_machine.run_dir(repo, row["run_id"])
        if read_json(run_machine.run_path(rdir)) is not None:
            return rdir
    rdir = run_machine.run_dir(repo, ticket_id)
    return rdir if os.path.isfile(run_machine.run_path(rdir)) else None
