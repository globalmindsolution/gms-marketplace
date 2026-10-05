"""acs_lib.analysis_publish — publication of the reviewed analysis (ADR-0114 §5,
ADR-0127, ADR-0133).

Publishing used to be a prose `cp` and `git add`: nothing checked that the
published bytes were the reviewed bytes. This is that step as code:

  1. refuse unless the loop's last review passed, and the draft FOLDER is
     still the exact files that review judged (its digest -- every file's
     sha256 -- was recorded at review time). The deterministic checks
     (`acs_lib.analysis_folder.check_folder`) ran on those files when the
     draft was recorded, and a finding failed that iteration's review
     (ADR-0125), so a passed review is a clean check;
  2. copy every file of the draft folder byte-for-byte into the resolved
     analysis folder, read each back to prove the copy, and remove the
     context files the new analysis no longer has -- ONLY `.md` files directly
     inside that `analysis/` folder, never anything outside it;
  3. record each file's sha256 and the run's docs folder's files as the paths
     this step wrote. It NEVER stages or commits (ADR-0127): only
     /acs:create-pr commits, and it reads these paths to group the documents
     into their own commit.

The target is resolved by RUN (ADR-0128, `acs_lib.run_docs`), with or without
a ticket: a Development run's analysis goes to
`<development_dir>/<feature>/<ticket-id or run-id>/analysis/`, a Discovery
run's to the feature's living `<prd_dir>/features/<feature>/analysis/`. A run
with no feature yet is refused, naming how to record one. A single
`analysis.md` of before ADR-0133 beside the folder is left where it is (the
folder's README wins for every reader) and named in the publication as
`superseded`.

Whether it goes to the repo at all is the user's saved choice (ADR-0132,
`acs_lib.doc_share`): kept LOCAL, the reviewed files are published to the
run's `steps/analyze-requirements/local/analysis/` and the publication is
recorded `local: true` with no files; undecided, publish is refused naming
`acs.py docs decide`.

`record_publication` then re-derives it from the working tree -- every file
still the reviewed bytes, no file the review never judged -- before the loop
is `completed`.
"""

import os

from ._common import GateError, now_iso
from . import analysis_folder, doc_share, run_docs
from .analysis_loop import _advance, _block, _expect, draft_dir, reviewed_iteration


def _inside(path, folder):
    if not folder:
        return False
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return path == folder or path.startswith(folder + os.sep)


def _repo_rel(root, path):
    return os.path.relpath(os.path.realpath(path), os.path.realpath(root)).replace(os.sep, "/")


def resolve_target(ctx, rdir):
    """(entry README.md path, docs_dir, where) for the run's analysis; the
    analysis folder is the entry's folder. `docs_dir` is the run's own
    Development folder, whose files the step records; a Discovery analysis is
    the feature's living folder and records only its own files; a LOCAL
    analysis (ADR-0132) is kept in the run's state folder and records nothing
    for /acs:create-pr. Refused (GateError) while the share choice or a
    not-yet-existing folder is undecided, naming `acs.py docs decide`, and --
    shared -- when the run has no feature to file it under."""
    layout = run_docs.run_layout(ctx, rdir)
    info = doc_share.require_decided(
        doc_share.where(ctx, "analysis.md", rdir, layout=layout), verb="publish")
    if info["share"] is False:
        return info["abs_entry_path"], None, info
    target = layout["paths"].get("analysis.md")
    if not target:
        raise GateError(
            "refusing to publish: run %s has no PRD feature to file its analysis under. "
            "Ask the user which feature it belongs to (propose PRD feature slugs with "
            "`acs.py slug`, or a new slug when none fits) and record it with `acs.py "
            "requirements refine` ({\"feature\": \"<slug>\"}), then publish again."
            % (layout.get("run_id") or os.path.basename(rdir)))
    docs_dir = layout["docs_dir"] if layout["phase"] == "development" else None
    return target, docs_dir, info


def _reviewed(loop):
    """(iteration, digest) of the draft the last (passed) review judged."""
    history = loop.get("history") or []
    if not history or not history[-1].get("passed"):
        raise GateError("refusing to publish: the last review did not pass")
    return reviewed_iteration(loop), history[-1].get("draft_sha256")


def publish(rdir, loop, ctx, tdir, ticket, summary=None):
    """Publish the reviewed draft folder. Returns (loop, report)."""
    _expect(loop, "publish")
    iteration, reviewed = _reviewed(loop)
    draft = draft_dir(rdir, iteration)
    if not os.path.isfile(os.path.join(draft, analysis_folder.README)):
        raise GateError("refusing to publish: no draft folder with a README.md at %s" % draft)
    combined, shas, total = analysis_folder.digest(draft)
    if combined != reviewed:
        raise GateError("refusing to publish: the draft folder is not the files the review "
                        "passed (reviewed %s, now %s)" % ((reviewed or "-")[:12], combined[:12]))
    entry, docs_dir, info = resolve_target(ctx, rdir)
    folder = os.path.dirname(entry)
    root = ctx.get("checkout_root")
    local = info["share"] is False
    try:
        written, removed = analysis_folder.copy_folder(draft, folder)
    except ValueError as exc:
        raise GateError("refusing to publish: %s" % exc)
    inside_repo = bool(root) and _inside(folder, root)
    if local:
        files = []  # kept in the run's state folder: nothing for create-pr to commit
    elif inside_repo and docs_dir and _inside(folder, docs_dir):
        files = _docs_files(root, docs_dir)
    elif inside_repo:
        files = sorted(_repo_rel(root, os.path.join(folder, name)) for name in written)
    else:
        files = []
    removed_paths = [_repo_rel(root, os.path.join(folder, name)) if inside_repo and not local
                     else os.path.join(folder, name) for name in removed]
    legacy = analysis_folder.legacy_sibling(entry)
    loop["publication"] = {"path": entry, "dir": folder, "sha256": combined, "bytes": total,
                           "iteration": iteration, "file_shas": written,
                           "removed": removed_paths,
                           "superseded": legacy if legacy and os.path.isfile(legacy) else None,
                           "docs_dir": docs_dir, "files": files,
                           "local": local, "share_scope": info.get("share_scope"),
                           "destination": doc_share.describe_choice(info),
                           "verified": False, "at": now_iso()}
    loop["events"].append({"at": now_iso(), "event": "publish",
                           "detail": "%s (%d file(s), %d removed)"
                                     % (folder, len(written), len(removed))})
    return loop, {"published": True, "publication": loop["publication"]}


def _docs_files(root, docs_dir):
    """Every file in the run's docs folder, repo-relative and sorted: the
    paths this step leaves uncommitted for /acs:create-pr (ADR-0127)."""
    out = []
    for base, dirs, names in os.walk(docs_dir):
        dirs.sort()
        for name in sorted(names):
            if name.endswith(".acs-tmp"):
                continue
            out.append(_repo_rel(root, os.path.join(base, name)))
    return sorted(out)


def record_publication(rdir, loop, ctx):
    """Re-derive the publication from the working tree: every published file
    is still the reviewed bytes, and the folder holds no `.md` file the review
    never judged. Nothing is committed, so HEAD is not asked (ADR-0127): the
    working tree is what /acs:create-pr will commit."""
    _expect(loop, "publish")
    pub = loop.get("publication")
    if not pub:
        _block(loop, "machinery", "nothing published yet: run `acs.py analysis publish`")
        return loop
    _iteration, reviewed = _reviewed(loop)
    folder = pub.get("dir") or os.path.dirname(pub["path"])
    shas = pub.get("file_shas")
    if not isinstance(shas, dict) or pub.get("sha256") != reviewed:
        _block(loop, "machinery", "the publication record is not the reviewed analysis: "
               "run `acs.py analysis publish` again")
        return loop
    if not os.path.isfile(pub["path"]):
        _block(loop, "machinery", "the published analysis %s is missing" % pub["path"])
        return loop
    problems = analysis_folder.verify(folder, shas)
    if problems:
        _block(loop, "machinery", "the published analysis is not the reviewed files: %s"
               % "; ".join(problems))
        return loop
    pub["verified"] = True
    _advance(loop, "completed", "record-publication", folder)
    return loop
