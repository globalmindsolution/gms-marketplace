"""acs_lib.run_docs — a RUN's documents in the repo: where each one is read from
and where a new one is written (ADR-0128, `acs_lib.doc_layout` for the folders).

Resolved by run, not by ticket: the run's feature (refined, else its ticket's
first), its phase (Discovery or Development, `requirements.run_phase`) and its
key (the ticket id, else the run id) place every document:

  analysis.md                a FOLDER since ADR-0133 -- README.md plus one file
                             per bounded context; the key names its README.md:
                             Discovery: <prd_dir>/features/<f>/analysis/README.md
                             Development: <development_dir>/<f>/<key>/analysis/README.md
  plan.md, test-cases.md     <development_dir>/<f>/<key>/
  tech-design.md,            <architecture_dir>/lld/<f>/<key>/
  api-contract.md

A reader that finds nothing there falls back to the legacy
`docs/tickets/<ID>/<name>`, then the ticket's workspace partition. The tech
design is also read under the name it had before ADR-0135, `design.md` --
beside each place it is looked for, and in the old local step folder
`steps/create-design/local/` -- so an older run or docs folder still
resolves. A run with no feature yet has no shared write target until one is
named (`acs.py requirements refine`, analyze-requirements' grouped ask).

Whether a run document is written to its phase folder at all is the user's
saved choice (ADR-0132, `acs_lib.doc_share`): `paths[name]` is the phase-folder
target when documents are SHARED, the run's own `steps/<skill>/local/<name>`
when they are kept LOCAL, and None -- with `needs[name]` naming the open
question -- while the share choice or a not-yet-existing folder is undecided.
`artifacts[name]` reads the existing file wherever it is.

For the analysis, `artifacts["analysis.md"]` is the folder's README.md (a
legacy single `analysis.md` -- beside the folder, in docs/tickets/<ID>/ or the
partition -- when no folder has one), `analysis_files` every file of it,
README first, `analysis_dir` the folder it is (None for a legacy single file),
and `analysis_target_dir` the folder a new analysis is published to.
"""

import os

from ._common import GateError, read_json
from . import analysis_folder, doc_layout, doc_share
from .repo import find_ticket_partition
from .run import load_run

#: Partition-relative places a document lived before the docs tree existed.
_PARTITION_LEGACY = {"plan.md": (os.path.join("phases", "code", "plan.md"),)}


def _ticket_features(ctx, ticket_id):
    from .tickets import load_ticket
    tdir, _archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    ticket = load_ticket(tdir) if os.path.isdir(tdir) else None
    return tdir, ticket if isinstance(ticket, dict) else None


def _with_legacy_names(candidates, name, local, rdir):
    """`candidates` with, after each, where the document was kept under its
    name before a rename (ADR-0135): the old local step folder after the
    local path, the old file name beside any other."""
    out = []
    for path in candidates:
        out.append(path)
        if path == local:
            out += doc_share.legacy_local_paths(rdir, name)
        else:
            out += [os.path.join(os.path.dirname(path), old)
                    for old in doc_layout.legacy_names(name)]
    return out


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
    shared, local = {}, {}
    for name in doc_layout.DOCUMENT_NAMES:
        shared[name] = doc_layout.document_target(root, name, feature, key, phase, settings)
        local[name] = doc_share.local_path(rdir if has_run else None, name)
    base = {"run_id": doc.get("run_id") if has_run else None, "phase": phase,
            "feature": feature, "key": key, "shared_paths": shared}
    paths, found, needs, share = {}, {}, {}, None
    for name in doc_layout.DOCUMENT_NAMES:
        info = doc_share.where(ctx, name, rdir if has_run else None, layout=base)
        needs[name] = info["needs"]
        if info["kind"] == "run":
            share = info["share"]
        if info["needs"]:
            paths[name] = None
        elif info["share"]:
            paths[name] = shared[name]
        else:
            paths[name] = local[name]
        # A reader finds the document wherever it is: where the decision files
        # it first, then the other side, then the legacy folders.
        order = [local[name], shared[name]] if info["share"] is False \
            else [shared[name], local[name]]
        candidates = [c for c in order if c]
        if name == "analysis.md":
            # A folder's README.md first, then the single file it replaced.
            candidates = [p for c in candidates
                          for p in (c, analysis_folder.legacy_sibling(c)) if p]
        candidates = _with_legacy_names(candidates, name, local[name],
                                        rdir if has_run else None)
        names = (name,) + doc_layout.legacy_names(name)
        legacy = doc_layout.legacy_ticket_dir(root, ticket_id)
        if legacy:
            candidates += [os.path.join(legacy, n) for n in names]
        if tdir:
            candidates += [os.path.join(tdir, n) for n in names]
            candidates += [os.path.join(tdir, rel) for rel in _PARTITION_LEGACY.get(name, ())]
        found[name] = next((c for c in candidates if os.path.isfile(c)), None)
    living = doc_layout.existing_feature_analysis(root, feature, settings) if feature else None
    legacy = doc_layout.legacy_ticket_dir(root, ticket_id)
    analysis = found.get("analysis.md")
    target = paths.get("analysis.md")
    return {
        "run_id": doc.get("run_id"), "ticket_id": ticket_id, "feature": feature,
        "phase": phase, "key": key,
        "prd_dir": doc_layout.prd_dir(root, settings) if root else None,
        "architecture_dir": doc_layout.architecture_dir(root, settings) if root else None,
        "development_dir": doc_layout.development_dir(root, settings) if root else None,
        "feature_dir": doc_layout.feature_dir(root, feature, settings),
        "feature_analysis": living,
        "feature_analysis_files": analysis_folder.file_list(living),
        "analysis_files": analysis_folder.file_list(analysis),
        "analysis_dir": analysis_folder.entry_folder(analysis),
        "analysis_target_dir": os.path.dirname(target) if target else None,
        "docs_dir": doc_layout.development_run_dir(root, feature, key, settings),
        "design_dir": doc_layout.design_run_dir(root, feature, key, settings),
        "legacy_dir": legacy if legacy and os.path.isdir(legacy) else None,
        "paths": paths, "artifacts": found,
        "shared_paths": shared, "local_paths": local, "needs": needs, "share": share,
        "locations": doc_layout.resolve_dirs(root, settings) if root else None,
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
