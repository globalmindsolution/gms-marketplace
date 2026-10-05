"""acs_lib.doc_share — whether a run's documents are SHARED in the repo or kept
LOCAL, and whether their folder still needs the user's answer (ADR-0132).

Two choices, each asked once and saved, never inferred:

  share    `docs.share_run_documents` (true|false; absent = undecided). It
           covers the per-run documents only -- analysis.md (a Development
           run's), plan.md, test-cases.md, design.md, api-contract.md. SHARED:
           the document is published to its phase folder (ADR-0128). LOCAL: it
           stays in the run's state folder, `<run>/steps/<skill>/local/<name>`
           (gitignored with the rest of the workspace), later steps still read
           it, and /acs:create-pr never commits it. Saved for this machine in
           `.acs/settings.local.json` (scope `user`) or for the team in
           `.acs/settings.json` (scope `team`); the settings cascade gives the
           machine's answer precedence.
  location a phase folder that resolves only to acs's built-in default (no
           `docs.<kind>_dir` and nothing discovered, `doc_layout.resolve_dir`)
           does not exist yet; acs never creates it without the user's answer,
           saved as `docs.<kind>_dir` in `.acs/settings.json`.

The LIVING documents -- the PRD and roadmap, the HLD and LLD, a feature's
living (Discovery) analysis -- are always shared; only their folder can need
an answer. `where` is the one question every writer asks before its first
write; `require_decided` is what a publisher calls so an undecided write is
refused, never guessed.
"""

import os

from ._common import GateError, read_json
from . import doc_layout
from .repo import checkout_root, main_repo_root
from .run import step_dir
from .settings import load_settings, settings_files, share_run_documents

#: The per-run document -> the step whose state folder keeps it when LOCAL.
LOCAL_STEPS = {
    "analysis.md": "analyze-requirements",
    "plan.md": "create-impl-plan",
    "test-cases.md": "create-test-docs",
    "design.md": "create-design",
    "api-contract.md": "create-api-contract",
}
#: The subfolder of that step folder a local document is kept in -- apart from
#: the step's working draft (`steps/<skill>/<name>`), which is revised in place.
LOCAL_DIRNAME = "local"
#: The living documents `where` answers for: always shared, by folder kind.
LIVING_DOCS = {"living:prd": "prd", "living:architecture": "architecture"}
DOC_CHOICES = tuple(LOCAL_STEPS) + tuple(LIVING_DOCS)
#: The two scopes a share choice is saved in, and the file each writes.
SCOPES = ("user", "team")
LOCAL_SETTINGS = os.path.join(".acs", "settings.local.json")
TEAM_SETTINGS = os.path.join(".acs", "settings.json")
DECIDE_HINT = "acs.py docs decide"


def local_path(rdir, name):
    """`<run>/steps/<skill>/local/<name>` (absolute), or None without a run or
    for a document that is never kept local."""
    if not rdir or name not in LOCAL_STEPS:
        return None
    return os.path.join(step_dir(rdir, LOCAL_STEPS[name]), LOCAL_DIRNAME, name)


def scope_files(cwd):
    """{scope: absolute settings file} -- `user` is this machine's
    `.acs/settings.local.json` (in the main checkout, which every linked
    worktree also reads), `team` the checkout's `.acs/settings.json` (so the
    answer lands on the branch being worked and is committed with it)."""
    top = checkout_root(cwd)
    if not top:
        raise GateError("not inside a git checkout: there is no .acs/ to save the answer in")
    main = main_repo_root(cwd) or top
    return {"user": os.path.join(main, LOCAL_SETTINGS),
            "team": os.path.join(top, TEAM_SETTINGS)}


def _scope_of(path):
    if path.endswith(LOCAL_SETTINGS):
        return "user"
    if os.path.dirname(os.path.dirname(path)) == os.path.expanduser("~"):
        return "user"
    return "team"


def share_source(cwd):
    """(value, scope, file) of the effective `docs.share_run_documents`: the
    most specific settings file that sets it, as the cascade resolves it.
    (None, None, None) when undecided."""
    value = scope = path = None
    for candidate in settings_files(cwd):
        data = read_json(candidate)
        docs = data.get("docs") if isinstance(data, dict) else None
        if isinstance(docs, dict) and isinstance(docs.get("share_run_documents"), bool):
            value, scope, path = docs["share_run_documents"], _scope_of(candidate), candidate
    return value, scope, path


def _rel(root, path):
    if not (root and path):
        return path
    rel = os.path.relpath(os.path.realpath(path), os.path.realpath(root))
    return rel.replace(os.sep, "/")


def _run_rel(rdir, path):
    if not (rdir and path):
        return None
    return os.path.relpath(path, rdir).replace(os.sep, "/")


def where(ctx, doc, rdir=None, layout=None):
    """Where `doc` goes, and what still needs the user's answer.

    {doc, kind: run|living, path, abs_path, share, share_scope, share_file,
     location_kind, location, location_source, needs, proposed_path,
     shared_path, local_path, feature, run_id}

    `path` is repo-relative when shared and run-relative when local; it is
    None while `needs` is non-empty (or, shared, while the run has no feature
    to file under). `proposed_path` is the folder a location question
    proposes. `layout` is a `run_docs.run_layout` already computed."""
    if doc not in DOC_CHOICES:
        raise GateError("unknown document %r (one of %s)" % (doc, ", ".join(DOC_CHOICES)))
    root = ctx.get("checkout_root")
    settings = ctx.get("settings")
    if settings is None and root:
        settings, _found = load_settings(root)
    if doc in LIVING_DOCS:
        kind_of, living = LIVING_DOCS[doc], True
        feature = run_id = None
        shared_abs = None
    else:
        if layout is None:
            from .run_docs import run_layout
            layout = run_layout(dict(ctx, settings=settings), rdir)
        phase = layout.get("phase") or "development"
        kind_of = doc_layout.document_kind(doc, phase)
        living = kind_of == "prd"
        feature, run_id = layout.get("feature"), layout.get("run_id")
        shared_abs = (layout.get("shared_paths") or {}).get(doc) or \
            doc_layout.document_target(root, doc, feature, layout.get("key"), phase, settings)
    location = doc_layout.resolve_dir(root, kind_of, settings)
    if living:
        share, scope, sfile = True, "living", None
    else:
        share, scope, sfile = share_run_documents(settings), None, None
        if share is not None and root:
            found, found_scope, found_file = share_source(root)
            if found == share:
                scope, sfile = found_scope, found_file
    needs = []
    if share is None:
        needs.append("share")
    if share is not False and location["source"] == "default":
        needs.append("location")
    has_run = bool(rdir and layout and layout.get("run_id"))
    local_abs = None if living or not has_run else local_path(rdir, doc)
    if doc in LIVING_DOCS:
        shared_rel = location["path"]
    else:
        shared_rel = _rel(root, shared_abs) if shared_abs else None
    if needs:
        path = abs_path = None
    elif share:
        path = shared_rel
        abs_path = (os.path.join(root, *shared_rel.split("/")) if root and shared_rel
                    else None)
    else:
        path, abs_path = _run_rel(rdir, local_abs), local_abs
    return {
        "doc": doc, "kind": "living" if living else "run", "run_id": run_id,
        "feature": feature, "path": path, "abs_path": abs_path,
        "share": share, "share_scope": scope, "share_file": sfile,
        "location_kind": kind_of, "location": location["path"],
        "location_source": location["source"], "needs": needs,
        "proposed_path": location["path"], "shared_path": shared_rel,
        "local_path": _run_rel(rdir, local_abs), "decide": DECIDE_HINT,
    }


def describe_choice(info):
    """The phrase a completion report names a document's destination with:
    `kept local (team default)`, `shared to docs/development/...`, ..."""
    if info.get("needs"):
        return "undecided (needs %s)" % " and ".join(info["needs"])
    if info.get("share"):
        return "shared to %s" % (info.get("path") or info.get("location"))
    return "kept local (%s default)" % (info.get("share_scope") or "saved")


def require_decided(info, verb="write"):
    """Refuse (GateError) a write whose destination still needs an answer."""
    needs = info.get("needs") or []
    if not needs:
        return info
    questions = []
    if "share" in needs:
        questions.append("share run documents in the repo or keep them local "
                         "(`--share yes|no --scope user|team`)")
    if "location" in needs:
        questions.append("the %s folder, which does not exist yet (proposed: %s; "
                         "`--location %s=<repo-relative path>`, or keep the documents "
                         "local)" % (info["location_kind"], info["proposed_path"],
                                     info["location_kind"]))
    raise GateError(
        "refusing to %s %s: the user has not decided %s. Ask them, then record the "
        "answer with `%s` and %s again." % (
            verb, info["doc"], "; nor ".join(questions), DECIDE_HINT, verb))
